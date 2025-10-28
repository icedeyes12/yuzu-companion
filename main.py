# [FILE: main.py]
# [VERSION: 1.0.0.69.1]
# [DATE: 2025-08-12]
# [PROJECT: HKKM - Yuzu Companion]
# [DESCRIPTION: Command-line interface for AI companion system]
# [AUTHOR: Project Lead: Bani Baskara]
# [TEAM: Deepseek, GPT, Qwen, Aihara]
# [REPOSITORY: https://guthib.com/icedeyes12]
# [LICENSE: MIT]

from app import handle_user_message, start_session, end_session_cleanup, summarize_memory, summarize_global_player_profile
from app import get_available_providers, get_all_models, set_preferred_provider, get_provider_models, get_vision_capabilities
from database import Database
from providers import get_ai_manager
from tools import multimodal_tools
from datetime import datetime
import threading
import webbrowser
import time
import re

def print_header(title):
    now = datetime.now().strftime("%H:%M")
    separator = "=" * 50
    print(f"\n{separator}\n{title}  |  Time: {now}\n{separator}")

def print_footer():
    print("-" * 50)
    print("2025 hkkm project | built with love")

def start_flask_server():
    from web import app
    print("Starting Flask web server...")
    app.run(debug=False, port=5000, host='0.0.0.0', use_reloader=False)

def open_browser():
    time.sleep(2)
    webbrowser.open('http://127.0.0.1:5000')

def launch_web_interface():
    print("Launching web interface...")
    
    flask_thread = threading.Thread(target=start_flask_server, daemon=True)
    flask_thread.start()
    
    open_browser()
    
    print("Web interface running at: http://127.0.0.1:5000")
    print("You can now use both terminal and web interfaces!")
    print("Press Ctrl+C in terminal to stop both interfaces")
    
    try:
        while flask_thread.is_alive():
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down web interface...")
        profile = Database.get_profile()
        end_session_cleanup(profile, interface="web", unexpected_exit=True)
        return

def chat_loop():
    profile = start_session(interface="terminal")
    active_session = Database.get_active_session()
    session_id = active_session['id']
    
    providers_config = profile.get('providers_config', {})
    current_provider = providers_config.get('preferred_provider', 'ollama')
    current_model = providers_config.get('preferred_model', 'glm-4.6:cloud')
    
    vision_capabilities = get_vision_capabilities()
    has_vision = vision_capabilities['has_vision']
    has_image_gen = vision_capabilities['has_image_generation']
    
    streaming = False
    system_prompt = None
    
    print_header(f"Talking with {profile['partner_name']} (Terminal)")
    print(f"Session: {active_session.get('name')} | Messages: {active_session.get('message_count', 0)}")
    print(f"AI Provider: {current_provider}/{current_model}")
    
    if has_vision or has_image_gen:
        print("Multimodal: ", end="")
        if has_vision:
            print("Vision", end="")
        if has_vision and has_image_gen:
            print(" + ", end="")
        if has_image_gen:
            print("Images", end="")
        print()
    
    print("\nType your message or use commands:")
    print("  /help, /?      - Show all commands")
    print("  /exit, /quit   - End chat session")
    print("\nMulti-line input: Type '...' on empty line to send")
    print("Cancel message: Ctrl+C")
    if has_vision:
        print("Include image URLs for automatic analysis")
    if has_image_gen:
        print("Use /imagine to generate images")
    print("-" * 50)
    
    try:
        while True:
            print(f"{profile['display_name']} > ", end="", flush=True)
            lines = []
            message_started = False
            
            while True:
                try:
                    line = input()
                    
                    if line.strip().startswith('/'):
                        cmd_line = line.strip()
                        break
                    
                    if line.strip() == "...":
                        break
                    
                    lines.append(line)
                    message_started = True
                    
                except KeyboardInterrupt:
                    if message_started or lines:
                        print("\nMessage cancelled.")
                        lines = []
                        message_started = False
                        break
                    else:
                        raise KeyboardInterrupt
                    
            if line.strip().startswith('/'):
                cmd_parts = line.strip().split()
                cmd = cmd_parts[0].lower()
                args = cmd_parts[1:] if len(cmd_parts) > 1 else []
                
                if cmd in ['/exit', '/quit', '/bye']:
                    print(f"\n{profile['partner_name']} > Ending terminal session...")
                    end_session_cleanup(profile, interface="terminal", unexpected_exit=False)
                    return
                
                elif cmd in ['/help', '/?']:
                    print("""
AVAILABLE COMMANDS:

BASIC:
  /help, /?      - Show this help message
  /exit, /quit   - End chat session

CHAT CONTROL:
  /model         - Switch AI provider/model
  /models        - List available models
  /providers     - List available AI providers  
  /system        - Set system prompt
  /stream        - Toggle streaming mode
  /info          - Show current status

MULTIMODAL:
  /vision        - Switch to vision model for image analysis
  /imagine       - Generate image from text prompt
  /capabilities  - Show available multimodal features

SESSION MANAGEMENT:
  /session       - Switch to different session
  /sessions      - List all sessions
  /clear         - Clear current chat history
  /history       - Show chat statistics

MEMORY & CONTEXT:
  /context       - Update session context
  /profile       - Update global player profile
  /memory        - View memory status

CONFIGURATION:
  /config        - Open configuration menu
  /web           - Launch web interface

EXAMPLES:
  /imagine a cute anime cat with blue eyes
  /vision
  /model ollama/glm-4.6:cloud
                    """.strip())
                    continue
                
                elif cmd == '/model':
                    if args:
                        model_arg = ' '.join(args)
                        if '/' in model_arg:
                            provider_part, model_part = model_arg.split('/', 1)
                            result = set_preferred_provider(provider_part.strip(), model_part.strip())
                            print(result)
                            profile = Database.get_profile()
                            providers_config = profile.get('providers_config', {})
                            current_provider = providers_config.get('preferred_provider', 'ollama')
                            current_model = providers_config.get('preferred_model', 'glm-4.6:cloud')
                        else:
                            all_models = get_all_models()
                            found = False
                            for provider, models in all_models.items():
                                if model_arg in models:
                                    result = set_preferred_provider(provider, model_arg)
                                    print(result)
                                    current_provider = provider
                                    current_model = model_arg
                                    found = True
                                    break
                            if not found:
                                print(f"Model '{model_arg}' not found in any provider")
                    else:
                        print("Usage: /model <provider>/<model> OR /model <model_name>")
                    continue
                
                elif cmd == '/models':
                    all_models = get_all_models()
                    print("AVAILABLE MODELS:")
                    for provider, models in all_models.items():
                        current_marker = " <- CURRENT" if provider == current_provider else ""
                        print(f"\n{provider.upper()}{current_marker}:")
                        for model in models:
                            model_marker = " *" if model == current_model else ""
                            vision_marker = " Vision" if multimodal_tools.is_vision_model(model, provider) else ""
                            print(f"  - {model}{model_marker}{vision_marker}")
                    continue
                
                elif cmd == '/providers':
                    providers = get_available_providers()
                    print("AVAILABLE AI PROVIDERS:")
                    for provider in providers:
                        current_marker = " <- CURRENT" if provider == current_provider else ""
                        vision_models = multimodal_tools.get_available_vision_models(provider)
                        has_vision = len(vision_models) > 0
                        vision_marker = " Vision" if has_vision else ""
                        print(f"  - {provider}{current_marker}{vision_marker}")
                    continue
                
                elif cmd == '/system':
                    if args:
                        system_prompt = ' '.join(args)
                        print(f"System prompt set: {system_prompt}")
                    else:
                        print("Usage: /system <your system prompt>")
                    continue
                
                elif cmd == '/stream':
                    streaming = not streaming
                    print(f"Streaming: {'ON' if streaming else 'OFF'}")
                    continue
                
                elif cmd == '/info':
                    active_session = Database.get_active_session()
                    session_memory = Database.get_session_memory(active_session['id'])
                    
                    vision_capabilities = get_vision_capabilities()
                    
                    print(f"""
CURRENT STATUS:
- Session: {active_session.get('name')} (ID: {active_session.get('id')})
- Messages: {active_session.get('message_count', 0)} in current session
- AI Provider: {current_provider}/{current_model}
- Streaming: {'ON' if streaming else 'OFF'}
- System Prompt: {system_prompt or 'Not set'}
- Session Context: {len(session_memory.get('session_context', ''))} chars
- Vision: {'Available' if vision_capabilities['has_vision'] else 'Unavailable'}
- Image Generation: {'Available' if vision_capabilities['has_image_generation'] else 'Unavailable'}
                    """.strip())
                    continue
                
                elif cmd == '/vision':
                    if not vision_capabilities['has_vision']:
                        print("No vision capabilities available.")
                        continue
                    
                    vision_provider = vision_capabilities['vision_provider']
                    vision_model = vision_capabilities['vision_model']
                    
                    result = set_preferred_provider(vision_provider, vision_model)
                    print(result)
                    
                    profile = Database.get_profile()
                    providers_config = profile.get('providers_config', {})
                    current_provider = providers_config.get('preferred_provider', 'ollama')
                    current_model = providers_config.get('preferred_model', 'glm-4.6:cloud')
                    
                    print("Now using vision model. Send messages with image URLs to analyze them!")
                    continue
                
                elif cmd == '/imagine':
                    if not vision_capabilities['has_image_generation']:
                        print("Image generation not available.")
                        continue
                    
                    if not args:
                        print("Usage: /imagine <prompt>")
                        continue
                    
                    prompt = ' '.join(args)
                    print(f"Generating image: {prompt}")
                    
                    image_url, error = multimodal_tools.generate_image(prompt)
                    
                    if image_url:
                        print(f"Image generated successfully!")
                        print(f"Image URL: {image_url}")
                        
                        active_session = Database.get_active_session()
                        session_id = active_session['id']
                        Database.add_message('user', f"/imagine {prompt}", session_id)
                        Database.add_message('assistant', f"Generated image: {image_url}", session_id)
                    else:
                        print(f"Image generation failed: {error}")
                    continue
                
                elif cmd == '/capabilities':
                    vision_capabilities = get_vision_capabilities()
                    
                    print("MULTIMODAL CAPABILITIES:")
                    print(f"Vision Analysis: {'Available' if vision_capabilities['has_vision'] else 'Unavailable'}")
                    if vision_capabilities['has_vision']:
                        print(f"   Provider: {vision_capabilities['vision_provider']}")
                        print(f"   Model: {vision_capabilities['vision_model']}")
                    
                    print(f"Image Generation: {'Available' if vision_capabilities['has_image_generation'] else 'Unavailable'}")
                    if vision_capabilities['has_image_generation']:
                        print(f"   Provider: {vision_capabilities['image_generation_provider']}")
                    
                    print("\nVISION MODELS BY PROVIDER:")
                    providers = get_available_providers()
                    for provider in providers:
                        vision_models = multimodal_tools.get_available_vision_models(provider)
                        if vision_models:
                            print(f"  {provider.upper()}:")
                            for model in vision_models:
                                print(f"    - {model}")
                    continue
                
                elif cmd == '/session':
                    session_management_menu()
                    continue
                
                elif cmd == '/sessions':
                    sessions = Database.get_all_sessions()
                    active_session = Database.get_active_session()
                    
                    print("ALL SESSIONS:")
                    for session in sessions:
                        active_marker = " ACTIVE" if session['id'] == active_session['id'] else ""
                        print(f"  [{session['id']}] {session['name']} ({session.get('message_count', 0)} msgs){active_marker}")
                    continue
                
                elif cmd == '/clear':
                    confirm = input("Clear current chat history? (y/N): ").strip().lower()
                    if confirm == 'y':
                        active_session = Database.get_active_session()
                        Database.clear_chat_history(active_session['id'])
                        print("Chat history cleared!")
                    continue
                
                elif cmd == '/history':
                    active_session = Database.get_active_session()
                    session_memory = Database.get_session_memory(active_session['id'])
                    
                    total_messages = active_session.get('message_count', 0)
                    user_messages = len([m for m in Database.get_chat_history() if m['role'] == 'user'])
                    assistant_messages = len([m for m in Database.get_chat_history() if m['role'] == 'assistant'])
                    
                    print(f"""
CHAT STATISTICS:
- Total messages: {total_messages}
- Your messages: {user_messages}
- AI responses: {assistant_messages}
- Session: {active_session.get('name')}
- Session Context: {len(session_memory.get('session_context', ''))} chars
- Last Updated: {session_memory.get('last_summarized', 'Never')}
                    """.strip())
                    continue
                
                elif cmd == '/context':
                    active_session = Database.get_active_session()
                    session_id = active_session['id']
                    profile = Database.get_profile()
                    chat_history = Database.get_chat_history(session_id=session_id)
                    
                    if len(chat_history) < 5:
                        print("Need at least 5 conversation messages to generate context")
                    else:
                        last_user_msg = next((msg for msg in reversed(chat_history) if msg['role'] == 'user'), None)
                        last_ai_reply = next((msg for msg in reversed(chat_history) if msg['role'] == 'assistant'), None)
                        
                        if last_user_msg and last_ai_reply:
                            if summarize_memory(profile, last_user_msg['content'], last_ai_reply['content'], session_id):
                                print("Session context updated!")
                            else:
                                print("Session context update failed")
                        else:
                            print("Need conversation history to generate context")
                    continue
                
                elif cmd == '/profile':
                    print("Analyzing player profile from ALL sessions...")
                    if summarize_global_player_profile():
                        print("Global player profile updated from ALL sessions!")
                    else:
                        print("Global profile analysis failed")
                    continue
                
                elif cmd == '/memory':
                    profile = Database.get_profile()
                    active_session = Database.get_active_session()
                    session_memory = Database.get_session_memory(active_session['id'])
                    
                    print(f"""
MEMORY STATUS:
SESSION MEMORY (Current):
  Context: {len(session_memory.get('session_context', ''))} chars
  Last Updated: {session_memory.get('last_summarized', 'Never')}
GLOBAL PROFILE (All Sessions):
  Summary: {len(profile.get('memory', {}).get('player_summary', ''))} chars
  Likes: {len(profile.get('memory', {}).get('key_facts', {}).get('likes', []))} items
  Last Updated: {profile.get('memory', {}).get('last_global_summary', 'Never')}
GLOBAL KNOWLEDGE:
  Facts: {len(profile.get('global_knowledge', {}).get('facts', ''))} chars
                    """.strip())
                    continue
                
                elif cmd == '/config':
                    config_menu()
                    continue
                
                elif cmd == '/web':
                    launch_web_interface()
                    return
                
                else:
                    print(f"Unknown command '{cmd}'. Type /help for available commands.")
                    continue
            
            if not lines:
                print("-" * 50)
                continue
                
            user_msg = "\n".join(lines).strip()
            if not user_msg:
                continue

            print(f"\n{profile['partner_name']} > ", end="", flush=True)
            
            response = handle_user_message(user_msg, interface="terminal")
            print(response)
            print("-" * 50)
            
    except KeyboardInterrupt:
        print(f"\n\n{profile['partner_name']} > Terminal session interrupted!")
        end_session_cleanup(profile, interface="terminal", unexpected_exit=True)
        return
        
    except Exception as e:
        print(f"\n\n{profile['partner_name']} > Terminal error: {e}")
        end_session_cleanup(profile, interface="terminal", unexpected_exit=True)
        return

def config_menu():
    profile = Database.get_profile()
    api_keys = Database.get_api_keys()
    session_history = profile.get("session_history", {})
    last_session = session_history.get("last_session", {})
    
    active_session = Database.get_active_session()
    session_memory = Database.get_session_memory(active_session['id'])
    
    global_knowledge = profile.get('global_knowledge', {})
    global_facts = global_knowledge.get('facts', '')
    
    profile_memory = profile.get('memory', {})
    
    vision_capabilities = get_vision_capabilities()
    
    print_header("CONFIG MENU")
    print(f"Single User Mode")
    print(f"Partner: {profile['partner_name']}")
    print(f"Your display name: {profile['display_name']}")
    print(f"Affection: {profile.get('affection', 50)}")
    print(f"Active Session: {active_session.get('name', 'Unknown')} (ID: {active_session.get('id')})")
    print(f"Session Context: {len(session_memory.get('session_context', ''))} chars | Last: {session_memory.get('last_summarized', 'Never')}")
    print(f"Global Profile: {len(profile_memory.get('player_summary', ''))} chars | Cross-session data")
    print(f"Global Knowledge: {len(global_facts)} chars | Manual facts")
    print(f"API keys: {len(api_keys)} available")
    
    print(f"Vision: {'Available' if vision_capabilities['has_vision'] else 'Unavailable'}")
    print(f"Image Generation: {'Available' if vision_capabilities['has_image_generation'] else 'Unavailable'}")
    
    print(f"Sessions: {session_history.get('total_sessions', 0)} total")
    if last_session.get('end_time'):
        print(f"Last session: {last_session.get('duration_minutes', 0):.1f} min, {last_session.get('message_count', 0)} messages")
    print(f"Total time: {session_history.get('total_time_minutes', 0):.1f} minutes")
    
    print("-"*50)
    print("1) Set your display name")
    print("2) Set partner name")
    print("3) Manage API keys")
    print("4) Set affection (0-100)")
    print("5) Update session context (current session)")
    print("6) Update global player profile (ALL sessions)")
    print("7) View session context")
    print("8) View global player profile")
    print("9) Clear chat history (current session)")
    print("10) View session history")
    print("11) Manage sessions")
    print("12) Manage global knowledge")
    print("13) AI Provider Settings")
    print("14) Multimodal Settings")
    print(" ")
    print("0) Back to main menu")
    print_footer()
    
    try:
        choice = input("> ").strip()
    except KeyboardInterrupt:
        return

    if choice == "1":
        new_name = input("Enter your display name: ").strip()
        if new_name:
            Database.update_profile({'display_name': new_name})
            print(f"Your name set to {new_name}")
    
    elif choice == "2":
        new_name = input("Enter your partner's name: ").strip()
        if new_name:
            Database.update_profile({'partner_name': new_name})
            print(f"Partner name set to {new_name}")
    
    elif choice == "3":
        api_key_menu()
    
    elif choice == "4":
        try:
            aff = int(input("Enter affection (0-100): ").strip())
            affection = max(0, min(100, aff))
            Database.update_profile({'affection': affection})
            print(f"Affection set to {affection}")
        except ValueError:
            print("Invalid number")
    
    elif choice == "5":
        active_session = Database.get_active_session()
        session_id = active_session['id']
        profile = Database.get_profile()
        chat_history = Database.get_chat_history(session_id=session_id)
        
        if len(chat_history) < 5:
            print("Need at least 5 conversation messages to generate context")
        elif chat_history:
            last_user_msg = next((msg for msg in reversed(chat_history) if msg['role'] == 'user'), None)
            last_ai_reply = next((msg for msg in reversed(chat_history) if msg['role'] == 'assistant'), None)
            
            if last_user_msg and last_ai_reply:
                if summarize_memory(profile, last_user_msg['content'], last_ai_reply['content'], session_id):
                    print(f"Session context updated for session {session_id}!")
                else:
                    print("Session context update failed")
            else:
                print("Need conversation history to generate context")
        else:
            print("No chat history to analyze")
    
    elif choice == "6":
        print("Analyzing player profile from ALL sessions...")
        if summarize_global_player_profile():
            print("Global player profile updated from ALL sessions!")
        else:
            print("Global profile analysis failed")
    
    elif choice == "7":
        active_session = Database.get_active_session()
        session_memory = Database.get_session_memory(active_session['id'])
        
        print(f"\nCURRENT SESSION CONTEXT (Session {active_session.get('id')}):")
        print(f"Session Name: {active_session.get('name')}")
        print(f"Context: {session_memory.get('session_context', 'No context yet')}")
        print(f"Last Updated: {session_memory.get('last_summarized', 'Never')}")
        input("\nPress Enter to continue...")
    
    elif choice == "8":
        profile = Database.get_profile()
        memory = profile.get('memory', {})
        key_facts = memory.get("key_facts", {})
        
        print(f"\nGLOBAL PLAYER PROFILE (All Sessions):")
        print(f"Summary: {memory.get('player_summary', 'No global summary yet')}")
        print(f"Likes: {', '.join(key_facts.get('likes', [])) or 'None'}")
        print(f"Dislikes: {', '.join(key_facts.get('dislikes', [])) or 'None'}")
        print(f"Personality: {', '.join(key_facts.get('personality_traits', [])) or 'None'}")
        print(f"Memories: {', '.join(key_facts.get('important_memories', [])) or 'None'}")
        print(f"Relationship: {memory.get('relationship_dynamics', 'No dynamics yet')}")
        print(f"Last Updated: {memory.get('last_global_summary', 'Never')}")
        input("\nPress Enter to continue...")
    
    elif choice == "9":
        active_session = Database.get_active_session()
        session_id = active_session['id']
        
        confirm = input(f"Clear chat history for session '{active_session.get('name')}'? (y/N): ").strip().lower()
        if confirm == 'y':
            Database.clear_chat_history(session_id)
            print(f"Chat history cleared for session {session_id}")
    
    elif choice == "10":
        view_session_history()
    
    elif choice == "11":
        session_management_menu()
    
    elif choice == "12":
        manage_global_knowledge()
    
    elif choice == "13":
        provider_settings_menu()
    
    elif choice == "14":
        multimodal_settings_menu()
    
    elif choice == "0":
        return
    
    else:
        print("Invalid choice")

def multimodal_settings_menu():
    vision_capabilities = get_vision_capabilities()
    
    print_header("MULTIMODAL SETTINGS")
    print(f"Vision Analysis: {'Available' if vision_capabilities['has_vision'] else 'Unavailable'}")
    if vision_capabilities['has_vision']:
        print(f"  Provider: {vision_capabilities['vision_provider']}")
        print(f"  Model: {vision_capabilities['vision_model']}")
    
    print(f"Image Generation: {'Available' if vision_capabilities['has_image_generation'] else 'Unavailable'}")
    if vision_capabilities['has_image_generation']:
        print(f"  Provider: {vision_capabilities['image_generation_provider']}")
    
    print("-" * 50)
    print("1) Test vision capabilities")
    print("2) Test image generation")
    print("3) View available vision models")
    print("4) Generate test image")
    print("0) Back")
    
    try:
        choice = input("> ").strip()
    except KeyboardInterrupt:
        return
    
    if choice == "1":
        if not vision_capabilities['has_vision']:
            print("No vision capabilities available")
            return
        
        print("Testing vision capabilities...")
        print("Try sending a message with an image URL like:")
        print("   'What's in this image? https://example.com/image.jpg'")
        print("   The system will automatically switch to vision model.")
        
    elif choice == "2":
        if not vision_capabilities['has_image_generation']:
            print("No image generation capabilities available")
            return
        
        print("Testing image generation...")
        print("Use /imagine command or type 'generate image of...'")
        print("   Examples:")
        print("   /imagine a cute anime cat")
        print("   generate image of a sunset over mountains")
        
    elif choice == "3":
        print("AVAILABLE VISION MODELS:")
        providers = get_available_providers()
        for provider in providers:
            vision_models = multimodal_tools.get_available_vision_models(provider)
            if vision_models:
                print(f"\n{provider.upper()}:")
                for model in vision_models:
                    print(f"  - {model}")
        input("\nPress Enter to continue...")
        
    elif choice == "4":
        if not vision_capabilities['has_image_generation']:
            print("Image generation not available")
            return
        
        prompt = input("Enter image prompt: ").strip()
        if not prompt:
            print("No prompt entered")
            return
        
        print(f"Generating: {prompt}")
        image_url, error = multimodal_tools.generate_image(prompt)
        
        if image_url:
            print(f"Image generated successfully!")
            print(f"URL: {image_url}")
            print("The image has been saved to your chat history")
        else:
            print(f"Failed: {error}")
            
    elif choice == "0":
        return
    
    else:
        print("Invalid choice")

def provider_settings_menu():
    profile = Database.get_profile()
    providers_config = profile.get('providers_config', {})
    current_provider = providers_config.get('preferred_provider', 'ollama')
    current_model = providers_config.get('preferred_model', 'glm-4.6:cloud')
    
    print_header("AI PROVIDER SETTINGS")
    print(f"Current: {current_provider}/{current_model}")
    print("-" * 50)
    
    ai_manager = get_ai_manager()
    available_providers = ai_manager.get_available_providers()
    all_models = ai_manager.get_all_models()
    
    print("Available Providers:")
    for provider in available_providers:
        current_marker = " <- CURRENT" if provider == current_provider else ""
        vision_models = multimodal_tools.get_available_vision_models(provider)
        has_vision = len(vision_models) > 0
        vision_marker = " Vision" if has_vision else ""
        print(f"  - {provider}{current_marker}{vision_marker}")
    
    print("\nOptions:")
    print("1) Change preferred provider")
    print("2) Change preferred model") 
    print("3) Test provider connections")
    print("0) Back")
    
    try:
        choice = input("> ").strip()
    except KeyboardInterrupt:
        return
    
    if choice == "1":
        print("\nSelect provider:")
        for i, provider in enumerate(available_providers, 1):
            vision_models = multimodal_tools.get_available_vision_models(provider)
            vision_info = " Vision" if vision_models else ""
            print(f"  {i}) {provider}{vision_info}")
        
        try:
            provider_choice = int(input("> ").strip())
            if 1 <= provider_choice <= len(available_providers):
                selected_provider = available_providers[provider_choice - 1]
                result = set_preferred_provider(selected_provider)
                print(result)
            else:
                print("Invalid selection")
        except ValueError:
            print("Invalid input")
    
    elif choice == "2":
        print("\nSelect provider to see models:")
        for i, provider in enumerate(available_providers, 1):
            vision_models = multimodal_tools.get_available_vision_models(provider)
            vision_info = " Vision" if vision_models else ""
            print(f"  {i}) {provider}{vision_info}")
        
        try:
            provider_choice = int(input("> ").strip())
            if 1 <= provider_choice <= len(available_providers):
                selected_provider = available_providers[provider_choice - 1]
                models = all_models.get(selected_provider, [])
                
                if models:
                    print(f"\nModels for {selected_provider}:")
                    for i, model in enumerate(models, 1):
                        vision_marker = " Vision" if multimodal_tools.is_vision_model(model, selected_provider) else ""
                        print(f"  {i}) {model}{vision_marker}")
                    
                    model_choice = int(input("Select model: ").strip())
                    if 1 <= model_choice <= len(models):
                        selected_model = models[model_choice - 1]
                        result = set_preferred_provider(selected_provider, selected_model)
                        print(result)
                    else:
                        print("Invalid selection")
                else:
                    print("No models available for this provider")
            else:
                print("Invalid selection")
        except ValueError:
            print("Invalid input")
    
    elif choice == "3":
        print("\nTesting provider connections...")
        for provider_name in available_providers:
            provider = ai_manager.providers.get(provider_name)
            if provider:
                status = "Connected" if provider.test_connection() else "Failed"
                vision_info = " Vision" if multimodal_tools.get_available_vision_models(provider_name) else ""
                print(f"  {provider_name}: {status}{vision_info}")
        input("\nPress Enter to continue...")
    
    elif choice == "0":
        return
    
    else:
        print("Invalid choice")

def manage_global_knowledge():
    profile = Database.get_profile()
    global_knowledge = profile.get('global_knowledge', {})
    current_facts = global_knowledge.get('facts', '')
    
    print_header("GLOBAL KNOWLEDGE")
    print("Global knowledge persists across ALL sessions")
    print("Use this for permanent facts about yourself/partner")
    print("-" * 50)
    
    if current_facts:
        print("Current global knowledge:")
        print(current_facts)
    else:
        print("No global knowledge yet.")
    
    print("\nOptions:")
    print("1) Edit global knowledge")
    print("2) Clear global knowledge")
    print("0) Back")
    
    try:
        sub_choice = input("> ").strip()
    except KeyboardInterrupt:
        return
    
    if sub_choice == "1":
        print("\nEnter your global knowledge (multi-line). Type '...' on empty line to finish:")
        lines = []
        while True:
            line = input()
            if line.strip() == "...":
                break
            lines.append(line)
        
        new_facts = "\n".join(lines).strip()
        if new_facts:
            global_knowledge['facts'] = new_facts
            Database.update_profile({'global_knowledge': global_knowledge})
            print("Global knowledge updated!")
        else:
            print("No content entered")
    
    elif sub_choice == "2":
        if current_facts and input("Clear all global knowledge? (y/N): ").strip().lower() == 'y':
            global_knowledge['facts'] = ''
            Database.update_profile({'global_knowledge': global_knowledge})
            print("Global knowledge cleared!")
    
    elif sub_choice == "0":
        return
    
    else:
        print("Invalid choice")
        
def session_management_menu():
    while True:
        sessions = Database.get_all_sessions()
        active_session = Database.get_active_session()
        
        print_header("SESSION MANAGEMENT")
        
        for session in sessions:
            active_marker = "ACTIVE" if session['id'] == active_session['id'] else "  "
            msg_count = session.get('message_count', 0)
            session_memory = Database.get_session_memory(session['id'])
            has_context = "Context" if session_memory.get('session_context') else "  "
            
            print(f"{active_marker} {has_context} [{session['id']}] {session['name']} ({msg_count} messages)")
        
        print("-" * 50)
        print("1) Switch to session")
        print("2) Create new session")
        print("3) Rename session")
        print("4) Delete session")
        print("5) View session context")
        print("0) Back")
        print_footer()
        
        try:
            choice = input("> ").strip()
        except KeyboardInterrupt:
            break
        
        if choice == "1":
            try:
                session_id = int(input("Enter session ID to switch to: ").strip())
                if Database.switch_session(session_id):
                    print(f"Switched to session {session_id}")
                else:
                    print("Session not found")
            except ValueError:
                print("Invalid ID")
        
        elif choice == "2":
            name = input("Enter session name (or press Enter for 'New Chat'): ").strip()
            if not name:
                name = "New Chat"
            
            session_id = Database.create_session(name)
            Database.switch_session(session_id)
            print(f"Created and switched to session {session_id}")
        
        elif choice == "3":
            try:
                session_id = int(input("Enter session ID to rename: ").strip())
                new_name = input("Enter new name: ").strip()
                
                if new_name:
                    if Database.rename_session(session_id, new_name):
                        print(f"Renamed session {session_id}")
                    else:
                        print("Session not found")
                else:
                    print("Name cannot be empty")
            except ValueError:
                print("Invalid ID")
        
        elif choice == "4":
            try:
                session_id = int(input("Enter session ID to delete: ").strip())
                confirm = input(f"Are you sure? This cannot be undone (y/N): ").strip().lower()
                
                if confirm == 'y':
                    if Database.delete_session(session_id):
                        print(f"Deleted session {session_id}")
                    else:
                        print("Session not found")
            except ValueError:
                print("Invalid ID")
        
        elif choice == "5":
            try:
                session_id = int(input("Enter session ID to view context: ").strip())
                session_memory = Database.get_session_memory(session_id)
                
                print(f"\nSESSION {session_id} CONTEXT:")
                print(f"Context: {session_memory.get('session_context', 'No context yet')}")
                print(f"Last Updated: {session_memory.get('last_summarized', 'Never')}")
                input("\nPress Enter to continue...")
            except ValueError:
                print("Invalid ID")
        
        elif choice == "0":
            break
        
        else:
            print("Invalid choice")

def api_key_menu():
    while True:
        keys = Database.get_api_keys()
        print("\nAPI KEY MANAGEMENT:")
        print("1) Add OpenRouter API key")
        print("2) Add Cerebras API key") 
        print("3) Add Chutes API key")
        print("4) View API keys")
        print("5) Remove API key")
        print("6) Back")
        
        try:
            sub_choice = input("> ").strip()
        except KeyboardInterrupt:
            break

        if sub_choice == "1":
            new_key = input("Enter OpenRouter API key: ").strip()
            if new_key:
                if Database.add_api_key('openrouter', new_key):
                    print("OpenRouter API key added")
                    print("Enables: Image generation + Vision models")
                else:
                    print("Failed to save API key")
            else:
                print("No key entered")
        
        elif sub_choice == "2":
            new_key = input("Enter Cerebras API key: ").strip()
            if new_key:
                if Database.add_api_key('cerebras', new_key):
                    print("Cerebras API key added")
                else:
                    print("Failed to save API key")
            else:
                print("No key entered")
        
        elif sub_choice == "3":
            new_key = input("Enter Chutes API key: ").strip()
            if new_key:
                if Database.add_api_key('chutes', new_key):
                    print("Chutes API key added")
                    print("Enables: Vision models (Qwen3-VL)")
                else:
                    print("Failed to save API key")
            else:
                print("No key entered")
        
        elif sub_choice == "4":
            keys = Database.get_api_keys()
            print(f"\nStored API keys:")
            for key_name, key_value in keys.items():
                capabilities = []
                if key_name == 'openrouter':
                    capabilities.append("image generation + vision")
                elif key_name == 'chutes':
                    capabilities.append("vision")
                
                cap_text = f" ({', '.join(capabilities)})" if capabilities else ""
                print(f"  {key_name}: {key_value[:10]}...{key_value[-5:]}{cap_text}")
            input("\nPress Enter to continue...")
        
        elif sub_choice == "5":
            keys = Database.get_api_keys()
            if keys:
                print("Select key to remove:")
                key_list = list(keys.items())
                for i, (key_name, key_value) in enumerate(key_list, 1):
                    print(f"  {i}: {key_name} - {key_value[:10]}...{key_value[-5:]}")
                try:
                    idx = int(input("> ").strip()) - 1
                    if 0 <= idx < len(key_list):
                        key_to_remove = key_list[idx][0]
                        if Database.remove_api_key(key_to_remove):
                            print(f"Removed: {key_to_remove}")
                        else:
                            print("Failed to remove key")
                    else:
                        print("Invalid selection")
                except ValueError:
                    print("Invalid input")
            else:
                print("No API keys to remove")
        
        elif sub_choice == "6":
            break
        
        else:
            print("Invalid choice")

def view_session_history():
    sessions = Database.get_all_sessions()
    recent_events = Database.get_recent_sessions(limit=10)
    
    print_header("SESSION HISTORY")
    print(f"Total sessions: {len(sessions)}")
    
    if recent_events:
        print("\nRecent session events:")
        for event in recent_events:
            print(f"  {event['timestamp']}: {event['content']}")
    else:
        print("\nNo recent session events.")
    
    input("\nPress Enter to continue...")

def main_menu():
    while True:
        profile = Database.get_profile()
        active_session = Database.get_active_session()
        chat_history = Database.get_chat_history()
        
        vision_capabilities = get_vision_capabilities()
        
        print_header("Yuzu Companion Terminal")
        print(f"User: {profile['display_name']}  |  Partner: {profile['partner_name']}")
        print(f"Affection: {profile.get('affection', 50)}")
        print(f"Active Session: {active_session.get('name')} ({len(chat_history)} messages)")
        
        vision_status = "Vision" if vision_capabilities['has_vision'] else "No"
        image_status = "Images" if vision_capabilities['has_image_generation'] else "No"
        print(f"Multimodal: Vision {vision_status} | Images {image_status}")
        
        print("-"*50)
        print("1) Talk with your partner (Terminal - Command Mode)")
        print("2) Launch Web Interface")
        print("3) Configuration")
        print("0) Exit")
        print_footer()
        
        try:
            choice = input("> ").strip()
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break

        if choice == "1":
            chat_loop()
            
        elif choice == "2":
            launch_web_interface()
            
        elif choice == "3":
            config_menu()
            
        elif choice == "0":
            print("Goodbye!")
            break
            
        else:
            print("Invalid choice")

if __name__ == "__main__":
    main_menu()
