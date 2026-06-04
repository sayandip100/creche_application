from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('creches', '0010_foodrecord'),
    ]

    operations = [
        migrations.CreateModel(
            name='CrecheAttendantPhoto',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('photo', models.ImageField(upload_to='attendants/photos/')),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('attendant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='photos', to='creches.crecheattendant')),
            ],
            options={
                'verbose_name': 'Creche Attendant Photo',
                'verbose_name_plural': 'Creche Attendant Photos',
            },
        ),
    ]