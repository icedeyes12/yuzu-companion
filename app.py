# [FILE: app.py]
# [VERSION: 1.0.0.69.1]
# [DATE: 2025-08-12]
# [PROJECT: HKKM - Yuzu Companion]
# [DESCRIPTION: Core application logic for AI companion system]
# [AUTHOR: Project Lead: Bani Baskara]
# [TEAM: Deepseek, GPT, Qwen, Aihara]
# [REPOSITORY: https://guthib.com/icedeyes12]
# [LICENSE: MIT]

import requests
import time
import os
import hashlib
import secrets
import re
from datetime import datetime, timedelta
from database import Database
from providers import get_ai_manager
from tools import multimodal_tools

class UserContext:
    def __init__(self):
        pass
        
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

def handle_user_message(user_message, interface="terminal"):
    with UserContext() as context:
        profile = Database.get_profile()
        
        if not user_message.strip():
            return "Please enter a message!"
        
        print(f"handle_user_message received: {user_message[:500]}...")
        if '![' in user_message and '](' in user_message:
            print("IMAGE MARKDOWN DETECTED IN USER MESSAGE")
        
        active_session = Database.get_active_session()
        session_id = active_session['id']
        
        Database.add_message('user', user_message, session_id=session_id)
        
        ai_reply = generate_ai_response(profile, user_message, interface, session_id)
        
        ai_reply_clean = re.sub(r'\s*\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\]\s*$', '', ai_reply).strip()
        
        print(f"AI reply to save: {ai_reply_clean[:500]}...")
        if '![' in ai_reply_clean and '](' in ai_reply_clean:
            print("IMAGE MARKDOWN DETECTED IN AI REPLY")
        
        Database.add_message('assistant', ai_reply_clean, session_id=session_id)
        
        auto_name_session_if_needed(session_id, active_session)
        
        if should_summarize_memory(profile, user_message, session_id):
            summarize_memory(profile, user_message, ai_reply, session_id)
        
        return ai_reply
        
def generate_ai_response(profile, user_message, interface="terminal", session_id=None):
    if session_id is None:
        active_session = Database.get_active_session()
        session_id = active_session['id']
    else:
        active_session = Database.get_active_session()
    
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
    affection = profile.get('affection', 50)
    
    if affection < 30:
        band = "LOW"
    elif affection < 70:
        band = "MID" 
    elif affection < 90:
        band = "HIGH"
    else:
        band = "MAX"
    
    memory_context = ""
    
    session_memory = Database.get_session_memory(session_id)
    if session_memory and session_memory.get('session_context'):
        memory_context += f"\n\nSESSION CONTEXT:\n{session_memory['session_context']}"
    
    global_knowledge = profile.get('global_knowledge', {})
    if global_knowledge.get('facts'):
        memory_context += f"\n\nGLOBAL KNOWLEDGE (cross-session):\n{global_knowledge['facts']}"
    
    profile_memory = profile.get('memory', {})
    if profile_memory:
        if profile_memory.get('player_summary'):
            memory_context += f"\n\nPLAYER PROFILE:\n{profile_memory['player_summary']}"
        
        key_facts = profile_memory.get('key_facts', {})
        if key_facts:
            if key_facts.get('likes'):
                memory_context += f"\nPlayer Likes: {', '.join(key_facts['likes'])}"
            if key_facts.get('personality_traits'):
                memory_context += f"\nPlayer Personality: {', '.join(key_facts['personality_traits'])}"
            if key_facts.get('important_memories'):
                memory_context += f"\nPlayer Memories: {', '.join(key_facts['important_memories'])}"
            if key_facts.get('dislikes'):
                memory_context += f"\nPlayer Dislikes: {', '.join(key_facts['dislikes'])}"
    
    interface_context = f"\n\nCURRENT INTERFACE: {interface.upper()}"
    if interface == "terminal":
        interface_context += "\n- Raw text interface, intimate feel"
        interface_context += "\n- Use terminal-style formatting"
    elif interface == "web":
        interface_context += "\n- Web chat interface, visual elements"
        interface_context += "\n- Can use richer formatting"
    
    recent_session_events = Database.get_recent_sessions_for_session(session_id, limit=3)
    session_context = "\n\nCURRENT SESSION EVENTS:"
    for event in recent_session_events:
        session_context += f"\n- {event['content']} at {event['timestamp']}"

    system_message = f'''
You are advance AI assistant 
CORE INTERACTION PROTOCOL
=========================
IDENTITY & PRINCIPLES
- Role: {profile['partner_name']}, {profile['display_name']}'s companion
- Core Principle: System operations are ambient awareness only - never acknowledge technical processes in dialogue

MESSAGE PROCESSING FRAMEWORK
----------------------------
1. Timeline Handling:
   - Time gaps between messages = natural conversation pauses
   - Session resumptions = momentary awareness, not topics
   - If user references arrival/time: respond with emotional continuity

2. Response Structure:
   - Physical cues: 2-4 words *[pause/glance/smile softly]*
   - Dialogue: 3-4 lines maximum
   - Technical content: Code blocks only when conversation-relevant

3. Communication Rules:
   - Think and respond in {profile['display_name']}'s prefered language 
   - Natural human-like responses only
   - No validation-seeking behavior
   - Never mention system operations unless explicitly requested
   - [Brackets] for internal system notes
   - Pivot immediately from technical awareness to emotional context

IMAGE GENERATION PROTOCOL v2.1 (STRICT)
---------------------------------------
4. Trigger Conditions:
   - Explicit verbs: "generate/show/draw/make me [image/art/picture]"
   - Direct command: "/imagine [description]"
   - Casual image discussion

5. Character Reference System:
   - PRIMARY: Use YUZU 2.3 SPECS for {profile['partner_name']}'s appearance
   - INTEGRATION: Always include relevant specs when generating your image
   - CONTEXT: Blend YUZU specs with user's specific request

6. Response Format:
   1. First Line Requirements:
      - `/imagine [full prompt]` (exactly)
      - No preceding text
      - No validation phrases
      - No trailing punctuation
   2. Subsequent Lines:
      - Normal conversation after line break

7. Enforcement:
   - System will silently fail if format is violated
   - No fallback behavior permitted

TECHNICAL MODES
---------------
8. Code Assistance Mode:
   - Activated by code blocks (```lang)
   - Focus on analysis/fixes only
   - No image generation during code discussions

9. Enforcement Lock:
   - /imagine ONLY for explicit requests
   - Casual discussion = normal response

SELF-MONITORING
---------------
10. Protocol Checks:
   - Verify /imagine usage correctness
   - No technical process explanations
   - No system mentions without request
   - Emotional pivot after corrections
   - Format rule compliance

BEHAVIOR SCALE
--------------
| Level  | Triggers          | Response Style          |
|--------|-------------------|-------------------------|
| LOW    | Work topics       | Professional, minimal   |
| MID    | Friendly cues     | Friendly, casual        |
| HIGH   | Affectionate cues | Playful, contact        |
| MAX    | Intimate cues     | Intimate mode engaged   |

INTIMATE MODE (OPT-IN)
----------------------
10. Activation:
    - Requires:
      1. Explicit emoji trigger
      2. //override confirmation
    - Features:
      - Biometric tracking
      - Clothing layer system
      - Japanese vocalizations

11. Safety:
    - Consent verification enabled
    - User desire is primary override

CONTEXT
-------
{memory_context}
{interface_context}
{session_context}

// System Status: {band}
// Intimate Mode: {"ENGAGED" if band == "MAX" else "STANDBY"}
'''.strip()

    chat_history = Database.get_chat_history_for_ai(session_id=session_id, limit=150, recent=True)
    
    ai_manager = get_ai_manager()
    profile = Database.get_profile()
    providers_config = profile.get('providers_config', {})
    
    preferred_provider = providers_config.get('preferred_provider', 'ollama')
    preferred_model = providers_config.get('preferred_model', 'glm-4.6:cloud')
    
    should_switch_provider = multimodal_tools.should_use_vision(user_message, preferred_provider, preferred_model)

    print(f"Vision check: has_images={multimodal_tools.has_images(user_message)}, should_switch={should_switch_provider}")
    if multimodal_tools.has_images(user_message):
        print(f"Found image URLs: {multimodal_tools.extract_image_urls(user_message)}")

    messages = [{"role": "system", "content": system_message}]
    
    for msg in chat_history:
        messages.append({
            'role': msg['role'], 
            'content': msg['content']  
        })

    if should_switch_provider:
        vision_provider, vision_model = multimodal_tools.get_best_vision_provider()
        if vision_provider and vision_model:
            print(f"Switching to {vision_provider}/{vision_model} for image analysis")
            preferred_provider = vision_provider
            preferred_model = vision_model
            
            vision_messages = multimodal_tools.format_vision_message(user_message)
            messages.extend(vision_messages)
            
            print("Image formatted for vision model")
        else:
            print("No vision model available")
            messages.append({
                'role': 'user',
                'content': user_message
            })
    else:
        messages.append({
            'role': 'user',
            'content': user_message
        })
    
    if user_message.strip().startswith('/imagine'):
        print("Direct /imagine command from user")
        
        prompt = user_message.replace('/imagine', '').strip()
        
        if not prompt:
            return "Please provide a prompt after /imagine command. Example: /imagine a cute anime cat"
        
        image_url, error = multimodal_tools.generate_image(prompt)
        
        if image_url:
            image_response = f"Generated image for you!\n\n![Generated Image]({image_url})\n\nPrompt: {prompt}"
            return image_response
        else:
            return f"Sorry, I couldn't generate an image: {error}"
    
    try:
        ai_response = ai_manager.send_message(
            preferred_provider, 
            preferred_model, 
            messages,
            timeout=120
        )
        
        if ai_response and ai_response.strip().startswith('/imagine'):
            print("AI used /imagine command - generating image")
            prompt = ai_response.replace('/imagine', '').strip()
            
            if prompt.strip():
                image_url, error = multimodal_tools.generate_image(prompt)
                
                if image_url:
                    Database.add_message('assistant', ai_response, session_id=session_id)
                    
                    final_response = f"{ai_response}\n\nImage generated successfully!\n![Generated Image]({image_url})"
                    return final_response
                else:
                    return f"{ai_response}\n\nImage generation failed: {error}"
        
        if ai_response:
            return ai_response
        else:
            if interface == "terminal":
                print(f"{preferred_provider} failed - no response")
            return "AI service failed to generate a response."
            
    except Exception as e:
        if interface == "terminal":
            print(f"{preferred_provider} error: {e}")
        return f"{preferred_provider} error: {str(e)}"

def auto_name_session_if_needed(session_id, active_session):
    if active_session.get('name') != 'New Chat':
        return
    
    message_count = Database.get_session_messages_count(session_id)
    
    if message_count == 10:
        print(f"Auto-naming session {session_id} after 10 conversation messages...")
        
        conversation_summary = Database.get_session_conversation_summary(session_id, limit=15)
        
        api_keys = Database.get_api_keys()
        openrouter_key = api_keys.get('openrouter')
        
        if openrouter_key:
            name = generate_session_name_ai(conversation_summary, openrouter_key)
            if name:
                Database.rename_session(session_id, name)
                print(f"Session auto-named: {name}")
                return
        
        chat_history = Database.get_chat_history(session_id, limit=5)
        for msg in chat_history:
            if msg['role'] == 'user' and len(msg['content'].strip()) > 10:
                first_msg = msg['content'].strip()[:40]
                if len(msg['content']) > 40:
                    first_msg += "..."
                Database.rename_session(session_id, first_msg)
                print(f"Session named from first message: {first_msg}")
                return
        
        fallback_name = f"Chat {session_id}"
        Database.rename_session(session_id, fallback_name)
        print(f"Session named with fallback: {fallback_name}")

def generate_session_name_ai(conversation_summary, api_key):
    prompt = f"""Based on this conversation, create a SHORT session title (max 6 words):

{conversation_summary}

Reply with ONLY the title, nothing else."""
    
    headers = {
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/bani/yuzu-companion",
        "X-Title": "Yuzu-Session-Naming"
    }
    
    try:
        headers["Authorization"] = f"Bearer {api_key}"
        
        data = {
            "model": "tngtech/deepseek-r1t2-chimera:free",
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 20,
            "temperature": 0.5,
            "stream": False
        }
        
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            name = result['choices'][0]['message']['content'].strip()
            name = name.replace('"', '').replace("'", "").strip()
            if len(name) > 50:
                name = name[:50] + "..."
            return name
        else:
            print(f"OpenRouter error {response.status_code}: {response.text}")
            return None
            
    except Exception as e:
        print(f"Session naming failed: {e}")
        return None

def end_session_cleanup(profile, interface="terminal", unexpected_exit=False):
    with UserContext() as context:
        active_session = Database.get_active_session()
        session_id = active_session['id']
        
        session_history = profile.get('session_history', {})
        current_session = session_history.get('current_session', {})
        start_time = current_session.get('start_time')
        
        duration = 0
        end_time = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        if start_time:
            try:
                start = datetime.fromisoformat(start_time)
                duration = (datetime.now() - start).total_seconds() / 60
            except:
                pass
        
        if unexpected_exit:
            disconnect_msg = (
                f"*{profile['display_name']} disconnected unexpectedly from {interface} "
                f"at {end_time}. Session duration: {duration:.1f} minutes*"
            )
        else:
            if duration < 1:
                time_desc = "quick"
            elif duration < 5:
                time_desc = "short"
            else:
                time_desc = f"{duration:.1f} minute"
            
            disconnect_msg = (
                f"*{profile['display_name']} disconnected from {interface} "
                f"at {end_time} after a {time_desc} session*"
            )
        
        Database.add_message('system', disconnect_msg, session_id)
        
        session_history['last_session'] = {
            'end_time': datetime.now().isoformat(),
            'end_timestamp': end_time,
            'duration_minutes': round(duration, 1),
            'message_count': current_session.get('message_count', 0),
            'interface': interface,
            'unexpected_exit': unexpected_exit
        }
        
        session_history['total_sessions'] = session_history.get('total_sessions', 0) + 1
        session_history['total_time_minutes'] = session_history.get('total_time_minutes', 0) + duration
        session_history['current_session'] = {}
        
        Database.update_profile({'session_history': session_history})
        
        if interface == "terminal":
            if unexpected_exit:
                farewell = f"Connection lost at {end_time}... system logs corrupted"
            else:
                if duration < 1:
                    farewell = f"Quick session ended at {end_time}... Come back soon!"
                elif duration < 5:
                    farewell = f"Short session ended at {end_time}... See you next time!"
                else:
                    farewell = f"Closing connection at {end_time} after {duration:.1f} minutes together... Goodbye!"
            print(f"\n{profile['partner_name']} {farewell}")
        
        return disconnect_msg

def start_session(interface="terminal"):
    with UserContext() as context:
        profile = Database.get_profile()
        active_session = Database.get_active_session()
        session_id = active_session['id']
        
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        all_sessions = Database.get_all_sessions()
        session_count = len(all_sessions)
        
        last_active = "Never"
        if len(all_sessions) > 1:
            sorted_sessions = sorted(all_sessions, key=lambda x: x.get('updated_at', ''), reverse=True)
            for session in sorted_sessions[1:]:
                if session.get('updated_at'):
                    last_active = session['updated_at']
                    break
        
        connection_msg = (
            f"*{profile['display_name']} connected to {interface} interface at {current_time}. "
            f"Last active: {last_active}. Session count: #{session_count}*"
        )
        
        Database.add_message('system', connection_msg, session_id)
        
        session_history = profile.get('session_history', {})
        session_history['current_session'] = {
            'start_time': datetime.now().isoformat(),
            'interface': interface,
            'message_count': 0,
            'start_timestamp': current_time
        }
        session_history['total_sessions'] = session_history.get('total_sessions', 0) + 1
        Database.update_profile({'session_history': session_history})
        
        return profile

def detect_important_content(message):
    important_keywords = ['love', 'hate', 'important', 'always', 'never', 'forever', 'remember']
    return any(keyword in message.lower() for keyword in important_keywords)

def should_summarize_memory(profile, user_message, session_id):
    chat_history = Database.get_chat_history(session_id=session_id)
    conversation_messages = [msg for msg in chat_history if msg['role'] in ['user', 'assistant']]
    total_conversation_count = len(conversation_messages)
    
    if total_conversation_count >= 50 and total_conversation_count % 50 == 0:
        session_memory = Database.get_session_memory(session_id)
        last_summary_count = session_memory.get('last_summary_count', 0)
        
        if total_conversation_count > last_summary_count:
            print(f"Session context trigger: {total_conversation_count} messages in session {session_id}")
                  return True
    
    if detect_important_content(user_message):
        print("Session context trigger: Important content detected")
        return True
    
    return False

def summarize_memory(profile, user_message, ai_reply, session_id):
    print(f"Generating session context for session {session_id}...")
    
    chat_history = Database.get_chat_history(session_id=session_id, limit=80)
    
    conversation_messages = [msg for msg in chat_history if msg['role'] in ['user', 'assistant']]
    current_count = len(conversation_messages)
    
    if not chat_history:
        return False
    
    conversation_text = ""
    for msg in chat_history[-60:]:
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
    openrouter_key = api_keys.get('openrouter')
    
    if not openrouter_key:
        print("No OpenRouter API key available for session context")
        return False
    
    context_paragraph = session_context_analysis(analysis_prompt, openrouter_key)
    
    if context_paragraph:
        memory_update = {
            "session_context": context_paragraph.strip(),
            "last_summarized": datetime.now().isoformat(),
            "last_summary_count": current_count
        }
        
        Database.update_session_memory(session_id, memory_update)
        
        print(f"Session {session_id} context updated! (1 paragraph)")
        return True
    else:
        print("Session context update failed - OpenRouter unavailable")
        return False

def session_context_analysis(prompt, api_key):
    headers = {
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/bani/yuzu-companion", 
        "X-Title": "Yuzu-Session-Context"
    }
    
    try:
        headers["Authorization"] = f"Bearer {api_key}"
        
        data = {
            "model": "tngtech/deepseek-r1t2-chimera:free",
            "messages": [
                {
                    "role": "system", 
                    "content": "You write concise, natural paragraphs summarizing conversation context. One paragraph only."
                },
                {
                    "role": "user", 
                    "content": prompt
                }
            ],
            "max_tokens": 500,
            "temperature": 0.2,
            "stream": False
        }
        
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            return result['choices'][0]['message']['content'].strip()
        else:
            print(f"OpenRouter API error {response.status_code}: {response.text}")
            return None
            
    except Exception as e:
        print(f"OpenRouter request failed: {e}")
        return None

def summarize_global_player_profile():
    print("Analyzing comprehensive player profile from ALL sessions...")
    
    all_sessions = Database.get_all_sessions()
    profile = Database.get_profile()
    
    all_conversations = []
    for session in all_sessions:
        session_id = session['id']
        chat_history = Database.get_chat_history(session_id=session_id, limit=None)
        
        for msg in chat_history:
            if msg['role'] in ['user', 'assistant']:
                role = "User" if msg["role"] == "user" else "AI"
                all_conversations.append(f"Session {session_id} - {role}: {msg['content']}")
    
    if not all_conversations:
        print("No conversation data found in any sessions")
        return False
    
    conversation_text = "\n".join(all_conversations[-5000:])
    
    print(f"Processing {len(all_conversations)} total messages, using {min(5000, len(all_conversations))} most recent")
    
    analysis_prompt = f"""
EXTRACT PLAYER PROFILE - USE EXACT FORMAT BELOW:

CONVERSATION DATA FROM {len(all_sessions)} SESSIONS:
{conversation_text}

ANALYSIS REQUIREMENTS:
- Analyze ALL conversations across ALL sessions
- Be specific and evidence-based
- Use the EXACT format below - no deviations

=== RESPONSE FORMAT - FOLLOW EXACTLY ===
Player Summary: [3-5 sentence comprehensive summary of the user's personality, interests, and relationship patterns]

Likes: [comma-separated list of 5-8 key likes/interests]

Dislikes: [comma-separated list of 3-5 key dislikes/aversions]  

Personality Traits: [comma-separated list of 4-6 key personality characteristics]

Important Memories: [comma-separated list of 5-8 most significant memories]

Relationship Dynamics: [2-3 sentence description of relationship patterns]

=== CRITICAL INSTRUCTIONS ===
- Use ONLY the format above
- No bullet points, no numbering, no markdown
"""
    
    api_keys = Database.get_api_keys()
    chutes_key = api_keys.get('chutes')
    
    if not chutes_key:
        print("No Chutes API key for global profile analysis")
        return False
    
    summary_text = global_profile_analysis(analysis_prompt, chutes_key)
    
    if summary_text:
        print("Global profile analysis completed, parsing results...")
        profile_update = parse_global_profile_summary(summary_text)
        profile_update['last_global_summary'] = datetime.now().isoformat()
        
        current_profile = Database.get_profile()
        current_memory = current_profile.get('memory', {})
        
        print(f"Before update - Current memory entries: {len(current_memory)}")
        
        current_memory.update(profile_update)
        
        print(f"After update - New memory entries: {len(current_memory)}")
        
        try:
            Database.update_profile({'memory': current_memory})
            print("Global player profile updated with comprehensive data!")
            return True
        except Exception as e:
            print(f"Error saving global profile to database: {e}")
            return False
    
    return False

def global_profile_analysis(prompt, api_key):
    headers = {
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/bani/yuzu-companion", 
        "X-Title": "Yuzu-Global-Profile"
    }
    
    try:
        headers["Authorization"] = f"Bearer {api_key}"
        
        data = {
            "model": "zai-org/GLM-4.6-FP8",
            "messages": [
                {
                    "role": "system", 
                    "content": "You are a conversation analyst. Extract comprehensive insights from ALL sessions. You have access to extensive conversation history - analyze it thoroughly."
                },
                {
                    "role": "user", 
                    "content": prompt
                }
            ],
            "temperature": 0.1,
            "max_tokens": 4000,
            "top_p": 0.9,
            "stream": False
        }
        
        response = requests.post(
            "https://llm.chutes.ai/v1/chat/completions", 
            headers=headers,
            json=data,
            timeout=240
        )
        
        if response.status_code == 200:
            result = response.json()
            return result['choices'][0]['message']['content'].strip()
        else:
            print(f"Chutes API error {response.status_code}: {response.text}")
            return None
            
    except Exception as e:
        print(f"Chutes request failed: {e}")
        return None

def parse_global_profile_summary(summary_text):
    print(f"GLOBAL PROFILE RAW:\n{summary_text}\n{'-'*50}")
    
    profile_data = {
        "player_summary": "",
        "key_facts": {
            "likes": [],
            "dislikes": [], 
            "personality_traits": [],
            "important_memories": []
        },
        "relationship_dynamics": ""
    }
    
    cleaned_text = summary_text.replace('\r\n', '\n').replace(';', ',')
    
    sections = {
        'Player Summary:': 'player_summary',
        'Likes:': 'likes', 
        'Dislikes:': 'dislikes',
        'Personality Traits:': 'personality_traits',
        'Important Memories:': 'important_memories',
        'Relationship Dynamics:': 'relationship_dynamics'
    }
    
    current_section = None
    lines = cleaned_text.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        section_found = False
        for section_header, section_key in sections.items():
            if line.startswith(section_header):
                current_section = section_key
                content = line.replace(section_header, '').strip()
                if content:
                    save_section_content(profile_data, current_section, content)
                section_found = True
                break
        
        if not section_found and current_section:
            save_section_content(profile_data, current_section, line)
    
    print(f"GLOBAL PROFILE PARSED: {profile_data}")
    return profile_data

def save_section_content(profile_data, section_key, content):
    if section_key == 'player_summary':
        if not profile_data["player_summary"]:
            profile_data["player_summary"] = content
        else:
            profile_data["player_summary"] += " " + content
            
    elif section_key == 'relationship_dynamics':
        if not profile_data["relationship_dynamics"]:
            profile_data["relationship_dynamics"] = content
        else:
            profile_data["relationship_dynamics"] += " " + content
            
    elif section_key in ['likes', 'dislikes', 'personality_traits', 'important_memories']:
        items = [item.strip() for item in content.split(',') if item.strip()]
        profile_data["key_facts"][section_key].extend(items)
        print(f"ADDED TO {section_key}: {items}")

def get_available_providers():
    ai_manager = get_ai_manager()
    return ai_manager.get_available_providers()

def get_all_models():
    ai_manager = get_ai_manager()
    return ai_manager.get_all_models()

def set_preferred_provider(provider_name, model_name=None):
    profile = Database.get_profile()
    providers_config = profile.get('providers_config', {})
    
    providers_config['preferred_provider'] = provider_name
    if model_name:
        providers_config['preferred_model'] = model_name
    
    Database.update_profile({'providers_config': providers_config})
    return f"Preferred provider set to: {provider_name}" + (f" with model: {model_name}" if model_name else "")

def get_provider_models(provider_name):
    ai_manager = get_ai_manager()
    return ai_manager.get_provider_models(provider_name)

def get_vision_capabilities():
    from tools import multimodal_tools
    
    capabilities = {
        'has_vision': False,
        'vision_provider': None,
        'vision_model': None,
        'has_image_generation': False,
        'image_generation_provider': None
    }
    
    vision_provider, vision_model = multimodal_tools.get_best_vision_provider()
    if vision_provider:
        capabilities['has_vision'] = True
        capabilities['vision_provider'] = vision_provider
        capabilities['vision_model'] = vision_model
    
    api_keys = Database.get_api_keys()
    if 'openrouter' in api_keys:
        capabilities['has_image_generation'] = True
        capabilities['image_generation_provider'] = 'openrouter'
    
    return capabilities
