import os
import django

# -----------------------------
# Setup Django environment
# -----------------------------
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "creache_app_project.settings")
django.setup()

from creches.models import CustomUser, CrecheAttendant
from healthcenter.models import Doctor, Nurse, HealthCenter

# -----------------------------
# Helper functions
# -----------------------------
def get_creches_for_user(user):
    """Return list of Creche names for a user."""
    return list(CrecheAttendant.objects.filter(user=user).values_list('creche__creche_name', flat=True))

def get_healthcenters_for_user(user):
    """Return list of HealthCenter names for a user."""
    hc_names = []
    if Doctor.objects.filter(user=user).exists():
        hc_names += list(Doctor.objects.filter(user=user).values_list('health_center__name', flat=True))
    if Nurse.objects.filter(user=user).exists():
        hc_names += list(Nurse.objects.filter(user=user).values_list('health_center__name', flat=True))
    return hc_names

# -----------------------------
# List all users
# -----------------------------
all_users = CustomUser.objects.all()

print("📌 User Assignments:\n")
for user in all_users:
    role = user.role
    username = user.username

    if role in ['super_attendant', 'attendant']:
        creches = get_creches_for_user(user)
        print(f"User: {username}, Role: {role}, Creche(s): {creches}")
    elif role in ['doctor', 'head_nurse', 'nurse']:
        hcs = get_healthcenters_for_user(user)
        print(f"User: {username}, Role: {role}, HealthCenter(s): {hcs}")
    elif role == 'superadmin':
        print(f"User: {username}, Role: {role}, Assigned Everywhere!")
    else:
        print(f"User: {username}, Role: {role}, No assignment found.")

print("\n✅ Done listing all user assignments.")