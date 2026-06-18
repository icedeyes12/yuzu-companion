# FILE: app/orchestrator.py
# DESCRIPTION: Single entrypoint for handling user messages.
#              Implements Thought → Action → Observation agentic loop.
#              Uses <tool>...</tool> protocol for tool invocation.

from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path
from typing import Any, AsyncIterator

from app.commands import (
    IMAGE_SHORTCUT_WARNING,
    is_markdown_image_shortcut,
    parse_image_path,
)
from app.db import Database
from app.llm_client import (
    generate_ai_response,
    generate_ai_response_streaming,
)
from app.logging_config import get_logger
from app.services.session_service import SessionService
from app.services.memory_service import MemoryService
from app.tools import multimodal_tools
from app.tools.schemas import get_openai_tools
from app.tools.registry import get_tool_role
from app.visual_context import store_visual_context

log = get_logger(__name__)

_TIMESTAMP_SUFFIX = re.compile(r"\s*\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\]\s*$")
_EMPTY_RESPONSE_FALLBACK = "I'm having trouble responding right now. Please try again."
_MD_IMAGE_PATTERN = re.compile(r"!\[[^\]]{0,200}\]\(([^)]{1,200})\)")

# Services

# Maximum orchestration loops to prevent runaway execution
_MAX_ORCHESTRATION_LOOPS = 30

# Stream fence timeout - incomplete streams abandoned after this duration (seconds)
_STREAM_FENCE_TIMEOUT = 300  # 5 minutes

# Allowed image directories (resolved at module load, not runtime)
_BASE_DIR = Path(__file__).resolve().parent.parent
_ALLOWED_IMAGE_DIRS = [
    (_BASE_DIR / "static").resolve(),
    (_BASE_DIR / "static" / "uploads").resolve(),
    (_BASE_DIR / "static" / "generated_images").resolve(),
    (_BASE_DIR / "uploads").resolve(),
    (_BASE_DIR / "generated_images").resolve(),
]
_ALLOWED_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


def _validate_image_path_safely(user_path: str) -> Path | None:
    """Validate a user-provided image path by searching trusted directories.

    SECURITY: This function NEVER constructs paths from user input directly.
    Instead, it extracts ONLY the filename (using os.path.basename) and
    searches for it in pre-defined trusted directories.

    This breaks the CodeQL taint chain completely - no part of the user's
    path string is used in path construction.

    Returns:
        Path object if valid image found, None otherwise.
    """
    if not user_path or not isinstance(user_path, str):
        return None

    # SECURITY: Extract ONLY the filename - this removes all directory components
    # and ensures no path traversal is possible. The filename is just a string
    # that we use to search in OUR trusted directories.
    filename = os.path.basename(user_path.replace("\\", "/"))

    if not filename:
        return None

    # Validate filename is not dangerous (defensive)
    if filename.startswith(".") or ".." in filename:
        log.warning("suspicious filename rejected: %s", filename[:50])
        return None

    # Check extension
    ext = Path(filename).suffix.lower()
    if ext not in _ALLOWED_IMAGE_EXTS:
        return None

    # SECURITY: Search ONLY in pre-resolved trusted directories
    # We construct paths using our constants, NOT user input
    for trusted_dir in _ALLOWED_IMAGE_DIRS:
        # Construct candidate using TRUSTED base + filename only
        candidate = trusted_dir / filename

        try:
            # Resolve and verify
            resolved = candidate.resolve()

            # Must exist and be a regular file
            if not resolved.is_file():
                continue

            # Verify resolved path is still within trusted_dir
            # (handles symlinks that might escape)
            try:
                rel = os.path.relpath(str(resolved), str(trusted_dir))
                if rel.startswith(".."):
                    log.warning("path escaped trusted dir: %s", filename[:50])
                    continue
            except ValueError:
                continue

            # Additional symlink check
            if resolved.is_symlink():
                log.warning("symlink rejected: %s", filename[:50])
                continue

            return resolved

        except (OSError, ValueError):
            continue

    return None


# --------------------------------------------------------------------
# Image-cache helpers
# --------------------------------------------------------------------


def _cache_uploaded_images(message: str) -> list[str]:
    """Extract image paths from uploaded-images marker, with path validation."""
    if "UPLOADED_IMAGES:" not in message or "IMAGE_UPLOAD:" not in message:
        return []

    paths: list[str] = []

    for line in message.split("\n"):
        if line.startswith("IMAGE_UPLOAD:"):
            user_path = line[len("IMAGE_UPLOAD:") :].strip()

            # Use the safe validator
            validated = _validate_image_path_safely(user_path)
            if validated:
                paths.append(str(validated))

    return paths


def _cache_images_from_message(message: str) -> list[str]:
    """Resolve image references in message to local cache paths, with validation."""
    uploaded = _cache_uploaded_images(message)
    if uploaded:
        return uploaded

    cached: list[str] = []
    for match in _MD_IMAGE_PATTERN.finditer(message):
        source = match.group(1)

        # Limit source length to prevent ReDoS
        if len(source) > 500:
            source = source[:500]

        if source.startswith(("static/", "uploads/", "generated_images/")):
            # Use the safe validator
            validated = _validate_image_path_safely(source)
            if validated:
                cached.append(str(validated))
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
    """Return (base64, mime) for a generated image file, or (None, None)."""
    import base64

    # Use the safe validator - this is the key for CodeQL
    validated_path = _validate_image_path_safely(image_path)
    if not validated_path:
        return None, None

    try:
        data = base64.b64encode(validated_path.read_bytes()).decode("utf-8")
    except OSError as e:
        log.warning("image read failed (%s): %s", validated_path, e)
        return None, None

    suffix = validated_path.suffix.lower()
    if suffix == ".png":
        mime = "image/png"
    elif suffix == ".gif":
        mime = "image/gif"
    else:
        mime = "image/jpeg"
    return data, mime


# --------------------------------------------------------------------
# Native tool-call helpers (for providers that support it)
# --------------------------------------------------------------------


async def _parse_raw_tool_calls_async(
    provider_name: str, raw_response: dict | None
) -> list[dict]:
    """Parse tool_calls from a raw provider API response (async)."""
    if not raw_response:
        return []
    try:
        # WORKAROUND: Lazy import to prevent circular dependency with app.providers
        from app.providers import get_ai_manager

        manager = await get_ai_manager()
        provider = manager.providers.get(provider_name)
        if not provider:
            return []
        calls = provider.parse_tool_calls(raw_response)
        return [
            {"name": c["name"], "arguments": c["arguments"]}
            for c in calls
            if c.get("name")
        ]
    except Exception:
        return []


async def _execute_tool_calls_async(
    tool_calls: list[dict], session_id: int
) -> list[tuple[str, dict]]:
    """Execute a list of tool calls and return results (async)."""
    from app.commands import _TOOL_ALIASES
    from app.tools.registry import execute_tool, is_terminal_tool

    results: list[tuple[str, dict, str]] = []
    for tc in tool_calls:
        raw_name = tc["name"]
        tool_name = _TOOL_ALIASES.get(raw_name, raw_name)
        arguments = tc.get("arguments", {})
        log.info("native tool_call: %s %s", tool_name, arguments)
        result = await execute_tool(tool_name, arguments, session_id=session_id)
        results.append((tool_name, result, tc.get("id", "")))
        if is_terminal_tool(tool_name) and result.get("ok"):
            break
    return results


# --------------------------------------------------------------------
# Response post-processing
# --------------------------------------------------------------------


def _clean(text: str) -> str:
    return _TIMESTAMP_SUFFIX.sub("", text).strip()


async def _persist_user_async(
    message: str, session_id: int, image_paths: list[str] | None
) -> None:
    await Database.add_message_async(
        "user", message, session_id=session_id, image_paths=image_paths or None
    )


async def _persist_assistant_async(
    content: str,
    session_id: int,
    image_paths: list[str] | None = None,
    tool_calls: list[dict] | None = None,
) -> None:
    """Persist an assistant response, with optional image paths (async)."""
    await Database.add_message_async(
        "assistant",
        content,
        session_id=session_id,
        image_paths=image_paths,
        tool_calls=tool_calls,
    )


async def _persist_tool_result_async(
    tool_name: str,
    markdown: str | None,
    session_id: int,
    tool_call_id: str | None = None,
) -> None:
    """Persist a tool result (async)."""
    if markdown is None:
        markdown = "Executed successfully without output."
    from app.commands import parse_image_path

    image_paths = []
    path = parse_image_path(markdown)
    if path:
        image_paths.append(path)

    await Database.add_message_async(
        get_tool_role(tool_name),
        markdown,
        session_id=session_id,
        image_paths=image_paths or None,
        tool_call_id=tool_call_id,
    )


async def _persist_observation_async(observation: str, session_id: int) -> None:
    """Persist a system observation as an internal message (async)."""
    await Database.add_message_async(
        "system_observation", observation, session_id=session_id
    )


# --------------------------------------------------------------------
# Synthesis pass (2nd LLM call after tools ran)
# --------------------------------------------------------------------


async def _build_image_context_async(
    tool_markdown: str, session_id: int
) -> list[dict[str, Any]] | None:
    image_path = parse_image_path(tool_markdown)
    if not image_path:
        return None
    # Assuming _load_image_base64 is fast or run it in thread if needed
    # It reads bytes, so better to use asyncio.to_thread if it's not already
    b64, mime = await asyncio.to_thread(_load_image_base64, image_path)
    if not (b64 and mime):
        return None
    # Assuming store_visual_context is fast/local
    store_visual_context(session_id, b64, mime)
    log.info("attached generated image to synthesis pass")
    return [{"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}]


async def _run_synthesis_async(
    profile: dict[str, Any],
    session_id: int,
    interface: str,
    tool_markdown: str,
) -> str | None:
    """Run a 2nd LLM pass to narrate around the tool result (async)."""
    image_context = await _build_image_context_async(tool_markdown, session_id)

    response = await generate_ai_response(
        profile,
        "",
        interface,
        session_id,
        image_content_for_context=image_context,
        is_tool_loop=True,
        tools=get_openai_tools(),
    )
    if not response or not response.choices or not response.choices[0].message.content:
        return None

    text = response.choices[0].message.content
    if not text or not text.strip():
        return None

    return _clean(text)


async def _stream_synthesis_async(
    profile: dict[str, Any],
    session_id: int,
    interface: str,
    tool_markdown: str,
) -> AsyncIterator[str]:
    """Stream the 2nd LLM pass (async).

    ephemeral_context: In-memory conversation turns not yet in DB.
    Contains the assistant's first-pass response with <command> blocks
    and the tool results, ensuring the LLM has full context.
    """
    image_context = await _build_image_context_async(tool_markdown, session_id)

    async for chunk in generate_ai_response_streaming(
        profile,
        "",
        interface,
        session_id,
        image_content_for_context=image_context,
        is_tool_loop=True,
        tools=get_openai_tools(),
    ):
        if hasattr(chunk, "choices") and chunk.choices:
            delta = chunk.choices[0].delta
            if getattr(delta, "content", None):
                yield delta.content


# --------------------------------------------------------------------
# Per-turn side effects
# --------------------------------------------------------------------

_PIPELINE_CHECK_INTERVAL = 5


async def _post_turn_async(
    profile: dict[str, Any],
    user_message: str,
    final_response: str,
    session_id: int,
    active_session: dict[str, Any],
) -> None:
    """Auto-rename session, summarize memory, trigger memory pipeline (async)."""
    # Auto-rename via service
    await SessionService.auto_name_session_if_needed_async(session_id, active_session)

    # Memory checks via service
    await MemoryService.run_per_message_checks_async(
        profile, user_message, final_response, session_id, active_session
    )

    # Clear request-scoped caches
    # _clear_request_cache was removed in Phase 2B safe deletions
    try:
        from app.memory.retrieval import _clear_embedding_cache

        _clear_embedding_cache()
    except Exception:
        pass


async def _finalize_and_persist_async(
    session_id: int,
    fence_id: int,
    profile: dict[str, Any],
    user_message: str,
    final_response: str,
    active_session: dict[str, Any],
) -> None:
    """Complete the stream fence and persist final state.

    This is the final cleanup step for a completed stream.
    """
    await StreamFence.complete(session_id, fence_id)
    log.info(f"[stream] fence {fence_id} completed")
    await _post_turn_async(
        profile, user_message, final_response, session_id, active_session
    )


# --------------------------------------------------------------------
# Public entry points
# --------------------------------------------------------------------


async def handle_user_message(user_message: str, interface: str = "terminal") -> str:
    """Process a user message end-to-end and return the assistant reply (async)."""
    profile = await Database.get_profile_async()
    if not user_message.strip():
        return "Please enter a message!"

    active_session = await Database.get_active_session_async()
    session_id = active_session["id"]
    cached_images = await asyncio.to_thread(_cache_images_from_message, user_message)

    stripped = user_message.strip()
    if stripped.startswith("/imagine "):
        # Direct /imagine shortcut — route to image_generate tool without LLM round-trip
        prompt = stripped[len("/imagine "):].strip()
        await _persist_user_async(user_message, session_id, cached_images)
        from app.tools.registry import execute_tool

        result = await execute_tool(
            "image_generate", {"prompt": prompt}, session_id=session_id
        )
        tool_markdown = result.get("markdown") or "Image generation failed."
        await _persist_tool_result_async(
            "image_generate", tool_markdown, session_id, tool_call_id=None
        )
        await _post_turn_async(
            profile, user_message, tool_markdown, session_id, active_session
        )
        return tool_markdown

    await _persist_user_async(user_message, session_id, cached_images)

    loop_count = 0
    final_response_text = ""
    start_time = asyncio.get_event_loop().time()

    while loop_count < _MAX_ORCHESTRATION_LOOPS:
        loop_count += 1
        if (
            asyncio.get_event_loop().time() - start_time > 900
        ):  # 15 minutes absolute timeout
            log.warning("[non-stream] 15-minute timeout reached")
            break

        try:
            response = await generate_ai_response(
                profile,
                user_message,
                interface,
                session_id,
                tools=get_openai_tools(),
                is_tool_loop=(loop_count > 1),
            )
        except Exception:
            raise

        if response is None:
            log.error("AI provider returned None")
            return final_response_text

        text_response = response.choices[0].message.content or ""
        text_response = _clean(text_response)

        finish_reason = getattr(response.choices[0], "finish_reason", None)

        tool_calls = []
        if getattr(response.choices[0].message, "tool_calls", None):
            import json as _json

            for tc in response.choices[0].message.tool_calls:
                try:
                    tool_calls.append(
                        {
                            "name": tc.function.name,
                            "arguments": _json.loads(tc.function.arguments),
                            "id": tc.id,
                        }
                    )
                except Exception:
                    pass

        tool_calls = tool_calls[:3]

        # Apply fallback only if there's no text AND no tool calls
        if not text_response and not tool_calls:
            text_response = _EMPTY_RESPONSE_FALLBACK

        tc_dicts = None
        if getattr(response.choices[0].message, "tool_calls", None):
            tc_dicts = [
                tc.model_dump() for tc in response.choices[0].message.tool_calls
            ][:3]

        if text_response.strip() or tc_dicts:
            await _persist_assistant_async(
                text_response, session_id, tool_calls=tc_dicts
            )

        final_response_text = text_response

        if not tool_calls and finish_reason != "tool_calls":
            break

        if not tool_calls:
            break

        tool_results = await _execute_tool_calls_async(tool_calls, session_id)

        tool_markdowns = []
        terminal_tool_executed = False
        for tool_name, tool_result, tc_id in tool_results:
            tool_markdown = tool_result.get("markdown")
            if tool_markdown is None:
                tool_markdown = (
                    str(tool_result)
                    if tool_result is not None
                    else "Executed successfully without output."
                )
            tool_markdowns.append(tool_markdown)

            from app.tools.registry import is_terminal_tool

            if is_terminal_tool(tool_name):
                terminal_tool_executed = True

            await _persist_tool_result_async(
                tool_name, tool_markdown, session_id, tool_call_id=tc_id
            )

        if terminal_tool_executed:
            log.info("[orchestrator] Terminal tool executed, skipping synthesis pass")
            break

    await _post_turn_async(
        profile, user_message, final_response_text, session_id, active_session
    )
    return final_response_text


class StreamFence:
    """Prevents race conditions between user message persistence and stream completion.

    Each stream gets a unique fence ID that must be cleared after successful completion.
    Abandoned fences expire after timeout to prevent deadlocks.
    """

    _fences: dict[int, dict[str, Any]] = {}  # session_id -> fence_info
    _lock = asyncio.Lock()

    @classmethod
    async def acquire(cls, session_id: int, user_msg_id: int) -> str:
        """Acquire a fence for a streaming session. Returns fence_id."""
        import uuid

        fence_id = str(uuid.uuid4())[:8]
        async with cls._lock:
            cls._fences[session_id] = {
                "fence_id": fence_id,
                "user_msg_id": user_msg_id,
                "acquired_at": asyncio.get_event_loop().time(),
                "completed": False,
            }
        return fence_id

    @classmethod
    async def complete(cls, session_id: int, fence_id: str) -> bool:
        """Mark fence as completed, allowing persistence."""
        async with cls._lock:
            if session_id in cls._fences:
                fence = cls._fences[session_id]
                if fence["fence_id"] == fence_id:
                    fence["completed"] = True
                    return True
        return False

    @classmethod
    async def is_completed(cls, session_id: int) -> bool:
        """Check if fence is completed or expired."""
        async with cls._lock:
            if session_id not in cls._fences:
                return True  # No fence = already cleared

            fence = cls._fences[session_id]
            elapsed = asyncio.get_event_loop().time() - fence["acquired_at"]

            # If completed or expired, clear it
            if fence["completed"] or elapsed > _STREAM_FENCE_TIMEOUT:
                del cls._fences[session_id]
                return True

            return False

    @classmethod
    async def cleanup_expired(cls) -> None:
        """Remove all expired fences."""
        async with cls._lock:
            now = asyncio.get_event_loop().time()
            expired = [
                sid
                for sid, fence in cls._fences.items()
                if now - fence["acquired_at"] > _STREAM_FENCE_TIMEOUT
            ]
            for sid in expired:
                del cls._fences[sid]


async def handle_user_message_streaming(
    user_message: str,
    interface: str = "terminal",
    session_id: int | None = None,
    provider: str | None = None,
    model: str | None = None,
    abort_check: callable[[], bool] | None = None,
    image_paths: list[str] | None = None,
) -> AsyncIterator[str]:
    profile = await Database.get_profile_async()
    if not user_message.strip() and not image_paths:
        yield "Please enter a message!"
        return

    if abort_check and abort_check():
        return

    if session_id is None:
        active_session = await Database.get_active_session_async()
        session_id = active_session["id"]
    else:
        active_session = {"id": session_id}

    cached_images = await asyncio.to_thread(_cache_images_from_message, user_message)
    all_image_paths = list(cached_images) if cached_images else []
    if image_paths:
        all_image_paths.extend(image_paths)

    user_msg_id = await _persist_user_async(
        user_message, session_id, all_image_paths or None
    )
    fence_id = await StreamFence.acquire(session_id, user_msg_id or 0)
    log.info(f"[stream] fence {fence_id} acquired for session {session_id}")

    loop_count = 0
    final_full_response = ""
    any_image_tool = False
    start_time = asyncio.get_event_loop().time()

    while loop_count < _MAX_ORCHESTRATION_LOOPS:
        loop_count += 1
        log.info("[stream] orchestration loop %d", loop_count)

        if asyncio.get_event_loop().time() - start_time > 900:  # 15 minutes
            log.warning("[stream] 15-minute timeout reached, breaking loop")
            break

        if abort_check and abort_check():
            log.info(f"[stream] abort detected, fence {fence_id} not completed")
            return

        response_chunks = []
        tool_call_acc = {}
        finish_reason = None

        try:
            async for chunk in generate_ai_response_streaming(
                profile,
                user_message,
                interface,
                session_id,
                provider,
                model,
                is_tool_loop=(loop_count > 1),
                tools=get_openai_tools(),
            ):
                if abort_check and abort_check():
                    log.info(f"[stream] abort detected in loop {loop_count}")
                    return

                if hasattr(chunk, "choices") and chunk.choices:
                    delta = chunk.choices[0].delta

                    if getattr(delta, "content", None):
                        response_chunks.append(delta.content)
                        # Strip Gemma TEE leaked tool syntax from visible stream
                        visible = delta.content
                        if "<|tool_call>" in visible:
                            visible = visible.split("<|tool_call>")[0]
                        if "<tool_call|>" in visible:
                            visible = visible.split("<tool_call|>")[0]

                        if visible:
                            if any_image_tool and not response_chunks[:-1]:
                                yield "\n\n" + visible
                            else:
                                yield visible

                    if getattr(delta, "tool_calls", None):
                        for tc_delta in delta.tool_calls:
                            idx = getattr(tc_delta, "index", 0)
                            if idx not in tool_call_acc:
                                tool_call_acc[idx] = {
                                    "name": "",
                                    "arguments": "",
                                    "id": "",
                                }
                            if getattr(tc_delta, "id", None):
                                tool_call_acc[idx]["id"] = tc_delta.id
                            if getattr(tc_delta, "function", None):
                                if getattr(tc_delta.function, "name", None):
                                    tool_call_acc[idx]["name"] += tc_delta.function.name
                                if getattr(tc_delta.function, "arguments", None):
                                    tool_call_acc[idx]["arguments"] += (
                                        tc_delta.function.arguments
                                    )

                    finish_reason = getattr(chunk.choices[0], "finish_reason", None)
                    if finish_reason == "tool_calls":
                        break
        except asyncio.CancelledError:
            log.info("[stream] cancelled - propagating to StreamBuffer")
            raise
        except Exception as e:
            log.error("[stream] error in loop %d: %s", loop_count, e)
            raise

        full_response = "".join(response_chunks)
        final_full_response = full_response

        import re

        # Auto-close cognitive blocks
        for tag in ["analysis", "think", "decision"]:
            open_pattern = re.compile(
                rf"^[ \t]*<{tag}>[ \t]*$", re.IGNORECASE | re.MULTILINE
            )
            close_pattern = re.compile(
                rf"^[ \t]*</{tag}>[ \t]*$", re.IGNORECASE | re.MULTILINE
            )
            open_count = len(open_pattern.findall(full_response))
            close_count = len(close_pattern.findall(full_response))
            if open_count > close_count:
                closing_tag = f"\n</{tag}>\n" * (open_count - close_count)
                full_response += closing_tag
                final_full_response += closing_tag
                yield closing_tag

        # --- Fallback for Gemma TEE native tool calls leaked as text ---
        import json as _json
        import uuid

        gemma_tool_pattern = re.compile(
            r"<\|tool_call>call:([a-zA-Z0-9_]+)\{(.*?)\}<tool_call\|>", re.DOTALL
        )
        gemma_matches = list(gemma_tool_pattern.finditer(full_response))

        if not tool_call_acc and gemma_matches:
            for match in gemma_matches:
                name = match.group(1)
                args_str = match.group(2)
                args = {}
                arg_pattern = re.compile(
                    r'([a-zA-Z0-9_]+):<\|"\|>(.*?)<\|"\|>', re.DOTALL
                )
                for arg_match in arg_pattern.finditer(args_str):
                    args[arg_match.group(1)] = arg_match.group(2)

                tc_id = "chatcmpl-tool-" + uuid.uuid4().hex[:16]
                tool_call_acc[tc_id] = {
                    "id": tc_id,
                    "name": name,
                    "arguments": _json.dumps(args),
                }

            # Clean up the text
            full_response = gemma_tool_pattern.sub("", full_response)
            full_response = full_response.replace(
                "I'm having trouble responding right now. Please try again.", ""
            ).strip()
            final_full_response = full_response

            finish_reason = "tool_calls"
        # ---------------------------------------------------------------

        if not tool_call_acc and finish_reason != "tool_calls":
            if loop_count == 1:
                if not _clean(full_response):
                    final_full_response = _EMPTY_RESPONSE_FALLBACK
                    yield _EMPTY_RESPONSE_FALLBACK
                elif is_markdown_image_shortcut(full_response):
                    final_full_response = IMAGE_SHORTCUT_WARNING
                    yield IMAGE_SHORTCUT_WARNING

            import re

            clean_db_response = re.sub(
                r"<tools>.*?</tools>", "", final_full_response, flags=re.DOTALL
            ).strip()
            await _persist_assistant_async(clean_db_response, session_id)
            break

        tool_calls_list = []
        import json as _json

        for tc in list(tool_call_acc.values())[:3]:  # Limit to 3 tools
            try:
                tool_calls_list.append(
                    {
                        "name": tc["name"],
                        "arguments": _json.loads(tc["arguments"]),
                        "id": tc["id"],
                    }
                )
            except Exception:
                pass

        if not tool_calls_list:
            await _persist_assistant_async(final_full_response, session_id)
            break

        # Format tcalls strictly to OpenAI spec
        tcalls = []
        for tc in list(tool_call_acc.values())[:3]:
            tcalls.append(
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {"name": tc["name"], "arguments": tc["arguments"]},
                }
            )

        await _persist_assistant_async(
            final_full_response, session_id, tool_calls=tcalls
        )

        results = await _execute_tool_calls_async(tool_calls_list, session_id)

        tool_markdowns = []
        generated_image_paths: list[str] = []
        for tool_name, result, tc_id in results:
            tm = result.get("markdown")
            if tm is None:
                tm = (
                    str(result)
                    if result is not None
                    else "Executed successfully without output."
                )
            tool_markdowns.append(tm)
            p = parse_image_path(tm)
            if p:
                generated_image_paths.append(p)
                any_image_tool = True

            await _persist_tool_result_async(
                tool_name, tm, session_id, tool_call_id=tc_id
            )

        combined_tool_markdown = "\n\n".join(tool_markdowns)
        if combined_tool_markdown:
            yield "\n\n" + combined_tool_markdown

        # Issue 1 fix: inject generated images into vision context for next pass
        # so the AI can actually "see" what it generated, not just assume
        if generated_image_paths:
            for img_path in generated_image_paths:
                b64, mime = await asyncio.to_thread(_load_image_base64, img_path)
                if b64 and mime:
                    store_visual_context(session_id, b64, mime)
                    log.info(
                        "[stream] injected generated image into visual context: %s",
                        img_path,
                    )

    import re

    clean_final_response = re.sub(
        r"<tools>.*?</tools>", "", final_full_response, flags=re.DOTALL
    ).strip()
    await _finalize_and_persist_async(
        session_id,
        fence_id,
        profile,
        user_message,
        clean_final_response,
        active_session,
    )
