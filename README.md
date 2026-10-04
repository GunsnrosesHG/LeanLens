# LeanLens — Smart Monitoring (Smartphone + Idle Detection)

> **PFE — Surveillance Intelligente et Analyse de Posture par Vision par Ordinateur**
> YOLO26n detector + temporal state machines, integrated end-to-end into the LeanLens
> video-analytics platform. GDPR-compliant (faces blurred before storage).

![status](https://img.shields.io/badge/status-delivered-brightgreen) ![tests](https://img.shields.io/badge/tests-36%2F36-brightgreen) ![latency](https://img.shields.io/badge/latency-25.9%20ms%20p50%20(36.8%20FPS)-blue) ![confidence](https://img.shields.io/badge/mean_confidence-0.954%20%E2%89%A50.84%20target-success)

---

## What it does

Watches surveillance cameras in real time and raises violation reports when:

| Behavior | How it is detected |
|---|---|
| 📱 **Smartphone usage** | YOLO26n detects `person_phone` + `smartphone`; per-identity state machine (3 hits → start, 5 misses → stop) |
| 🪑 **Prolonged inactivity (idle)** | Temporal logic: tracked person with < 15 px movement for 30 s → alert (per-person cooldown) |

Evidence photos are **face-blurred (GDPR) before storage**, horodatées, and appear
instantly in the LeanLens operator UI.

> **Step-by-step guide for a fresh clone: [docs/RUNNING.md](docs/RUNNING.md)**
> (prerequisites, upstream image pulls, build, bootstrap, verification, dev loops, troubleshooting).

## Quick start (Docker Desktop required)

```bash
# 1. Start the full platform (12 containers: UI, API, DB, model server, demo camera…)
docker compose -f docker-compose.pfe.yml up -d

# 2. Start the algorithm worker (detection + GDPR blur; profile "manual")
docker compose -f docker-compose.pfe.yml up -d leanlens-algo

# Note: the one-shot `leanlens-bootstrap` container seeds/migrates the DB on
# every `up -d` (idempotent) — no manual bootstrap step needed.
# Full guide (fresh clone → running platform): docs/RUNNING.md
```

**Then:**

| URL | What | Credentials |
|---|---|---|
| http://localhost/ | LeanLens operator UI (reports, live view) | `admin` / `LeanLens2026` |

| http://localhost/ | **UI v2** — shadcn-admin rebuild: dashboard KPIs, reports with GDPR-blurred evidence, cameras | `admin` / `LeanLens2026` |

> Rollback to the old CRA UI: set `location /` back to `http://front:3000` in `nginx/default.conf`, then `docker exec leanlens-webserver nginx -s reload`.
| http://localhost:6002 | Demo control panel (scene buttons + report counter) | — |
| http://localhost:8000/admin/ | Django admin | `admin` / `LeanLens2026` |

**Demo scenario** (buttons on :6002, or `bash docs/demo_script.sh`):

1. `phone` scene → within ~10 s the algorithm opens a phone event;
2. switch to `working` → event closes → **violation report with 2 blurred photos in the UI**;
3. `idle` scene → **idle alert at ~32 s** (threshold 30 s);
4. back to `working` → silence (no false positives).

## Measured results (test split, `best.pt`)

| Metric | Value |
|---|---|
| Mean confidence @ deployed threshold 0.84 | **0.954** (target ≥ 0.84 ✓) |
| Precision @ 0.84 | 0.750 |
| Latency (ONNX, 640 px) | p50 **25.9 ms** · p95 35.5 ms · **36.8 FPS** |
| Training | YOLO26n, epoch 38 fitness-best, ~15 min on GTX 1650 |
| Unit tests | 36/36 green (`cd algorithm && python -m unittest discover -s tests -v`) |

## Repository map

```
algorithm/           Algorithm container (src/ + tests/) — the PFE algorithm
  model_server/      Flask + YOLO26n inference server (models/best.pt)
brand/               LeanLens logo assets (drop-in replacements, PWA icons)
demo/                Fake camera (real test-split scenes) + demo driver + scene picker
docs/                Report, defense plan + deck, demo script, fresh-DB bootstrap, screenshots
  report.md          Full end-of-studies report (English)
  soutenance_plan.md Oral defense plan (French) + LeanLens_Soutenance.pptx
  ACCOMPLISHMENTS.md Day-by-day log with all measured numbers
  RUNNING.md         Fresh clone → running platform (step-by-step)
  CLEANUP_PLAN.md    What can be deleted, when (3 waves)
frontend/            UI v2 (React + Vite + shadcn-admin), served by nginx
nginx/               Reverse proxy (UI brand rewriting + media serving)
training/            Dataset pipeline, training, eval, calibration, export, realtime demo
docker-compose.pfe.yml  The whole platform, Windows/Docker-Desktop ready
LeanLens_PFE_Audit.rar  Submission archive (code + docs + weights, 71 MB)
```

## Training your own model

```bash
python training/prepare_data.py                 # COCO bootstrap (or plug FPI-Det/Roboflow/CVAT)
python training/train.py --config training/configs/leanlens.yaml
python training/val.py --weights training/runs/train/leanlens_exp1/weights/best.pt --split test
python training/calibrate_confidence.py --weights ... --target 0.84
cp training/runs/train/leanlens_exp1/weights/best.pt models/best.pt   # deploy to the model server
docker compose -f docker-compose.pfe.yml up -d --force-recreate leanlens-model
```

## Notes

- Demo thresholds are lowered (0.4) for the synthetic demo camera; **production
  threshold is 0.84** (`calibration.json`).
- The demo camera serves **real photos from the test split** (chosen by measured
  predictions — `demo/pick_scenes.py`), not drawings, so the model behaves exactly
  as validated.
- All processing is on-prem; no data leaves the machine.
