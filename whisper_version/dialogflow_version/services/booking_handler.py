import pandas as pd
from datetime import datetime, timedelta
import os
import pickle
import sqlite3
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ['https://www.googleapis.com/auth/calendar']

def get_calendar_service():
    """Authenticate and return Google Calendar service."""
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('google-credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    
    return build('calendar', 'v3', credentials=creds)

def book_appointment(doctor, appointment_datetime):
    """
    Books an appointment by:
    1. Updating database to mark slot as Booked
    2. Fetching doctor's email from DB
    3. Creating Google Calendar event for the doctor
    4. SAVING the new Google Calendar Event ID to the DB
    Returns: (success, message)
    """
    try:
        db_path = os.getenv('DATABASE_PATH', 'clinic.db')
        conn = sqlite3.connect(db_path, timeout=10, check_same_thread=False)

        cursor = conn.cursor()
        
        datetime_str = appointment_datetime.isoformat()
        
        # Fetch Specialty AND the new Email column
        cursor.execute("""
            SELECT Specialty, Email FROM schedules 
            WHERE LOWER(Doctor) = LOWER(?) 
            AND DateTime = ? 
            AND Status = 'Open'
        """, (doctor, datetime_str))
        
        result = cursor.fetchone()
        if not result:
            conn.close()
            return False, "This slot is no longer available."
        
        specialty = result[0]
        doctor_email = result[1]

        if not doctor_email:
            conn.close()
            return False, f"Could not find an email address for {doctor} in the database."
        
        # --- Create calendar event FIRST to get the ID ---
        try:
            service = get_calendar_service()
            event = {
                'summary': f'Appointment with {doctor}',
                'description': f'Medical appointment with {doctor} ({specialty}). Booked by Voice Agent.',
                'start': {'dateTime': appointment_datetime.isoformat(), 'timeZone': 'Africa/Cairo'},
                'end': {'dateTime': (appointment_datetime + timedelta(hours=1)).isoformat(), 'timeZone': 'Africa/Cairo'},
                'attendees': [{'email': doctor_email}],
                'reminders': {'useDefault': False, 'overrides': [{'method': 'email', 'minutes': 24 * 60}, {'method': 'popup', 'minutes': 30}]},
            }
            
            # --- EXECUTE and GET the created event ---
            created_event = service.events().insert(calendarId='primary', body=event, sendUpdates='all').execute()
            calendar_event_id = created_event.get('id')
            
        except HttpError as cal_error:
            print(f"Calendar error: {cal_error}")
            return False, f"Failed to create calendar event: {cal_error}"
        except Exception as e:
            print(f"Calendar error (non-http): {e}")
            return False, "An unknown error occurred while creating the calendar event."

        # --- NOW, update the database with the event ID ---
        cursor.execute("""
            UPDATE schedules 
            SET Status = 'Booked', CalendarEventId = ?
            WHERE LOWER(Doctor) = LOWER(?) 
            AND DateTime = ?
        """, (calendar_event_id, doctor, datetime_str))
        
        conn.commit()
        conn.close()
        
        return True, f"Appointment booked successfully! The calendar for {doctor} has been updated."
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return False, "Failed to book appointment due to a database error."
    except Exception as e:
        print(f"Booking error: {e}")
        return False, f"Failed to book appointment. An unknown error occurred: {e}"

def cancel_appointment_flow(doctor, appointment_datetime):
    """
    Cancels an appointment by:
    1. Finding the booking in the DB
    2. Getting the CalendarEventId
    3. Deleting the event from Google Calendar
    4. Updating the DB status back to 'Open'
    Returns: (success, message)
    """
    try:
        db_path = os.getenv('DATABASE_PATH', 'clinic.db')
        conn = sqlite3.connect(db_path, timeout=10, check_same_thread=False)

        cursor = conn.cursor()
        
        datetime_str = appointment_datetime.isoformat()
        
        # Find the booked appointment and get its CalendarEventId
        cursor.execute("""
            SELECT CalendarEventId FROM schedules 
            WHERE LOWER(Doctor) = LOWER(?) 
            AND DateTime = ? 
            AND Status = 'Booked'
        """, (doctor, datetime_str))
        
        result = cursor.fetchone()
        if not result:
            conn.close()
            # Check if it was already open or just doesn't exist
            return False, "I couldn't find a booked appointment for that doctor at that specific time."
        
        calendar_event_id = result[0]
        
        # --- Delete from Google Calendar ---
        try:
            if calendar_event_id:
                service = get_calendar_service()
                service.events().delete(calendarId='primary', eventId=calendar_event_id, sendUpdates='all').execute()
            else:
                # Booking exists but has no calendar ID. This is a data sync issue, but we can still cancel it.
                print(f"Warning: No CalendarEventId found for {doctor} at {datetime_str}. Cancelling in DB only.")

        except HttpError as e:
            if e.resp.status == 404:
                # Event already deleted in calendar. That's fine.
                print("Calendar event already gone. Proceeding with DB cancellation.")
            else:
                print(f"Calendar deletion error: {e}")
                return False, "Failed to cancel the calendar event. Please try again."
        except Exception as e:
            print(f"General error during calendar deletion: {e}")
            return False, "An error occurred trying to contact the calendar service."

        # --- Update database status back to 'Open' ---
        cursor.execute("""
            UPDATE schedules 
            SET Status = 'Open', CalendarEventId = NULL 
            WHERE LOWER(Doctor) = LOWER(?) 
            AND DateTime = ?
        """, (doctor, datetime_str))
        
        conn.commit()
        conn.close()
        
        return True, f"Your appointment with {doctor} at {appointment_datetime.strftime('%I:%M %p')} has been successfully cancelled."
        
    except sqlite3.Error as e:
        print(f"Database error during cancellation: {e}")
        return False, "Failed to cancel the appointment due to a database error."
    except Exception as e:
        print(f"Cancellation error: {e}")
        return False, f"Failed to cancel the appointment. An unknown error occurred: {e}"

def validate_slot(doctor, appointment_datetime):
    """Check if a slot is available. Returns: ('available'|'booked'|'not_found'|'error')"""
    try:
        db_path = os.getenv('DATABASE_PATH', 'clinic.db')
        conn = sqlite3.connect(db_path, timeout=10, check_same_thread=False)

        cursor = conn.cursor()
        
        datetime_str = appointment_datetime.isoformat()
        
        cursor.execute("""
            SELECT Status FROM schedules 
            WHERE LOWER(Doctor) = LOWER(?) 
            AND DateTime = ?
        """, (doctor, datetime_str))
        
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            return 'not_found'
        
        status = result[0]
        if status == 'Open':
            return 'available'
        elif status == 'Booked':
            return 'booked'
        else:
            return 'not_found'
            
    except sqlite3.Error as e:
        print(f"Database error in validate_slot: {e}")
        return 'error'
    except Exception as e:
        print(f"Error in validate_slot: {e}")
        return 'error'

