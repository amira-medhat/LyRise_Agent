import os
import uuid
import traceback
import sqlite3
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

# --- Internal Imports ---

from llm.llm_manager_OpenAI import (
    Agent, 
    generate_react_prompt, 
    known_actions, 
    action_re
)
# --- Import the session manager ---
from services.session_manager import get_session, update_session

# ----------------------------------------
# Setup
# ----------------------------------------
load_dotenv()
app = Flask(__name__)

# --- STOP: The global LLMManager is GONE. ---
# We no longer have a global 'llm' object. 
# Agents are now created per-session.
# --- END ---


# ----------------------------------------
# Routes
# ----------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/doctors", methods=["GET"])
def get_doctors():
    """
    Return all doctors and specialties from DB for the frontend.
    """
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
    Main endpoint: handles user messages using a ReAct loop.
    It manages the agent's state (history) and executes tools.
    """
    try:
        user_message = request.json["message"]
        # Get a session ID from the frontend, or create a default one
        session_id = request.json.get("session_id", "default_session")

        # === Step 1: Get or Create the Agent for this session ===
        session_data = get_session(session_id)
        if "agent" not in session_data:
            print(f"[DEBUG] Creating new agent for session: {session_id}")
            # Generate the master system prompt with tools, doctors, etc.
            system_prompt = generate_react_prompt()
            # Create a new agent instance
            agent = Agent(system=system_prompt)
            session_data["agent"] = agent
        else:
            # Retrieve the existing agent (with its conversation history)
            agent = session_data["agent"]

        # === Step 2: Run the ReAct Loop ===
        
        final_answer = "I'm sorry, I seem to have run into an issue." # Default
        next_prompt = user_message
        
        # Limit the number of turns to prevent infinite loops
        for i in range(5): 
            
            # --- Call the LLM ---
            # agent() adds user_message to history, gets LLM reply, adds reply to history
            result = agent(next_prompt) 
            print(f"[DEBUG] ReAct Turn {i+1} (Session: {session_id}):\n{result}")

            # --- Check for an Action ---
            actions = [action_re.match(a) for a in result.split('\n') if action_re.match(a)]

            if actions:
                # --- Execute Action ---
                action, action_input_json = actions[0].groups()
                
                if action not in known_actions:
                    observation = f"Error: Unknown action '{action}'. Please use one of: {list(known_actions.keys())}"
                else:
                    # --- Call the Tool ---
                    try:
                        print(f" -- Running Tool: {action}({action_input_json})")
                        # The tool wrapper (e.g., tool_check_availability) is called here
                        observation = known_actions[action](action_input_json)
                    except Exception as e:
                        print(f"[ERROR] Tool execution failed: {e}")
                        traceback.print_exc()
                        observation = f"Error running action {action}: {e}"
                
                print(f" -- Observation: {observation}")
                # Feed the observation back into the agent for the next loop
                next_prompt = f"Observation: {observation}"

            else:
                # --- No Action: This is the Final Answer ---
                # We parse the result to send *only* the answer part
                if "Answer:" in result:
                    # Split on "Answer:" and take the last part
                    final_answer = result.split("Answer:", 1)[-1].strip()
                else:
                    # Fallback if it's a simple chat reply without "Answer:"
                    final_answer = result
                
                break # Exit the loop
        
        # === Step 3: Save the agent's updated state (history) ===
        # This is technically already done since 'agent' is a mutable object
        # but update_session is good practice.
        update_session(session_id, "agent", agent)

        # === Step 4: Return the final response ===
        return jsonify({"reply": final_answer})

    except Exception as e:
        print(f"[ERROR] chat() failed: {e}")
        traceback.print_exc()
        return jsonify({"reply": "Internal error occurred, please try again."}), 500


# ----------------------------------------
# Entry Point
# ----------------------------------------
if __name__ == "__main__":
    print("Running Flask app with ReAct agent...")
    app.run(debug=True, port=5000)