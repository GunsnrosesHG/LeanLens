#!/usr/bin/env python
"""Bootstrap base LeanLens — première installation sur base VIERGE.

Le entrypoint.sh officiel fake les migrations Mailer (workaround pour leur DB
de production pré-existante) mais sur une base vierge, le signal post_migrate
de Mailer plante (table 'days_of_week' jamais créée) et bloque tout.

Stratégie (vérifiée sur le fork) :
  1. migrer toutes les apps SAUF Mailer
  2. migrer Mailer pour DE BON (le signal crée alors les 7 jours sur la table
     réelle, fraîchement créée)
  3. créer l'admin, enregistrer l'algorithme PFE, la caméra de démo et le lien

Identifiants créés :
  UI      : http://localhost/          admin / LeanLens2026
  Django  : http://localhost:8000/admin/   admin / LeanLens2026
  Postgres: leanlens / leanlens-pfe   (base : leanlens)

Usage :
  # monté dans le conteneur via ./docs:/bootstrap_docs:ro (docker-compose.pfe.yml)
  docker exec leanlens-django python -c "import sys; sys.path.insert(0,'/app/src'); \
      sys.argv=['bootstrap']; exec(open('/bootstrap_docs/bootstrap_pfe_fresh_db.py').read())"
"""
import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.core.management import call_command  # noqa: E402

ADMIN_USER = "admin"
ADMIN_PASSWORD = "LeanLens2026"
DEMO_CAMERA_ID = "192.168.1.64"


def migrate_all() -> None:
    # Racine du problème (fork upstream) : le entrypoint.sh officiel FAKE les
    # migrations Mailer 0001+0002 (workaround pour leur DB de production qui
    # existait déjà) => sur une base vierge, django_migrations REGISTRE Mailer
    # comme appliqué alors que les tables n'existent pas.
    # Séquence correcte en base VIERGE :
    #   0. DÉBRANCHER le signal Mailer post_migrate — Django l'émet MÊME pour
    #      les migrations faked, et il interroge 'days_of_week' avant création ;
    #   1. --fake zero : annuler les enregistrements factices de Mailer ;
    #   2. migrer Mailer POUR DE BON (tables enfin créées) ;
    #   3. migrer TOUT le reste (CameraAlgorithms 0002 dépend de Mailer 0002) ;
    #   4. semer les 7 jours manuellement (le signal étant débranché).
    from django.db import connection
    from django.db.migrations.executor import MigrationExecutor
    from django.db.models.signals import post_migrate
    from django.db.utils import ProgrammingError

    from src.Mailer.signals import create_days_of_week

    post_migrate.disconnect(create_days_of_week)

    # État constaté après entrypoint.sh : PARTIEL et variable (tables créées
    # sans enregistrement, enregistrements sans tables, colonnes finales déjà
    # en place). Stratégie auto-réparatrice, migration par migration, dans
    # l'ordre des dépendances :
    #   - tentative RÉELLE ;
    #   - si la base est dans un état déjà couvert ("already exists" /
    #     "does not exist") -> --fake (enregistrement seul) et on continue.
    executor = MigrationExecutor(connection)
    targets = executor.loader.graph.leaf_nodes()
    plan = executor.migration_plan(targets, clean_start=False)
    for migration, _backwards in plan:
        app_label, name = migration.app_label, migration.name
        try:
            call_command("migrate", app_label, name, "--noinput", verbosity=0)
        except ProgrammingError as exc:
            msg = str(exc).lower()
            if "already exists" in msg or "does not exist" in msg:
                print(f"  {app_label}.{name} : état partiel -> --fake ({exc})")
                call_command("migrate", app_label, name, "--noinput", fake=True, verbosity=0)
            else:
                raise


def seed_days_of_week() -> None:
    # Filet de sécurité : le signal de Mailer est censé l'avoir déjà fait.
    from src.Mailer.models import DayOfWeek

    if DayOfWeek.objects.exists():
        return
    for day in ("Monday", "Tuesday", "Wednesday", "Thursday",
                "Friday", "Saturday", "Sunday"):
        DayOfWeek.objects.create(day=day)
    print("7 jours créés (filet de sécurité)")


def create_admin() -> None:
    from django.contrib.auth import get_user_model

    User = get_user_model()
    if User.objects.filter(username=ADMIN_USER).exists():
        print(f"admin '{ADMIN_USER}' existe déjà (mot de passe inchangé)")
    else:
        User.objects.create_superuser(ADMIN_USER, password=ADMIN_PASSWORD)
        print(f"superuser créé : {ADMIN_USER} / {ADMIN_PASSWORD}")

    # Compte de service du worker (P2) : leanlens-algo interroge
    # get-process/<ip>/ en JWT pour suspendre/reprendre la détection selon le
    # toggle de la page Algorithmes (POST toggle-process/). PAS superuser.
    WORKER_USER, WORKER_PASSWORD = "leanlens-worker", "WorkerPFE-2026"
    worker, w_created = User.objects.get_or_create(
        username=WORKER_USER, defaults={"email": "worker@leanlens.local"}
    )
    worker.email = worker.email or "worker@leanlens.local"
    worker.set_password(WORKER_PASSWORD)
    worker.is_staff = False
    worker.is_superuser = False
    worker.save()
    print(f"worker de service : {WORKER_USER} / {WORKER_PASSWORD}",
          "(créé)" if w_created else "(mis à jour)")


def register_pfe_algorithm() -> None:
    """Enregistre l'algorithme PFE (bulk_create : le save() surchargé amont
    exige une image présente dans le registre controller)."""
    from src.CameraAlgorithms.models import Algorithm

    if Algorithm.objects.filter(name="smartphone_idle_control").exists():
        print("algorithme déjà enregistré")
        return
    created = Algorithm.objects.bulk_create([
        Algorithm(
            name="smartphone_idle_control",
            image_name="leanlens-smartphone-idle:latest",
            description="Détection smartphone + idle (YOLO26, RGPD blur) — PFE",
            is_available=True,
            used_in="dashboard",
        )
    ])
    print(f"algorithme enregistré : {created[0].name}")


def seed_demo_camera() -> None:
    """Caméra de démo (fake camera HTTP) + lien avec l'algorithme PFE.

    Camera.save() standard (chiffre le mot de passe, name par défaut) ;
    CameraAlgorithm.save() standard (process_id=0 jusqu'au démarrage réel).
    """
    from src.CameraAlgorithms.models import Algorithm, Camera, CameraAlgorithm

    camera, created = Camera.objects.get_or_create(
        id=DEMO_CAMERA_ID,
        defaults={"username": "demo", "password": "demo", "name": "LeanLens Demo Camera"},
    )
    print(f"caméra {DEMO_CAMERA_ID} : {'créée' if created else 'existante'}")

    algo = Algorithm.objects.filter(name="smartphone_idle_control").first()
    if algo is None:
        print("!! algorithme PFE absent, lien non créé")
        return
    link, created = CameraAlgorithm.objects.get_or_create(
        algorithm=algo, camera=camera, defaults={"is_active": True}
    )
    if not created:
        link.is_active = True
        link.save(update_fields=["is_active"])
    print(f"lien caméra↔algorithme : {'créé' if created else 'confirmé (is_active=True)'}")


def print_credentials() -> None:
    print("-- Identifiants LeanLens " + "-" * 30)
    print("  UI LeanLens : http://localhost/        admin / LeanLens2026")
    print("  Admin Django: http://localhost:8000/admin/   admin / LeanLens2026")
    print("  Postgres    : base 'leanlens', user 'leanlens', mdp 'leanlens-pfe'")


def main() -> None:
    print("== 1/5 migrations (signal Mailer débranché) ==")
    migrate_all()
    print("== 2/5 jours de la semaine ==")
    seed_days_of_week()
    print("== 3/5 admin ==")
    create_admin()
    print("== 4/5 algorithme PFE + caméra de démo ==")
    register_pfe_algorithm()
    seed_demo_camera()
    print("== 5/5 identifiants ==")
    print_credentials()
    print("BOOTSTRAP_DONE")


if __name__ == "__main__":
    main()
