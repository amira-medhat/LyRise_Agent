import sqlite3
import os
from datetime import datetime

def get_available_slots(start_date, end_date, doctor=None):
    """
    Reads the schedule from SQLite and filters for available slots.
    Returns: (slots_list, doctor_exists) tuple
    - slots_list: list of time strings or None on error
    - doctor_exists: True if doctor found in system, False otherwise, None if no doctor specified
    """
    try:
        db_path = os.getenv('DATABASE_PATH', 'schedules.db')
        conn = sqlite3.connect(db_path, timeout=10, check_same_thread=False)

        cursor = conn.cursor()
        
        # Convert timezone-aware datetime to naive
        start_naive = start_date.replace(tzinfo=None) if start_date.tzinfo else start_date
        end_naive = end_date.replace(tzinfo=None) if end_date.tzinfo else end_date
        
        # Handle doctor filtering
        if doctor:
            doctor_clean = doctor.strip()
            
            # Check if doctor exists (case-insensitive)
            cursor.execute("SELECT DISTINCT Doctor FROM schedules WHERE LOWER(Doctor) = LOWER(?)", (doctor_clean,))
            doctor_exists = cursor.fetchone() is not None
            
            if not doctor_exists:
                conn.close()
                return [], False
            
            # Get available slots for specific doctor
            cursor.execute("""
                SELECT DateTime FROM schedules 
                WHERE LOWER(Doctor) = LOWER(?) 
                AND Status = 'Open' 
                AND DateTime >= ? 
                AND DateTime < ?
                ORDER BY DateTime
            """, (doctor_clean, start_naive, end_naive))
        else:
            # Get all available slots
            cursor.execute("""
                SELECT DateTime FROM schedules 
                WHERE Status = 'Open' 
                AND DateTime >= ? 
                AND DateTime < ?
                ORDER BY DateTime
            """, (start_naive, end_naive))
            doctor_exists = None
        
        rows = cursor.fetchall()
        conn.close()
        
        if rows:
            slots = [datetime.fromisoformat(row[0]).strftime('%I:%M %p') for row in rows]
            return slots, doctor_exists
        else:
            return [], doctor_exists

    except sqlite3.Error as e:
        print(f"ERROR in schedule_handler: {e}")
        return None, None
    except Exception as e:
        print(f"ERROR in schedule_handler: {e}")
        return None, None