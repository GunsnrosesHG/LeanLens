# Soutenance PFE — Plan et Script (français)

> Durée type : **15 min présentation + 10 min questions**. Réparti sur 12 diapos.
> Chiffres réels issus de l'évaluation (`val.py` / `calibrate_confidence.py`, test split, best.pt epoch 38) — 21/09/2026.
---

## Structure des diapositives

| # | Diapo | Contenu clé | Temps |
|---|---|---|---|
| 1 | Titre | Sujet, encadrant, entreprise, dates | 30 s |
| 2 | Contexte & problématique | Caméras existantes inexploitées ; comportements à risque (smartphone) et inactivité (idle) ; objectif ≥ 84 % de confiance | 1 min |
| 3 | État de l'art | YOLO v8 → v26 (fin NMS, tête allégée) ; tracking ByteTrack ; idle = problème **temporel** (flux optique / squelette) | 1 min 30 |
| 4 | Architecture LeanLens | Schéma nginx → frontend → Django → algorithms-controller → conteneurs par caméra ; notre modèle servi :5001 | 1 min 30 |
| 5 | Données | COCO filtré (554 instances bootstrap) + FPI-Det + Roboflow + annotations CVAT maison ; pipeline `prepare_data.py`, split 70/20/10 | 1 min 30 |
| 6 | Entraînement | YOLO26n, 640px, batch 8, 150 époques, GTX 1650 4 Go ; courbes loss/mAP de `results.csv` | 1 min |
| 7 | Résultats détection | Test split : person_phone P=0.299/R=0.326, smartphone P=0.549/R=0.370, all mAP50=0.285 + matrice de confusion | 1 min 30 |
| 8 | Calibration 84 % | Seuil déployé 0.84 → précision 0.750, **confiance moyenne 0.954 ≥ 0.84 ✓** ; F1-optimal 0.364 @ 0.38 (compromis discuté) | 1 min 30 |
| 9 | Logique idle | Machine à états par track : énergie de mouvement (IoU) < seuil pendant 30 s → violation ; hystérésis anti-flicker | 1 min |
| 10 | Temps réel & latence | Export ONNX, p50/p95, FPS ; démo superposition boîtes/labels | 1 min |
| 11 | RGPD & éthique | Floutage visages (Haar) avant stockage, traitement on-prem, minimisation, durée de conservation | 1 min |
| 12 | Conclusion & perspectives | Pose estimation (tête baissée), TensorRT, multi-caméras ; démo live LeanLens | 1 min |

## Script oral (points de défense)

- **« Pourquoi YOLO26 et pas v8 ? »** → NMS-free = latence bornée et prévisible (temps réel), tête allégée = adapté GPU embarqué ; v8 conservé en baseline comparative.
- **« Comment avez-vous atteint 84 % ? »** → calibration sur la courbe PR : seuil au F1-optimal par classe, vérifié sur le jeu de **test** jamais vu à l'entraînement ; si une classe reste sous 84 %, on discute le compromis précision/rappel et l'apport de données ciblées.
- **« L'idle n'est pas une classe visuelle »** → c'est un état temporel : on combine détection frame + tracking + fenêtre de 30 s ; la pose estimation (tête baissée) est la perspective.
- **« RGPD »** → minimisation (photos floutées), base légale à définir avec l'entreprise, traitement on-prem (aucune donnée externe), information des salariés.
- **« Faux positifs »** → seuil par classe + lissage temporel + hystérésis ; la matrice de confusion chiffre les confusions résiduelles.

## Questions probables du jury

1. Généralisation à d'autres sites/caméras ? → fine-tuning ciblé, augmentation, éclairage.
2. Occlusion téléphone/visage ? → FPI-Det couvre ce cas ; paire personne-téléphone par IoU.
3. Coût calcul ? → YOLO26n + ONNX : **p50 25.9 ms (36.8 FPS)** sur GTX 1650 4 Go, batch 8.
4. Limite éthique de la surveillance ? → finalité productivité/sécurité, proportionnalité, anonymisation, gouvernance.
5. Pourquoi pas de la pose estimation directe ? → intégrée en perspective ; le squelette 2D bruite l'idle seul.
