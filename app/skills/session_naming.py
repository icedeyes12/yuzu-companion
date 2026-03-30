# FILE: app/skills/session_naming.py
# DESCRIPTION: Skill helper for naming a session from recent conversation context.

from app.database import Database


def run_session_naming(session_id, active_session):
    if active_session.get("name") != "New Chat":
        return None

    message_count = Database.get_session_messages_count(session_id)
    if message_count != 10:
        return None

    conversation_summary = Database.get_session_conversation_summary(session_id, limit=15)
    api_keys = Database.get_api_keys()
    openrouter_key = api_keys.get("openrouter")

    if openrouter_key:
        name = generate_session_name_ai(conversation_summary, openrouter_key)
        if name:
            Database.rename_session(session_id, name)
            return name

    chat_history = Database.get_chat_history(session_id, limit=5)
    for msg in chat_history:
        if msg["role"] == "user" and len(msg["content"].strip()) > 10:
            first_msg = msg["content"].strip()[:40]
            if len(msg["content"]) > 40:
                first_msg += "..."
            Database.rename_session(session_id, first_msg)
            return first_msg

    fallback_name = f"Chat {session_id}"
    Database.rename_session(session_id, fallback_name)
    return fallback_name


def generate_session_name_ai(conversation_summary, api_key):
    import requests

    prompt = f"""Based on this conversation, create a SHORT session title (max 6 words):

{conversation_summary}

Reply with ONLY the title, nothing else."""

    headers = {
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/icedeyes/yuzu-companion",
        "X-Title": "Yuzu-Session-Naming",
    }

    try:
        headers["Authorization"] = f"Bearer {api_key}"
        data = {
            "model": "tngtech/deepseek-r1t2-chimera:free",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 1000,
            "temperature": 3,
            "stream": False,
        }
        response = requests.post(
            "https://llm.chutes.ai/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=30,
        )

        if response.status_code == 200:
            result = response.json()
            name = result["choices"][0]["message"]["content"].strip()
            name = name.replace('"', "").replace("'", "").strip()
            if len(name) > 50:
                name = name[:50] + "..."
            return name
        return None
    except Exception:
        return None
