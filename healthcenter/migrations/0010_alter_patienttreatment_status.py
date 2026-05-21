# Generated manually to fix status field migration

from django.db import migrations, models


def convert_status_to_integer(apps, schema_editor):
    """Convert status field from CharField to IntegerField"""
    PatientTreatment = apps.get_model('healthcenter', 'PatientTreatment')
    
    # Update all records, converting string status to integer
    for record in PatientTreatment.objects.all():
        if record.status == 'pending' or record.status == '' or record.status is None:
            record.status = 0
        elif record.status == 'in_progress':
            record.status = 1
        elif record.status == 'completed':
            record.status = 2
        elif record.status == 'cancelled':
            record.status = 3
        else:
            record.status = 0  # Default fallback
        record.save()


def reverse_status_to_string(apps, schema_editor):
    """Reverse conversion (not typically used)"""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('healthcenter', '0009_patienttreatment_image'),
    ]

    operations = [
        migrations.RunPython(convert_status_to_integer, reverse_status_to_string),
        migrations.AlterField(
            model_name='patienttreatment',
            name='status',
            field=models.IntegerField(choices=[(0, 'Pending'), (1, 'In Progress'), (2, 'Completed'), (3, 'Cancelled')], default=0),
        ),
    ]
