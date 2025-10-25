import os
import uuid
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone 
import pytz 
import traceback
import sqlite3

# Import our handlers
# Assuming your handlers are in a 'services' subdirectory as implied
from services.dialogflow_handler import detect_intent_texts
from services.schedule_handler import get_available_slots
from services.booking_handler import book_appointment, validate_slot, cancel_appointment_flow
from services.session_manager import get_session, update_session, clear_session
from helpers.helper_functions import parse_datetime_param, parse_date_range_param

load_dotenv()
app = Flask(__name__)

LOCAL_TIMEZONE = pytz.timezone('Africa/Cairo') 

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/doctors', methods=['GET'])
def get_doctors():
    try:
        db_path = os.getenv('DATABASE_PATH', 'clinic.db') # Changed to clinic.db
        conn = sqlite3.connect(db_path, timeout=10, check_same_thread=False)

        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT Doctor, Specialty FROM schedules ORDER BY Doctor")
        doctors = [{'name': row[0], 'specialty': row[1]} for row in cursor.fetchall()]
        conn.close()
        return jsonify({'doctors': doctors})
    except Exception as e:
        print(f"Error fetching doctors: {e}")
        return jsonify({'doctors': []}), 500


# --- THIS IS THE NEW, RESTRUCTURED CHAT FUNCTION ---
@app.route('/chat', methods=['POST'])
def chat():
    try:
        user_message = request.json['message']
        session_id = request.json.get('session_id', str(uuid.uuid4()))
        dialogflow_response = detect_intent_texts(user_message, session_id)
        
        session = get_session(session_id)
        
        if not dialogflow_response:
            return jsonify({"reply": "I'm having trouble connecting. Please try again.", "session_id": session_id})

        intent_name = dialogflow_response.intent.display_name
        agent_reply = dialogflow_response.fulfillment_text
        parameters = dialogflow_response.parameters
        
        # Get context from session
        awaiting_info = session.get('awaiting_info')
        
        # Debug logging
        print(f"\n=== CHAT DEBUG ===")
        print(f"Intent: {intent_name}")
        print(f"Parameters: {dict(parameters)}")
        print(f"Session: {session}")
        print(f"Awaiting: {awaiting_info}")
        print(f"==================\n")

        # --- 1. HANDLE FOLLOW-UP QUESTIONS FIRST ---
        # If the user provides info while we're waiting, process it
        # BUT: Don't intercept if it's a new primary intent (List Schedules, Book, Cancel)
        if awaiting_info and (parameters.get('date-time') or parameters.get('doctor')) and intent_name not in ['List Schedules', 'Book Schedule', 'Cancel Appointment']:
            date_param = parameters.get('date-time')
            doctor_param = parameters.get('doctor', '')
            if isinstance(doctor_param, str):
                doctor_param = doctor_param.strip() or None
            
            # --- Follow-up for List Schedules ---
            if awaiting_info == 'list_schedules_date' and date_param:
                doctor = session.get('schedule_doctor') # Get doctor from memory
                try:
                    start_dt, end_dt = parse_date_range_param(date_param)
                    if not start_dt or not end_dt:
                        raise ValueError("Invalid date range")
                    
                    slots, doctor_exists = get_available_slots(start_dt, end_dt, doctor)
                    
                    date_str = start_dt.strftime('%B %d') if (end_dt - start_dt).days == 1 else f"{start_dt.strftime('%B %d')} to {(end_dt - timedelta(days=1)).strftime('%B %d')}"
                    
                    if slots is None:
                        agent_reply = "I'm sorry, I'm having trouble reading the schedule file."
                    elif doctor_exists is False:
                        agent_reply = f"I'm sorry, but we don't have {doctor} in our clinic."
                    elif not slots:
                        agent_reply = f"{doctor} has no available slots on {date_str}." if doctor else f"There are no available slots on {date_str}."
                    else:
                        slots_str = ", ".join(slots)
                        agent_reply = f"{doctor} has the following open slots on {date_str}: {slots_str}." if doctor else f"The following slots are open on {date_str}: {slots_str}."
                    
                    clear_session(session_id)
                    return jsonify({"reply": agent_reply, "session_id": session_id})

                except Exception as e:
                    print(f"Date parsing error in follow-up: {e}")
                    agent_reply = "I couldn't understand that date. Please try again (e.g., 'tomorrow' or 'October 25th')."
                    return jsonify({"reply": agent_reply, "session_id": session_id})
            
            # --- Follow-up for Book (if they provide doctor and/or datetime) ---
            elif awaiting_info == 'book_schedule_datetime':
                if doctor_param:
                    update_session(session_id, 'doctor', doctor_param)
                if date_param:
                    update_session(session_id, 'datetime', date_param)
                intent_name = 'Book Schedule' # Force intent to re-run logic
            
            # --- Follow-up for Cancel (if they provide doctor and/or datetime) ---
            elif awaiting_info == 'cancel_schedule_datetime':
                if doctor_param:
                    update_session(session_id, 'cancel_doctor', doctor_param)
                if date_param:
                    update_session(session_id, 'cancel_datetime', date_param)
                intent_name = 'Cancel Appointment' # Force intent to re-run logic


        # --- 2. HANDLE PRIMARY INTENTS ---
        
        if intent_name in ['List Schedules', 'List Schedules - provide doctor', 'List Schedules - provide datetime']:
            # IMPORTANT: Clear ALL previous context when starting a new schedule inquiry
            clear_session(session_id)
            update_session(session_id, 'awaiting_info', 'list_schedules_date')

            doctor = parameters.get('doctor', '')
            if isinstance(doctor, str):
                doctor = doctor.strip() or None
            
            date_param = parameters.get('date-time')
            if date_param:
                date_param = dict(date_param) if hasattr(date_param, '__iter__') and not isinstance(date_param, str) else date_param

            # Validate doctor exists if provided
            if doctor:
                # Quick check if doctor exists in database
                db_path = os.getenv('DATABASE_PATH', 'schedules.db')
                conn = sqlite3.connect(db_path, timeout=10, check_same_thread=False)

                cursor = conn.cursor()
                cursor.execute("SELECT DISTINCT Doctor FROM schedules WHERE LOWER(Doctor) = LOWER(?)", (doctor,))
                doctor_exists = cursor.fetchone() is not None
                conn.close()
                
                if not doctor_exists:
                    agent_reply = f"I'm sorry, but we don't have {doctor} in our clinic."
                    clear_session(session_id)
                    return jsonify({"reply": agent_reply, "session_id": session_id})
                
                update_session(session_id, 'schedule_doctor', doctor)
            
            if not date_param:
                # --- ASKS FOLLOW-UP QUESTION ---
                agent_reply = "For which date would you like to check the schedule?" if not doctor else f"For which date would you like to check {doctor}'s schedule?"
                return jsonify({"reply": agent_reply, "session_id": session_id})
            
            # --- All info was provided in one shot ---
            try:
                start_dt, end_dt = parse_date_range_param(date_param)
                if not start_dt or not end_dt:
                    raise ValueError("Invalid date range")
                
                slots, doctor_exists = get_available_slots(start_dt, end_dt, doctor)
                
                date_str = start_dt.strftime('%B %d') if (end_dt - start_dt).days == 1 else f"{start_dt.strftime('%B %d')} to {(end_dt - timedelta(days=1)).strftime('%B %d')}"
                
                if slots is None:
                    agent_reply = "I'm sorry, I'm having trouble reading the schedule file."
                elif doctor_exists is False:
                    agent_reply = f"I'm sorry, but we don't have {doctor} in our clinic."
                elif not slots:
                    agent_reply = f"{doctor} has no available slots on {date_str}." if doctor else f"There are no available slots on {date_str}."
                else:
                    slots_str = ", ".join(slots)
                    agent_reply = f"{doctor} has the following open slots on {date_str}: {slots_str}." if doctor else f"The following slots are open on {date_str}: {slots_str}."
                
                clear_session(session_id)

            except (ValueError, KeyError) as e:
                print(f"Date parsing error: {e}")
                agent_reply = "I couldn't understand the date you mentioned. Please try again."
                # Don't clear session, let them try again
                return jsonify({"reply": agent_reply, "session_id": session_id})


        elif intent_name in ['Book Schedule', 'Book Schedule - provide doctor', 'Book Schedule - provide datetime']:
            
            # Extract parameters BEFORE clearing session
            doctor_param = parameters.get('doctor', '')
            if isinstance(doctor_param, str):
                doctor_param = doctor_param.strip() or None
            else:
                doctor_param = None
            
            date_param = parameters.get('date-time')
            if date_param:
                date_param = dict(date_param) if hasattr(date_param, '__iter__') and not isinstance(date_param, str) else date_param
            
            # --- FIX: Check if this is a new request or a follow-up ---
            if not session.get('booking_flow'):
                clear_session(session_id) # It's new, so clear any old contexts
            
            update_session(session_id, 'booking_flow', True) # Set/confirm booking flow
            update_session(session_id, 'awaiting_info', 'book_schedule_datetime') # Set context

            # Update session with any new info from parameters
            if doctor_param:
                update_session(session_id, 'doctor', doctor_param)
            if date_param:
                update_session(session_id, 'datetime', date_param)
            
            # Get current state from session
            doctor = session.get('doctor')
            date_param = session.get('datetime')
            
            # Check what's missing and ask
            if not doctor:
                agent_reply = "Which doctor would you like to book an appointment with?"
            elif not date_param:
                agent_reply = f"What date and time would you like to see {doctor}?"
            else:
                # All info present, attempt to book
                try:
                    appointment_dt = parse_datetime_param(date_param)
                    appointment_naive = appointment_dt.replace(tzinfo=None) # Keep for validate_slot
                    
                    slot_status = validate_slot(doctor, appointment_naive)
                    
                    print(f"Slot status for {doctor} at {appointment_naive}: {slot_status}")
                    
                    if slot_status == 'available':
                        success, message = book_appointment(doctor, appointment_naive) 
                        agent_reply = message
                        if success:
                            clear_session(session_id)
                    elif slot_status == 'booked':
                        agent_reply = f"Sorry, this slot is already booked. {doctor} is not available at {appointment_dt.strftime('%I:%M %p on %B %d')}. Please choose another time."
                        update_session(session_id, 'datetime', None) # Clear bad date
                    elif slot_status == 'error':
                        agent_reply = "An error occurred while checking the schedule. Please try again."
                        clear_session(session_id)
                    else: # 'not_found'
                        agent_reply = f"Sorry, {doctor} doesn't have a slot at {appointment_dt.strftime('%I:%M %p on %B %d')}. Please choose another time."
                        update_session(session_id, 'datetime', None)
                        
                except Exception as e:
                    print(f"Booking error: {e}")
                    traceback.print_exc()
                    agent_reply = "I couldn't understand the date and time. Please specify when you'd like the appointment (e.g., 'tomorrow at 1:00 PM')."
                    update_session(session_id, 'datetime', None)

        elif intent_name in ['Cancel Appointment', 'Cancel Appointment - provide doctor', 'Cancel Appointment - provide datetime']:

            # --- FIX: Check if this is a new request or a follow-up ---
            if not session.get('cancel_flow'):
                clear_session(session_id) # It's new, so clear any old contexts

            update_session(session_id, 'cancel_flow', True) # Set/confirm cancel flow
            update_session(session_id, 'awaiting_info', 'cancel_schedule_datetime') # Set context
            
            # Update session with any new info
            doctor = parameters.get('doctor', '')
            if isinstance(doctor, str) and doctor.strip():
                update_session(session_id, 'cancel_doctor', doctor.strip())
            
            date_param = parameters.get('date-time')
            if date_param:
                date_param = dict(date_param) if hasattr(date_param, '__iter__') and not isinstance(date_param, str) else date_param
                update_session(session_id, 'cancel_datetime', date_param)
            
            # Get current state from session
            doctor = session.get('cancel_doctor')
            date_param = session.get('cancel_datetime')
            
            if not doctor:
                agent_reply = "Which doctor's appointment would you like to cancel?"
            elif not date_param:
                agent_reply = f"What date and time is your appointment with {doctor}?"
            else:
                # All info present, attempt to cancel
                try:
                    appointment_dt = parse_datetime_param(date_param)
                    appointment_naive = appointment_dt.replace(tzinfo=None)
                    
                    print(f"Cancelling {doctor} at {appointment_naive}")
                    
                    success, message = cancel_appointment_flow(doctor, appointment_naive)
                    agent_reply = message
                    if success:
                        clear_session(session_id)
                    else:
                        update_session(session_id, 'cancel_datetime', None) # Clear bad date
                        
                except Exception as e:
                    print(f"Cancellation error: {e}")
                    traceback.print_exc()
                    agent_reply = "I couldn't understand the date and time. Please specify when your appointment is."
                    update_session(session_id, 'cancel_datetime', None)
        
        # --- 3. HANDLE FALLBACKS ---
        else:
            # Fallback if no primary intent is matched, but we still have context
            if session.get('awaiting_info') == 'list_schedules_date':
                agent_reply = "Sorry, I didn't catch that. What date were you interested in?"
            elif session.get('awaiting_info') == 'book_schedule_datetime':
                agent_reply = "Sorry, I missed that. What was the doctor or time you wanted to book?"
            elif session.get('awaiting_info') == 'cancel_schedule_datetime':
                agent_reply = "Sorry, I didn't get that. What was the doctor or time for the cancellation?"
            # If no context, use Dialogflow's default fallback
            # agent_reply is already set to dialogflow_response.fulfillment_text

    except Exception as e:
        print(f"!!! UNHANDLED ERROR IN CHAT: {e}")
        print(traceback.print_exc())
        agent_reply = "I'm sorry, I encountered an internal error. Please try again."
        session_id = request.json.get('session_id', str(uuid.uuid4())) # Ensure session_id is available
        clear_session(session_id) # Clear broken session

    return jsonify({"reply": agent_reply, "session_id": session_id})

if __name__ == '__main__':
    print(f"Running Flask app with timezone: {LOCAL_TIMEZONE.tzname(datetime.now())}")
    app.run(debug=True)


