# leanlens_smartphone_control — Conteneur algorithme LeanLens

Conteneur Python suivant le schéma de référence idle-control du projet
dont LeanLens est dérivé :
détection **smartphone** + **personne idle** sur les flux caméras de la plateforme LeanLens
(projet dérivé d'une base de code open source), avec anonymisation RGPD des preuves.

## Pipeline

```
snapshot ONVIF (ou RTSP) → serveur YOLO26 (/predict) → tracking + machines à états
→ preuves JPEG floutées (volume images partagé) → POST /api/reports/report-with-photos/
```

- **smartphone** : état ouvert après `PHONE_MIN_HITS` détections ≥ `CONF_PHONE` (0.84),
  fermé après `PHONE_MISSES_TO_END` frames sans détection → 1 rapport par incident.
- **idle** : track dont le centre de boîte bouge de moins de `IDLE_MOVE_TOLERANCE_PX`
  pendant `IDLE_SECONDS` (30 s) → rapport avec cooldown = durée idle.
- **RGPD** : `BLUR_FACES=1` (défaut) → visages pixellisés (Haar cascade, offline)
  sur les preuves uniquement, jamais sur les frames d'analyse.

## Contrat d'intégration (env vars, identiques à idle-control)

| Variable | Rôle |
|---|---|
| `camera_url` | URL snapshot ONVIF (`http://onvif:3456/onvif-http/snapshot?camera_ip=<ip>`) |
| `camera_stream_url` | RTSP (optionnel ; si présent, prioritaire) |
| `username` / `password` | auth caméra |
| `server_url` | hôte du model server ; dérivé en `http://<hôte>:5000` |
| `MODEL_SERVER_URL` | override URL complète du model server |
| `link_reports` | `http://django:8000/api/reports/report-with-photos/` |
| `folder` | `images/<ip>` (preuves) |
| `camera_ip` | IP caméra |
| `algorithm_name` | `smartphone_idle_control` |
| `extra` / `areas` | zones JSON (string) |
| `IMAGES_ROOT` | racine du volume images (`/var/www/leanlens/images`) |
| `USE_LOCAL_MODEL` | `1` = embarque le modèle (pas de model server) |
| `CONF_THRESHOLD` / `CONF_PHONE` / `CONF_IDLE` | seuils (0.84) |
| `PHONE_MIN_HITS` / `PHONE_MISSES_TO_END` | robustesse anti faux positifs |
| `IDLE_SECONDS` / `IDLE_MOVE_TOLERANCE_PX` | logique idle |
| `BLUR_FACES` | anonymisation RGPD (défaut 1) |
| `DEBUG_FRAMES` | logs périodiques |

## Rapport POSTé (contrat backend, cf. `src/Reports/views.py`)

```json
{
  "algorithm": "smartphone_idle_control",
  "camera": "192.168.1.64",
  "start_tracking": "2026-09-16 10:00:00.123456",
  "stop_tracking": "2026-09-16 10:01:30.654321",
  "violation_found": true,
  "extra": {},
  "photos": [{"image": "images/192.168.1.64/20260916_100000_phone_start_track3.jpg",
               "date": "2026-09-16 10:00:00.123456"}]
}
```

## Enregistrement dans la plateforme (2 minutes)

Une fois l'image buildée et poussée/presente sur la machine :

1. **Docker** : `docker build -t <registry>/leanlens_smartphone_control:latest .`
2. **UI LeanLens** → *Configuration → Algorithms → Add algorithm* :
   - Name: `smartphone_idle_control` (affiché « smartphone idle control »)
   - Image: `<registry>/leanlens_smartphone_control:latest`
   - La plateforme vérifie l'image (`/image/search`) puis la télécharge si besoin.
3. **Caméras** → sélectionner la caméra → cocher *smartphone idle control* → la
   plateforme POST `/run` à algorithms-controller qui démarre le conteneur avec
   les env vars du tableau ci-dessus.

Alternativement, via Django shell — **attention** : `Algorithm.save()` est
surchargé en amont (avec `is_available=True` il interroge le controller via
`sender("search", ...)` et échoue hors production ; avec `False` il ne sauvegarde
jamais). Passer par `bulk_create` (VÉRIFIÉ sur le fork LeanLens) :
```python
from src.CameraAlgorithms.models import Algorithm
Algorithm.objects.bulk_create([
    Algorithm(
        name="smartphone_idle_control",
        image_name="leanlens-smartphone-idle:latest",
        description="Détection smartphone + idle (YOLO26, RGPD blur)",
        is_available=True, used_in="dashboard",
    )
])
```

**Enregistrement E2E prouvé** : le test `tests/test_e2e_demo.py` valide la chaîne
complète contre le model server réel (HTTP /predict) — 74 tracks sur 15 frames
test, preuve floutée RGPD écrite, payload Django accepté (HTTP 201). Lancer :
`cd algorithm && MODEL_URL=http://127.0.0.1:5000 PYTHONPATH=src python -m unittest tests.test_e2e_demo -v`

## Lancement manuel (démo, sans plateforme)

```bash
docker build -t leanlens-model algorithm/model_server
docker build -t leanlens-algo algorithm

docker network create leanlens
docker run -d --name leanlens-model --network leanlens \
  -v $(pwd)/models:/models:ro -e MODEL_WEIGHTS=/models/best.pt -p 5000:5000 leanlens-model

docker run --rm --name leanlens-algo --network leanlens \
  -e camera_url='rtsp://user:pass@192.168.1.64/h264_stream' \
  -e camera_stream_url='rtsp://user:pass@192.168.1.64/h264_stream' \
  -e MODEL_SERVER_URL='http://leanlens-model:5000' \
  -e link_reports='http://host.docker.internal:8000/api/reports/report-with-photos/' \
  -e camera_ip='192.168.1.64' -e folder='images/192.168.1.64' \
  -e IMAGES_ROOT='/tmp/proofs' -e CONF_THRESHOLD='0.84' \
  -v $(pwd)/proofs:/tmp/proofs \
  leanlens-algo
```

## Tests

```bash
cd algorithm && python -m unittest tests.test_config tests.test_logic tests.test_gdpr tests.test_reporter -v
```

16 tests hors-ligne (machines à états, RGPD, reporter payload, dérivation URLs).

## Conformité au modèle YOLO attendu

Le model server attend un modèle 3 classes entraîné par `training/` :
`0=person_phone, 1=smartphone, 2=person_idle` (voir `training/configs/leanlens.yaml`).
