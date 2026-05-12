# FILE: app/orchestrator.py
# DESCRIPTION: Single entrypoint for handling user messages.
#              Coordinates: LLM call -> tool detection -> tool exec -> synthesis.
# v3.1.0: Universal inline command path with placeholder emission.

from __future__ import annotations

import re
from typing import Any, Iterator

from app.commands import (
    IMAGE_SHORTCUT_WARNING,
    StreamFilter,
    detect_command,
    execute_command,
    extract_markdown_image_path,
    is_markdown_image_shortcut,
    parse_image_path,
)
from app.database import Database
from app.database.db_queries import TOOL_ROLE_UNIVERSAL
from app.llm_client import (
    generate_ai_response,
    generate_ai_response_streaming,
)
from app.logging_config import get_logger
from app.tools import multimodal_tools
from app.tools.registry import execute_tool, get_tool_role
from app.visual_context import store_visual_context

log = get_logger(__name__)

_TIMESTAMP_SUFFIX = re.compile(r"\s*\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\]\s*$")
_NESTED_COMMAND_PREFIXES = ("/request", "/imagine")
_EMPTY_RESPONSE_FALLBACK = "I'm having trouble responding right now. Please try again."
_MD_IMAGE_PATTERN = re.compile(r"!\[[^\]]{0,200}\]\(([^)]{1,200})\)")

# Throttle: only check pipeline every Nth message
_PIPELINE_CHECK_INTERVAL = 5


# ---------------------------------------------------------------------------
# Image-cache helpers
# ---------------------------------------------------------------------------


def _cache_uploaded_images(message: str) -> list[str]:
    """Extract image paths from uploaded-images marker, with path validation."""
    if "UPLOADED_IMAGES:" not in message or "IMAGE_UPLOAD:" not in message:
        return []
    
    import os
    paths: list[str] = []
    allowed_dirs = ("static/", "uploads/", "generated_images/")
    
    for line in message.split("\n"):
        if line.startswith("IMAGE_UPLOAD:"):
            candidate = line[len("IMAGE_UPLOAD:"):].strip()
            if not candidate:
                continue
            candidate = os.path.normpath(candidate)
            if candidate.startswith("..") or candidate.startswith("/"):
                log.warning("rejected path traversal attempt: %s", candidate[:50])
                continue
            if not any(candidate.startswith(d) for d in allowed_dirs):
                log.warning("rejected path outside allowed dirs: %s", candidate[:50])
                continue
            if os.path.isfile(candidate):
                paths.append(candidate)
    return paths


def _cache_images_from_message(message: str) -> list[str]:
    """Resolve image references in *message* to local cache paths."""
    import os
    uploaded = _cache_uploaded_images(message)
    if uploaded:
        return uploaded

    allowed_dirs = ("static/", "uploads/", "generated_images/")
    cached: list[str] = []
    
    for match in _MD_IMAGE_PATTERN.finditer(message):
        source = match.group(1)
        if len(source) > 500:
            source = source[:500]
        if source.startswith(("static/", "uploads/", "generated_images/")):
            local = source if source.startswith("static/") else f"static/{source}"
            local = os.path.normpath(local)
            if not any(local.startswith(d) for d in allowed_dirs):
                continue
            if ".." in local or local.startswith("/"):
                continue
            if os.path.isfile(local):
                cached.append(local)
        else:
            local = multimodal_tools.download_image_to_cache(source)
            if local:
                cached.append(local)

    if not cached:
        for url in multimodal_tools.extract_image_urls(message)[:3]:
            local = multimodal_tools.download_image_to_cache(url)
            if local:
                cached.append(local)
    return cached


def _load_image_base64(image_path: str) -> tuple[str | None, str | None]:
    """Return (base64, mime) for a generated image file."""
    import base64
    import os
    if not os.path.exists(image_path):
        log.warning("image not found: %s", image_path)
        return None, None
    try:
        with open(image_path, "rb") as f:
            data = base64.b64encode(f.read()).decode("utf-8")
    except OSError as e:
        log.warning("image read failed (%s): %s", image_path, e)
        return None, None
    mime = "image/png" if image_path.lower().endswith(".png") else "image/jpeg"
    return data, mime


# ---------------------------------------------------------------------------
# Response post-processing
# ---------------------------------------------------------------------------


def _clean(text: str) -> str:
    return _TIMESTAMP_SUFFIX.sub("", text).strip()


def _persist_user(
    message: str, session_id: int, image_paths: list[str] | None
) -> None:
    Database.add_message(
        "user", message, session_id=session_id, image_paths=image_paths or None
    )


def _persist_first_pass(text: str, session_id: int) -> None:
    """Store first pass (acknowledgment + tool call) as assistant message."""
    Database.add_message("assistant", text, session_id=session_id)


def _persist_tool_result(
    tool_name: str,
    xml: str,
    markdown: str,
    session_id: int,
    use_universal: bool = True,
) -> None:
    """Store tool result with appropriate role.
    
    v3.1.0: use_universal=True stores with 'tools' role.
    """
    role = TOOL_ROLE_UNIVERSAL if use_universal else get_tool_role(tool_name)
    # Store XML format for synthesis, markdown for backward compat
    Database.add_message(role, xml, session_id=session_id)


def _strip_nested_commands(text: str) -> str:
    """Remove leading-slash command lines from a synthesis response."""
    return "\n".join(
        line
        for line in text.split("\n")
        if not line.strip().startswith(_NESTED_COMMAND_PREFIXES)
    )


# ---------------------------------------------------------------------------
# Synthesis pass (2nd LLM call after a tool ran)
# ---------------------------------------------------------------------------


def _build_image_context(
    tool_result: dict, session_id: int
) -> list[dict[str, Any]] | None:
    """Build image context for synthesis from tool result."""
    # Try to get image path from markdown or data
    markdown = tool_result.get("markdown", "")
    image_path = parse_image_path(markdown)
    if not image_path:
        # Check data for image_path
        data = tool_result.get("data", {})
        if isinstance(data, dict):
            image_path = data.get("image_path")
    
    if not image_path:
        return None
    
    b64, mime = _load_image_base64(image_path)
    if not (b64 and mime):
        return None
    
    store_visual_context(session_id, b64, mime)
    log.info("attached generated image to synthesis pass")
    return [{"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}]


def _run_synthesis(
    profile: dict[str, Any],
    session_id: int,
    interface: str,
    first_pass_text: str,
    tool_result: dict,
    is_image_tool: bool,
) -> str | None:
    """Run a 2nd LLM pass to narrate around the tool result.

    Returns the cleaned synthesis text, or None when the LLM returned nothing.
    """
    image_context: list[dict[str, Any]] | None = None
    if is_image_tool:
        image_context = _build_image_context(tool_result, session_id)

    # Build context with tool result
    tool_xml = tool_result.get("xml", "")
    
    text, _ = generate_ai_response(
        profile, "", interface, session_id,
        image_content_for_context=image_context,
        tool_result_context=tool_xml,  # v3.1.0: pass tool result for synthesis
    )
    if not text or not text.strip():
        return None

    cleaned = _clean(text)
    nested = detect_command(cleaned)
    if nested:
        if is_image_tool:
            log.info("ignoring nested command in image synthesis")
            cleaned = _strip_nested_commands(cleaned)
        else:
            log.info("executing nested command: /%s", nested["command"])
            tool_name, nested_result = execute_command(nested, session_id=session_id)
            nested_md = nested_result.get("markdown", str(nested_result))
            nested_xml = nested_result.get("xml", nested_md)
            _persist_tool_result(tool_name, nested_xml, nested_md, session_id)
            cleaned = nested_md
    return cleaned


def _stream_synthesis(
    profile: dict[str, Any],
    session_id: int,
    interface: str,
    first_pass_text: str,
    tool_result: dict,
    is_image_tool: bool,
) -> Iterator[tuple[str, str]]:
    """Stream the 2nd LLM pass.

    Yields (chunk, full_so_far) tuples.
    """
    image_context: list[dict[str, Any]] | None = None
    if is_image_tool:
        image_context = _build_image_context(tool_result, session_id)

    tool_xml = tool_result.get("xml", "")
    
    sf = StreamFilter()
    accumulated: list[str] = []
    for chunk in generate_ai_response_streaming(
        profile, "", interface, session_id,
        image_content_for_context=image_context,
        tool_result_context=tool_xml,
    ):
        for safe in sf.feed(chunk):
            accumulated.append(safe)
            yield safe, "".join(accumulated)
    for safe in sf.flush():
        accumulated.append(safe)
        yield safe, "".join(accumulated)


# ---------------------------------------------------------------------------
# Per-turn side effects
# ---------------------------------------------------------------------------


def _post_turn(
    profile: dict[str, Any],
    user_message: str,
    final_response: str,
    session_id: int,
    active_session: dict[str, Any],
) -> None:
    """Auto-rename session, summarize memory, trigger memory pipeline."""
    from app.session_lifecycle import auto_name_session_if_needed
    from app.profile_analysis import (
        should_summarize_memory,
        summarize_memory,
    )

    auto_name_session_if_needed(session_id, active_session)
    if should_summarize_memory(profile, user_message, session_id):
        summarize_memory(profile, user_message, final_response, session_id)
    
    msg_count = Database.get_session_messages_count(session_id)
    if msg_count % _PIPELINE_CHECK_INTERVAL == 0:
        _trigger_memory_pipeline(session_id)
    
    try:
        from app.memory.memory import _clear_request_cache
        _clear_request_cache(session_id)
    except Exception:
        pass
    try:
        from app.memory.retrieval import _clear_embedding_cache
        _clear_embedding_cache()
    except Exception:
        pass


def _trigger_memory_pipeline(session_id: int) -> None:
    try:
        from app.memory.memory import trigger_memory_pipeline_async
        count = Database.get_session_messages_count(session_id)
        if not trigger_memory_pipeline_async(session_id, count):
            log.info("memory pipeline skipped (count=%s)", count)
    except Exception as e:  # noqa: BLE001
        log.warning("memory pipeline trigger failed: %s", e)


# ---------------------------------------------------------------------------
# v3.1.0: Tool execution helpers
# ---------------------------------------------------------------------------


def _execute_tool_from_call(
    tool_call: dict,
    session_id: int,
) -> tuple[str, dict]:
    """Execute a tool from parsed tool_call dict.
    
    Args:
        tool_call: {"name": str, "args": dict}
        session_id: Session ID for tool execution
        
    Returns:
        (tool_name, result_dict) where result_dict has ok, data, markdown, xml
    """
    from app.commands import _TOOL_ALIASES
    
    raw_name = tool_call.get("name", "")
    tool_name = _TOOL_ALIASES.get(raw_name, raw_name)
    args = tool_call.get("args", {})
    
    log.info("executing tool: %s %s", tool_name, args)
    result = execute_tool(tool_name, args, session_id=session_id)
    
    return tool_name, result


def _is_image_tool_result(tool_result: dict) -> bool:
    """Check if tool result contains an image."""
    markdown = tool_result.get("markdown", "")
    if parse_image_path(markdown):
        return True
    data = tool_result.get("data", {})
    if isinstance(data, dict) and data.get("image_path"):
        return True
    return False


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


def handle_user_message(user_message: str, interface: str = "terminal") -> str:
    """Process a user message end-to-end and return the assistant reply.

    v3.1.0 Flow:
      1. Store user message
      2. LLM first pass (may include <tools> block)
      3. If tool detected: store first pass, execute tool, store result, synthesis
      4. If no tool: store response directly
    """
    profile = Database.get_profile()
    if not user_message.strip():
        return "Please enter a message!"

    active_session = Database.get_active_session()
    session_id = active_session["id"]
    cached_images = _cache_images_from_message(user_message)

    # Fast-path: user typed /imagine directly
    stripped = user_message.strip()
    if stripped.startswith("/imagine"):
        prompt = stripped[len("/imagine"):].strip()
        if prompt:
            from app.commands import _TOOL_ALIASES, _parse_args
            raw_name = "imagine"
            tool_name = _TOOL_ALIASES.get(raw_name, raw_name)
            args = _parse_args(raw_name, prompt)
            tool_result = execute_tool(tool_name, args, session_id=session_id)
            tool_xml = tool_result.get("xml", tool_result.get("markdown", ""))
            tool_markdown = tool_result.get("markdown", str(tool_result))
            _persist_tool_result(tool_name, tool_xml, tool_markdown, session_id)
            _post_turn(profile, user_message, tool_markdown, session_id, active_session)
            return tool_markdown
        else:
            return "Please provide a prompt after /imagine. Example: /imagine a cute anime cat"

    try:
        text_response, raw_api_response = generate_ai_response(
            profile, user_message, interface, session_id
        )
    except Exception:
        _persist_user(user_message, session_id, cached_images)
        raise

    _persist_user(user_message, session_id, cached_images)

    if text_response is None:
        log.error("AI provider returned None")
        return ""

    text_response = _clean(text_response) or _EMPTY_RESPONSE_FALLBACK

    if is_markdown_image_shortcut(text_response):
        log.warning(
            "intercepted markdown image shortcut: %s",
            extract_markdown_image_path(text_response),
        )
        return IMAGE_SHORTCUT_WARNING

    # v3.1.0: Single path - check for <tools> block or legacy /command
    sf = StreamFilter()
    # Feed the full response to detect tools
    for _ in sf.feed(text_response):
        pass
    for _ in sf.flush():
        pass

    tool_call = sf.tool_call
    
    # Fallback: check for legacy /command format
    if not tool_call:
        cmd_info = detect_command(text_response)
        if cmd_info:
            tool_call = {
                "name": cmd_info.get("command", ""),
                "args": cmd_info.get("args", {}),
            }

    if not tool_call:
        # No tool - plain response
        Database.add_message("assistant", text_response, session_id=session_id)
        _post_turn(profile, user_message, text_response, session_id, active_session)
        return text_response

    # Tool execution path
    # Store first pass (includes acknowledgment + tool call)
    _persist_first_pass(text_response, session_id)
    
    # Execute tool
    tool_name, tool_result = _execute_tool_from_call(tool_call, session_id)
    tool_xml = tool_result.get("xml", tool_result.get("markdown", ""))
    tool_markdown = tool_result.get("markdown", str(tool_result))
    
    # Store tool result with universal role
    _persist_tool_result(tool_name, tool_xml, tool_markdown, session_id)
    
    # Check if image tool
    is_image_tool = _is_image_tool_result(tool_result)
    
    # Run synthesis
    synthesis = _run_synthesis(
        profile, session_id, interface, text_response, tool_result, is_image_tool
    )

    if synthesis:
        Database.add_message("assistant", synthesis, session_id=session_id)
        final_response = (
            f"{tool_markdown}\n\n{synthesis}" if is_image_tool else synthesis
        )
        _post_turn(profile, user_message, final_response, session_id, active_session)
        return final_response

    _post_turn(profile, user_message, tool_markdown, session_id, active_session)
    return tool_markdown


def handle_user_message_streaming(
    user_message: str,
    interface: str = "terminal",
    provider: str | None = None,
    model: str | None = None,
) -> Iterator[str]:
    """Streaming entrypoint with incremental chunk delivery.

    v3.1.0 Flow:
      1. Stream first pass, detect <tools> block
      2. If tool detected:
         - Emit placeholder event
         - Store first pass
         - Execute tool
         - Emit result event
         - Stream synthesis
      3. If no tool: stream response live
    """
    profile = Database.get_profile()
    if not user_message.strip():
        yield "Please enter a message!"
        return

    active_session = Database.get_active_session()
    session_id = active_session["id"]
    cached_images = _cache_images_from_message(user_message)

    # Fast-path: user typed /imagine directly
    stripped = user_message.strip()
    if stripped.startswith("/imagine"):
        prompt = stripped[len("/imagine"):].strip()
        if prompt:
            from app.commands import _TOOL_ALIASES, _parse_args
            raw_name = "imagine"
            tool_name = _TOOL_ALIASES.get(raw_name, raw_name)
            args = _parse_args(raw_name, prompt)
            
            # v3.1.0: Emit tool_executing event
            yield {
                "type": "tool_executing",
                "name": tool_name,
                "args": args,
            }
            
            tool_result = execute_tool(tool_name, args, session_id=session_id)
            tool_xml = tool_result.get("xml", tool_result.get("markdown", ""))
            tool_markdown = tool_result.get("markdown", str(tool_result))
            _persist_tool_result(tool_name, tool_xml, tool_markdown, session_id)
            
            # v3.1.0: Emit tool_result event
            yield {
                "type": "tool_result",
                "name": tool_name,
                "status": "ok" if tool_result.get("ok", True) else "error",
                "markdown": tool_markdown,
            }
            
            _post_turn(profile, user_message, tool_markdown, session_id, active_session)
            return
        else:
            yield "Please provide a prompt after /imagine. Example: /imagine a cute anime cat"
            return

    sf = StreamFilter()
    visible_chunks: list[str] = []
    
    try:
        for chunk in generate_ai_response_streaming(
            profile, user_message, interface, session_id, provider, model
        ):
            for output in sf.feed(chunk):
                if isinstance(output, dict):
                    # v3.1.0: Placeholder or result event
                    yield output
                else:
                    # Normal text chunk
                    visible_chunks.append(output)
                    yield output
                    
        for output in sf.flush():
            if isinstance(output, dict):
                yield output
            else:
                visible_chunks.append(output)
                yield output
    except Exception:
        _persist_user(user_message, session_id, cached_images)
        raise

    _persist_user(user_message, session_id, cached_images)

    full_response = _clean(sf.full_text) or _EMPTY_RESPONSE_FALLBACK
    visible_response = _clean("".join(visible_chunks))

    log.info("[stream] full_response=%r, sf.tool_call=%s, len=%d",
             full_response[:200], sf.tool_call, len(full_response))

    if is_markdown_image_shortcut(full_response):
        log.warning(
            "intercepted markdown image shortcut (stream): %s",
            extract_markdown_image_path(full_response),
        )
        yield IMAGE_SHORTCUT_WARNING
        return

    tool_call = sf.tool_call
    
    # Fallback: check for legacy /command
    if not tool_call:
        cmd_info = detect_command(full_response)
        if cmd_info:
            tool_call = {
                "name": cmd_info.get("command", ""),
                "args": cmd_info.get("args", {}),
            }

    if not tool_call:
        # No tool - plain response (already streamed)
        text = visible_response or _EMPTY_RESPONSE_FALLBACK
        Database.add_message("assistant", text, session_id=session_id)
        _post_turn(profile, user_message, text, session_id, active_session)
        return

    # Tool execution path
    # Store first pass
    _persist_first_pass(full_response, session_id)
    
    # v3.1.0: Emit tool_executing event before execution
    # (for legacy /command, placeholder wasn't shown during streaming)
    yield {
        "type": "tool_executing",
        "name": tool_call["name"],
        "args": tool_call.get("args", {}),
    }
    
    # Execute tool
    tool_name, tool_result = _execute_tool_from_call(tool_call, session_id)
    tool_xml = tool_result.get("xml", tool_result.get("markdown", ""))
    tool_markdown = tool_result.get("markdown", str(tool_result))
    
    # Store tool result
    _persist_tool_result(tool_name, tool_xml, tool_markdown, session_id)
    
    # Emit tool result event (v3.1.0: proper event for frontend)
    yield {
        "type": "tool_result",
        "name": tool_name,
        "status": "ok" if tool_result.get("ok", True) else "error",
        "markdown": tool_markdown,
    }

    # Check if image tool
    is_image_tool = _is_image_tool_result(tool_result)
    
    # Stream synthesis
    synthesis_chunks: list[str] = []
    full_synthesis = ""
    yielded_synthesis_header = False
    
    try:
        for chunk, full in _stream_synthesis(
            profile, session_id, interface, full_response, tool_result, is_image_tool
        ):
            synthesis_chunks.append(chunk)
            full_synthesis = full
            if not yielded_synthesis_header:
                yield "\n\n" + chunk if is_image_tool else chunk
                yielded_synthesis_header = True
            else:
                yield chunk
    except Exception as e:  # noqa: BLE001
        log.warning("synthesis stream failed, no narration yielded: %s", e)

    synthesis = _clean(full_synthesis) if full_synthesis else None

    if synthesis:
        Database.add_message("assistant", synthesis, session_id=session_id)
        final_response = (
            f"{tool_markdown}\n\n{synthesis}" if is_image_tool else synthesis
        )
        _post_turn(profile, user_message, final_response, session_id, active_session)
    else:
        _post_turn(profile, user_message, tool_markdown, session_id, active_session)
