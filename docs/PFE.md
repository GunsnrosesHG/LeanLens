# LeanLens PFE — Surveillance Intelligente et Analyse de Posture

> **Sujet** : Détection de l'usage de smartphone et de l'inactivité (« idle ») des employés
> par vision par ordinateur, intégrée à la plateforme LeanLens.
> **Objectif de confiance** : ≥ 84 % par classe | **Modèle** : YOLO26 (baseline YOLOv8)

## 1. Architecture livrée

```
┌────────────────────────── Plateforme LeanLens ──────────────────────────┐
│  nginx :80 → frontend React :3000        Django :8000 (API, rapports)               │
│  algorithms-controller :3333 (lance 1 conteneur / caméra / algorithme)               │
│  onvif :3456 (snapshots)                 PostgreSQL + Redis                          │
└──────────────────────────────────────────────────────────────────────────────────────┘
                    │ POST /run (env vars: camera_url, server_url, link_reports…)
                    ▼
┌────────────── Ajouts PFE ────────────────────────────────────────────────────────────┐
│ leanlens-algo (algorithm/)         leanlens-model :5000 (algorithm/model_server/)    │
│  snapshot/RTSP → pre/post filtre    Flask + YOLO26 → POST /predict (JPEG→detections) │
│  tracking + machines à états                                                         │
│  preuves JPEG floutées RGPD ──────────────────────────────────────── volume partagé  │
│  POST /api/reports/report-with-photos/ ──► Django → Report + Image → UI (photos)     │
└──────────────────────────────────────────────────────────────────────────────────────┘
                    ▲
┌────────────── training/ (YOLO) ──────────────────────────────────────────────────────┐
│ download_dataset.py (COCO/Roboflow/FPI-Det) → data/ YOLO 3 classes                   │
│ train.py → val.py → calibrate_confidence.py (84 %) → export_latency.py               │
│ realtime_demo.py (démo caméra indépendante)                                          │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

## 2. Plan de sprint — 7 jours (réaliste)

Hypothèse : dataset public bootstrapé (COCO + Roboflow), GPU Colab gratuit, caméra de test
ou vidéo de substitution. Tout ce qui est listé **existe déjà dans ce dépôt**.

### Jour 1 — Données
- **Matin** : `python download_dataset.py --source coco --max-images 500` (COCO val2017,
  filtre `cell phone`, option `--pair-person-phone`).
- **Après-midi** : Roboflow → choisir 1–2 datasets (`Idle/Using_Phone` 8.9k, `Student
  Behaviour`), exporter YOLOv8, `--source roboflow`. Vérifier comptages par classe
  affichés par le script. Objectif : ≥ 800 instances `smartphone`, ≥ 400 `person_phone`.
- Livrable : `training/data/` rempli, split 70/20/10 stratifié.

### Jour 2 — Entraînement
- Colab (T4) : `train.py --weights yolo26n.pt --epochs 120 --imgsz 640 --batch 16`.
- Si YOLO26 indisponible dans la version ultralytics installée : `yolov8n.pt` en
  baseline + noter la version exacte (`pip freeze | grep ultralytics`).
- Surveiller : mAP50 > 0.7 dès epoch ~40 avec le bootstrap COCO.
- Livrable : `runs/train/exp1/weights/best.pt` + `leanlens_train_metrics.json`.

### Jour 3 — Évaluation & calibration
- `val.py --split test` → P/R/F1/mAP **par classe** + matrice de confusion.
- `calibrate_confidence.py` → seuil F1-optimal + confiance moyenne ≥ 0.84.
- Si une classe < 84 % : augmentation ciblée (nuit/flou via `configs/leanlens.yaml`),
  ajouter d'images FPI-Det, ou remonter le seuil de la classe (accepté, cf. rapport).
- Livrable : `runs/calibration_report.json`, tableau P/R/F1 par classe (capture plots).

### Jour 4 — Intégration plateforme
- Build des images : `docker build -t leanlens-model algorithm/model_server` et
  `docker build -t leanlens-algo algorithm` (copier `best.pt` dans `./models/`).
- `docker compose -f docker-compose.pfe.yml up -d` → UI :80/:3000.
- Enregistrer l'algorithme (UI *Configuration → Algorithms* ou Django shell, cf.
  `algorithm/README.md`), l'attacher à une caméra → `algorithms-controller` le lance.
- Vérifier : un `Report` + `Image` apparaît en base après un incident simulé
  (montrer un téléphone à la caméra 30 s).
- Livrable : rapport visible dans le dashboard LeanLens avec photo floutée.

### Jour 5 — Temps réel & latence
- `export_latency.py --formats onnx openvino --benchmark` → p50/p95/FPS.
- `realtime_demo.py --weights best.pt --source <webcam ou RTSP> --conf <seuil calibré>`.
- Capturer 2–3 vidéos de démonstration (smartphone + idle 30 s).
- Livrable : `runs/export_report.json` + vidéos démo.

### Jour 6 — RGPD & robustesse
- Vérifier `BLUR_FACES=1` sur les preuves (aucun visage reconnaissable dans `/images`).
- Rédiger la section RGPD (cf. §5) : finalité, base légale, minimisation, durée.
- Tests de résilience : couper la caméra / le model server → le conteneur logge et
  retry (`reconnect_delay_s`), aucun crash.
- Livrable : captures avant/après floutage + note RGPD.

### Jour 7 — Rapport & soutenance
- Remplir les tableaux du rapport avec : métriques par classe, courbe P/R vs seuil,
  matrice de confusion, latences p50/p95, FPS.
- Captures : dashboard LeanLens avec rapport smartphone/idle, photo anonymisée,
  `docker ps` montrant le conteneur algorithme lancé par la plateforme.
- Répéter la démo : caméra → détection → rapport UI en < 2 min.

### Plan B (si GPU/Colab indisponible)
Jour 2–3 remplacés par : fine-tuning **YOLOv8n** (CPU, 30 epochs, imgsz 480) ou
inférence-only avec `yolo26n.pt` COCO + post-filtre géométrique (téléphone dans la
boîte personne) — l'objectif 84 % est alors documenté comme « travail futur ».

## 3. État de l'art — datasets (à citer dans le rapport)

| Dataset | Taille | Annotations | Usage PFE | Licence |
|---|---|---|---|---|
| **FPI-Det** (ICASSP 2026, arXiv 2509.09111) | 22 879 imgs | têtes + téléphones, surveillance, occlusions | dur (occlusion, petits objets) | MIT |
| **Roboflow Idle/Using_Phone** | ~8 900 imgs | comportements (Idle, Using_Phone, Working…) | classes 0 et 2 | variable |
| **COCO 2017** (Lin et al., 2014) | 118k+5k | 80 classes dont `person`, `cell phone` | bootstrap classes 0/1 | CC-BY 4.0 |
| **State Farm Distracted Driver** | ~100k | 10 comportements au volant | transfert comportemental | recherche |
| **Kaggle cell-phone / smartphone sets** | 1k–3k | téléphones seuls | complément classe 1 | variable |

**Verrou scientifique** : l'état « idle » est temporel (absence de mouvement sur une
fenêtre), donc non capturable par un dataset d'images seul. Deux réponses dans la
littérature : (a) classification de frames idle (Roboflow, perdre la notion de durée),
(b) détection objet + logique de tracking temporelle (choisi ici, cf. `logic.py`).

## 4. Métriques & protocole d'évaluation

- **Par classe** : précision, rappel, F1 (à seuil calibré), AP50, AP50-95
  (`val.py` + plots Ultralytics).
- **Objectif ≥ 84 %** : interprété comme (i) confiance moyenne des détections retenues
  ≥ 0.84 **et** (ii) F1 ≥ 0.84 au seuil retenu — mesuré par `calibrate_confidence.py`,
  justifié par la courbe P/R vs seuil.
- **Latence** : p50/p95 + FPS (dummy frames), `export_latency.py --benchmark`,
  formats ONNX/OpenVINO/NMS-free (YOLO26 `nms=False`).
- **Système** : temps de bout en bout incident → rapport UI (cible < 10 s),
  taux de rapports par heure vs incidents réels (faux positifs résiduels).

## 5. Éthique & RGPD (section à reprendre dans le rapport)

1. **Finalité et proportionnalité** : détection de comportements à risque (smartphone
   au poste) et d'inactivité, dans le cadre de la sécurité et de la productivité.
   Pas de reconnaissance faciale, pas d'identification nominative : le rapport lie
   une *track* anonyme à un instantané flouté.
2. **Minimisation** : seules les frames d'incident sont conservées ; visages
   pixellisés à la source (`gdpr.py`, cascade Haar locale, aucun envoi cloud) ;
   résolution JPEG 85 réduite.
3. **Base légale** (à choisir avec l'entreprise) : intérêt légitime + information des
   employés (affichage sur site, consultation CSE le cas échéant). Le consentement
   n'est en général pas la base appropriée en contexte employeur (déséquilibre).
4. **Durée de conservation** : propositions — preuves 30 jours, agrégats statistiques
   12 mois (à paramétrer côté Django/SQL).
5. **Sécurité** : réseau interne uniquement, aucune dépendance cloud à l'exécution
   (Haar cascade embarquée, modèle local), accès API authentifié (JWT existant).
6. **Limites honnêtes** : le floutage Haar peut rater des profils ; documenter un
   taux d'échec et un second passage éventuel (detection YOLO-face) en travail futur.

## 6. Mapping code ↔ livrables

| Livrable demandé | Implémentation |
|---|---|
| Dataset annoté | `training/data/` + scripts d'acquisition (`download_dataset.py`, `prepare_data.py`) |
| Rapport état de l'art | §3 ci-dessus + README `training/` |
| Scripts d'entraînement | `training/train.py` (+ val, calibration, export) |
| Algorithme de détection d'inactivité | `algorithm/src/logic.py` (machines à états, 16 tests) |
| Détection temps réel + overlay | `training/realtime_demo.py` |
| Intégration plateforme | `algorithm/` (conteneur + model server) + `docker-compose.pfe.yml` |
| Anonymisation RGPD | `algorithm/src/gdpr.py` |
| Matrice de confusion / courbes | sorties `val.py` (plots Ultralytics) + `calibration_report.json` |
