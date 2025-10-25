import sqlite3
import os
from datetime import datetime

class ScheduleHandler:
    """
    Handles all database operations related to doctor schedules.
    Used by LLMManager and Flask routes to check available slots, doctors, etc.
    """

    def __init__(self, db_path=None):
        self.db_path = db_path or os.getenv("DATABASE_PATH", "schedules.db")

    # -------------------------------------------------
    # Internal utility: create DB connection
    # -------------------------------------------------
    def _connect(self):
        try:
            conn = sqlite3.connect(self.db_path)
            return conn
        except sqlite3.Error as e:
            print(f"[ERROR] Could not connect to DB: {e}")
            return None

    # -------------------------------------------------
    # Get all available doctors (used in system prompt)
    # -------------------------------------------------
    def get_all_doctors(self):
        """
        Returns a list of all distinct doctor names from the schedules table.
        Used in LLMManager.generate_initial_context().
        """
        try:
            conn = self._connect()
            if not conn:
                return []
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT Doctor FROM schedules ORDER BY Doctor")
            doctors = [row[0] for row in cursor.fetchall()]
            conn.close()
            return doctors
        except Exception as e:
            print(f"[ERROR] get_all_doctors failed: {e}")
            return []

    def get_doctors_with_specialties(self):
        """
        Returns a dict mapping doctor names to their specialties.
        """
        try:
            conn = self._connect()
            if not conn:
                return {}
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT Doctor, Specialty FROM schedules ORDER BY Doctor")
            doctors = {row[0]: row[1] for row in cursor.fetchall()}
            conn.close()
            return doctors
        except Exception as e:
            print(f"[ERROR] get_doctors_with_specialties failed: {e}")
            return {}

    # -------------------------------------------------
    # Check available slots between two datetimes
    # -------------------------------------------------
    def get_available_slots(self, start_date, end_date, doctor=None):
        """
        Reads the schedule from SQLite and filters for available slots.
        Returns: (slots_list, doctor_exists)
        - slots_list: list of time strings or None on error
        - doctor_exists: True if doctor found, False otherwise, None if unspecified
        """
        try:
            conn = self._connect()
            if not conn:
                return None, None
            cursor = conn.cursor()

            # Convert timezone-aware datetime to naive (SQLite stores naive)
            if isinstance(start_date, str):
                start_date = datetime.fromisoformat(start_date)
            if isinstance(end_date, str):
                end_date = datetime.fromisoformat(end_date)
            start_naive = start_date.replace(tzinfo=None) if start_date.tzinfo else start_date
            end_naive = end_date.replace(tzinfo=None) if end_date.tzinfo else end_date
            print(f"[DEBUG] get_available_slots from {start_naive} to {end_naive} for doctor: {doctor}")

            if doctor:
                doctor_clean = doctor.strip()
                # Check if doctor exists
                cursor.execute(
                    "SELECT DISTINCT Doctor FROM schedules WHERE LOWER(Doctor) = LOWER(?)",
                    (doctor_clean,),
                )
                doctor_exists = cursor.fetchone() is not None
                print(f"[DEBUG] Doctor exists: {doctor_exists}")

                if not doctor_exists:
                    conn.close()
                    return [], False

                # Get available slots for that doctor
                cursor.execute(
                    """
                    SELECT DateTime FROM schedules
                    WHERE LOWER(Doctor) = LOWER(?)
                    AND Status = 'Open'
                    AND DateTime >= ?
                    AND DateTime < ?
                    ORDER BY DateTime
                    """,
                    (doctor_clean, start_naive, end_naive),
                )
            else:
                # No doctor filter — list all open slots
                cursor.execute(
                    """
                    SELECT DateTime FROM schedules
                    WHERE Status = 'Open'
                    AND DateTime >= ?
                    AND DateTime < ?
                    ORDER BY DateTime
                    """,
                    (start_naive, end_naive),
                )
                doctor_exists = None

            rows = cursor.fetchall()
            print(f"[DEBUG] Query returned {len(rows)} rows")
            
            # Debug: Check what dates exist in DB for this doctor
            cursor.execute(
                "SELECT DateTime, Status FROM schedules WHERE LOWER(Doctor) = LOWER(?) ORDER BY DateTime LIMIT 5",
                (doctor_clean if doctor else '%',)
            )
            sample_rows = cursor.fetchall()
            print(f"[DEBUG] Sample DB entries for {doctor}: {sample_rows}")
            conn.close()

            if rows:
                slots = [
                    datetime.fromisoformat(row[0]).strftime("%I:%M %p")
                    for row in rows
                ]
                return slots, doctor_exists
            else:
                return [], doctor_exists

        except sqlite3.Error as e:
            print(f"[SQLite ERROR] {e}")
            return None, None
        except Exception as e:
            print(f"[ERROR] in get_available_slots: {e}")
            return None, None