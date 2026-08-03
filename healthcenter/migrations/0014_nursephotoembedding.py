from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('healthcenter', '0013_nursephoto'),
    ]

    operations = [
        migrations.CreateModel(
            name='NursePhotoEmbedding',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('embedding', models.BinaryField(null=True, blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('nurse', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='photo_embeddings', to='healthcenter.nurse')),
                ('nurse_photo', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='embeddings', to='healthcenter.nursephoto')),
            ],
            options={
                'verbose_name': 'Nurse Photo Embedding',
                'verbose_name_plural': 'Nurse Photo Embeddings',
            },
        ),
    ]