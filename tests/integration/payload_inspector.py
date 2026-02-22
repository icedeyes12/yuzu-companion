#!/usr/bin/env python3
"""
Payload Inspector
- Can be executed from /tests/integration
- Dumps full payload to /debug_logs
- Outputs both .json and .md
"""

import sys
import json
from datetime import datetime
from pathlib import Path


# ==========================================================
# Resolve project root (works when running from /tests/integration)
# ==========================================================

CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_FILE.parent.parent.parent
DEBUG_DIR = PROJECT_ROOT / "debug_logs"

sys.path.insert(0, str(PROJECT_ROOT))


# ==========================================================
# Imports from project
# ==========================================================

from app import generate_ai_response
from database import Database
from providers import get_ai_manager


# ==========================================================
# Utility: Ensure debug directory exists
# ==========================================================

def ensure_debug_dir():
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)


# ==========================================================
# Utility: Write JSON + Markdown dump
# ==========================================================

def dump_payload(provider, model, messages, kwargs):
    ensure_debug_dir()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"payload_{timestamp}"

    json_path = DEBUG_DIR / f"{base_name}.json"
    md_path = DEBUG_DIR / f"{base_name}.md"

    payload = {
        "timestamp": timestamp,
        "provider": provider,
        "model": model,
        "message_count": len(messages),
        "messages": messages,
        "kwargs": kwargs
    }

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"# Payload Dump — {timestamp}\n\n")
        f.write(f"**Provider:** `{provider}`  \n")
        f.write(f"**Model:** `{model}`  \n")
        f.write(f"**Message Count:** {len(messages)}  \n\n")
        f.write("---\n\n")

        for i, msg in enumerate(messages):
            f.write(f"## [{i}] Role: `{msg['role']}`\n\n")

            content = msg["content"]

            if isinstance(content, str):
                f.write("```text\n")
                f.write(content)
                f.write("\n```\n\n")
            elif isinstance(content, list):
                f.write("_Multimodal content_\n\n")
                for part in content:
                    if part.get("type") == "text":
                        f.write("```text\n")
                        f.write(part["text"])
                        f.write("\n```\n\n")
                    elif part.get("type") == "image_url":
                        f.write("`[Image attached]`\n\n")

        f.write("---\n\n")
        f.write("## kwargs\n\n")
        f.write("```json\n")
        f.write(json.dumps(kwargs, indent=2))
        f.write("\n```\n")

    print(f"[DUMPED] {json_path.name}")
    print(f"[DUMPED] {md_path.name}")


# ==========================================================
# Interceptor
# ==========================================================

def install_interceptor():
    ai_manager = get_ai_manager()
    original_send = ai_manager.send_message

    def wrapper(provider, model, messages, **kwargs):
        dump_payload(provider, model, messages, kwargs)
        return "[MOCKED] Payload captured — not sent to LLM"

    ai_manager.send_message = wrapper
    return original_send


# ==========================================================
# Main
# ==========================================================

def main():
    print("Payload Inspector active")
    print("Debug output → /debug_logs\n")

    original = install_interceptor()

    try:
        while True:
            user_msg = input("Your message: ").strip()
            if user_msg.lower() in ("exit", "quit"):
                break
            if not user_msg:
                continue

            profile = Database.get_profile()
            response = generate_ai_response(profile, user_msg)
            print("Response:", response)

    except KeyboardInterrupt:
        pass

    finally:
        get_ai_manager().send_message = original
        print("\nInterceptor stopped")


if __name__ == "__main__":
    main()