from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('healthcenter', '0010_patienttreatment_status'),
    ]

    operations = [
        migrations.CreateModel(
            name='DoctorPhoto',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('photo', models.ImageField(upload_to='doctors/photos/')),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('doctor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='photos', to='healthcenter.doctor')),
            ],
            options={
                'verbose_name': 'Doctor Photo',
                'verbose_name_plural': 'Doctor Photos',
            },
        ),
    ]