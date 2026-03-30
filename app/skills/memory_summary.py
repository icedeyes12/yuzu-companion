# FILE: app/skills/memory_summary.py
# DESCRIPTION: Skill helper for session context summarization and episodic sync.

from datetime import datetime

from app.database import Database


def run_memory_summary(profile, user_message, ai_reply, session_id):
    chat_history = Database.get_chat_history(session_id=session_id, limit=80)

    conversation_messages = [msg for msg in chat_history if msg["role"] in ["user", "assistant"]]
    current_count = len(conversation_messages)

    if not chat_history:
        return False

    conversation_text = ""
    for msg in chat_history[-100:]:
        role = "User" if msg["role"] == "user" else "AI"
        conversation_text += f"{role}: {msg['content']}\n"

    analysis_prompt = f"""
Write ONE paragraph summarizing the current conversation context in this session.

Recent Conversation:
{conversation_text}

Current Interaction:
User: {user_message}
AI: {ai_reply}

Write one concise paragraph (3-5 sentences) summarizing what this session is about,
the current topics being discussed, and the general context. No lists, no bullet points,
just a natural paragraph.
"""

    api_keys = Database.get_api_keys()
    openrouter_key = api_keys.get("openrouter")

    if not openrouter_key:
        return False

    context_paragraph = session_context_analysis(analysis_prompt, openrouter_key)

    if context_paragraph:
        memory_update = {
            "session_context": context_paragraph.strip(),
            "last_summarized": datetime.now().isoformat(),
            "last_summary_count": current_count,
            "last_message_time": datetime.now().isoformat(),
        }

        Database.update_session_memory(session_id, memory_update)

        try:
            from app.memory.extractor import create_episodic_memory, calculate_emotional_weight

            emotional = calculate_emotional_weight(chat_history[-20:])
            importance = 0.5 + emotional * 0.3
            try:
                create_episodic_memory(
                    session_id,
                    context_paragraph.strip(),
                    emotional,
                    importance,
                    source_message_ids=[m["id"] for m in chat_history[-20:]],
                )
            except Exception as e:
                print(f"[WARNING] Sync episodic to DB failed: {e}")
        except Exception as e:
            print(f"[WARNING] Structured-DB sync skipped: {e}")

        return True

    return False


def session_context_analysis(prompt, api_key):
    import requests

    headers = {
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/icedeyes12/yuzu-companion",
        "X-Title": "Yuzu-Session-Context",
    }

    try:
        headers["Authorization"] = f"Bearer {api_key}"
        data = {
            "model": "Qwen/Qwen3-Next-80B-A3B-Instruct",
            "messages": [
                {
                    "role": "system",
                    "content": "You write concise, natural paragraphs summarizing conversation context. One paragraph only.",
                },
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 500,
            "temperature": 0.2,
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
            return result["choices"][0]["message"]["content"].strip()
        return None
    except Exception:
        return None
