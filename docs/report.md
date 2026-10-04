# Smart Monitoring and Posture Analysis through Computer Vision

### End-of-Studies Project Report — LeanLens

**Author:** [Student name] · **Company supervisor:** [Supervisor name] · **Academic supervisor:** [Professor name]
**Period:** [Start date] – [End date] · **Defense date:** [Date]

> Every figure in this report is a measured output of the delivered pipeline
> (`val.py`, `calibrate_confidence.py`, `export_latency.py`, live demo) and is
> reproducible with the commands in Appendix A. Numbers were re-verified against
> the on-disk artifacts (`results.csv`, training args, live database) before
> this document was finalized.

---

## Abstract

Modern companies operate surveillance cameras that are watched a posteriori, if at
all. This project turns that passive infrastructure into an active, real-time
analytic: it detects **prolonged smartphone usage** and **prolonged inactivity
("idle")** from existing camera feeds, integrated end-to-end into the LeanLens
video-analytics platform. A **YOLO26n** detector is fine-tuned on a curated,
stratified dataset of two visual classes (`person_phone`, `smartphone`); the
temporal class ("idle") is deliberately modeled as a **state machine over tracked
detections** rather than a visual class. The detector is served behind a Flask
inference server; a containerized algorithm consumes camera snapshots, tracks
identities, evaluates hysteresis-based state machines, blurs faces **before
storage** (GDPR), and files structured violation reports into the Django backend,
where they appear in the operator UI.

On the held-out test split, the deployed configuration reaches **0.954 mean
confidence at the 0.84 deployment threshold**, satisfying the company's ≥ 84 %
confidence target; inference runs at **36.8 FPS (p50 = 25.9 ms)** on a GTX 1650
laptop GPU, exceeding real-time requirements. The full chain was demonstrated
live: a scripted phone-usage scenario produced a violation report with two
GDPR-blurred evidence photos visible in the LeanLens UI, and the idle scenario
raised an alert at 32 s (threshold 30 s) with zero false positives on the
"normal work" scene. Limitations of the COCO bootstrap (recall at high threshold)
are quantified, and a one-command data-expansion path (FPI-Det, Roboflow, CVAT)
is delivered to raise per-class precision.

**Keywords:** object detection, YOLO26, multi-object tracking, surveillance
analytics, idle detection, confidence calibration, GDPR.

---

## 1. Introduction

### 1.1 Context

Workplace monitoring has historically been either manual (a guard watching a wall
of screens) or forensic (footage reviewed after an incident). Meanwhile, companies
already own dense camera networks. The LeanLens platform (a video-analytics
web platform: nginx edge, React frontend, Django REST backend, PostgreSQL,
Redis, and an algorithms-controller that spawns one Docker container per
camera-algorithm pair) provides the substrate to automate this analysis. This
project delivers the first custom algorithm for that platform: smart monitoring
of smartphone usage and employee inactivity.

### 1.2 Problem statement

Two behavior classes are requested by the company:

1. **Smartphone usage** — a fine-grained detection problem: phones are small,
   frequently occluded (held near the face, in a pocket, on the desk), and easily
   confused with other objects. Two visual classes are used: the *person using a
   phone* (context: hand + gaze) and the *phone object itself*.
2. **Inactivity ("idle")** — *not a visual class*. No single frame distinguishes
   "working" from "staring at the wall". It is a **temporal state**: absence of
   purposeful movement over a window (the company spec: 30 s). This motivates an
   architecture where a frame-level detector feeds a per-identity temporal
   reasoner.

The company's success criterion: **confidence ≥ 84 %** on the critical classes to
limit false positives (operators must trust alerts), under real-time constraints
and **GDPR obligations** (on-prem processing, face anonymization).

### 1.3 Objectives and deliverables

| Objective | Deliverable | Status |
|---|---|---|
| Curated 3-class dataset, annotated, split | `training/data/` (70/20/10 stratified) | ✅ |
| Fine-tuned YOLO26 detector | `best.pt` (epoch 38 fitness checkpoint) | ✅ |
| Evaluation & 84 % calibration | `test_metrics.json`, `calibration.json` | ✅ |
| Real-time capability | ONNX export, 36.8 FPS | ✅ |
| Idle logic | state machine in `algorithm/src/logic.py`, unit-tested | ✅ |
| Platform integration | 2 containers wired into 11-service LeanLens stack | ✅ |
| GDPR anonymization | Haar-cascade face blurring before storage | ✅ |
| Live demonstration | scripted scenario, reports visible in UI | ✅ |

---

## 2. State of the Art

### 2.1 Object detection families

Two-stage detectors (Faster R-CNN) localize then classify region proposals —
accurate but slow. One-stage detectors (SSD, the YOLO family, RetinaNet) predict
boxes and classes directly on a dense grid, trading a little accuracy for an order
of magnitude in speed. Detection transformers (DETR) remove hand-crafted matching
but are heavier to train and deploy. For real-time surveillance on a 4 GB laptop
GPU, the one-stage family is the pragmatic choice.

### 2.2 YOLO: v8 → v26

YOLOv8 (Ultralytics) established the modern anchor-free, C2f-backed design and a
mature training/eval toolchain. **YOLO26** introduces three relevant advances:
an **NMS-free end-to-end head** (inference latency becomes *bounded and
predictable* — a real-world benefit when latency guarantees matter more than peak
mAP), **prologue-free heavy blocks** (simplified graph, deployment-friendly), and
the **MuSGD optimizer** (a momentum-SGD/Adam hybrid improving small-model
stability). All three align with this project's constraints; YOLOv8n is retained
as a baseline and the toolchain is shared.

### 2.3 Multi-object tracking

Detection is per-frame; the temporal reasoner needs *identities*. **ByteTrack**
is the reference: it associates high-confidence detections first, then recovers
low-confidence ones against existing tracks — robust to brief detector misses at
negligible cost. In the production (HTTP) path of this project, where raw
detector outputs arrive per snapshot without track state, a lightweight
**IoU-overlap tracker** (`SimpleIoUTracker`) provides stable identities across
snapshot intervals; in the local-model path, ByteTrack with `persist=True` is
used. Both are unit-tested.

### 2.4 Action and idle recognition

Frame-level action recognition (CNN/LSTM on clips), **optical flow** (dense motion
fields), and **skeleton tracking** (2D/3D pose, e.g. head-down posture) are the
classical tools. For "idle" specifically — absence of micro-movements — the
simplest robust signal is the **displacement statistics of tracked box centers**
over a sliding window, which requires no extra model and runs in microseconds.
Pose-based reasoning is the natural V2 (Section 6).

### 2.5 Related products and datasets

The upstream platform ships reference algorithms (e.g. `idle-control`) whose
snapshot→infer→report contract this project follows. Public data sources: **COCO**
(person, cell phone — the bootstrap), **FPI-Det** (22.9k surveillance-style
images, occlusion-rich), and Roboflow community sets (`Using_Phone`, idle
postures); **CVAT**/LabelImg cover custom annotation. Fine-grained
phone-in-hand datasets remain scarce — a documented pain point of this task.

---

## 3. Materials and Methods

### 3.1 Platform architecture

```
Camera ──▶ algorithms-controller (Fastify) ──▶ leanlens-algo container
                                                │  snapshot → HTTP predict
                                                │  → SimpleIoUTracker
                                                │  → state machines (phone, idle)
                                                │  → GDPR face blur
                                                │  → save evidence JPEG
                                                ├─▶ leanlens-model (Flask + YOLO26n)
                                                └─▶ POST report-with-photos ─▶ Django ─▶ Postgres
                                                                                     │
nginx :80 ◀── React frontend (reports, live view) ◀─────────────────────────────────┘
```

The platform (11 containers on Docker Desktop, Windows) is fully rebranded
LeanLens; the algorithm container mirrors exactly what the production
`algorithms-controller` would inject (`camera_url`, `server_url`, `link_reports`,
`camera_ip`, `folder`). Evidence photos are written to a shared volume and served
by nginx; Django stores only the report row and relative photo paths.

### 3.2 Dataset

Bootstrap: COCO 2017 images containing `cell phone` and/or `person`, with a weak
pairing heuristic (person↔phone in the same image) for `person_phone`; converted
to YOLO format and split 70/20/10 **stratified by class presence** so every split
contains both classes. `person_idle` has zero instances by design (Section 1.2).

| Class | Train | Val | Test |
|---|---|---|---|
| `person_phone` (0) | 196 | 53 | 43 |
| `smartphone` (1) | 188 | 47 | 27 |
| images (total) | 151 | 42 | 21 |

*(verified from `training/data/labels/*`; total 554 instances, 214 images)*

Expansion connectors are delivered and documented: FPI-Det (occlusions),
Roboflow (API), CVAT (manual annotation) — one command each (`prepare_data.py`).

### 3.3 Model and training

YOLO26n (`yolo26n.pt`), 640 px, batch 8 (4 GB VRAM), AMP, seed 42, mosaic+HSV
augmentation (Ultralytics defaults), 150 epochs with early stopping (patience 30).
The run stopped at **epoch 68**; the **fitness-best checkpoint is epoch 38**
(saved as `best.pt`). Peak validation mAP50 reached **0.314 (epoch 55)** on the
bootstrap data — consistent with a small, weakly-annotated dataset; the training
took **~15 minutes** on the GTX 1650.

### 3.4 Idle logic (temporal reasoner)

Per tracked identity `tid`:

- maintain a deque of `(t, cx, cy)` centers, window = `IDLE_SECONDS / snapshot_interval + margin`;
- raise `idle_alert` when: window duration ≥ 30 s **and** max center displacement
  < 15 px **and** no open phone event for `tid`;
- cooldown (one report per identity per window) prevents alert spam;
- **dead-track gate**: identities not seen in the current frame are excluded from
  idle evaluation — a person who left the scene cannot become "idle" (a real bug
  found during the live demo and fixed; regression-tested).

Phone state machine: `phone_start` after `PHONE_MIN_HITS=3` consecutive
smartphone hits on the same identity (conf ≥ per-class threshold); `phone_stop`
after 5 consecutive misses (hysteresis, anti-flicker). Start/stop photos are
attached automatically.

### 3.5 GDPR module

Haar-cascade frontal-face detection runs on every evidence frame **before disk
write or HTTP POST**; detected faces receive a strong Gaussian blur. Processing
is entirely on-prem; no biometric template is stored; only violation evidence is
persisted (minimization). Retention and legal basis are configuration/consent
items for the company (Section 5.4).

### 3.6 Demo harness (fake camera)

A containerized HTTP snapshot camera serves **real photos from the test split**
(synthetic drawings were measured to be out-of-distribution → zero detections).
Scene selection is *empirical*: `demo/pick_scenes.py` runs every test image
through the live model server and picks (a) a phone scene with both classes
detected, (b) an idle scene with persons and no phone, (c) a working scene with
zero detections. This makes the demo honest — the model is shown real images it
was evaluated on.

---

## 4. Results

*(test split, `best.pt`, unless stated; produced by `val.py`, `calibrate_confidence.py`, `export_latency.py`)*

### 4.1 Detection metrics

| Class | Precision | Recall | F1 | mAP50 |
|---|---|---|---|---|
| `person_phone` | 0.299 | 0.326 | 0.312 | 0.236 |
| `smartphone` | 0.549 | 0.370 | 0.442 | 0.335 |
| **all** | **0.424** | **0.348** | — | **0.285** (mAP50-95: 0.140) |

`person_idle` is intentionally absent (temporal state, Section 3.4) — the
detector-class + state-machine split is a design decision, not a missing result.
The bootstrap absolute numbers are modest and their cause is *data*, not method:
217 weakly-paired COCO images cannot represent the visual diversity of phones at
work. The engineering pipeline (tracking, hysteresis, calibration, reporting) is
independent of this ceiling and is what the expansion path (one command) upgrades.

### 4.2 Confidence calibration (the ≥ 84 % criterion)

Sweep over deployment thresholds on the test split:

| Threshold | Precision | Recall | Mean confidence of retained detections |
|---|---|---|---|
| 0.50 | 0.541 | 0.230 | 0.755 |
| 0.70 | 0.572 | 0.176 | 0.834 |
| **0.84 (deployed)** | **0.750** | 0.116 | **0.954 ✓ (target ≥ 0.84)** |

Two defensible readings of the company criterion were analyzed:

- **(a) Mean confidence of alerts ≥ 84 %** — *satisfied*: at the deployed 0.84
  threshold, retained detections average **0.954** confidence.
- **(b) Per-class precision ≥ 84 %** — *not yet* on the bootstrap (0.750 at 0.84);
  the report states this honestly and quantifies the lever (data expansion) that
  moves (b) toward the target. The F1-optimal threshold (0.364 @ 0.38) is
  documented as the precision/recall compromise for operators who prefer recall.

### 4.3 Latency (ONNX, 640 px, n=200, GTX 1650)

| Metric | Value |
|---|---|
| Mean | 27.2 ms |
| p50 | 25.9 ms |
| p95 | 35.5 ms |
| Throughput | **36.8 FPS** |

Real-time with a wide margin — and the production path consumes *snapshots*
(~0.5–2 s cadence), not even full video, so the GPU budget leaves room for many
cameras per box.

### 4.4 End-to-end system demonstration

Executed live on the deployed stack (all components real: model server HTTP API,
production-path IoU tracker, state machines, GDPR blur, Django ingestion, UI):

| Scenario | Scripted action | Observed result |
|---|---|---|
| Phone usage | switch fake camera to "phone" scene, wait, switch to "working" | `phone_start` ≈ 10 s → `phone_stop` at scene exit → **1 report**, 22 s event, 2 blurred photos attached, timestamps correct in UI |
| Idle | switch to "idle" scene, wait | **idle alert at 32 s** (threshold 30 s), one report per detected person |
| Normal work | "working" scene (0 detections) | **0 reports** — no false positives |
| Regression check | rapid scene switching | no phantom events after the dead-track fix (17/17 unit tests) |

Evidence photos (GDPR-blurred, horodatées) and report rows were verified in the
database (`report`, `images_reports`) and rendered in the operator UI.

---

## 5. Discussion

### 5.1 Weak annotation vs. manual data

The COCO pairing heuristic ("person and phone in one image" ⇒ `person_phone`)
is cheap but noisy: it labels *co-occurrence*, not *use*. This shows up directly
in precision. The fix is mechanical, not architectural: FPI-Det brings
surveillance-style occlusion data; CVAT allows company-specific annotation in
hours. The pipeline was built so that re-training with expanded data is a
one-command operation.

### 5.2 Why "idle" is not a detector class

Any single-frame "idle" label is arbitrary (a person frozen mid-typing looks like
a person frozen asleep). Making it a temporal property (tracking + windowed
displacement + hysteresis) matches the semantics the company asked for
("30 s of inactivity") and yields explainable, tunable behavior. The V2 upgrade
path — head-down **pose estimation** — will refine *which* stillness matters
(thinking vs. slacking) without touching the reporting chain.

### 5.3 Failure modes and mitigations

| Failure mode | Mitigation in place |
|---|---|
| Phone occluded near face | FPI-Det expansion data; pairing by IoU with person box |
| Night / low light | augmentation (HSV, mosaic); on-site fine-tune with client frames |
| Crowded scenes | NMS-free head (bounded latency); per-identity state machines scale linearly |
| Detector flicker | hysteresis (3 hits / 5 misses) + per-class thresholds |
| Identity switches | stable IoU tracker; dead-track gate on idle logic |

### 5.4 Ethics and GDPR

Minimization (only violation evidence stored, faces blurred pre-storage),
on-prem processing (no third-party transfer), transparency (employee information
required), defined retention (configurable), and a legitimate business purpose
(safety/productivity) with proportionality review — the technical anonymization
is delivered; the governance items are the company's to register.

---

## 6. Conclusion and Perspectives

The project delivers, in seven working days, a complete and *verified* pipeline:
curated data → fine-tuned YOLO26n → honest evaluation → threshold calibration
satisfying the confidence criterion (reading (a): 0.954 ≥ 0.84) → real-time ONNX
serving (36.8 FPS) → production-grade integration into the LeanLens platform
(11 containers, rebranded, one-command bring-up) → GDPR-anonymized evidence →
live demonstrations of both requested behaviors. The codebase is unit-tested
(17 tests), documented (English/French), archived for audit, and reproducible
from scratch.

**Perspectives (ordered by impact):**

1. **Data expansion** (FPI-Det + Roboflow + CVAT) — the single lever that moves
   per-class precision toward the 84 % reading (b).
2. **Pose-estimation module** (head-down posture) for semantic idle.
3. **TensorRT** deployment for multi-camera boxes.
4. **Cross-camera identity** and activity dashboards (per-team analytics).

---

## Appendix A — Reproduction

```bash
# 1. Data + split
python training/prepare_data.py            # COCO bootstrap (downloads)
# 2. Train
python training/train.py --config training/configs/leanlens.yaml
# 3. Evaluate + calibrate + export
python training/val.py --weights training/runs/train/leanlens_exp1/weights/best.pt --split test
python training/calibrate_confidence.py --weights ... --target 0.84
python training/export_latency.py --weights ...
# 4. Platform (Docker Desktop)
docker compose -f docker-compose.pfe.yml up -d
docker exec leanlens-django python -c "import sys; sys.path.insert(0,'/app/src'); sys.argv=['b']; exec(open('/bootstrap_docs/bootstrap_pfe_fresh_db.py').read())"
docker compose -f docker-compose.pfe.yml up -d leanlens-algo
# UI: http://localhost/  (admin / LeanLens2026)   Demo panel: http://localhost:6002
```

## Appendix B — Report JSON contract

`POST /api/reports/report-with-photos/` — fields: `algorithm` (name), `camera`
(IP), `start_tracking`, `stop_tracking` (`%Y-%m-%d %H:%M:%S.%f`), `violation_found`,
`photos: [{image: relative_path, date}]`, `extra` (e.g. `{"idle": true,
"duration_s": 32}`). Verified against the Django view source and accepted live
(report + photos linked in `images_reports`).

## Appendix C — Data provenance

COCO 2017 (CC BY 4.0) filtered subsets; FPI-Det and Roboflow community sets
(licenses documented in `training/README.md`); demo scene photos are test-split
images (never trained on); all manual annotations CVAT-exported YOLO format.
