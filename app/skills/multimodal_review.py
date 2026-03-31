# FILE: app/skills/multimodal_review.py
# DESCRIPTION: Skill helper for multimodal image intake, vision routing, and image review.

from __future__ import annotations

import base64
import os
from typing import Any, Dict, List, Optional, Tuple

from app.tools import multimodal_tools

VISUAL_CONTEXT_BUFFER = {}
VISUAL_CONTEXT_TURNS = 3

def _extract_markdown_image_sources(text: str) -> List[str]:
    """Extract markdown image destinations without regex."""
    sources: List[str] = []
    index = 0

    while True:
        start = text.find('![', index)
        if start == -1:
            break

        open_paren = text.find('](', start + 2)
        if open_paren == -1:
            index = start + 2
            continue

        url_start = open_paren + 2
        close_paren = text.find(')', url_start)
        if close_paren == -1:
            index = url_start
            continue

        source = text[url_start:close_paren].strip()
        if source:
            sources.append(source)

        index = close_paren + 1

    return sources



def cache_images_from_message(user_message: str) -> List[str]:
    """Extract image URLs or upload markers from a user message and cache local copies."""
    cached_paths: List[str] = []

    if "UPLOADED_IMAGES:" in user_message and "IMAGE_UPLOAD:" in user_message:
        # Restrict IMAGE_UPLOAD paths to the static/uploads directory to prevent path traversal
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        uploads_dir = os.path.abspath(os.path.join(base_dir, "static", "uploads"))
        for line in user_message.split("\n"):
            if line.startswith("IMAGE_UPLOAD:"):
                path = line.replace("IMAGE_UPLOAD:", "").strip()
                # Join with uploads_dir and normalize, then ensure the result stays within uploads_dir
                candidate_path = os.path.abspath(os.path.normpath(os.path.join(uploads_dir, path)))
                if candidate_path.startswith(uploads_dir + os.sep) and os.path.isfile(candidate_path):
                    cached_paths.append(candidate_path)
        return cached_paths

    for source in _extract_markdown_image_sources(user_message):
        if source.startswith(("static/", "uploads/", "generated_images/")):
            local_path = source if source.startswith("static/") else f"static/{source}"
            if os.path.isfile(local_path):
                cached_paths.append(local_path)
                print(f"[Vision] Local image found → {local_path}")
        else:
            cached = multimodal_tools.download_image_to_cache(source)
            if cached:
                cached_paths.append(cached)

    if not cached_paths:
        urls = multimodal_tools.extract_image_urls(user_message)
        for url in urls[:3]:
            cached = multimodal_tools.download_image_to_cache(url)
            if cached:
                cached_paths.append(cached)

    return cached_paths


def parse_image_result_from_formatted(formatted_result: str) -> Optional[str]:
    """Extract the generated image path from a formatted tool result."""
    start = formatted_result.find('src="')
    if start == -1:
        return None

    start += len('src="')
    end = formatted_result.find('"', start)
    if end == -1:
        return None

    value = formatted_result[start:end].strip()
    return value or None


def load_generated_image_base64(img_path: str) -> Tuple[Optional[str], Optional[str]]:
    """Load an image file and return a base64 payload plus MIME type."""
    try:
        if not os.path.exists(img_path):
            print(f"[Vision2nd] Image file not found: {img_path}")
            return None, None

        with open(img_path, "rb") as f:
            img_data = f.read()

        mime_type = "image/png" if img_path.endswith(".png") else "image/jpeg"
        img_b64 = base64.b64encode(img_data).decode("utf-8")
        return img_b64, mime_type
    except Exception as e:
        print(f"[Vision2nd] Failed to load image: {e}")
        return None, None


def _store_visual_context(session_id, image_base64, mime):
    VISUAL_CONTEXT_BUFFER[session_id] = {
        "base64": image_base64,
        "mime": mime,
        "turns_left": VISUAL_CONTEXT_TURNS,
    }


def attach_generated_image_to_messages(
    img_path: str,
    messages: List[Dict],
    session_id: Any,
    store_visual_context_fn=None,
) -> bool:
    """Attach a generated image to an outgoing message list for vision models."""
    try:
        img_b64, mime_type = load_generated_image_base64(img_path)
        if not img_b64:
            return False

        store_fn = store_visual_context_fn or _store_visual_context
        store_fn(session_id, img_b64, mime_type)

        messages.append(
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "[Generated image attached for your natural response]"},
                    {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{img_b64}"}},
                ],
            }
        )
        print("[IMAGE TOOL] Generated image attached to conversation for vision model")
        return True
    except Exception as e:
        print(f"[IMAGE TOOL] Failed to load generated image: {e}")
        return False


def prepare_multimodal_turn(
    messages: List[Dict],
    user_message: str,
    current_provider: str,
    current_model: str,
    image_content_for_context=None,
) -> Tuple[List[Dict], str, str]:
    """Prepare messages and provider/model selection for multimodal turns."""
    prepared_messages = list(messages)

    if image_content_for_context is not None:
        vision_provider, vision_model = multimodal_tools.get_best_vision_provider()
        if vision_provider and vision_model:
            print(f"[Vision] Force switching to {vision_provider}/{vision_model} for image_tools output")
            prepared_messages.append(
                {
                    "role": "user",
                    "content": [{"type": "text", "text": "Here's the generated image for your reference."}] + image_content_for_context,
                }
            )
            return prepared_messages, vision_provider, vision_model

    should_switch_provider = multimodal_tools.should_use_vision(user_message, current_provider, current_model)
    if should_switch_provider:
        vision_provider, vision_model = multimodal_tools.get_best_vision_provider()
        if vision_provider and vision_model:
            current_provider = vision_provider
            current_model = vision_model
            vision_messages = multimodal_tools.format_vision_message(user_message)
            if prepared_messages and prepared_messages[-1]["role"] == "user":
                prepared_messages = prepared_messages[:-1] + vision_messages

    return prepared_messages, current_provider, current_model


def is_model_using_markdown_image_shortcut(response_text: str) -> bool:
    """Detect if a model is trying to output a markdown image instead of using the image tool."""
    if not response_text:
        return False

    for source in _extract_markdown_image_sources(response_text):
        if source.startswith(("static/", "uploads/", "generated_images/")):
            return True
    return False


def extract_prompt_from_markdown_image(response_text: str) -> Optional[str]:
    """Extract the image path or URL from markdown image syntax."""
    sources = _extract_markdown_image_sources(response_text)
    return sources[0] if sources else None


def run_multimodal_review(
    messages: List[Dict],
    user_message: str,
    current_provider: str,
    current_model: str,
    session_id: Any = None,
    image_content_for_context=None,
) -> Dict[str, Any]:
    """High-level multimodal review workflow for image-heavy turns."""
    cached_image_paths = cache_images_from_message(user_message)
    prepared_messages, provider, model = prepare_multimodal_turn(
        messages,
        user_message,
        current_provider,
        current_model,
        image_content_for_context=image_content_for_context,
    )

    return {
        "messages": prepared_messages,
        "provider": provider,
        "model": model,
        "cached_image_paths": cached_image_paths,
        "has_images": bool(cached_image_paths),
        "session_id": session_id,
    }
