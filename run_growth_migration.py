"""
Script to add weight_pic and height_pic columns to ChildGrowthMonitoring table.
"""
import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'creache_app_project.settings')

import django
django.setup()

from django.db import connection

with connection.cursor() as cursor:
    cursor.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'creches_childgrowthmonitoring'"
    )
    cols = cursor.fetchall()
    col_names = [c[0] for c in cols]
    print("Current columns:", col_names)
    
    if 'weight_pic' not in col_names:
        print("Adding weight_pic column...")
        cursor.execute(
            "ALTER TABLE creches_childgrowthmonitoring ADD COLUMN weight_pic varchar(100) NULL"
        )
        print("weight_pic column added")
    else:
        print("weight_pic column already exists")
        
    if 'height_pic' not in col_names:
        print("Adding height_pic column...")
        cursor.execute(
            "ALTER TABLE creches_childgrowthmonitoring ADD COLUMN height_pic varchar(100) NULL"
        )
        print("height_pic column added")
    else:
        print("height_pic column already exists")
    
    # Verify final state
    cursor.execute(
        "SELECT column_name, data_type, is_nullable "
        "FROM information_schema.columns "
        "WHERE table_name = 'creches_childgrowthmonitoring' "
        "ORDER BY ordinal_position"
    )
    cols = cursor.fetchall()
    print("\nFinal columns:")
    for c in cols:
        print(f"  {c[0]:25s} {c[1]:20s} nullable={c[2]}")

print("\nMigration completed successfully!")