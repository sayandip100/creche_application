from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('healthcenter', '0017_medicineunit'),
    ]

    operations = [
        migrations.AddField(
            model_name='patienttreatment',
            name='doctor_prescription',
            field=models.TextField(blank=True, help_text="Doctor's prescription details", null=True),
        ),
        migrations.AddField(
            model_name='patienttreatment',
            name='doctor_prescription_image',
            field=models.ImageField(blank=True, help_text="Doctor's prescription image/file", null=True, upload_to='doctor_prescriptions/'),
        ),
    ]