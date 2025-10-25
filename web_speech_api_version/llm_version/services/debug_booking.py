#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime
import pytz
from booking_handler import validate_slot

# Test the exact scenario
LOCAL_TIMEZONE = pytz.timezone('Africa/Cairo')

# Simulate what happens when user says "tomorrow at 1:00 PM"
# This would be parsed by Dialogflow as something like "2025-10-24T13:00:00"
date_param = "2025-10-24T13:00:00"

print(f"Original date_param: {date_param}")

# Parse as done in app.py
appointment_dt = datetime.fromisoformat(date_param)
print(f"Parsed datetime: {appointment_dt}")
print(f"Has timezone info: {appointment_dt.tzinfo is not None}")

if not appointment_dt.tzinfo:
    appointment_dt = LOCAL_TIMEZONE.localize(appointment_dt)
    print(f"Localized datetime: {appointment_dt}")

# Convert to naive for Excel comparison (as done in app.py)
appointment_naive = appointment_dt.replace(tzinfo=None)
print(f"Naive datetime for validation: {appointment_naive}")
print(f"ISO format: {appointment_naive.isoformat()}")

# Test validation
doctor = "Dr. Smith"
result = validate_slot(doctor, appointment_naive)
print(f"Validation result: {result}")

# Let's also check what's actually in the database
import sqlite3
conn = sqlite3.connect('schedules.db')
cursor = conn.cursor()

cursor.execute("""
    SELECT DateTime, Status FROM schedules 
    WHERE LOWER(Doctor) = LOWER(?) 
    AND DateTime = ?
""", (doctor, appointment_naive))

db_result = cursor.fetchone()
print(f"Direct DB query result: {db_result}")

# Let's also try with the ISO format
cursor.execute("""
    SELECT DateTime, Status FROM schedules 
    WHERE LOWER(Doctor) = LOWER(?) 
    AND DateTime = ?
""", (doctor, appointment_naive.isoformat()))

db_result2 = cursor.fetchone()
print(f"DB query with ISO format: {db_result2}")

conn.close()