from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('healthcenter', '0011_doctorphoto'),
    ]

    operations = [
        migrations.CreateModel(
            name='DoctorPhotoEmbedding',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('embedding', models.BinaryField(null=True, blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('doctor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='photo_embeddings', to='healthcenter.doctor')),
                ('doctor_photo', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='embeddings', to='healthcenter.doctorphoto')),
            ],
            options={
                'verbose_name': 'Doctor Photo Embedding',
                'verbose_name_plural': 'Doctor Photo Embeddings',
                'unique_together': {('doctor',)},
            },
        ),
    ]