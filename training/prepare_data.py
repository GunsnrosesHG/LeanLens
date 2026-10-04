"""Préparation du dataset LeanLens : COCO/CVAT → YOLO + split stratifié.

Entrées acceptées :
- Export **COCO** (un `annotations.json` / `*_annotations.coco.json` + images)
- Export **CVAT** (XML 1.1 for images, `annotations.xml` + images)

Sorties : arborescence YOLO Ultralytics
    training/data/
    ├── images/{train,val,test}/...
    └── labels/{train,val,test}/<même nom>.txt

Classes (mappage automatique si possible, sinon via --coco-map) :
    0 = person_phone, 1 = smartphone, 2 = person_idle

Usage :
    python prepare_data.py --coco /chemin/export/  --split 0.7 0.2 0.1
    python prepare_data.py --cvat  /chemin/annotations.xml
    python prepare_data.py --coco export.json --coco-map person=0 "cell phone=1"
"""

from __future__ import annotations

import argparse
import json
import random
import shutil
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

from leanlens_common import HERE, YOLO_NAMES

IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
LENNLENS_IDS = {name.lower(): i for i, name in enumerate(YOLO_NAMES)}


def ensure_tree() -> dict[str, Path]:
    tree = {
        f"{kind}_{split}": HERE / "data" / kind / split
        for kind in ("images", "labels")
        for split in ("train", "val", "test")
    }
    for d in tree.values():
        d.mkdir(parents=True, exist_ok=True)
        (d / ".gitkeep").touch(exist_ok=True)
    return tree


def parse_coco_map_arg(pairs: list[str] | None) -> dict[str, int]:
    """--coco-map 'person=0' 'cell phone=1' -> {'person': 0, 'cell phone': 1}"""
    out: dict[str, int] = {}
    for pair in pairs or []:
        name, _, idx = pair.partition("=")
        out[name.strip()] = int(idx)
    return out


def auto_map_coco(categories: list[dict]) -> dict[int, int]:
    """Mappe automatiquement les catégories COCO vers les 3 classes LeanLens.

    Heuristiques : 'phone' → smartphone (1), 'person using/talking' → person_phone (0),
    'idle/bored' → person_idle (2). Retourne {cat_id_coco: class_id_yolo}.
    """
    mapping: dict[int, int] = {}
    for cat in categories:
        name = str(cat.get("name", "")).lower()
        cid = int(cat["id"])
        if "phone" in name and any(k in name for k in ("using", "talk", "person", "hold")):
            mapping[cid] = LENNLENS_IDS["person_phone"]
        elif "phone" in name or "smartphone" in name or "mobile" in name:
            mapping[cid] = LENNLENS_IDS["smartphone"]
        elif any(k in name for k in ("idle", "bored", "sleep", "inactive")):
            mapping[cid] = LENNLENS_IDS["person_idle"]
        # 'person' seul : ignoré (pas assez d'info comportementale) sauf si rien d'autre
    return mapping


def coco_to_records(coco_json: Path) -> tuple[list[dict], dict[int, str]]:
    data = json.loads(coco_json.read_text(encoding="utf-8"))
    cats = {int(c["id"]): str(c["name"]) for c in data.get("categories", [])}
    imgs = {int(im["id"]): im for im in data.get("images", [])}
    records: list[dict] = []
    for ann in data.get("annotations", []):
        cat_id = int(ann["category_id"])
        img = imgs[int(ann["image_id"])]
        w, h = float(img["width"]), float(img["height"])
        x, y, bw, bh = [float(v) for v in ann["bbox"]]
        records.append({
            "image": img.get("file_name"),
            "img_w": w, "img_h": h,
            "cat_id": cat_id,
            "bbox_xywh": (x, y, bw, bh),
        })
    return records, cats


def cvat_to_records(xml_path: Path) -> tuple[list[dict], dict[int, str]]:
    """CVAT XML 1.1 for images : <image><box label="..."/></image>."""
    root = ET.parse(xml_path).getroot()
    labels: dict[str, int] = {}
    next_id = 0
    records: list[dict] = []
    for img in root.iter("image"):
        name = img.get("name")
        w, h = float(img.get("width", 0)), float(img.get("height", 0))
        for box in img.iter("box"):
            label = box.get("label", "")
            if label not in labels:
                labels[label] = next_id
                next_id += 1
            xtl, ytl = float(box.get("xtl", 0)), float(box.get("ytl", 0))
            xbr, ybr = float(box.get("xbr", 0)), float(box.get("ybr", 0))
            records.append({
                "image": name,
                "img_w": w, "img_h": h,
                "cat_id": labels[label],
                "bbox_xywh": (xtl, ytl, xbr - xtl, ybr - ytl),
            })
    cats = {v: k for k, v in labels.items()}
    return records, cats


def remap(records: list[dict], coco_map: dict[str, int], cats: dict[int, str]) -> list[dict]:
    """Applique le mappage catégories → classes LeanLens (0/1/2)."""
    if not records:
        return records
    is_coco = isinstance(next(iter(cats)), int)
    out = []
    for r in records:
        if is_coco:
            cat_name = cats.get(r["cat_id"], str(r["cat_id"]))
            if cat_name in coco_map:
                target = coco_map[cat_name]
            else:
                # tente le nom exact LeanLens
                target = LENNLENS_IDS.get(cat_name.lower())
            if target is None:
                continue  # catégorie non mappée : ignorée
        else:
            target = LENNLENS_IDS.get(cats.get(r["cat_id"], "").lower())
            if target is None:
                continue
        out.append({**r, "target": target})
    return out


def group_by_image(records: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for r in records:
        grouped.setdefault(r["image"], []).append(r)
    return grouped


def stratified_split(images: list[str], records: list[dict], ratios: tuple[float, float, float], seed: int):
    """Split par image, stratifié par classe majoritaire de l'image si possible."""
    rng = random.Random(seed)
    by_img = group_by_image(records)
    dominant = {img: Counter(r["target"] for r in rows).most_common(1)[0][0]
                for img, rows in by_img.items()}
    rng.shuffle(images)
    buckets: dict[int, list[str]] = {}
    for img in images:
        buckets.setdefault(dominant.get(img, -1), []).append(img)

    train, val, test = [], [], []
    for _, imgs in sorted(buckets.items()):
        n = len(imgs)
        n_train = round(ratios[0] * n)
        n_val = round(ratios[1] * n)
        train += imgs[:n_train]
        val += imgs[n_train:n_train + n_val]
        test += imgs[n_train + n_val:]
    return train, val, test


def write_split(tree: dict[str, Path], img_rows: list[tuple[str, list[dict]]], split: str,
                src_dir: Path, copy: bool) -> int:
    n = 0
    for img_name, rows in img_rows:
        src = src_dir / img_name
        if not src.exists():
            # fichier relatif type "folder/img.jpg" dans les exports COCO
            src = src_dir / img_name.replace("\\", "/")
        if not src.exists():
            continue
        dst_img = tree[f"images_{split}"] / Path(img_name).name
        if copy:
            shutil.copy2(src, dst_img)
        else:
            shutil.move(str(src), dst_img)

        w, h = rows[0]["img_w"], rows[0]["img_h"]
        lines = []
        for r in rows:
            x, y, bw, bh = r["bbox_xywh"]
            # COCO = coin supérieur gauche ; CVAT = déjà xtl/ytl → normalisation commune
            cx = (x + bw / 2) / w
            cy = (y + bh / 2) / h
            nw, nh = bw / w, bh / h
            cx, cy, nw, nh = (max(0.0, min(1.0, v)) for v in (cx, cy, nw, nh))
            lines.append(f"{r['target']} {cx:.6f} {cy:.6f} {nw:.6f} {nh:.6f}")
        (tree[f"labels_{split}"] / (Path(img_name).stem + ".txt")).write_text(
            "\n".join(lines) + "\n", encoding="utf-8"
        )
        n += 1
    return n


def main() -> None:
    parser = argparse.ArgumentParser(description="Préparation dataset LeanLens (COCO/CVAT → YOLO)")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--coco", type=Path, help="Dossier export COCO ou chemin du JSON d'annotations")
    src.add_argument("--cvat", type=Path, help="Chemin du XML CVAT (annotations.xml)")
    parser.add_argument("--images-dir", type=Path, default=None,
                        help="Dossier des images si différent du dossier COCO")
    parser.add_argument("--coco-map", nargs="*", type=str, default=None,
                        help='Mappage manuel : "cell phone=1" "person=0"')
    parser.add_argument("--split", nargs=3, type=float, default=(0.7, 0.2, 0.1),
                        metavar=("TRAIN", "VAL", "TEST"))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--move", action="store_true",
                        help="Déplacer les images au lieu de les copier")
    args = parser.parse_args()

    assert abs(sum(args.split) - 1.0) < 1e-6, "--split doit sommer à 1.0"

    tree = ensure_tree()

    if args.coco:
        coco_json = args.coco if args.coco.is_file() else None
        if coco_json is None:
            candidates = sorted(args.coco.glob("*annotations*.json"))
            if not candidates:
                raise SystemExit(f"Aucun JSON COCO trouvé dans {args.coco}")
            coco_json = candidates[0]
        src_dir = args.images_dir or args.coco if args.coco.is_dir() else args.coco.parent
        records, cats = coco_to_records(coco_json)
        coco_map = parse_coco_map_arg(args.coco_map) or {}
        auto = auto_map_coco([{"id": k, "name": v} for k, v in cats.items()])
        auto.update({k: v for k, v in coco_map.items()})  # override manuel prioritaire
        # traduction nom→id catégorie pour remap()
        name_to_target = {cats[cid]: t for cid, t in auto.items()}
        remapped = []
        for r in records:
            t = name_to_target.get(cats.get(r["cat_id"], ""))
            if t is not None:
                remapped.append({**r, "target": t})
    else:
        src_dir = args.images_dir or args.cvat.parent
        records, cats = cvat_to_records(args.cvat)
        remapped = remap(records, {}, cats)

    if not remapped:
        raise SystemExit("Aucune annotation mappée vers les classes LeanLens — "
                         "vérifie --coco-map / labels CVAT (person_phone, smartphone, person_idle).")

    grouped = group_by_image(remapped)
    images = sorted(grouped)
    train, val, test = stratified_split(images, remapped, args.split, args.seed)

    counts = Counter()
    for split, names in (("train", train), ("val", val), ("test", test)):
        rows = [(img, grouped[img]) for img in names]
        written = write_split(tree, rows, split, src_dir, copy=not args.move)
        counts[split] += written
        cls_count = Counter(r["target"] for img in names for r in grouped[img])
        print(f"[{split}] {written} images | " +
              ", ".join(f"{YOLO_NAMES[c]}={cls_count.get(c, 0)}" for c in sorted(cls_count)))

    print(f"\nTerminé. splits={dict(counts)} — dataset : {HERE / 'data'}")
    print("Le fichier configs/leanlens.yaml pointe déjà vers ce dossier (résolution auto).")


if __name__ == "__main__":
    main()
