from creches.models import CustomUser, TeaGarden, Creche, CrecheAttendant
from healthcenter.models import HealthCenter, Doctor, Nurse

def run():
    # -----------------------------
    # 1. Create Users
    # -----------------------------
    users = [
        {"username": "superadmin", "role": "superadmin", "password": "admin123"},
        {"username": "tgh1", "role": "teagarden_head", "password": "123"},
        {"username": "super_att_1", "role": "super_attendant", "password": "123"},
        {"username": "att_1", "role": "attendant", "password": "123"},
        {"username": "doc1", "role": "doctor", "password": "123"},
        {"username": "doc2", "role": "doctor", "password": "123"},  # second doctor
        {"username": "hn1", "role": "head_nurse", "password": "123"},
        {"username": "nurse1", "role": "nurse", "password": "123"},
    ]

    user_objects = {}
    for u in users:
        user_obj, created = CustomUser.objects.get_or_create(
            username=u["username"],
            defaults={"role": u["role"]}
        )
        if not created and user_obj.role != u["role"]:
            user_obj.role = u["role"]
        user_obj.set_password(u["password"])
        user_obj.save()
        user_objects[u["username"]] = user_obj

    # -----------------------------
    # 2. Tea Garden
    # -----------------------------
    tg, _ = TeaGarden.objects.get_or_create(
        tea_garden_code="TG001",
        defaults={"tea_garden_name": "Assam Tea Garden"}
    )

    # -----------------------------
    # 3. Creche
    # -----------------------------
    creche, _ = Creche.objects.get_or_create(
        creche_code="CR001",
        defaults={
            "tea_garden": tg,
            "creche_name": "Creche 1"
        }
    )

    # -----------------------------
    # 4. Health Center
    # -----------------------------
    hc, _ = HealthCenter.objects.get_or_create(
        code="HC001",
        defaults={
            "tea_garden": tg,
            "name": "Health Center 1"
        }
    )

    # -----------------------------
    # 5. Link Attendants to Creche
    # -----------------------------
    attendants = ["super_att_1", "att_1"]
    for username in attendants:
        CrecheAttendant.objects.get_or_create(
            user=user_objects[username],
            creche=creche
        )

    # -----------------------------
    # 6. Doctors
    # -----------------------------
    doctors = ["doc1", "doc2"]
    for username in doctors:
        Doctor.objects.get_or_create(
            user=user_objects[username],
            health_center=hc
        )

    # -----------------------------
    # 7. Nurses
    # -----------------------------
    Nurse.objects.get_or_create(
        user=user_objects["hn1"],
        health_center=hc,
        defaults={"role": "head_nurse"}
    )
    Nurse.objects.get_or_create(
        user=user_objects["nurse1"],
        health_center=hc,
        defaults={"role": "nurse"}
    )

    print("✅ All data created successfully (safe to rerun)!")