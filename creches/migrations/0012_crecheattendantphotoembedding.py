from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('creches', '0011_crecheattendantphoto'),
    ]

    operations = [
        migrations.CreateModel(
            name='CrecheAttendantPhotoEmbedding',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('embedding', models.BinaryField(null=True, blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('attendant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='photo_embeddings', to='creches.crecheattendant')),
                ('attendant_photo', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='embeddings', to='creches.crecheattendantphoto')),
            ],
            options={
                'verbose_name': 'Creche Attendant Photo Embedding',
                'verbose_name_plural': 'Creche Attendant Photo Embeddings',
            },
        ),
    ]