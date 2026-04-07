# creches/scripts/test_data.py

from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import date, timedelta
import random

from creches.models import *
from healthcenter.models import *

User = get_user_model()


def run():
    """Seed complete dummy data for all models."""
    print("🚀 Seeding data...")

    # -----------------------------
    # USERS
    # -----------------------------
    superadmin, _ = User.objects.get_or_create(
        username="admin",
        defaults={"role": "superadmin"}
    )
    superadmin.set_password("1234")
    superadmin.save()

    tg_head, _ = User.objects.get_or_create(
        username="tg_head",
        defaults={"role": "teagarden_head"}
    )

    staff_users = []
    for i in range(1, 8):
        u, _ = User.objects.get_or_create(
            username=f"staff{i}",
            defaults={"role": "staff"}
        )
        u.set_password("1234")
        u.save()
        staff_users.append(u)

    # -----------------------------
    # TEA GARDEN
    # -----------------------------
    tg, _ = TeaGarden.objects.get_or_create(
        tea_garden_code="TG001",
        defaults={
            "tea_garden_name": "Green Valley Tea Garden",
            "district_name": "Darjeeling",
            "block_name": "Block A"
        }
    )

    # -----------------------------
    # CRECHES
    # -----------------------------
    creches = []
    for i in range(1, 3):
        c, _ = Creche.objects.get_or_create(
            creche_code=f"CR00{i}",
            defaults={
                "tea_garden": tg,
                "creche_name": f"Creche {i}"
            }
        )
        creches.append(c)

    # -----------------------------
    # ATTENDANTS
    # -----------------------------
    attendants = []
    for i, c in enumerate(creches):
        att, _ = CrecheAttendant.objects.get_or_create(
            creche=c,
            user=staff_users[i],
            defaults={"role": "super_attendant" if i == 0 else "attendant"}
        )
        attendants.append(att)

    # -----------------------------
    # CHILDREN
    # -----------------------------
    children = []
    for c in creches:
        for i in range(5):
            child = Child.objects.create(
                creche=c,
                name=f"{c.creche_name}_Child_{i}",
                age_years=random.randint(2, 6),
                gender=random.choice(["Male", "Female"]),
                created_by=random.choice(staff_users)
            )
            children.append(child)

    # -----------------------------
    # CHILD ATTENDANCE
    # -----------------------------
    for c in creches:
        attendance, _ = ChildAttendance.objects.get_or_create(
            creche=c,
            attendance_date=date.today(),
            attendance_mode="GROUP",
            defaults={"marked_by": random.choice(attendants)}
        )

        for child in Child.objects.filter(creche=c):
            ChildAttendanceDetail.objects.get_or_create(
                child_attendance=attendance,
                child=child,
                defaults={
                    "attendance_status": random.choice(["PRESENT", "ABSENT"])
                }
            )

    # -----------------------------
    # ATTENDANT ATTENDANCE
    # -----------------------------
    for att in attendants:
        AttendantAttendance.objects.get_or_create(
            attendant=att,
            attendance_date=date.today(),
            defaults={
                "creche": att.creche,
                "check_in_time": timezone.now(),
                "geo_verified": True
            }
        )

    # -----------------------------
    # FOOD MONITORING
    # -----------------------------
    for c in creches:
        FoodMonitoring.objects.create(
            creche=c,
            monitoring_date=date.today(),
            meal_type="Lunch",
            food_description="Rice, Dal, Sabji",
            estimated_calories=450,
            entered_by=random.choice(attendants)
        )

    # -----------------------------
    # HEALTH CENTERS
    # -----------------------------
    centers = []
    for i in range(1, 3):
        hc, _ = HealthCenter.objects.get_or_create(
            code=f"HC00{i}",
            defaults={
                "tea_garden": tg,
                "name": f"Health Center {i}"
            }
        )
        centers.append(hc)

    # -----------------------------
    # DOCTORS
    # -----------------------------
    doctors = []
    for i, hc in enumerate(centers):
        doc, _ = Doctor.objects.get_or_create(
            health_center=hc,
            user=staff_users[i+2],
            defaults={"specialization": "General Physician"}
        )
        doctors.append(doc)

    # -----------------------------
    # NURSES
    # -----------------------------
    nurses = []
    for i, hc in enumerate(centers):
        nurse, _ = Nurse.objects.get_or_create(
            health_center=hc,
            user=staff_users[i+4],
            defaults={"role": "head_nurse" if i == 0 else "nurse"}
        )
        nurses.append(nurse)

    # -----------------------------
    # DOCTOR ATTENDANCE
    # -----------------------------
    for doc in doctors:
        DoctorAttendance.objects.get_or_create(
            doctor=doc,
            attendance_date=date.today(),
            defaults={
                "health_center": doc.health_center,
                "check_in_time": timezone.now(),
                "nurse_present": True,
                "hygiene_maintained": True,
                "patients_visited_today": random.randint(5, 20)
            }
        )

    # -----------------------------
    # NURSE ATTENDANCE
    # -----------------------------
    for nurse in nurses:
        NurseAttendance.objects.get_or_create(
            nurse=nurse,
            attendance_date=date.today(),
            defaults={
                "health_center": nurse.health_center,
                "check_in_time": timezone.now(),
                "geo_verified": True
            }
        )

    # -----------------------------
    # MEDICINES
    # -----------------------------
    medicines = []
    for i in range(1, 6):
        med, _ = Medicine.objects.get_or_create(
            medicine_name=f"Medicine {i}",
            defaults={
                "medicine_code": f"MED00{i}",
                "min_stock_level": 5
            }
        )
        medicines.append(med)

    # -----------------------------
    # STOCK
    # -----------------------------
    for hc in centers:
        for med in medicines:
            HealthCenterMedicineStock.objects.get_or_create(
                health_center=hc,
                medicine=med,
                defaults={"current_stock_qty": random.randint(10, 50)}
            )

    # -----------------------------
    # STOCK TRANSACTIONS
    # -----------------------------
    for hc in centers:
        for med in medicines:
            MedicineStockTransaction.objects.create(
                health_center=hc,
                medicine=med,
                transaction_type=random.choice(["IN", "OUT"]),
                quantity=random.randint(1, 10)
            )

    # -----------------------------
    # PATIENT TREATMENT
    # -----------------------------
    for hc in centers:
        for i in range(3):
            treatment = PatientTreatment.objects.create(
                health_center=hc,
                nurse=random.choice(nurses),
                patient_name=f"Patient_{i}",
                age=random.randint(10, 60)
            )

            for med in medicines[:3]:
                PatientTreatmentMedicine.objects.create(
                    treatment=treatment,
                    medicine=med,
                    prescribed_qty=5,
                    issued_qty=3
                )

    # -----------------------------
    # REQUISITION
    # -----------------------------
    for hc in centers:
        req = WeeklyMedicineRequisition.objects.create(
            health_center=hc,
            nurse=random.choice(nurses),
            requisition_week_start=date.today(),
            requisition_week_end=date.today() + timedelta(days=7),
            status="SUBMITTED"
        )

        for med in medicines:
            WeeklyMedicineRequisitionDetail.objects.create(
                requisition=req,
                medicine=med,
                available_stock_qty=random.randint(1, 10),
                requested_qty=random.randint(5, 20),
                auto_low_stock_flag=random.choice([True, False])
            )

    print("🔥 ALL DATA SEEDED SUCCESSFULLY")


# Optional: if you want to also keep Django management command
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = "Seed complete dummy data for all models"

    def handle(self, *args, **kwargs):
        run()