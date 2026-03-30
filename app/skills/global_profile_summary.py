# FILE: app/skills/global_profile_summary.py
# DESCRIPTION: Skill helper for global profile analysis across all sessions.

import os
import requests
import traceback
from datetime import datetime
from typing import Dict, Optional

from app.database import Database
from app.skills.memory_curation import merge_profile_data as curation_merge_profile_data
from app.skills.memory_curation import parse_global_profile_summary as curation_parse_global_profile_summary

def summarize_global_player_profile():
    """Analyze ALL conversation history across ALL sessions with optimized sampling"""
    all_sessions = Database.get_all_sessions()
    Database.get_profile()
    
    # CONFIGURABLE SETTINGS
    MAX_MSGS_PER_SESSION = 2000           # Messages per session limit
    MAX_CONTEXT_CHARS = 900000           # Max characters (≈175K tokens)
    RECENT_RATIO = 0.7                   # 70% recent messages, 30% random from older
    MIN_MSG_LENGTH = 5                   # Skip very short messages
    
    print(f"[INFO] Starting global profile analysis for {len(all_sessions)} sessions")
    print(f"[CONFIG] Max {MAX_MSGS_PER_SESSION} msgs/session, {MAX_CONTEXT_CHARS:,} max chars")
    print(f"[CONFIG] Sampling: {int(RECENT_RATIO*100)}% recent, {int((1-RECENT_RATIO)*100)}% random")
    
    # Sort sessions by date (newest first for priority)
    sorted_sessions = sorted(
        all_sessions, 
        key=lambda x: x.get('created_at', ''), 
        reverse=True
    )
    
    all_conversations = []
    total_messages_processed = 0
    total_sessions_with_data = 0
    
    for session in sorted_sessions:
        session_id = session['id']
        session_name = session.get('name', f'Session {session_id}')
        
        # Get ALL messages for this session
        all_messages = Database.get_chat_history(session_id=session_id, limit=None)
        
        if not all_messages:
            continue
            
        total_sessions_with_data += 1
        
        # Filter only user/assistant messages
        filtered_messages = [
            msg for msg in all_messages 
            if msg['role'] in ['user', 'assistant'] 
            and len(msg['content'].strip()) >= MIN_MSG_LENGTH
        ]
        
        if not filtered_messages:
            continue
            
        # Select messages with 70/30 strategy
        if len(filtered_messages) <= MAX_MSGS_PER_SESSION:
            selected_messages = filtered_messages
            selection_method = "all"
        else:
            # Calculate counts
            recent_count = int(MAX_MSGS_PER_SESSION * RECENT_RATIO)
            random_count = MAX_MSGS_PER_SESSION - recent_count
            
            # Get recent messages (newest first)
            recent_messages = filtered_messages[-recent_count:]
            
            # Get random sample from older messages
            older_messages = filtered_messages[:-recent_count]
            
            if len(older_messages) > 0 and random_count > 0:
                import random
                random_sample = random.sample(
                    older_messages, 
                    min(random_count, len(older_messages))
                )
                selected_messages = recent_messages + random_sample
                selection_method = f"recent+random ({recent_count}+{len(random_sample)})"
            else:
                selected_messages = recent_messages
                selection_method = f"recent only ({len(recent_messages)})"
        
        # Process selected messages
        session_conversations = []
        for msg in selected_messages:
            role = "User" if msg["role"] == "user" else "AI"
            content = msg['content'].strip()
            
            # Clean and truncate if too long
            if len(content) > 400:
                content = content[:400] + "..."
            
            session_conversations.append(f"{role}: {content}")
            total_messages_processed += 1
        
        if session_conversations:
            # Format session header with stats
            session_header = f"\n\n=== SESSION: {session_name} ==="
            session_header += f"\n[Total: {len(filtered_messages)} msgs | Selected: {len(selected_messages)} | Method: {selection_method}]"
            
            session_text = session_header + "\n" + "\n".join(session_conversations)
            all_conversations.append(session_text)
    
    if not all_conversations:
        print("[INFO] No conversations found for analysis")
        return False
    
    # Combine all text
    conversation_text = "".join(all_conversations)
    
    # Apply character limit
    if len(conversation_text) > MAX_CONTEXT_CHARS:
        print(f"[WARNING] Conversation text too long ({len(conversation_text):,} chars), truncating to {MAX_CONTEXT_CHARS:,}")
        # Try to keep complete sessions by removing oldest sessions first
        while len(conversation_text) > MAX_CONTEXT_CHARS and len(all_conversations) > 1:
            # Remove oldest session (first in list after reverse sort)
            all_conversations.pop(0)
            conversation_text = "".join(all_conversations)
            print(f"[INFO] Removed oldest session, now {len(conversation_text):,} chars")
    
    print("[INFO] Analysis Summary:")
    print(f"  - Sessions total: {len(all_conversations)}")
    print(f"  - Messages processed: {total_messages_processed}")
    print(f"  - Data volume: {len(conversation_text):,} chars")
    print(f"  - Model utilization: ~{len(conversation_text)//4:,} tokens")
    
    # Create analysis prompt (sama seperti sebelumnya)
    analysis_prompt = f"""# PLAYER PROFILE ANALYSIS TASK

## CONVERSATION HISTORY:
Below is the complete conversation history between the User and AI across multiple sessions.

{conversation_text}

## ANALYSIS INSTRUCTIONS:
You are an expert psychologist and data analyst. Your task is to analyze the conversation history above and extract deep insights about the User.

### FOCUS AREAS:
1. **Personality Analysis**: Identify core personality traits, communication style, emotional patterns
2. **Interests & Preferences**: What does the user like/dislike? Topics they frequently discuss
3. **Behavioral Patterns**: How do they interact? Response patterns, engagement style
4. **Relationship Dynamics**: How is their relationship with the AI? Emotional tone, trust level, interaction patterns, and development over time.

### OUTPUT FORMAT REQUIREMENTS:
You MUST use this exact format. Do not add any commentary, explanations, or additional text.

Player Summary: [Provide a comprehensive summary of the user's personality, interests, and overall interaction patterns. Be specific and evidence-based.]

Likes: [Provide specific likes, interests, or positive preferences. Format as comma-separated list.]

Dislikes: [Provide specific dislikes, aversions, or negative preferences. Format as comma-separated list.]

Personality Traits: [Provide personality characteristics. Use descriptive adjectives.]

Important Memories: [List significant memories, experiences, or topics that were emotionally important or frequently mentioned.]

Relationship Dynamics: [Provide analysis of the relationship dynamics between User and AI. Include emotional tone, trust level, interaction patterns, and development over time.]

### CRITICAL RULES:
- Base EVERYTHING on evidence from the conversations
- Be specific and concrete - avoid vague statements
- No markdown formatting, no bullet points, no numbering
- Follow the EXACT format above - no additional sections"""
    
    api_keys = Database.get_api_keys()
    openrouter_key = api_keys.get('openrouter')
    
    if not openrouter_key:
        print("[ERROR] No OpenRouter API key found")
        return False
    
    print("[INFO] Sending to Server...")
    
    summary_text = global_profile_analysis(analysis_prompt)
    
    if summary_text:
        print(f"[SUCCESS] Analysis received: {len(summary_text):,} chars")
        
        # Save raw analysis for debugging
        os.makedirs("debug_logs", exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        debug_file = f"debug_logs/profile_summary_{timestamp}.txt"
        
        with open(debug_file, "w", encoding="utf-8") as f:
            f.write("=== GLOBAL PROFILE ANALYSIS ===\n")
            f.write(f"Date: {timestamp}\n")
            f.write(f"Sessions: {len(all_conversations)}\n")
            f.write(f"Messages: {total_messages_processed}\n")
            f.write(f"Chars: {len(conversation_text)}\n")
            f.write("\n=== RAW ANALYSIS ===\n")
            f.write(summary_text)
        
        print(f"[DEBUG] Raw analysis saved to: {debug_file}")
        
        # Parse and update profile
        profile_update = curation_parse_global_profile_summary(summary_text)
        profile_update['last_global_summary'] = datetime.now().isoformat()
        profile_update['sessions_analyzed'] = len(all_conversations)
        profile_update['total_messages'] = total_messages_processed
        profile_update['analysis_chars'] = len(conversation_text)
        
        # Merge with existing profile
        current_profile = Database.get_profile()
        current_memory = current_profile.get('memory', {})
        current_memory = curation_merge_profile_data(current_memory, profile_update)
        
        try:
            Database.update_profile({'memory': current_memory})
            
            # Success report
            print(f"\n{'='*50}")
            print("GLOBAL PROFILE UPDATE COMPLETE!")
            print(f"{'='*50}")
            print(f"✅ Sessions analyzed: {len(all_conversations)}")
            print(f"✅ Messages processed: {total_messages_processed}")
            print(f"✅ Data volume: {len(conversation_text):,} chars")
            print(f"✅ Player summary: {len(current_memory.get('player_summary', '')):,} chars")
            print(f"✅ Likes identified: {len(current_memory.get('key_facts', {}).get('likes', []))}")
            print(f"✅ Personality traits: {len(current_memory.get('key_facts', {}).get('personality_traits', []))}")
            print("✅ Relationship analysis saved")
            print(f"{'='*50}")
            
            return True
            
        except Exception as e:
            print(f"[ERROR] Database update failed: {str(e)}")
            traceback.print_exc()
            return False
    
    print("[ERROR] Analysis generation failed")
    return False


def global_profile_analysis(prompt: str) -> Optional[str]:
    """Analyze conversation history using qwen with optimal settings"""
    api_key = Database.get_api_key("chutes")
    headers = {
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/icedeyes12/yuzu-companion", 
        "X-Title": "Yuzu-Global-Profile",
        "Authorization": f"Bearer {api_key}"
    }
    
    try:
        
        model = "Qwen/Qwen3-Next-80B-A3B-Instruct"
        
        # Optimize for long context analysis
        data = {
            "model": model,
            "messages": [
                {
                    "role": "system", 
                    "content": """You are an expert psychologist and data analyst specializing in conversation analysis. 
                    Your task is to extract deep, meaningful insights from conversation history.
                    
                    ANALYSIS APPROACH:
                    1. Read and comprehend the ENTIRE conversation history
                    2. Identify patterns, themes, and significant moments
                    3. Extract evidence-based insights about personality, preferences, and relationship dynamics
                    4. Be specific, concrete, and thorough
                    5. Follow the output format EXACTLY as specified
                    
                    Your analysis should be comprehensive, insightful, and directly based on the conversation evidence."""
                },
                {
                    "role": "user", 
                    "content": prompt
                }
            ],
            "temperature": 0.2,  # Low temperature for consistent analysis
            "max_tokens": 4000,  
            "top_p": 0.9,
            "frequency_penalty": 0.0,
            "presence_penalty": 0.1,
            "stream": False
        }
        
        print(f"[DEBUG] Using model: {model}")
        print(f"[DEBUG] Prompt tokens estimate: ~{len(prompt) // 4}")
        print(f"[DEBUG] Max response tokens: {data['max_tokens']}")
        
        response = requests.post(
            "https://llm.chutes.ai/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=300  # 5 minute timeout for large analysis
        )
        
        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content'].strip()
            
            print(f"[SUCCESS] Analysis complete: {len(content):,} characters")
            return content
            
        else:
            error_msg = f"Chutes API error: {response.status_code}"
            
            try:
                error_data = response.json()
                error_detail = error_data.get('error', {}).get('message', 'Unknown')
                error_msg += f" - {error_detail}"
                
                print(f"[ERROR] {error_msg}")
                
                # Handle specific errors
                if "insufficient_quota" in error_detail.lower():
                    print("[ERROR] Insufficient API quota")
                    return _try_free_model(prompt, api_key)
                elif "model not found" in error_detail.lower():
                    print("[WARNING] GLM-4.7 not available, trying alternatives...")
                    return _try_alternative_models(prompt, api_key)
                    
            except Exception:
                error_msg += f" - {response.text[:200]}"
                print(f"[ERROR] {error_msg}")
            
            return None
            
    except requests.exceptions.Timeout:
        print("[ERROR] Request timeout - analysis took too long")
        return None
    except Exception as e:
        print(f"[ERROR] Analysis failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def _try_alternative_models(prompt: str, api_key: str) -> Optional[str]:
    """Try alternative models if GLM-4.7 fails"""
    alternatives = [
        ("z-ai/glm-4.6", 8000),  # GLM-4.6
        ("qwen/qwen3-235b-a22b-2507", 6000),  # Qwen 3 235B
        ("deepseek/deepseek-chat-v3.1", 6000),  # DeepSeek V3.1
        ("tngtech/deepseek-r1t2-chimera", 4000),  # Chimera
        ("google/gemini-2.0-flash-exp:free", 4000),  # Gemini Flash (free)
    ]
    
    headers = {
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/icedeyes12/yuzu-companion", 
        "X-Title": "Yuzu-Global-Profile",
        "Authorization": f"Bearer {api_key}"
    }
    
    for model in alternatives:
        print(f"[INFO] Trying alternative model: {model}")
        
        try:
            # Potong prompt secara signifikan untuk model free
            shortened_prompt = prompt[:20000] + "\n\n...[prompt truncated for lighter model]"
            actual_prompt = shortened_prompt
            
            data = {
                "model": model,
                "messages": [
                    {
                        "role": "system", 
                        "content": "You are a conversation analyst. Extract comprehensive insights from the conversation history."
                    },
                    {
                        "role": "user", 
                        "content": actual_prompt
                    }
                ],
                "temperature": 0.2,
                "max_tokens": 2000,  # Free models have lower limits
                "top_p": 0.9,
                "stream": False
            }
            
            response = requests.post(
                "https://llm.chutes.ai/v1/chat/completions",
                headers=headers,
                json=data,
                timeout=300
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content'].strip()
                print(f"[SUCCESS] Free model response: {len(content):,} chars")
                return content
                
        except Exception as e:
            print(f"[WARNING] Free model {model} error: {str(e)}")
            continue
    
    print("[ERROR] All free models failed")
    return None


def _try_free_model(prompt: str, api_key: str) -> Optional[str]:
    """Try free model if quota exhausted"""
    free_models = [
        "google/gemini-2.0-flash-exp:free",
        "deepseek/deepseek-chat-v3.1:free",
        "qwen/qwen3-235b-a22b:free",
    ]
    
    headers = {
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/icedeyes12/yuzu-companion", 
        "X-Title": "Yuzu-Global-Profile",
        "Authorization": f"Bearer {api_key}"
    }
    
    for model in free_models:
        print(f"[INFO] Trying free model: {model}")
        
        try:
            # Potong prompt secara signifikan untuk model free
            shortened_prompt = prompt[:15000] + "\n\n...[analysis limited due to free tier constraints]"
            
            data = {
                "model": model,
                "messages": [
                    {
                        "role": "system", 
                        "content": "Extract key insights from conversation history. Focus on most important patterns."
                    },
                    {
                        "role": "user", 
                        "content": shortened_prompt
                    }
                ],
                "temperature": 0.3,
                "max_tokens": 2000,  # Free models have lower limits
                "top_p": 0.9,
                "stream": False
            }
            
            response = requests.post(
                "https://llm.chutes.ai/v1/chat/completions",
                headers=headers,
                json=data,
                timeout=300
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content'].strip()
                print(f"[SUCCESS] Free model response: {len(content):,} chars")
                return content
                
        except Exception as e:
            print(f"[WARNING] Free model {model} error: {str(e)}")
            continue
    
    print("[ERROR] All free models failed")
    return None


def parse_global_profile_summary(summary_text: str) -> Dict:
    """Parse the global profile summary text into structured data"""
    profile_data = {
        "player_summary": "",
        "key_facts": {
            "likes": [],
            "dislikes": [], 
            "personality_traits": [],
            "important_memories": []
        },
        "relationship_dynamics": "",
        "last_updated": datetime.now().isoformat()
    }
    
    # Clean the text
    cleaned_text = summary_text.replace('\r\n', '\n').replace('\r', '\n')
    
    # Normalize section headers
    section_patterns = {
        'Player Summary:': 'player_summary',
        'Player Summary': 'player_summary',
        'Summary:': 'player_summary',
        'Summary': 'player_summary',
        
        'Likes:': 'likes',
        'Likes': 'likes',
        'Interests:': 'likes',
        'Interests': 'likes',
        
        'Dislikes:': 'dislikes',
        'Dislikes': 'dislikes',
        'Aversions:': 'dislikes',
        
        'Personality Traits:': 'personality_traits',
        'Personality Traits': 'personality_traits',
        'Traits:': 'personality_traits',
        'Personality:': 'personality_traits',
        
        'Important Memories:': 'important_memories',
        'Important Memories': 'important_memories',
        'Memories:': 'important_memories',
        'Key Memories:': 'important_memories',
        
        'Relationship Dynamics:': 'relationship_dynamics',
        'Relationship Dynamics': 'relationship_dynamics',
        'Relationship:': 'relationship_dynamics',
        'Dynamics:': 'relationship_dynamics'
    }
    
    lines = cleaned_text.split('\n')
    current_section = None
    buffer = []
    
    def save_current_section():
        if current_section and buffer:
            content = ' '.join(buffer).strip()
            if current_section == 'player_summary':
                profile_data["player_summary"] = content
            elif current_section == 'relationship_dynamics':
                profile_data["relationship_dynamics"] = content
            elif current_section in ['likes', 'dislikes', 'personality_traits', 'important_memories']:
                # Parse comma-separated lists
                items = [item.strip() for item in content.split(',') if item.strip()]
                profile_data["key_facts"][current_section] = items
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Check if this line starts a new section
        section_found = False
        for pattern, section_key in section_patterns.items():
            if line.startswith(pattern):
                # Save previous section
                save_current_section()
                
                # Start new section
                current_section = section_key
                buffer = []
                
                # Remove the pattern from the line
                remaining = line[len(pattern):].strip()
                if remaining:
                    buffer.append(remaining)
                
                section_found = True
                break
        
        if not section_found and current_section:
            # Continue current section
            buffer.append(line)
    
    # Save the last section
    save_current_section()
    
    # Clean up the data
    for section in ['player_summary', 'relationship_dynamics']:
        if profile_data[section]:
            # Remove any trailing punctuation
            profile_data[section] = profile_data[section].strip()
            if profile_data[section].endswith('.'):
                profile_data[section] = profile_data[section][:-1]
    
    # Clean lists
    for key in ['likes', 'dislikes', 'personality_traits', 'important_memories']:
        if profile_data["key_facts"][key]:
            # Remove duplicates and empty items
            unique_items = []
            seen = set()
            for item in profile_data["key_facts"][key]:
                if item and item not in seen:
                    seen.add(item)
                    unique_items.append(item)
            profile_data["key_facts"][key] = unique_items
    
    print(f"[DEBUG] Parsed profile: player_summary={len(profile_data['player_summary'])} chars, "
          f"likes={len(profile_data['key_facts']['likes'])}, "
          f"personality_traits={len(profile_data['key_facts']['personality_traits'])}")
    
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
        profile_data["key_facts"][section_key] = items

