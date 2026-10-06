# Running LeanLens — from `git clone` to a working platform

This guide takes a **fresh clone** of this repository to a fully working LeanLens
platform with a live demo. It assumes nothing except Docker and Git.

- Tested on **Windows 11 + Docker Desktop (WSL2 backend)**; the same commands work
  on Linux/macOS with Docker Engine + Compose v2.
- First run: **~10–15 min** (image builds) + **~2 min** (image pulls + DB bootstrap).
- Every command is run from the repository root.
- Rehearsed from a **fresh clone** (every build context, Dockerfile, bind-mount
  source, compose `config`, and service count in this guide re-verified).

---

## 1. Prerequisites

| Requirement | Why |
|---|---|
| **Git** | cloning the repo |
| **Docker Desktop** (Windows/macOS) or **Docker Engine + Compose v2** (Linux) | runs the whole platform (13 containers) |
| ~10 GB free disk, ≥8 GB RAM | images ≈ 8 GB |
| Node.js 20+ *(optional)* | frontend development loop |
| Python 3.11+ *(optional)* | running algorithm tests / training tooling |

No `.env` file is needed anywhere: all configuration lives in
`docker-compose.pfe.yml` with working defaults.

---

## 2. Get the code

```bash
git clone https://github.com/GunsnrosesHG/LeanLens.git
cd LeanLens
git log --oneline        # branch: main
```

What is **not** in the repo (on purpose, see §11): runtime data (`volumes/`),
the COCO dataset (except the 3 demo scene photos), `node_modules/`, local
secrets (`.jwt-token`), the audit `.rar`, and agent-tooling folders.

---

## 3. One-time: the four upstream images

`docker-compose.pfe.yml` names every image `leanlens/*`. Most are **built from
this repo** (§4), but four services come from the upstream open-source
5sControl project and are simply re-tagged locally. Pull them once:

```bash
docker pull 5scontrol/onvif:latest             && docker tag 5scontrol/onvif:latest             leanlens/onvif:latest
docker pull 5scontrol/algorithms-controller:latest && docker tag 5scontrol/algorithms-controller:latest leanlens/algorithms-controller:latest
docker pull 5scontrol/5scontrol_front:latest   && docker tag 5scontrol/5scontrol_front:latest   leanlens/front:latest
# Optional — only needed for the "extras" profile (camera discovery), skip on Windows:
docker pull 5scontrol/onviffinder:latest       && docker tag 5scontrol/onviffinder:latest       leanlens/onviffinder:latest
```

Notes:

- `leanlens/front` is the **legacy CRA UI, rollback fallback only** — the active
  UI is built from `frontend/`. If you prefer building it from the source tree
  in this repo instead of pulling: `docker build -t leanlens/front:latest ./LeanLens-frontend-main/frontend-main`.
- `leanlens/algorithms-controller` restart-loops by design (known upstream bug);
  the platform is architected to bypass it — see §12.

---

## 4. Build the project images (first run only)

```bash
docker compose -f docker-compose.pfe.yml build
```

Builds, from source in this repo:

| Image | Built from | Contents |
|---|---|---|
| `leanlens/django` | `LeanLens-backend-main/backend-main/` | REST API |
| `leanlens-front-v2` | `frontend/` | new shadcn-admin UI (static bundle) |
| `leanlens-leanlens-model` | `algorithm/model_server/` | YOLO26 inference server (`models/best.pt` mounted read-only) |
| `leanlens-leanlens-algo` | `algorithm/` | PFE worker: detection, face blur, heartbeat |
| `leanlens-fake-camera` | `demo/fake_camera/` | synthetic scene camera |
| `leanlens-demo-driver` | `demo/` | scene buttons + report counter (the :6002 panel) |

Rebuilding a single image later:

```bash
docker compose -f docker-compose.pfe.yml build django        # or front-v2, leanlens-algo, ...
```

---

## 5. Start the platform

```bash
# 0. Create the runtime volume directories (a fresh clone has none).
#    Compose would create them itself, but on Linux it does so as root —
#    pre-creating them keeps ownership with your user:
mkdir -p volumes/images volumes/videos volumes/database volumes/log

# 1. Everything except the algorithm worker (12 containers):
docker compose -f docker-compose.pfe.yml up -d

# 2. The algorithm worker (profile "manual", so it starts explicitly):
docker compose -f docker-compose.pfe.yml up -d leanlens-algo
```

What happens automatically at `up -d`:

- **`leanlens-bootstrap`** (one-shot) runs `docs/bootstrap_pfe_fresh_db.py`:
  creates/migrates the DB, seeds the admin user, the PFE algorithm, the demo
  camera `192.168.1.64` and its link. **Idempotent**, retries 30× until the DB
  is ready. `docker ps` shows it as `Exited (0)` — that is success.
- `fake-camera` mounts the 3 demo scene photos committed under
  `training/data/images/test/`.

> The worker carries `profiles: ["manual"]` so a bare `up -d` does not start
> detection; naming the service explicitly (command above) enables it anyway.

---

## 6. Verify (~30 seconds)

```bash
# All containers up. Use -a: the one-shot bootstrap shows "Exited (0)",
# which IS success. 13 lines after step 2 (docker ps alone shows the 12 Up):
docker ps -a --format '{{.Names}}\t{{.Status}}'

# Front door answers:
curl -s -o /dev/null -w "%{http_code}\n" http://localhost/            # 200

# API answers (auth works end-to-end). `sed -n … p` yields EMPTY when the
# response is not the JSON we expect, so the guard fails loudly — instead of
# passing an HTML error page through as the "token" (which then surfaces as a
# confusing nginx 400 on the next command).
TOKEN=$(curl -s -X POST http://localhost/api/auth/jwt/create/ \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"LeanLens2026"}' \
  | sed -nE 's/.*"access":"([^"]+)".*/\1/p')
[ -n "$TOKEN" ] && echo "login OK" || echo "login FAILED — is the API up? see §12"

# Worker heartbeat / GDPR blur status. `stale:true` until the worker has
# published (it does so every 60 s), so re-run this after a minute if needed:
curl -s http://localhost/api/core/gdpr/status/ -H "Authorization: JWT $TOKEN"
```

Then open **http://localhost/** and log in.

---

## 7. Sign in

| Where | URL | Credentials |
|---|---|---|
| **LeanLens UI (v2)** | http://localhost/ | `admin` / `LeanLens2026` |
| Django admin | http://localhost:8000/admin/ | `admin` / `LeanLens2026` |
| Demo control panel | http://localhost:6002 | — |
| API service account (worker, non-staff) | `POST /api/auth/jwt/create/` | `leanlens-worker` / `WorkerPFE-2026` |
| Postgres (host tooling) | localhost:5432, db `leanlens` | `leanlens` / `leanlens-pfe` |

> The JWT header prefix is **`JWT`**, not `Bearer`: `Authorization: JWT <access>`.

---

## 8. Run the demo

Open http://localhost:6002 (or run `bash docs/demo_script.sh`) and press:

| Step | Scene | Expected result |
|---|---|---|
| 1 | **phone** | within ~10 s the worker opens a phone event |
| 2 | **working** | event closes → **violation report with 2 face-blurred photos** appears in the UI |
| 3 | **idle** | **idle alert at ~32 s** (30 s threshold) |
| 4 | **working** | silence — no false positives |

Evidence photos land in the Reports page of the UI (blurred **before** storage,
GDPR). The GDPR page shows a live *"Face blurring active"* indicator fed by the
worker heartbeat.

Also worth showing:

- **Cameras page** — add/delete cameras (discovery scan degrades gracefully to
  manual entry on Windows), toggle an algorithm on a camera: the worker
  suspends processing within ~10 s (poll interval 5 s).
- **Algorithms page** — assignment of `smartphone_idle_control` to cameras.

---

## 9. Service map

| Container | Role | Host port | Image source |
|---|---|---|---|
| `leanlens-django` | REST API + admin | 8000 | build (repo) |
| `leanlens-db` | PostgreSQL 15 | 5432 | `postgres:15` |
| `leanlens-redis` | cache, GDPR status | 6379 | `redis` |
| `leanlens-webserver` | nginx reverse proxy + on-the-fly rebrand (`sub_filter`) | **80** | `nginx:latest` + `nginx/default.conf` |
| `leanlens-front-v2` | **active UI** (shadcn-admin rebuild) | — | build `frontend/` |
| `leanlens-front` | legacy UI, rollback only | — | re-tag `5scontrol/5scontrol_front` |
| `leanlens-onvif` | ONVIF snapshots/streams | 3456 | re-tag `5scontrol/onvif` |
| `leanlens-algorithms-controller` | upstream algo REST (**crash-loops, bypassed**) | 3333 | re-tag `5scontrol/algorithms-controller` |
| `leanlens-model` | YOLO26 inference server | 5000 | build `algorithm/model_server/` |
| `leanlens-algo` | **PFE worker** (detection, blur, assignment polling, heartbeat) | — | build `algorithm/` (profile `manual`) |
| `leanlens-fake-camera` | demo camera (real test-split photos) | 6001 | build `demo/fake_camera/` |
| `leanlens-demo-driver` | demo scene buttons | 6002 | build `demo/` |
| `leanlens-bootstrap` | one-shot DB seed (Exited 0 = OK) | — | `leanlens/django` |
| `leanlens-onviffinder` | camera discovery (profile `extras`, host networking — not for Windows) | — | re-tag `5scontrol/onviffinder` |

Network: all services talk on the `leanlens` Docker network; the browser only
ever needs **:80** (UI + API), plus **:6002** for the demo panel and **:8000**
for Django admin.

---

## 10. Day-to-day commands

```bash
docker compose -f docker-compose.pfe.yml ps                  # status
docker logs -f leanlens-algo --tail 100                      # worker logs
docker compose -f docker-compose.pfe.yml logs -f django      # API logs
docker restart leanlens-webserver                            # reload nginx (after container recreate)
docker compose -f docker-compose.pfe.yml up -d --build front-v2    # deploy a new UI build
docker compose -f docker-compose.pfe.yml build leanlens-algo \
  && docker compose -f docker-compose.pfe.yml up -d leanlens-algo  # deploy a new worker
docker compose -f docker-compose.pfe.yml down                # stop everything (keeps DB data)
```

---

### Frontend development loop (`frontend/`)

```bash
cd frontend
npm ci                    # first time (~2 min)
npm run dev               # Vite dev server; /api and /images proxy to http://localhost
npm run build             # typecheck (tsc -b) + production bundle
npx tsc --noEmit          # typecheck only
npm run lint              # eslint
npm test                  # vitest (headless)
```

- **No `.env` required** (the Clerk key in `.env.example` is a template leftover).
- The TanStack Router route tree **regenerates during `npm run build`** — do not
  run `npx tsr generate` (it errors).
- The built bundle is served through nginx only after
  `docker compose -f docker-compose.pfe.yml build front-v2 && ... up -d front-v2`.

### Algorithm development loop (`algorithm/`)

```bash
pip install -r algorithm/requirements.txt        # once
cd algorithm
python -m unittest discover -s tests -v          # 36/36 green
docker compose -f docker-compose.pfe.yml build leanlens-algo    # (from repo root)
```

Weights: `models/best.pt` is committed and mounted read-only into the model
server. To deploy a retrained model, copy it over `models/best.pt` and
`docker compose -f docker-compose.pfe.yml up -d --force-recreate leanlens-model`
(see README → *Training your own model*).

### Training (`training/`)

Dataset, training, calibration and export tooling — see README →
*Training your own model*, plus `training/README.md`. The dataset itself is
fetched with `python training/download_dataset.py --source coco --max-images 400`.

---

## 11. Git workflow & what's ignored

- Work on a branch: `git checkout -b feat/…` → commit → push → PR.
- **Ignored on purpose** (don't fight `.gitignore`):
  - `volumes/` — runtime DB dumps, evidence photos, videos, logs
  - `.jwt-token` — transient admin JWT from curl checks
  - `node_modules/`, `dist/`, `frontend/.tanstack/`, `training/runs/`, `*.log`
  - dataset images (except the **3 committed demo scenes**), `training/yolo26n.pt`
  - `LeanLens_PFE_Audit.rar` (regenerate: `"/c/Program Files/WinRAR/Rar.exe" a -r -ep1 -y -m3 LeanLens_PFE_Audit.rar …` — see MANIFEST inside the archive)
  - agent-tooling folders (`.claude/`, `.swarm/`, `CLAUDE.md`, `.mcp.json`, …)
- **Committed on purpose**: `models/best.pt` (runtime dependency of the model
  server) and the 3 demo scene photos (runtime dependency of `fake-camera`).
- Never commit `.env`-style files, `.jwt-token`, or anything under `volumes/`.

---

## 12. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| http://localhost → **502** after recreating the Django container | nginx cached the old container IP | `docker restart leanlens-webserver` |
| §6 **login check fails**: `/api/…` → **502** while `/` still returns 200 (typical after a Docker Desktop restart) | Django started while `db`/`redis` were still down, so it never bound `:8000` | `docker compose -f docker-compose.pfe.yml up -d --force-recreate django && docker restart leanlens-webserver` |
| `leanlens-algorithms-controller` keeps restarting | known upstream crash-loop; platform bypasses it architecturally | ignore it — and **never** call `POST /create-process/` |
| `GET /api/core/find_cameras/` → 500 | `onviffinder` (profile `extras`) not deployed on Windows | add cameras manually in the UI (graceful fallback) |
| Worker doesn't react to the UI toggle | worker not running | `docker compose -f docker-compose.pfe.yml up -d leanlens-algo` |
| `docker compose build` can't find an image name | skipped §3 | pull + re-tag the four upstream images |
| Port already in use (80, 8000, 5432…) | another stack occupies it | stop it, or edit the host side of the `ports:` mapping |
| Demo scenes missing (fake-camera serves nothing) | `training/data/images/test/` wiped | restore the 3 `coco_*.jpg` files (committed in git: `git checkout -- training/data/images/test/`) |
| First `up -d` before DB is ready | bootstrap retries | wait ~30 s; `docker logs leanlens-bootstrap` |

---

## 13. Full reset (destructive)

```bash
docker compose -f docker-compose.pfe.yml down -v     # stop + DELETE the DB volume
rm -rf volumes/*                                     # wipe evidence photos/videos/logs
docker compose -f docker-compose.pfe.yml up -d       # fresh bootstrap re-seeds everything
```
