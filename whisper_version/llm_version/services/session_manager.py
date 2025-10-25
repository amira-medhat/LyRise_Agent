"""Manages conversation context for multi-turn booking flow."""

sessions = {}

def get_session(session_id):
    """Get or create session context."""
    if session_id not in sessions:
        sessions[session_id] = {}
    return sessions[session_id]

def update_session(session_id, key, value):
    """Update session context."""
    session = get_session(session_id)
    session[key] = value

def clear_session(session_id):
    """Clear session context."""
    if session_id in sessions:
        del sessions[session_id]
