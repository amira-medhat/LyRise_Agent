# =====================================================
# llm_manager_OpenAI.py — ReAct Agent & Tool Definitions
# =====================================================

import re
import json
import os
import pytz
from datetime import datetime
from openai import OpenAI

# --- Internal Imports for Tools ---
from services.schedule_handler import ScheduleHandler
from services.booking_handler import book_appointment, cancel_appointment_flow
from helpers.helper_functions import parse_datetime_param, parse_date_range_param

# =====================================================
# 1. Agent Class 
# =====================================================

# --- Setup OpenAI client ---
try:
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    MODEL_NAME = "gpt-4o" # or "gpt-3.5-turbo"
except Exception as e:
    print(f"ERROR: OpenAI API key not set or invalid. {e}")
    client = None

class Agent:
    """
    The ReAct Agent class. Holds conversation history (self.messages)
    and executes LLM calls.
    """
    def __init__(self, system=""):
        if not client:
            raise ValueError("OpenAI client is not initialized. Check API key.")
        self.system = system
        self.messages = []
        if self.system:
            self.messages.append({"role": "system", "content": system})

    def __call__(self, message):
        """
        Adds a user message and gets the agent's next response.
        """
        self.messages.append({"role": "user", "content": message})
        result = self.execute()
        self.messages.append({"role": "assistant", "content": result})
        return result

    def execute(self):
        """
        Calls the OpenAI API with the current message history.
        """
        completion = client.chat.completions.create(
                        model=MODEL_NAME, 
                        temperature=0,
                        messages=self.messages)
        return completion.choices[0].message.content

# =====================================================
# 2. ReAct System Prompt Generation
# =====================================================

LOCAL_TIMEZONE = pytz.timezone("Africa/Cairo")
schedule_handler = ScheduleHandler()

def generate_react_prompt():
    """
    Creates the system prompt for the ReAct agent,
    including current time, doctor list, and tool definitions.
    """
    # Get current time and doctor list
    now = datetime.now(LOCAL_TIMEZONE)
    current_date = now.strftime("%A, %B %d, %Y")
    current_time = now.strftime("%I:%M %p")
    
    doctors_with_specialties = schedule_handler.get_doctors_with_specialties()
    doctors_str = "\n".join([f"- {name} ({specialty})" for name, specialty in doctors_with_specialties.items()])

    # Define the specialty to name mapping
    specialty_map = {specialty.lower(): name for name, specialty in doctors_with_specialties.items()}

    prompt = f"""
You are a friendly and professional **Clinic Scheduling Agent** in Cairo, Egypt.
You run in a loop of Thought, Action, PAUSE, Observation.
At the end of the loop you output an Answer.
Use Thought to describe your reasoning.
Use Action to run one of the actions available to you - then return PAUSE.
Observation will be the result of running those actions.

**Current Context:**
Today is: {current_date}
The current time is: {current_time}

**Available Doctors & Specialties:**
{doctors_str}

**CRITICAL RULES:**
1.  **Specialty Mapping:** You MUST map specialties to names (e.g., "cardiologist" -> "Dr. Smith").
2.  **Date/Time Reasoning:** Use the current date and time to resolve relative dates (e.g., "today", "tomorrow", "Monday").
3.  **Use JSON:** All tool inputs MUST be a valid JSON string.
4.  **Implicit Context:** Use context from the conversation. If the user mentions a doctor, remember it.
5.  **Confirmation:** ALWAYS check availability before booking. ALWAYS ask the user to confirm a slot before calling `book_slot`.

**Your available actions are:**

check_availability:
Returns a list of open time slots for a specific doctor on a specific date.
e.g. Action: check_availability: {{"doctor": "Dr. Smith", "date": "2025-11-10"}}

book_slot:
Books a specific time slot *after* it has been confirmed.
e.g. Action: book_slot: {{"doctor": "Dr. Smith", "datetime": "2025-11-10T14:00:00"}}

cancel_slot:
Cancels a specific booked slot *after* it has been confirmed.
e.g. Action: cancel_slot: {{"doctor": "Dr. Smith", "datetime": "2025-11-10T14:00:00"}}

**Example Session:**

Question: Can I see the cardiologist on Monday?
Thought: The user wants the "cardiologist", which maps to "Dr. Smith". Today is {current_date}, so "Monday" is [Reason about the date for next Monday]. I need to check availability.
Action: check_availability: {{"doctor": "Dr. Smith", "date": "YYYY-MM-DD"}}
PAUSE

Observation: Available slots for Dr. Smith on YYYY-MM-DD: 09:00 AM, 11:00 AM, 02:00 PM

Thought: Dr. Smith has three slots. I should ask the user which one they prefer.
Answer: Dr. Smith has slots available at 09:00 AM, 11:00 AM, and 02:00 PM on Monday. Which one would you like?

Question: The 11am one sounds good.
Thought: The user wants to book the 11:00 AM slot. I must confirm this before booking.
Answer: Great. Just to confirm, you'd like to book with Dr. Smith at 11:00 AM on Monday?

Question: Yes
Thought: The user confirmed. Now I can call the book_slot tool.
Action: book_slot: {{"doctor": "Dr. Smith", "datetime": "YYYY-MM-DDT11:00:00"}}
PAUSE

Observation: Appointment booked successfully! The calendar for Dr. Smith has been updated.

Thought: The booking was successful. I should inform the user.
Answer: Perfect! I've booked you with Dr. Smith for 11:00 AM on Monday.
"""
    return prompt.strip()


# =====================================================
# 3. Tool Definitions (Wrappers & known_actions)
# =====================================================

# This regex finds the action and its JSON input
action_re = re.compile(r'^Action: (\w+): (.*)$')

def tool_check_availability(params_json):
    """
    Wrapper for get_available_slots.
    Expects params_json: '{"doctor": "Dr. A", "date": "2025-11-10"}'
    """
    try:
        params = json.loads(params_json.strip())
        doctor = params.get("doctor")
        date_str = params.get("date")

        if not doctor or not date_str:
            return "Error: You must provide both 'doctor' and 'date'."

        # Use helper to parse the date
        start_dt, end_dt = parse_date_range_param(date_str)
        
        if not start_dt:
            return f"Error: Invalid date format: {date_str}. Use YYYY-MM-DD."

        slots, doctor_exists = schedule_handler.get_available_slots(start_dt, end_dt, doctor)
        
        if doctor_exists is False:
            return f"Error: Doctor '{doctor}' not found."
        if slots is None:
            return "Error: An error occurred while reading the schedule."
        if not slots:
            return f"No open slots found for {doctor} on {date_str}."
        
        return f"Available slots for {doctor} on {date_str}: {', '.join(slots)}"
        
    except json.JSONDecodeError as e:
        return f"Error: Invalid JSON format for tool. Input was: {params_json}"
    except Exception as e:
        return f"Error executing tool_check_availability: {e}"

def tool_book_slot(params_json):
    """
    Wrapper for book_appointment.
    Expects params_json: '{"doctor": "Dr. A", "datetime": "2025-11-10T14:00:00"}'
    """
    try:
        params = json.loads(params_json.strip())
        doctor = params.get("doctor")
        dt_str = params.get("datetime")
        
        if not doctor or not dt_str:
            return "Error: You must provide both 'doctor' and 'datetime'."

        appointment_dt = parse_datetime_param(dt_str) # Your helper
        if not appointment_dt:
            return f"Error: Invalid datetime format: {dt_str}. Use ISO format (YYYY-MM-DDTHH:MM:SS)."

        # book_appointment already returns (success, message)
        success, message = book_appointment(doctor, appointment_dt)
        return message # This is the perfect "Observation"
        
    except json.JSONDecodeError as e:
        return f"Error: Invalid JSON format for tool. Input was: {params_json}"
    except Exception as e:
        return f"Error executing tool_book_slot: {e}"

def tool_cancel_slot(params_json):
    """
    Wrapper for cancel_appointment_flow.
    Expects params_json: '{"doctor": "Dr. A", "datetime": "2025-11-10T14:00:00"}'
    """
    try:
        params = json.loads(params_json.strip())
        doctor = params.get("doctor")
        dt_str = params.get("datetime")

        if not doctor or not dt_str:
            return "Error: You must provide both 'doctor' and 'datetime'."
        
        appointment_dt = parse_datetime_param(dt_str)
        if not appointment_dt:
            return f"Error: Invalid datetime format: {dt_str}. Use ISO format (YYYY-MM-DDTHH:MM:SS)."

        # cancel_appointment_flow already returns (success, message)
        success, message = cancel_appointment_flow(doctor, appointment_dt)
        return message # This is the perfect "Observation"

    except json.JSONDecodeError as e:
        return f"Error: Invalid JSON format for tool. Input was: {params_json}"
    except Exception as e:
        return f"Error executing tool_cancel_slot: {e}"


# --- The master dictionary for the ReAct loop ---
known_actions = {
    "check_availability": tool_check_availability,
    "book_slot": tool_book_slot,
    "cancel_slot": tool_cancel_slot,
}