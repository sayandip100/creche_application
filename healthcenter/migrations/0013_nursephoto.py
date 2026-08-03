from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('healthcenter', '0012_doctorphotoembedding'),
    ]

    operations = [
        migrations.CreateModel(
            name='NursePhoto',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('photo', models.ImageField(upload_to='nurses/photos/')),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('nurse', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='photos', to='healthcenter.nurse')),
            ],
            options={
                'verbose_name': 'Nurse Photo',
                'verbose_name_plural': 'Nurse Photos',
            },
        ),
    ]