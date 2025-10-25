# =====================================================
# llm_manager.py — Context-Aware LLM Conversation Engine (OpenAI version)
# =====================================================

import json
import os
from datetime import datetime, timedelta
import pytz
from services.schedule_handler import ScheduleHandler
from dateparser import parse as parse_date
from openai import OpenAI

class LLMManager:
    """
    Manages the full conversation lifecycle with:
    - initial context prompt
    - intent classification
    - reasoning through follow-ups
    - delegating to backend services (list/book/cancel)
    """

    def __init__(self, model_name="gpt-5-nano"):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = model_name
        self.conversation = []  # single conversation history
        self.active_intent = None  # current active intent
        self.LOCAL_TIMEZONE = pytz.timezone("Africa/Cairo")
        self.schedule_handler = ScheduleHandler()
        self.conversation.append(self.generate_initial_context())

    # =====================================================
    # 1️⃣ Generate Initial Context (System Prompt)
    # =====================================================
    def generate_initial_context(self):
        """
        Creates a rich system prompt that defines:
        - Current time/date
        - Role of the assistant
        - Available doctors
        - Behavior when missing info
        """
        now = datetime.now(self.LOCAL_TIMEZONE)
        current_date = now.strftime("%A, %B %d, %Y")
        current_time = now.strftime("%I:%M %p")
        print(f"[DEBUG] Generating initial context at {current_date} {current_time}")

        doctors_with_specialties = self.schedule_handler.get_doctors_with_specialties()
        print(f"[DEBUG] Available doctors: {doctors_with_specialties}")
        doctors_str = "\n".join([f"- {name} ({specialty})" for name, specialty in doctors_with_specialties.items()])

        system_prompt = f"""
You are a friendly and professional **Clinic Scheduling Agent**.
Today is {current_date}, and the time is {current_time}.
You are based in **Cairo, Egypt**.

Your main skills:
- List available slots for doctors.
- Book appointments.
- Cancel appointments.
- Handle general chat politely.

Available doctors in the clinic:
{doctors_str}

IMPORTANT: When user mentions a specialty (like "cardiologist", "dentist", "general practitioner"), you MUST map it to the actual doctor name from the list above.
For example: "cardiologist" → "Dr. Smith", "dentist" → "Dr. John", "general practitioner" → "Dr. Mark"
If a user mentions a doctor/specialty that is NOT in this list, say:
"I'm sorry, we don't have that doctor in our clinic."

CRITICAL CONTEXT MEMORY RULES:
1. ALWAYS remember information from previous messages in the conversation.
2. If user previously mentioned a doctor and now provides only a date/time, USE THE PREVIOUS DOCTOR.
3. If user previously asked about a doctor and now says "today", "tomorrow", or a time, COMBINE THEM.
4. When user says "today" - that means {current_date}.
5. When user says "tomorrow" - that means the next day after {current_date}.
6. Single-word responses like "yes", "ok", "sure", "U" mean confirmation - keep previous context.
7. If user provides time like "11 am" after discussing a doctor, link them together.
8. Don't ask for additional info from the user like his name or email.

Intent Classification:
For "list" (checking availability):
- Is Dr. [Name] available?
- Show me slots for Dr. [Name]
- What's the schedule?
- Can you list available times?

For "book" (making appointment):
- I need to book an appointment
- Book with Dr. [Name]
- Schedule an appointment
- I want to make an appointment
- Yes, book it / Please book it

For "cancel" (canceling appointment):
- Can I cancel an appointment?
- Cancel my appointment with Dr. [Name]
- I want to cancel

Everything else → "chat".

Behavior Guidelines:
- If user asks about clinic info (doctors, today's date), answer directly and briefly.
- If completely off-topic, politely redirect to scheduling.
- NEVER ask for information the user already provided in previous messages.
- If date/time is missing AND not mentioned before, ask naturally.
- If doctor is missing AND not mentioned before, ask naturally.
- BEFORE booking or canceling, ALWAYS confirm details with user and wait for confirmation.
- Don't create fictional information.
- Keep responses warm, short, and natural (1-2 sentences).
"""
        context_msg = {"role": "system", "content": system_prompt}
        print(f"[DEBUG] Initial context message created (length: {len(system_prompt)} chars)")
        return context_msg

    # =====================================================
    # 🔹 Token Utility Helpers
    # =====================================================
    def estimate_tokens(self, text):
        """Approximate token count (1.3× words)."""
        return int(len(text.split()) * 1.3)

    def trim_history(self, history, max_tokens=3500):
        """
        Keeps conversation history within reasonable token limits.
        Retains system prompt + most recent exchanges.
        """
        if not history:
            return [self.generate_initial_context()]

        system_msg = history[0] if history[0]["role"] == "system" else self.generate_initial_context()
        rest = history[1:] if history[0]["role"] == "system" else history

        total = self.estimate_tokens(system_msg["content"])
        trimmed = []

        for msg in reversed(rest):
            content = msg.get("content", "")
            if not content:
                continue
            tokens = self.estimate_tokens(content)
            if total + tokens < max_tokens:
                trimmed.insert(0, msg)
                total += tokens
            else:
                break

        return [system_msg] + trimmed


    # =====================================================
    # 3️⃣ Process Query
    # =====================================================
    def process_query(self, query):
        """
        Handles context memory, missing info, and service mapping.
        """
        # Refresh system context with current time/doctors while keeping conversation history
        if self.conversation and self.conversation[0].get("role") == "system":
            self.conversation[0] = self.generate_initial_context()
        
        print(f"[DEBUG] History has {len(self.conversation)} messages")
        if self.conversation:
            print(f"[DEBUG] First message role: {self.conversation[0].get('role', 'unknown')}")
        self.conversation.append({"role": "user", "content": query})
        trimmed_history = self.trim_history(self.conversation)
        print(f"[DEBUG] Trimmed history to {len(trimmed_history)} messages")

        # Step 1: Ask LLM to extract structured info
        now = datetime.now(self.LOCAL_TIMEZONE)
        extraction_prompt = f"""
Analyze the ENTIRE conversation history to extract information. Look at previous messages to fill in missing details.

IMPORTANT CONTEXT RULES:
1. If the user previously mentioned a doctor, and now asks about availability/booking/canceling without specifying a doctor again, USE THE PREVIOUS DOCTOR.
2. If the user says "today", convert it to ISO format: {now.strftime("%Y-%m-%d")}T00:00:00
3. If user says just a time like "11 am" or "11:00", combine it with the date context from conversation.
4. CRITICAL: Clinic hours are 9:00 AM to 4:00 PM. When user says "1" or "1 pm" or "1 o'clock", assume PM (13:00) not AM (01:00).
5. CRITICAL: Map specialties to doctor names: "cardiologist" → "Dr. Smith", "dentist" → "Dr. John", "general practitioner" → "Dr. Mark"
6. CRITICAL: is_confirmation is true ONLY when the agent asked the user to confirm booking/canceling details and the user says "yes", "ok", "sure".
   Example: Agent asks "Just to confirm, do you want to book with Dr. Mark at 11 AM?" → User says "yes" → is_confirmation: true

Current user message: "{query}"

You MUST respond with ONLY this JSON format, nothing else:
{{
  "type": "book" or "list" or "cancel" or "chat",
  "doctor": "exact doctor name from conversation or empty string",
  "datetime": "ISO datetime string YYYY-MM-DDTHH:MM:SS or empty string",
  "is_confirmation": true or false (true if user is confirming a previous request)
}}


Examples:
- User asks "is dr mark available today" → type: "list", doctor: "Dr. Mark", datetime: "{now.strftime("%Y-%m-%d")}T00:00:00", is_confirmation: false
- User asks "when is the cardiologist available" → type: "list", doctor: "Dr. Smith", datetime: "{now.strftime("%Y-%m-%d")}T00:00:00", is_confirmation: false
- User says "can you book that appointment" after seeing "1:00 PM" slot → type: "book", doctor: "Dr. Mark", datetime: "{now.strftime("%Y-%m-%d")}T13:00:00", is_confirmation: false
- User says "book at 1 pm" → type: "book", doctor: "Dr. Mark", datetime: "{now.strftime("%Y-%m-%d")}T13:00:00", is_confirmation: false
- Agent asks "Just to confirm, book with Dr. Mark at 11 AM?" → User says "yes" → type: "book", doctor: "Dr. Mark", datetime: "{now.strftime("%Y-%m-%d")}T11:00:00", is_confirmation: true
- User says "dr mark today 11 am" for cancel → type: "cancel", doctor: "Dr. Mark", datetime: "{now.strftime("%Y-%m-%d")}T11:00:00", is_confirmation: false

Do not include any explanation, just the JSON.
"""
        try:
            print(f"[DEBUG] Conversation history for extraction: {len(trimmed_history)} messages")
            extraction_messages = trimmed_history + [{"role": "user", "content": extraction_prompt}]
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=extraction_messages
            )
            content = completion.choices[0].message.content.strip()
            print(f"[DEBUG] OpenAI extraction response: {content}")
            
            # Try to extract JSON if wrapped in markdown code blocks
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0].strip()
            elif '```' in content:
                content = content.split('```')[1].split('```')[0].strip()
            
            structured = json.loads(content)
        except Exception as e:
            print(f"[ERROR] JSON extraction failed: {e}")
            print(f"[ERROR] Raw content was: {content if 'content' in locals() else 'N/A'}")
            structured = {"type": "", "doctor": "", "datetime": ""}

        doctor = structured.get("doctor", "")
        date = structured.get("datetime", "")
        is_confirmation = structured.get("is_confirmation", False)
        print(f"[DEBUG] Extracted - Type: {structured.get('type')}, Doctor: {doctor}, DateTime: {date}, IsConfirmation: {is_confirmation}")

        if date:
            parsed = parse_date(date, settings={"TIMEZONE": "Africa/Cairo", "RETURN_AS_TIMEZONE_AWARE": False})
            if parsed:
                # Format to SQLite-compatible ISO string (no timezone)
                date = parsed.strftime("%Y-%m-%dT%H:%M:%S")
        reply = ""

        # Step 3: Handle based on intent
        if structured["type"] == "list":
            if not doctor:
                reply = "Which doctor would you like me to check availability for?"
            else:
                # Convert date string to datetime safely
                start_dt = None
                end_dt = None
                if date:
                    try:
                        start_dt = datetime.fromisoformat(date)
                        end_dt = start_dt + timedelta(days=1)
                    except Exception as e:
                        print(f"[WARN] Could not parse date in list intent: {e}")
                
                if start_dt and end_dt:
                    slots, doctor_exists = self.schedule_handler.get_available_slots(start_dt, end_dt, doctor)
                    if slots:
                        # Filter out None values for safety
                        slots = [s for s in slots if s]
                        if slots:
                            reply = f"{doctor} has available slots at {', '.join(slots)}."
                        else:
                            reply = f"Sorry, {doctor} has no valid slots at that time."
                    elif doctor_exists is False:
                        reply = f"Sorry, we don't have {doctor} in our clinic."
                    else:
                        reply = f"Sorry, {doctor} has no available slots at that time."
                else:
                    reply = "Could you clarify the date or day you'd like me to check?"


        elif structured["type"] == "book":
            if not doctor:
                reply = "Which doctor would you like to book an appointment with?"
            elif not date:
                reply = f"When would you like to see {doctor}?"
            else:
                if not is_confirmation:
                    time_str = datetime.fromisoformat(date).strftime("%I:%M %p") if date else ""
                    reply = f"Just to confirm, you'd like to book an appointment with {doctor} at {time_str}. Should I proceed?"
                # else: leave reply empty, app.py will call book_appointment and set the reply

        elif structured["type"] == "cancel":
            if not doctor:
                reply = "Which doctor's appointment would you like to cancel?"
            else:
                if not is_confirmation:
                    time_str = datetime.fromisoformat(date).strftime("%I:%M %p") if date else ""
                    reply = f"Just to confirm, you'd like to cancel your appointment with {doctor}{' at ' + time_str if time_str else ''}. Should I proceed?"
                # else: leave reply empty, app.py will call cancel_appointment_flow and set the reply

        else:
            # Chat fallback
            chat_messages = trimmed_history + [{"role": "user", "content": "Respond naturally to the user in plain text. Do NOT include any JSON in your response. Just have a friendly conversation."}]
            try:
                completion = self.client.chat.completions.create(
                    model=self.model,
                    messages=chat_messages
                )
                reply = completion.choices[0].message.content.strip()
            except Exception:
                reply = "I'm happy to help with scheduling or general questions!"

        # Step 4: Save history
        self.conversation.append({"role": "assistant", "content": reply})

        return {
            "type": structured["type"],
            "doctor": doctor,
            "datetime": date,
            "is_confirmation": is_confirmation,
            "reply": reply
        }
