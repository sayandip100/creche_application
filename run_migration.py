import django
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'creache_app_project.settings')
django.setup()

from django.db import connection

cursor = connection.cursor()
columns_to_add = {
    'symptoms': 'text NULL',
    'diagnosis': 'text NULL',
    'doctor_remarks': 'text NULL',
    'followup_date': 'date NULL',
}

for col_name, col_type in columns_to_add.items():
    try:
        cursor.execute(f'ALTER TABLE healthcenter_patienttreatment ADD COLUMN {col_name} {col_type}')
        print(f'Added column: {col_name}')
    except Exception as e:
        if 'already exists' in str(e).lower():
            print(f'Column already exists: {col_name}')
        else:
            print(f'Column {col_name}: {e}')

# Also add doctor_id if not already there
try:
    cursor.execute('ALTER TABLE healthcenter_patienttreatment ADD COLUMN doctor_id integer REFERENCES healthcenter_doctor(id)')
    print('Added column: doctor_id')
except Exception as e:
    if 'already exists' in str(e).lower():
        print('Column already exists: doctor_id')
    else:
        print(f'Column doctor_id: {e}')

print('Migration complete')