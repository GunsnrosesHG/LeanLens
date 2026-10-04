"""Téléchargement + conversion de datasets publics vers training/data (YOLO LeanLens).

Sources supportées :
  --source coco        COCO 2017 val (auto-download, filtre person / cell phone)
  --source roboflow    N'importe quel projet/version Roboflow (via API key, format YOLO)
  --source fpidet      FPI-Det : instructions de téléchargement manuel + conversion
                       locale (COCO JSON ou XML VOC) une fois les fichiers placés

Mappage vers les classes LeanLens (0=person_phone, 1=smartphone, 2=person_idle) :
  cell phone / smartphone / mobile phone  -> 1
  using_phone / using phone / calling     -> 0
  idle / sleeping / bored                 -> 2
  Heuristique optionnelle --pair-person-phone : une boîte `person` COCO chevauchant
  un `cell phone` devient person_phone (annotation faible, à revoir à la main).

Usage :
  python download_dataset.py --source coco --max-images 400
  python download_dataset.py --source roboflow --workspace mon-ws --project mon-proj --version 3
  python download_dataset.py --source fpidet --local /chemin/fpi-det/
"""

from __future__ import annotations

import argparse
import json
import shutil
import time
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from pathlib import Path

import requests

from leanlens_common import HERE, YOLO_NAMES
from prepare_data import ensure_tree

IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
LENNLENS = {n: i for i, n in enumerate(YOLO_NAMES)}
COCO_BASE = "http://images.cocodataset.org"


def target_for(name: str) -> int | None:
    n = name.lower().strip()
    if "phone" in n and any(k in n for k in ("using", "call", "talk")):
        return LENNLENS["person_phone"]
    if any(k in n for k in ("idle", "sleep", "bored")):
        return LENNLENS["person_idle"]
    if "phone" in n or "mobile" in n:
        return LENNLENS["smartphone"]
    return None


def write_example(tree: dict[str, Path], split: str, stem: str, src_img: Path, boxes: list[tuple[int, float, float, float, float]], img_w: int, img_h: int, prefix: str) -> None:
    """boxes = [(class_id, cx, cy, w, h) normalisés]"""
    dst_img = tree[f"images_{split}"] / f"{prefix}_{stem}{src_img.suffix.lower()}"
    shutil.copy2(src_img, dst_img)
    lines = [f"{c} {x:.6f} {y:.6f} {w:.6f} {h:.6f}" for c, x, y, w, h in boxes]
    (tree[f"labels_{split}"] / f"{prefix}_{stem}.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- COCO

def coco_filter_annotations(ann_json: Path, max_images: int, pair: bool) -> dict[str, list[tuple[int, float, float, float, float, int, int]]]:
    """Retourne {file_name: [(class, cx, cy, w, h, W, H)]} pour les images pertinentes."""
    data = json.loads(ann_json.read_text(encoding="utf-8"))
    cats = {int(c["id"]): c["name"].lower() for c in data["categories"]}
    phone_ids = [cid for cid, n in cats.items() if n in ("cell phone", "mobile phone")]
    person_ids = [cid for cid, n in cats.items() if n == "person"]
    if not phone_ids:
        raise SystemExit(f"Aucune catégorie 'cell phone' dans {ann_json.name}")

    imgs = {int(im["id"]): im for im in data["images"]}
    per_file: dict[str, list] = {}
    for ann in data["annotations"]:
        cid = int(ann["category_id"])
        if cid not in phone_ids and cid not in person_ids:
            continue
        im = imgs[int(ann["image_id"])]
        W, H = int(im["width"]), int(im["height"])
        x, y, w, h = [float(v) for v in ann["bbox"]]
        box = (cx, cy, nw, nh) = ((x + w / 2) / W, (y + h / 2) / H, w / W, h / H)
        per_file.setdefault(im["file_name"], []).append({
            "cat": "person" if cid in person_ids else "phone", "box": box,
        })

    out: dict[str, list] = {}
    phones_first = [f for f, items in per_file.items() if any(i["cat"] == "phone" for i in items)]
    for fname in sorted(phones_first)[:max_images] if max_images else phones_first:
        items = per_file[fname]
        boxes = []
        # dimensions : re-trouvées depuis imgs
        W = H = None
        for iid, im in imgs.items():
            if im["file_name"] == fname:
                W, H = int(im["width"]), int(im["height"])
                break
        phone_boxes = [i["box"] for i in items if i["cat"] == "phone"]
        for i in items:
            if i["cat"] == "phone":
                boxes.append((LENNLENS["smartphone"], *i["box"]))
            elif pair:
                cx, cy, _, _ = i["box"]
                if any(abs(cx - pb[0]) < 0.2 and abs(cy - pb[1]) < 0.25 for pb in phone_boxes):
                    boxes.append((LENNLENS["person_phone"], *i["box"]))
        if W is None:
            continue
        out[fname] = boxes
    return out


def run_coco(args) -> Counter:
    tree = ensure_tree()
    data_dir = HERE / ".datasets" / "coco"
    data_dir.mkdir(parents=True, exist_ok=True)
    ann_zip = data_dir / "annotations_trainval2017.zip"
    if not ann_zip.exists():
        url = f"{COCO_BASE}/annotations/annotations_trainval2017.zip"
        print(f"[coco] téléchargement {url} (~250 Mo)…")
        ann_zip.write_bytes(requests.get(url, timeout=120).content)
    ann_json = data_dir / "annotations" / "instances_val2017.json"
    if not ann_json.exists():
        with zipfile.ZipFile(ann_zip) as z:
            z.extract("annotations/instances_val2017.json", data_dir)

    selected = coco_filter_annotations(ann_json, args.max_images, args.pair_person_phone)
    print(f"[coco] {len(selected)} images contenant un téléphone")
    counts: Counter = Counter()
    img_dir = data_dir / "val2017"
    img_dir.mkdir(exist_ok=True)
    for i, (fname, boxes) in enumerate(sorted(selected.items())):
        dst = img_dir / fname
        if not dst.exists():
            r = requests.get(f"{COCO_BASE}/val2017/{fname}", timeout=60)
            r.raise_for_status()
            dst.write_bytes(r.content)
        stem = Path(fname).stem
        for c, *_ in boxes:
            counts[c] += 1
        split = "train" if (i % 10) < 7 else ("val" if (i % 10) < 9 else "test")
        write_example(tree, split, stem, dst, boxes, 0, 0, prefix="coco")
        if (i + 1) % 50 == 0:
            print(f"[coco] {i + 1}/{len(selected)}")
    print("[coco] terminé.")
    return counts


# ---------------------------------------------------------------------- Roboflow

def run_roboflow(args) -> Counter:
    tree = ensure_tree()
    base = f"https://api.roboflow.com/{args.workspace}/{args.project}/{args.version}/yolov8"
    print(f"[roboflow] requête {base}")
    r = requests.get(base, params={"api_key": args.api_key}, timeout=60)
    r.raise_for_status()
    info = r.json()
    link = (info.get("export") or {}).get("link")
    for _ in range(30):  # génération asynchrone possible
        if link:
            break
        time.sleep(10)
        link = (requests.get(base, params={"api_key": args.api_key}, timeout=60).json()
                .get("export") or {}).get("link")
    if not link:
        raise SystemExit("Export Roboflow indisponible (lien introuvable).")

    zf = HERE / ".datasets" / f"roboflow_{args.project}_v{args.version}.zip"
    zf.parent.mkdir(parents=True, exist_ok=True)
    if not zf.exists():
        print(f"[roboflow] téléchargement zip…")
        zf.write_bytes(requests.get(f"{link}?api_key={args.api_key}", timeout=300).content)

    counts: Counter = Counter()
    extract_dir = zf.with_suffix("")
    if not extract_dir.exists():
        zipfile.ZipFile(zf).extractall(extract_dir)
    names = {}
    data_yaml = extract_dir / "data.yaml"
    if data_yaml.exists():
        import yaml
        names_list = yaml.safe_load(data_yaml.read_text(encoding="utf-8")).get("names", [])
        names = {i: n for i, n in enumerate(names_list)}

    for split, target in (("train", "train"), ("valid", "val"), ("test", "test")):
        img_dir = extract_dir / split
        if not img_dir.exists():
            continue
        n = 0
        for img_path in sorted(img_dir.iterdir()):
            if img_path.suffix.lower() not in IMG_EXTS:
                continue
            lbl = img_path.with_suffix(".txt")
            if not lbl.exists():
                continue
            boxes = []
            for line in lbl.read_text(encoding="utf-8").splitlines():
                p = line.split()
                if len(p) != 5:
                    continue
                cid = int(float(p[0]))
                cname = names.get(cid, str(cid))
                t = target_for(cname)
                if t is not None:
                    boxes.append((t, *(float(v) for v in p[1:])))
            stem = img_path.stem
            for c, *_ in boxes:
                counts[c] += 1
            write_example(tree, target, stem, img_path, boxes, 0, 0, prefix=f"rf_{args.project}"[:24])
            n += 1
        print(f"[roboflow] {split}: {n} images converties")
    return counts


# ----------------------------------------------------------------------- FPI-Det

def run_fpidet(args) -> Counter:
    print(
        "\n[FPI-Det] Téléchargement manuel (MIT license) :\n"
        "  1. https://github.com/KvCgRv/FPI-Det  → Google Drive (connecté) ou Baidu (code: Mofo)\n"
        f"  2. Extraire dans : {args.local}\n"
        "  3. Relancer : python download_dataset.py --source fpidet --local <chemin>\n"
    )
    local = Path(args.local) if args.local else None
    if not local or not local.exists():
        print("[FPI-Det] dossier local absent — instructions affichées, arrêt.")
        return Counter()

    counts: Counter = Counter()
    tree = ensure_tree()
    jsons = list(local.rglob("*.json"))
    xmls = list(local.rglob("*.xml"))
    if jsons:
        # attendu : annotations COCO (faces/heads + phone)
        ann = max(jsons, key=lambda p: p.stat().st_size)
        data = json.loads(ann.read_text(encoding="utf-8"))
        cats = {int(c["id"]): c["name"].lower() for c in data.get("categories", [])}
        imgs = {int(im["id"]): im for im in data.get("images", [])}
        per_img: dict[int, list] = {}
        for a in data.get("annotations", []):
            per_img.setdefault(int(a["image_id"]), []).append(a)
        n = 0
        for iid, anns in per_img.items():
            im = imgs.get(iid)
            if not im:
                continue
            W, H = int(im["width"]), int(im["height"])
            fpath = local / im["file_name"]
            if not fpath.exists():
                continue
            boxes = []
            heads, phones = [], []
            for a in anns:
                cname = cats.get(int(a["category_id"]), "")
                x, y, w, h = [float(v) for v in a["bbox"]]
                box = ((x + w / 2) / W, (y + h / 2) / H, w / W, h / H)
                if "phone" in cname:
                    phones.append(box)
                    boxes.append((LENNLENS["smartphone"], *box))
                elif any(k in cname for k in ("head", "face")):
                    heads.append(box)
            if args.pair_person_phone:
                for hb in heads:
                    if any(abs(hb[0] - pb[0]) < 0.2 and abs(hb[1] - pb[1]) < 0.25 for pb in phones):
                        boxes.append((LENNLENS["person_phone"], *hb))
            if boxes:
                counts.update(b[0] for b in boxes)
                split = "train" if (n % 10) < 8 else ("val" if (n % 10) < 9 else "test")
                write_example(tree, split, f"{iid}", fpath, boxes, W, H, prefix="fpidet")
                n += 1
                if args.max_images and n >= args.max_images:
                    break
        print(f"[FPI-Det] {n} images converties depuis COCO JSON : {ann.name}")
    elif xmls:
        print(f"[FPI-Det] {len(xmls)} XML détectés — conversion VOC :")
        n = 0
        for xml_path in xmls:
            root = ET.parse(xml_path).getroot()
            W = int(float(root.findtext("size/width", "0") or 0))
            H = int(float(root.findtext("size/height", "0") or 0))
            img_path = xml_path.with_suffix(".jpg")
            if not img_path.exists():
                img_path = xml_path.with_suffix(".png")
            if not img_path.exists() or not W or not H:
                continue
            boxes = []
            for obj in root.iter("object"):
                t = target_for(obj.findtext("name", ""))
                if t is None:
                    continue
                bb = obj.find("bndbox")
                x1, y1 = float(bb.findtext("xmin", 0)), float(bb.findtext("ymin", 0))
                x2, y2 = float(bb.findtext("xmax", 0)), float(bb.findtext("ymax", 0))
                boxes.append((t, (x1 + x2) / 2 / W, (y1 + y2) / 2 / H, (x2 - x1) / W, (y2 - y1) / H))
            if boxes:
                counts.update(b[0] for b in boxes)
                split = "train" if (n % 10) < 8 else ("val" if (n % 10) < 9 else "test")
                write_example(tree, split, img_path.stem, img_path, boxes, W, H, prefix="fpidet")
                n += 1
                if args.max_images and n >= args.max_images:
                    break
        print(f"[FPI-Det] {n} images converties depuis XML VOC")
    else:
        print("[FPI-Det] aucun JSON/XML trouvé dans le dossier local.")
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Téléchargement datasets publics LeanLens")
    parser.add_argument("--source", required=True, choices=["coco", "roboflow", "fpidet"])
    parser.add_argument("--max-images", type=int, default=500)
    parser.add_argument("--pair-person-phone", action="store_true",
                        help="Annotation faible : person chevauchant un phone -> person_phone")
    parser.add_argument("--local", type=str, default=None, help="(fpidet) dossier extrait localement")
    parser.add_argument("--workspace", type=str, default=None, help="(roboflow)")
    parser.add_argument("--project", type=str, default=None, help="(roboflow)")
    parser.add_argument("--version", type=int, default=None, help="(roboflow)")
    parser.add_argument("--api-key", type=str, default=None,
                        help="(roboflow) ou env ROBOFLOW_API_KEY")
    args = parser.parse_args()

    if args.source == "roboflow":
        import os
        args.api_key = args.api_key or os.environ.get("ROBOFLOW_API_KEY")
        if not (args.api_key and args.workspace and args.project and args.version):
            raise SystemExit("--workspace/--project/--version/--api-key requis (ou ROBOFLOW_API_KEY)")
        counts = run_roboflow(args)
    elif args.source == "coco":
        counts = run_coco(args)
    else:
        counts = run_fpidet(args)

    total = sum(counts.values())
    print("\n=== Résumé des instances converties ===")
    for cid, name in enumerate(YOLO_NAMES):
        print(f"  {cid} {name:14s}: {counts.get(cid, 0)}")
    print(f"  TOTAL: {total} instances dans training/data/")
    print("NB : relance val/train directement ; les prefixes évitent les collisions de noms.")


if __name__ == "__main__":
    main()
