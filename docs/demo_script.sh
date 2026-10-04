#!/usr/bin/env bash
# =============================================================================
# LeanLens PFE — Démo de soutenance (Jours 4-5)
# Usage :  bash docs/demo_script.sh
# Prérequis : Docker Desktop démarré (images déjà buildées).
#
# Scénario validé en J5 (toutes les étapes mesurées sur cette machine) :
#   fake camera (photos réelles du split test) -> leanlens-algo (YOLO26n via
#   model server) -> machine à états -> flou GDPR -> Django -> UI LeanLens.
# =============================================================================
set -uo pipefail
cd "$(dirname "$0")/.."

echo "=== 1/6 Démarrage de la plateforme (9 conteneurs + algo) ==="
docker compose -f docker-compose.pfe.yml up -d
echo "    -> nginx:80 (UI)  django:8000  model:5000  fake-camera:6001  panel:6002"

echo "=== 2/6 Santé du model server (best.pt epoch 38) ==="
for i in $(seq 1 15); do
  if curl -fs http://localhost:5000/health >/dev/null 2>&1; then
    curl -s http://localhost:5000/health; echo; break
  fi
  sleep 2
done

echo "=== 3/6 Bootstrap base fraîche (idempotent — requis si première install) ==="
# Upstream fake les migrations Mailer (workaround prod) -> crash sur base neuve.
# Ce bootstrap : signal déconnecté -> migrate réel -> admin/LeanLens2026 -> algo en DB.
docker exec django python -c "
import sys; sys.path.insert(0, '/app/src'); sys.argv=['bootstrap']
exec(open('/bootstrap_docs/bootstrap_pfe_fresh_db.py').read())
" 2>/dev/null || echo "    (skip: monté seulement si docs/ est branché, cf. ACCOMPLISHMENTS.md)"

echo "=== 4/6 Scénario PHONE (usage smartphone) ==="
curl -s -X POST -H 'Content-Type: application/json' \
     -d '{"mode":"phone"}' http://localhost:6001/mode >/dev/null
docker compose -f docker-compose.pfe.yml restart leanlens-algo >/dev/null 2>&1
echo "    scène = photo réelle person_phone+smartphone (track stable)"
echo "    -> phone_start attendu en ~10 s, rapport à la pose du téléphone"
echo "    UI : http://localhost/ (admin / LeanLens2026) — rapports avec photos floutées"

echo "=== 5/6 Scénario IDLE (inactivité 30 s) ==="
echo "    basculer : curl -X POST -H 'Content-Type: application/json' \"
echo "               -d '{\\\"mode\\\":\\\"idle\\\"}' http://localhost:6001/mode"
echo "    -> idle_alert à ~32 s (seuil 30 s), 1 rapport par personne détectée"

echo "=== 6/6 Observation en direct ==="
echo "    Panneau démo : http://localhost:6002 (scènes + compteur rapports)"
echo "    Rapports DB  : docker exec leanlens-db psql -U leanlens -d leanlens \\"
echo "                   -c 'SELECT id, violation_found, date_created FROM report;'"
echo "    Photos       : volumes/images/192.168.1.64/ (visages floutés GDPR)"
echo "    Logs algo    : docker logs -f leanlens-algo"
