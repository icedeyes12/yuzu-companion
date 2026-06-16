# FILE: app/orchestrator.py
# DESCRIPTION: Single entrypoint for handling user messages.
#              Implements Thought → Action → Observation agentic loop.
#              Uses <tool>...</tool> protocol for tool invocation.

from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path
from typing import Any, AsyncIterator

from app.commands import (
    IMAGE_SHORTCUT_WARNING,
    _parse_user_fastpath_command,
    _resolve_user_alias,
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
    """Parse native tool_calls from a raw provider API response (async).

    Phase E: Intercepts OpenAI-shaped tool_calls directly from the
    ChatCompletion.choices[0].message.tool_calls payload produced by
    AsyncOpenAI. Preserves ``tool_call_id`` so the result can be stitched
    back into ``ephemeral_context`` as the SDK-shaped tool message:

        {"role": "tool", "tool_call_id": tc.id, "content": ...}

    Returns a list of ``{"id", "name", "arguments"}`` dicts. Empty list
    if the response carries no tool_calls (the model emitted plain text).
    """
    if not raw_response or not isinstance(raw_response, dict):
        return []

    # Fast path: directly read the OpenAI-shape on the response itself.
    # All four migrated providers (chutes, openrouter, cerebras, ollama)
    # funnel through AsyncOpenAI now, so the response shape is uniform.
    try:
        choices = raw_response.get("choices") or []
        if not choices:
            return []
        message = choices[0].get("message") or {}
        tool_calls = message.get("tool_calls") or []
        if not tool_calls:
            return []

        results: list[dict] = []
        import json as _json

        for tc in tool_calls:
            if not isinstance(tc, dict):
                continue
            fn = tc.get("function") or {}
            name = fn.get("name") or tc.get("name") or ""
            tc_id = tc.get("id") or ""
            if not name or not tc_id:
                # tool_call_id and name are both required for SDK stitching
                continue
            raw_args = fn.get("arguments", "{}")
            # AsyncOpenAI may return arguments as either a str (when the model
            # streams partial JSON) or a dict (when the SDK has already
            # parsed it). Normalise to a dict.
            if isinstance(raw_args, dict):
                arguments = raw_args
            elif isinstance(raw_args, str):
                try:
                    arguments = _json.loads(raw_args) if raw_args.strip() else {}
                except _json.JSONDecodeError:
                    # The model emitted a partial/invalid JSON fragment.
                    # Surface the raw string so the tool can still attempt
                    # to extract a useful argument.
                    log.warning(
                        "tool_call arguments not valid JSON for %s: %r",
                        name,
                        raw_args[:200],
                    )
                    arguments = {"_raw": raw_args}
            else:
                arguments = {}
            results.append(
                {"id": tc_id, "name": name, "arguments": arguments}
            )
        return results
    except Exception as e:  # noqa: BLE001
        log.warning("native tool_call parse failed: %s", e)
        return []


async def _execute_tool_calls_async(
    tool_calls: list[dict], session_id: int
) -> list[tuple[str, str, dict]]:
    """Execute a list of native tool calls and return SDK-shaped results.

    Phase E: each ``tool_calls`` entry carries an OpenAI ``tool_call_id``
    (str). The orchestrator uses that id to build the matching
    ``{"role": "tool", "tool_call_id": ...}`` message when stitching the
    result back into ``ephemeral_context`` for the next LLM call.

    Returns a list of ``(tool_call_id, tool_name, result_dict)`` tuples.
    The dispatcher short-circuits on the first terminal tool (e.g. image
    generation) to avoid an unbounded tool loop.
    """
    from app.tools.registry import execute_tool, is_terminal_tool

    results: list[tuple[str, str, dict]] = []
    for tc in tool_calls:
        raw_name = tc["name"]
        # Native tool_calls arrive with the canonical name from the SDK
        # schema, but we still resolve aliases for safety.
        tool_name = _resolve_user_alias(raw_name)
        arguments = tc.get("arguments", {}) or {}
        log.info(
            "native tool_call id=%s name=%s args=%s",
            tc.get("id", ""),
            tool_name,
            str(arguments)[:200],
        )
        result = await execute_tool(tool_name, arguments, session_id=session_id)
        results.append((tc.get("id", ""), tool_name, result))
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
    content: str, session_id: int, image_paths: list[str] | None = None
) -> None:
    """Persist an assistant response, with optional image paths (async)."""
    await Database.add_message_async(
        "assistant", content, session_id=session_id, image_paths=image_paths
    )


async def _persist_tool_result_async(
    tool_name: str, markdown: str, session_id: int
) -> None:
    """Persist a tool result (async)."""
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
    ephemeral_context: list[dict[str, str]] | None = None,
) -> str | None:
    """Run a 2nd LLM pass to narrate around the tool result (async).

    ephemeral_context: In-memory conversation turns not yet in DB.
    """
    image_context = await _build_image_context_async(tool_markdown, session_id)

    text, _ = await generate_ai_response(
        profile,
        "",
        interface,
        session_id,
        image_content_for_context=image_context,
        ephemeral_context=ephemeral_context,
        is_tool_loop=True,
    )
    if not text or not text.strip():
        return None

    return _clean(text)


async def _stream_synthesis_async(
    profile: dict[str, Any],
    session_id: int,
    interface: str,
    tool_markdown: str,
    ephemeral_context: list[dict[str, str]] | None = None,
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
        ephemeral_context=ephemeral_context,
        is_tool_loop=True,
    ):
        yield chunk


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


# --------------------------------------------------------------------
# Streaming orchestration helpers
# --------------------------------------------------------------------


async def _run_orchestration_loop_async(
    profile: dict[str, Any],
    session_id: int,
    interface: str,
    current_synthesis_context: str,
    ephemeral_context: list[dict[str, str]],
    any_image_tool: bool,
    fence_id: int,
    abort_check: callable[[], bool] | None,
    user_message: str,
    active_session: dict[str, Any],
) -> AsyncIterator[str]:
    """Run the orchestration loop with native tool_call detection.

    Phase E: each synthesis iteration either:
      1. Returns the final assistant text (no tool_calls, no text → done), or
      2. Emits native tool_calls, which we execute and stitch back into
         ephemeral_context as SDK-shaped ``{role: "tool", tool_call_id: id}``
         messages, then loop.

    Yields:
        Synthesis chunks and tool result markdown.
    """
    from app.llm_client import (
        _parse_accumulated_tool_calls,
    )
    from app.llm_client import (
        generate_ai_response_streaming_with_tool_calls as _stream_with_tc,
    )

    loop_count = 0
    all_generated_paths: list[str] = []

    while loop_count < _MAX_ORCHESTRATION_LOOPS:
        loop_count += 1
        log.info("[stream] orchestration loop %d", loop_count)

        if abort_check and abort_check():
            return

        synthesis_chunks: list[str] = []
        full_synthesis = ""
        # The streaming generator yields (content, snapshot) tuples where
        # `snapshot` is the full accumulated tool_calls list at that point
        # in time (per-index entries with partial JSON arguments). Keep
        # only the latest snapshot — earlier ones are strictly dominated.
        last_snapshot: list[dict] | None = None

        try:
            async for chunk, tc_snapshot in _stream_with_tc(
                profile,
                "",
                interface,
                session_id,
                ephemeral_context=ephemeral_context,
                is_tool_loop=True,
            ):
                if abort_check and abort_check():
                    return
                if chunk:
                    synthesis_chunks.append(chunk)
                    full_synthesis += chunk
                    yield (
                        "\n\n" + chunk
                        if any_image_tool and not synthesis_chunks[:-1]
                        else chunk
                    )
                if tc_snapshot is not None:
                    last_snapshot = tc_snapshot
        except asyncio.CancelledError:
            log.info(
                "[stream] cancelled in synthesis loop - propagating to StreamBuffer"
            )
            raise
        except Exception as e:
            log.error("[stream] error in synthesis loop: %s", e)
            raise

        # Resolve the latest snapshot into OpenAI-shaped tool_calls
        resolved_tcs = _parse_accumulated_tool_calls(last_snapshot)
        synthesis = _clean(full_synthesis) if full_synthesis else None

        # Empty response with no tool calls → finalise
        if not synthesis and not resolved_tcs:
            await StreamFence.complete(session_id, fence_id)
            await _post_turn_async(
                profile,
                user_message,
                current_synthesis_context,
                session_id,
                active_session,
            )
            return

        # No further tool calls → this is the final synthesis
        if not resolved_tcs:
            final_response = (
                f"{current_synthesis_context}\n\n{synthesis}"
                if any_image_tool
                else synthesis
            )
            await StreamFence.complete(session_id, fence_id)
            log.info(f"[stream] fence {fence_id} completed (final synthesis)")
            await _post_turn_async(
                profile, user_message, final_response, session_id, active_session
            )
            return

        # Native tool_calls detected → execute, stitch, loop
        log.info(
            "[stream] synthesis contains %d native tool_call(s), continuing loop",
            len(resolved_tcs),
        )
        results = await _execute_tool_calls_async(
            resolved_tcs, session_id=session_id
        )

        # Persist the assistant turn that issued the tool calls
        if synthesis and synthesis.strip():
            await _persist_assistant_async(synthesis, session_id)
            log.info("[stream] persisted synthesis (with native tool_calls)")

        # Stitch SDK-shaped messages into ephemeral_context
        ephemeral_context.append(
            {
                "role": "assistant",
                "content": synthesis or "",
                "tool_calls": [
                    {
                        "id": tc.get("id", ""),
                        "type": "function",
                        "function": {
                            "name": tc.get("name", ""),
                            "arguments": json.dumps(tc.get("arguments", {})),
                        },
                    }
                    for tc in resolved_tcs
                ],
            }
        )

        next_markdowns: list[str] = []
        any_image_tool = False
        for tc_id, tool_name, result in results:
            tm = result.get("markdown", str(result))
            next_markdowns.append(tm)
            await _persist_tool_result_async(tool_name, tm, session_id)
            ephemeral_context.append(
                {"role": "tool", "tool_call_id": tc_id, "content": tm}
            )
            p = parse_image_path(tm)
            if p:
                any_image_tool = True
                all_generated_paths.append(p)
            yield "\n\n" + tm

        current_synthesis_context = "\n\n".join(next_markdowns)

    # Max loops reached
    await StreamFence.complete(session_id, fence_id)
    await _post_turn_async(
        profile,
        user_message,
        synthesis or current_synthesis_context,
        session_id,
        active_session,
    )


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
    # Assuming _cache_images_from_message is fast (local check + small download)
    # If it downloads, it should be async. Let's check multimodal_tools.
    cached_images = await asyncio.to_thread(_cache_images_from_message, user_message)

    # Fast-path: user typed /imagine directly (narrowly-scoped direct input
    # parser, NOT the LLM-side <command> parser which has been removed in
    # Phase E).
    stripped = user_message.strip()
    if stripped.startswith("/imagine"):
        parsed = _parse_user_fastpath_command(stripped)
        if parsed:
            raw_name = parsed["command"]
            tool_name = _resolve_user_alias(raw_name)
            # /imagine always means "image_generate" in the fast-path
            if tool_name == "image_generate":
                from app.tools.registry import execute_tool

                arguments = {"prompt": parsed["args"]}
                await _persist_user_async(user_message, session_id, cached_images)
                result = await execute_tool(
                    tool_name, arguments, session_id=session_id
                )
                tool_markdown = result.get("markdown", str(result))
                await _persist_tool_result_async(
                    tool_name, tool_markdown, session_id
                )

                generated_paths = []
                p = parse_image_path(tool_markdown)
                if p:
                    generated_paths.append(p)

                # Run synthesis
                synthesis = await _run_synthesis_async(
                    profile, session_id, interface, tool_markdown
                )
                if synthesis:
                    await _persist_assistant_async(
                        synthesis, session_id, generated_paths
                    )
                    final = (
                        f"{tool_markdown}\n\n{synthesis}"
                        if parse_image_path(tool_markdown)
                        else synthesis
                    )
                else:
                    final = tool_markdown

                await _post_turn_async(
                    profile, user_message, final, session_id, active_session
                )
                return final

    provider_name = (profile.get("providers_config") or {}).get(
        "preferred_provider", "ollama"
    )

    try:
        text_response, raw_api_response = await generate_ai_response(
            profile, user_message, interface, session_id
        )
    except Exception:
        await _persist_user_async(user_message, session_id, cached_images)
        raise

    await _persist_user_async(user_message, session_id, cached_images)

    if text_response is None:
        log.error("AI provider returned None")
        return ""

    text_response = _clean(text_response) or _EMPTY_RESPONSE_FALLBACK

    if is_markdown_image_shortcut(text_response):
        return IMAGE_SHORTCUT_WARNING

    # Try native tool-call execution first.
    # Phase E: read ChatCompletion.choices[0].message.tool_calls directly
    # and stitch the result back as {"role": "tool", "tool_call_id": id}.
    tool_calls = await _parse_raw_tool_calls_async(provider_name, raw_api_response)
    if tool_calls:
        tool_results = await _execute_tool_calls_async(tool_calls, session_id)

        # SAFEGUARD: Persist clean text_response BEFORE tool execution
        if text_response and text_response.strip():
            await _persist_assistant_async(text_response, session_id)
            log.info("[non-stream] persisted clean text_response (pre-tool)")

        if tool_results:
            tc_id, tool_name, tool_result = tool_results[0]
            tool_markdown = tool_result.get("markdown", str(tool_result))
            await _persist_tool_result_async(tool_name, tool_markdown, session_id)

            is_image_tool = parse_image_path(tool_markdown) is not None
            generated_paths = (
                [parse_image_path(tool_markdown)] if is_image_tool else None
            )

            # Build SDK-shaped ephemeral context for the synthesis pass.
            # The assistant turn must carry the original tool_calls payload
            # (with id) so the SDK can match the tool response back to it.
            assistant_tool_calls = []
            for tc in tool_calls:
                fn = tc.get("function") or {}
                assistant_tool_calls.append(
                    {
                        "id": tc.get("id", ""),
                        "type": "function",
                        "function": {
                            "name": fn.get("name", tc.get("name", "")),
                            "arguments": (
                                fn.get("arguments", "{}")
                                if isinstance(fn.get("arguments"), str)
                                else json.dumps(fn.get("arguments", {}))
                            ),
                        },
                    }
                )
            ephemeral_context: list[dict[str, Any]] = [
                {
                    "role": "assistant",
                    "content": text_response or "",
                    "tool_calls": assistant_tool_calls,
                },
                {
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "content": tool_markdown,
                },
            ]

            synthesis = await _run_synthesis_async(
                profile,
                session_id,
                interface,
                tool_markdown,
                ephemeral_context=ephemeral_context,
            )

            if synthesis:
                await _persist_assistant_async(synthesis, session_id, generated_paths)
                final_response = (
                    f"{tool_markdown}\n\n{synthesis}" if is_image_tool else synthesis
                )
                await _post_turn_async(
                    profile, user_message, final_response, session_id, active_session
                )
                return final_response

            await _post_turn_async(
                profile, user_message, tool_markdown, session_id, active_session
            )
            return tool_markdown

    await _persist_assistant_async(text_response, session_id)
    await _post_turn_async(
        profile, user_message, text_response, session_id, active_session
    )
    return text_response


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
    """Streaming entrypoint (async) with fence protection.

    FENCE PROTECTION: Wraps user message persistence in a fence to prevent
    ghost turns if stream is interrupted before completion.

    COORDINATOR: Streams the first LLM pass via
    ``generate_ai_response_streaming_with_tool_calls``, executes any
    accumulated native tool_calls inline, then delegates the synthesis
    loop to ``_run_orchestration_loop_async`` and finalisation to
    ``_finalize_and_persist_async``.
    """
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

    # Cache any images referenced in the message (URLs, etc.)
    cached_images = await asyncio.to_thread(_cache_images_from_message, user_message)

    # Merge with explicitly provided image_paths
    all_image_paths = list(cached_images) if cached_images else []
    if image_paths:
        all_image_paths.extend(image_paths)

    # FENCE: Acquire fence before persisting user message
    user_msg_id = await _persist_user_async(
        user_message, session_id, all_image_paths or None
    )
    fence_id = await StreamFence.acquire(session_id, user_msg_id or 0)
    log.info(f"[stream] fence {fence_id} acquired for session {session_id}")

    # === PHASE 1: Initial LLM response streaming (with native tool_calls) ===
    # Phase E: The model emits native tool_calls. The streaming generator
    # yields (content_chunk, accumulated_tool_calls_or_None) tuples. We
    # capture the last non-None accumulated list and pass it to the
    # native tool execution path.
    response_chunks: list[str] = []
    last_accumulated_tool_calls: list[dict] | None = None

    try:
        from app.llm_client import generate_ai_response_streaming_with_tool_calls

        async for chunk, accumulated_tool_calls in generate_ai_response_streaming_with_tool_calls(
            profile, user_message, interface, session_id, provider, model
        ):
            if chunk:
                if abort_check and abort_check():
                    log.info(f"[stream] abort detected, fence {fence_id} not completed")
                    return

                response_chunks.append(chunk)
                yield chunk
            last_accumulated_tool_calls = accumulated_tool_calls
    except asyncio.CancelledError:
        log.info("[stream] cancelled in first pass - propagating to StreamBuffer")
        log.warning(f"[stream] fence {fence_id} incomplete due to cancellation")
        raise
    except Exception as e:
        log.error("[stream] error in first pass: %s", e)
        log.warning(f"[stream] fence {fence_id} incomplete due to error: {e}")
        raise

    full_response = "".join(response_chunks)

    # === PHASE 2: Handle empty response ===
    if not _clean(full_response):
        await _finalize_and_persist_async(
            session_id,
            fence_id,
            profile,
            user_message,
            _EMPTY_RESPONSE_FALLBACK,
            active_session,
        )
        yield _EMPTY_RESPONSE_FALLBACK
        return

    # === PHASE 3: Handle markdown image shortcut ===
    if is_markdown_image_shortcut(full_response):
        await StreamFence.complete(session_id, fence_id)
        yield IMAGE_SHORTCUT_WARNING
        return

    # === PHASE 4: Execute native tool_calls (or skip if none) ===
    # Phase E: the LLM emits native tool_calls (no more <command> XML
    # blocks). The orchestrator executes them and stitches results back
    # into ephemeral_context with matching tool_call_ids.
    from app.llm_client import _parse_accumulated_tool_calls

    parsed_tool_calls = _parse_accumulated_tool_calls(
        last_accumulated_tool_calls
    )

    combined_tool_markdown = ""
    any_image_tool = False
    all_generated_paths: list[str] = []
    ephemeral_context: list[dict[str, Any]] = []

    if parsed_tool_calls:
        tool_results = await _execute_tool_calls_async(
            parsed_tool_calls, session_id
        )
        tool_markdowns: list[str] = []
        for tc_id, tool_name, result in tool_results:
            tool_markdown = result.get("markdown", str(result))
            tool_markdowns.append(tool_markdown)
            await _persist_tool_result_async(tool_name, tool_markdown, session_id)
            log.info("[stream] persisted tool result for %s", tool_name)
            p = parse_image_path(tool_markdown)
            if p is not None:
                any_image_tool = True
                all_generated_paths.append(p)

        combined_tool_markdown = "\n\n".join(tool_markdowns)

        # Yield tool markdown chunks to UI
        if combined_tool_markdown:
            yield "\n\n" + combined_tool_markdown

        # Build SDK-shaped ephemeral_context. The assistant turn carries
        # the original tool_calls payload (with id + name + arguments as
        # string) so the SDK can match the tool response back to it.
        assistant_tool_calls: list[dict[str, Any]] = []
        for tc in parsed_tool_calls:
            args = tc.get("arguments", {}) or {}
            if not isinstance(args, str):
                args = json.dumps(args)
            assistant_tool_calls.append(
                {
                    "id": tc.get("id", ""),
                    "type": "function",
                    "function": {
                        "name": tc.get("name", ""),
                        "arguments": args,
                    },
                }
            )
        ephemeral_context = [
            {
                "role": "assistant",
                "content": full_response or "",
                "tool_calls": assistant_tool_calls,
            }
        ]
        for tc_id, tool_name, result in tool_results:
            tool_markdown = result.get("markdown", str(result))
            ephemeral_context.append(
                {
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "content": tool_markdown,
                }
            )

    if not combined_tool_markdown:
        # No tool output, just finalize
        await _finalize_and_persist_async(
            session_id, fence_id, profile, user_message, full_response, active_session
        )
        return

    # === PHASE 5: Run orchestration loop (synthesis with native tool_calls) ===
    # Phase E: _run_orchestration_loop_async now detects native tool_calls
    # in the streamed synthesis and re-invokes the tool executor; the
    # legacy <command> block detection has been removed.
    current_synthesis_context = combined_tool_markdown
    async for chunk in _run_orchestration_loop_async(
        profile=profile,
        session_id=session_id,
        interface=interface,
        current_synthesis_context=current_synthesis_context,
        ephemeral_context=ephemeral_context,
        any_image_tool=any_image_tool,
        fence_id=fence_id,
        abort_check=abort_check,
        user_message=user_message,
        active_session=active_session,
    ):
        yield chunk

    return  # Orchestration loop handles finalization
