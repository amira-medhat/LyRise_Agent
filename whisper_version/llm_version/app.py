import os
import uuid
import traceback
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import pytz

# --- Internal Imports ---
# from llm.llm_manager_Ollama import LLMManager        # Ollama version
from llm.llm_manager_OpenAI import LLMManager        # OpenAI version
from services.schedule_handler import ScheduleHandler
from services.booking_handler import book_appointment, validate_slot, cancel_appointment_flow
from helpers.helper_functions import parse_datetime_param, parse_date_range_param

# ----------------------------------------
# Setup
# ----------------------------------------
load_dotenv()
app = Flask(__name__)

LOCAL_TIMEZONE = pytz.timezone("Africa/Cairo")
llm = LLMManager()



# ----------------------------------------
# Routes
# ----------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/doctors", methods=["GET"])
def get_doctors():
    """Return all doctors and specialties from DB."""
    try:
        db_path = os.getenv("DATABASE_PATH", "clinic.db")
        conn = sqlite3.connect(db_path, timeout=10, check_same_thread=False)

        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("SELECT DISTINCT Doctor, Specialty FROM schedules ORDER BY Doctor")
        doctors = [{"name": row[0], "specialty": row[1]} for row in cursor.fetchall()]
        conn.close()
        return jsonify({"doctors": doctors})
    except Exception as e:
        print(f"[ERROR] get_doctors failed: {e}")
        return jsonify({"doctors": []}), 500


# ----------------------------------------
# Core Chat Endpoint
# ----------------------------------------
@app.route("/chat", methods=["POST"])
def chat():
    """
    Main endpoint: handles user messages.
    Uses LLMManager to infer context, intent, and generate replies.
    Always refreshes system context to reflect time and doctors list.
    """

    schedule_handler = ScheduleHandler()
    try:
        user_message = request.json["message"]

        # === Step 1: Let LLM handle reasoning ===
        llm_response = llm.process_query(user_message)
        print(f"[DEBUG] LLM response: {llm_response}")

        reply = llm_response.get("reply", "I'm not sure how to respond.")
        intent_type = llm_response.get("type", "chat")
        doctor = llm_response.get("doctor")
        datetime_param = llm_response.get("datetime")

        print(f"[DEBUG] Intent: {intent_type}, Doctor: {doctor}, Datetime: {datetime_param}")

        # === Step 2: Functional actions ===
        if intent_type == "list":
            print(f"[DEBUG] Processing list intent for doctor: {doctor}, datetime: {datetime_param}")

            if doctor and datetime_param:
                dt = parse_datetime_param(datetime_param)
                if dt:
                    start_dt = dt.astimezone(LOCAL_TIMEZONE).replace(hour=0, minute=0, second=0, microsecond=0)
                    end_dt = start_dt + timedelta(days=1)
                    print(f"[DEBUG] Listing slots for {doctor} from {start_dt} to {end_dt}")

                    slots, doctor_exists = schedule_handler.get_available_slots(start_dt, end_dt, doctor)
                    print(f"[DEBUG] schedule_handler returned slots={slots}, doctor_exists={doctor_exists}")

                    if slots is None:
                        reply = "I'm having trouble reading the schedule."
                    elif doctor_exists is False:
                        reply = f"I couldn't find {doctor} in our clinic records."
                    elif not slots:
                        reply = f"{doctor} has no available slots on that day."
                    else:
                        valid_slots = [s for s in slots if s]  # remove None values just in case
                        reply = f"{doctor} has these open slots: {', '.join(valid_slots)}."
                else:
                    reply = f"Could you clarify the date you'd like to check for {doctor}?"

            elif doctor and not datetime_param:
                reply = f"For which date would you like to check {doctor}'s schedule?"

            elif datetime_param and not doctor:
                reply = "Which doctor's schedule would you like to check for that date?"

            else:
                reply = "Please tell me which doctor and date you'd like to check availability for."



        elif intent_type == "book":
            print(f"[DEBUG] Processing booking for doctor: {doctor}, datetime: {datetime_param}")
            if doctor and datetime_param:
                dt = parse_datetime_param(datetime_param)
                if dt:
                    is_confirmation = llm_response.get("is_confirmation", False)
                    appointment_dt = dt.astimezone(LOCAL_TIMEZONE).replace(tzinfo=None)
                    slot_status = validate_slot(doctor, appointment_dt)
                    print(f"[DEBUG] validate_slot returned: {slot_status} for {doctor} at {appointment_dt}")
                    print(f"[DEBUG] slot_status is {slot_status} is_confirmation: {is_confirmation}")

                    if slot_status == "available":
                        if is_confirmation:
                            print(f"[DEBUG] Proceeding to book appointment for {doctor} at {appointment_dt}")
                            success, message = book_appointment(doctor, appointment_dt)
                            print(f"[DEBUG] book_appointment has been called with success {success} and message {message}")
                            reply = message if success else "Booking failed, please try again."
                        # else: reply already set by LLM (confirmation question)
                    elif slot_status == "booked":
                        reply = f"Sorry, this slot is already booked for {doctor}."
                    elif slot_status == "not_found":
                        reply = f"{doctor} doesn't have availability at that time."
                    else:
                        reply = "Something went wrong while checking availability."


        elif intent_type == "cancel":
            if doctor and datetime_param:
                dt = parse_datetime_param(datetime_param)
                if dt:
                    is_confirmation = llm_response.get("is_confirmation", False)
                    appointment_dt = dt.astimezone(LOCAL_TIMEZONE).replace(tzinfo=None)
                    if is_confirmation:
                        success, message = cancel_appointment_flow(doctor, appointment_dt)
                        reply = message if success else f"No appointment found for {doctor} at {appointment_dt.strftime('%I:%M %p')}."
                    # else: reply already set by LLM (confirmation question)


        # === Step 3: Return combined response ===
        return jsonify({"reply": reply})

    except Exception as e:
        print(f"[ERROR] chat() failed: {e}")
        traceback.print_exc()
        return jsonify({"reply": "Internal error occurred, please try again."}), 500


# ----------------------------------------
# Entry Point
# ----------------------------------------
if __name__ == "__main__":
    print(f"Running Flask app with timezone: {LOCAL_TIMEZONE.tzname(datetime.now())}")
    app.run(debug=True, port=5000)
