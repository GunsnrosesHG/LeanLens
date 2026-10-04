# PFE (LeanLens) : OrderOperationTimespan.employee passe de SET_NULL à
# DO_NOTHING. Les tables ERP sont non gérées (managed=False, schéma 'erp'
# absent du déploiement LeanLens) : avec SET_NULL, le collector Django
# émettait un UPDATE sur la table inexistante à chaque suppression de compte
# utilisateur (500 UndefinedTable sur DELETE /api/auth/users/<id>/).
# Migration state-only (aucun impact base de données, modèle non géré).

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("erp_5s", "0002_alter_items_table_alter_operations_table_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="orderoperationtimespan",
            name="employee",
            field=models.ForeignKey(
                null=True, on_delete=models.DO_NOTHING, to="Employees.customuser"
            ),
        ),
    ]
