import os
from google.cloud import dialogflow

def detect_intent_texts(text, session_id):
    """Returns the result of detect intent with texts as inputs."""
    project_id = os.getenv('DIALOGFLOW_PROJECT_ID')
    
    session_client = dialogflow.SessionsClient()
    session = session_client.session_path(project_id, session_id)
    
    print(f"Session path: {session}\n")

    text_input = dialogflow.TextInput(text=text, language_code="en-US")
    query_input = dialogflow.QueryInput(text=text_input)

    try:
        response = session_client.detect_intent(
            request={"session": session, "query_input": query_input}
        )
        return response.query_result
    except Exception as e:
        print(f"Error communicating with Dialogflow: {e}")
        return None