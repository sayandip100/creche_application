#!/usr/bin/env python
"""
Script to fix the PatientTreatment sequence issue
Run: python fix_sequence.py
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'creache_app_project.settings')
django.setup()

from django.db import connection

try:
    cursor = connection.cursor()
    
    # Reset the sequence for PatientTreatment table
    cursor.execute("""
        SELECT setval(
            pg_get_serial_sequence('healthcenter_patienttreatment', 'id'),
            (SELECT COALESCE(MAX(id), 0) FROM healthcenter_patienttreatment) + 1
        )
    """)
    
    print("✓ Sequence reset successfully!")
    print("You can now add new patients without the duplicate key error.")
    
except Exception as e:
    print(f"✗ Error: {e}")
