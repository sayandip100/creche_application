# Generated to rename Teacher/TeacherPhoto/TeacherPhotoEmbedding to Staff/StaffPhoto/StaffPhotoEmbedding
# while preserving existing data (tables and FK columns are renamed, not dropped).

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('school', '0003_teacherphoto_teacherphotoembedding'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='Teacher',
            new_name='Staff',
        ),
        migrations.RenameModel(
            old_name='TeacherPhoto',
            new_name='StaffPhoto',
        ),
        migrations.RenameModel(
            old_name='TeacherPhotoEmbedding',
            new_name='StaffPhotoEmbedding',
        ),
        migrations.RenameField(
            model_name='staffphoto',
            old_name='teacher',
            new_name='staff',
        ),
        migrations.RenameField(
            model_name='staffphotoembedding',
            old_name='teacher_photo',
            new_name='staff_photo',
        ),
        migrations.RenameField(
            model_name='staffphotoembedding',
            old_name='teacher',
            new_name='staff',
        ),
        migrations.AlterField(
            model_name='staffphoto',
            name='photo',
            field=models.ImageField(upload_to='school/staff/photos/'),
        ),
        migrations.AlterField(
            model_name='staff',
            name='user',
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='school_staff',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name='staff',
            name='school',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='staff',
                to='school.school',
            ),
        ),
    ]