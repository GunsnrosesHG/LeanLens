# LeanLens PFE — Module d'entraînement (YOLO26 / YOLOv8)

Squelette CV du PFE « Surveillance Intelligente et Analyse de Posture » :
détection `person_phone` / `smartphone` / `person_idle`, objectif **confiance ≥ 84 %**,
intégration avec la plateforme LeanLens (dérivée d'une base de code open source).

## Installation

```bash
cd training
python -m venv venv && source venv/bin/activate   # Windows : venv\Scripts\activate
pip install torch torchvision   # choisir la build CUDA/CPU : pytorch.org
pip install -r requirements.txt
```

## Pipeline en 6 étapes

```
① Annotation  →  ② prepare_data.py  →  ③ train.py  →  ④ val.py  →  ⑤ calibrate_confidence.py  →  ⑥ export_latency.py  →  ⑦ realtime_demo.py
```

### ① Annoter (LabelImg / CVAT / Roboflow)

3 classes, ids **fixes** (à respecter partout) :

| id | classe | description |
|----|--------|-------------|
| 0 | `person_phone` | personne utilisant un smartphone (main + regard écran) |
| 1 | `smartphone` | objet seul, posé ou tenu en main |
| 2 | `person_idle` | personne immobile / tête baissée (frames idle) |

- Exporter en **YOLO** (Roboflow) ou **COCO / CVAT XML** (étape ② convertit).
- Pré-annotation : CVAT *model-assisted labeling* avec COCO `person` + `cell phone`.
- Visez ≥ 1500 instances par classe, plusieurs caméras/angles/éclairages, occlusions
  (téléphone près du visage, posé sur bureau) et **frames négatives** (personne sans téléphone).

### ② Préparer les données

```bash
# Export COCO (dossier avec *_annotations.coco.json + images)
python prepare_data.py --coco /chemin/export/ --split 0.7 0.2 0.1

# Export CVAT XML
python prepare_data.py --cvat /chemin/annotations.xml

# Mappage manuel des catégories COCO si l'auto-détection ne suffit pas
python prepare_data.py --coco export.json --coco-map "cell phone=1" "person=0"
```

Crée `data/images|labels/{train,val,test}/` + split **stratifié** par classe dominante.
Le comptage par classe/split est affiché : surveillez le déséquilibre.

### ③ Entraîner (fine-tuning)

```bash
python train.py --weights yolo26n.pt --epochs 150 --batch 16 --device 0 --name exp1
python train.py --weights yolo26s.pt --epochs 200 --imgsz 960 --name exp2   # petits objets
python train.py --weights yolov8n.pt --name baseline_v8                      # baseline comparative
```

Sorties : `runs/train/<name>/weights/best.pt` + `leanlens_train_metrics.json`.

### ④ Évaluer

```bash
python val.py --weights runs/train/exp1/weights/best.pt --split test
```

Précision / rappel / F1 / mAP50 / mAP50-95 **par classe** + matrice de confusion
(`runs/val_test_metrics.json` + plots Ultralytics).

### ⑤ Calibrer le seuil (objectif 84 %)

```bash
python calibrate_confidence.py --weights runs/train/exp1/weights/best.pt --split test
```

Balaye les seuils 0.30→0.95 : choisit le **F1 optimal** et vérifie la **confiance
moyenne ≥ 0.84** des détections retenues → `runs/calibration_report.json`.

### ⑥ Exporter + mesurer la latence

```bash
python export_latency.py --weights best.pt --formats onnx openvino --benchmark
```

YOLO26 : export **NMS-free** par défaut (`--with-nms` pour l'ancien chemin).
Rapport p50/p95/FPS → `runs/export_report.json`.

### ⑦ Temps réel

```bash
python realtime_demo.py --weights best.pt --source 0                       # webcam
python realtime_demo.py --weights best.pt --source rtsp://user:pass@ip/stream --save out.mp4
python realtime_demo.py --weights best.pt --conf 0.84 --idle-seconds 30
```

ByteTrack + lissage des confiances (5 frames) + idle 30 s (immobilité du centre
de boîte) + superposition boîtes/labels/FPS.

## Intégration LeanLens (prochaine étape)

La plateforme lance un conteneur par (caméra, algorithme) via `algorithms-controller`
(`/run` Fastify :3333 → Docker), avec env vars : `camera_url` (snapshot ONVIF),
`camera_stream_url` (RTSP), `server_url` (serveur d'inférence), `link_reports`,
`areas`/`extra` (zones). Le rapport est POSTé au backend Django :

```
POST {link_reports}   (api/reports/report-with-photos/)
{ "algorithm": "<nom>", "camera": "<ip>", "start_tracking": "...", "stop_tracking": "...",
  "violation_found": true, "extra": {...}, "photos": [{"image": <jpeg>, "date": "..."}] }
```

→ Le conteneur `leanlens_smartphone_control` (calqué sur `idle-control`) : snapshots
ONVIF ou RTSP → inférence YOLO26 → logique idle/tracking → POST rapport. Le modèle
sera servi par un conteneur « model server » (comme `idle_python_server` :5001).

## Éthique & RGPD

- Traitement **on-premise**, aucune image vers le cloud.
- **Anonymisation des visages** (floutage) avant tout stockage/POST des photos.
- Durée de conservation limitée des images de rapports ; finalité documentée
  (productivité/sécurité), information des employés (affichage + registre).

## Datasets publics (sans annoter à la main)

```bash
# 1. COCO 2017 val — extrait les images avec un téléphone (person/cell phone),
#    option --pair-person-phone : personne chevauchant un téléphone -> person_phone (annotation faible)
python download_dataset.py --source coco --max-images 400

# 2. N'importe quel projet Roboflow (ex. "Idle/Using_Phone" 8.9k images) :
#    exporter en YOLOv8 ou passer workspace/project/version + ROBOFLOW_API_KEY
python download_dataset.py --source roboflow --workspace <ws> --project <proj> --version 3

# 3. FPI-Det (22.9k images, MIT, surveillance, occlusions) — téléchargement manuel
#    https://github.com/KvCgRv/FPI-Det (Google Drive connecté ou Baidu, code: Mofo)
python download_dataset.py --source fpidet --local /chemin/extrait/
```

Les trois convertissent vers `training/data/` (YOLO, classes 0/1/2, préfixes anti-collision
`coco_` / `rf_<projet>_` / `fpidet_`). Recommandé : COCO (bootstrap) + FPI-Det (occlusions)
+ Roboflow idle (classe 2) + quelques centaines d'images locales de vos caméras.

## Structure

```
training/
├── configs/leanlens.yaml        # config dataset (3 classes + augmentations)
├── data/                        # images/ + labels/ (train/val/test) — généré
├── leanlens_common.py           # utils partagés
├── download_dataset.py          # COCO / Roboflow / FPI-Det -> data/ (YOLO)
├── prepare_data.py              # COCO/CVAT → YOLO + split stratifié
├── train.py                     # fine-tuning
├── val.py                       # évaluation par classe
├── calibrate_confidence.py      # seuil optimal + confiance moyenne ≥ 84 %
├── export_latency.py            # ONNX/OpenVINO/TensorRT + latence
├── realtime_demo.py             # démo caméra (tracking + idle + overlay)
└── runs/                        # sorties (gitignorées)
```
