# Generated manually - only creates MedicineUnit model and unit FK on Medicine
# (other fields in this migration were already added manually via run_migration.py)

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('healthcenter', '0016_doctorcheckin_attendance_date_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='MedicineUnit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('unit_name', models.CharField(max_length=100, unique=True)),
            ],
            options={
                'verbose_name': 'Medicine Unit',
                'verbose_name_plural': 'Medicine Units',
                'ordering': ['unit_name'],
            },
        ),
        migrations.AddField(
            model_name='medicine',
            name='unit',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='medicines', to='healthcenter.medicineunit'),
        ),
    ]