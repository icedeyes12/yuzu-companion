# FILE: app/tools/http_request.py
# DESCRIPTION: HTTP request tool for external API calls

import os
import requests
import socket
import ipaddress
from urllib.parse import urlparse
from datetime import datetime

from app.tools.schemas import ToolDefinition, ToolParam, error_result, ok_result

MAX_BYTES = 2 * 1024 * 1024
TIMEOUT = 90

TOOL_DEFINITION = ToolDefinition(
    name="http_request",
    description="Make HTTP requests to public HTTPS endpoints. "
                "Use for web searches, fetching data from public APIs, or retrieving content. "
                "Only accepts public HTTPS URLs. Returns text or image content.",
    role="request_tools",
    category="integration",
    execution_mode="external",
    aliases=["request"],
    safety_notes="HTTPS only. Blocks private, loopback, and link-local targets to reduce SSRF risk.",
    parameters=[
        ToolParam(
            name="url",
            description="The full HTTPS URL to request",
            type="string",
            required=True,
        ),
        ToolParam(
            name="method",
            description="HTTP method to use",
            type="string",
            required=False,
            default="GET",
            enum=["GET", "POST", "PUT", "DELETE", "PATCH"],
        ),
        ToolParam(
            name="body",
            description="JSON-serializable body to send with POST/PUT/PATCH requests",
            type="object",
            required=False,
            default=None,
        ),
    ],
    is_terminal=True,
)


def is_safe_public_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        return False
    if not parsed.hostname:
        return False
    try:
        ip = socket.gethostbyname(parsed.hostname)
        ip_obj = ipaddress.ip_address(ip)
        if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local or ip_obj.is_reserved:
            return False
    except Exception:
        return False
    return True


def _get_media_dir():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    media_dir = os.path.join(project_root, "static", "media")
    os.makedirs(media_dir, exist_ok=True)
    return media_dir


def execute(arguments: dict, **kwargs) -> dict:
    from app.database import Database

    profile = Database.get_profile() or {}
    partner_name = profile.get("partner_name", "Yuzu")

    url = (arguments.get("url") or "").strip()
    method = (arguments.get("method") or "GET").strip().upper()
    body = arguments.get("body")

    full_command = f"/request {method} {url}" if method != "GET" else f"/request {url}"

    if not url:
        return error_result(
            "No URL provided",
            TOOL_DEFINITION,
            "/request",
            partner_name,
        )

    if not is_safe_public_url(url):
        return error_result(
            "Unsafe or invalid URL (HTTPS public endpoints only)",
            TOOL_DEFINITION,
            full_command,
            partner_name,
        )

    try:
        req_kwargs = {"timeout": TIMEOUT, "stream": True}
        if body is not None and method in ("POST", "PUT", "PATCH"):
            req_kwargs["json"] = body

        resp = getattr(requests, method.lower())(url, **req_kwargs)

        content = b""
        for chunk in resp.iter_content(8192):
            content += chunk
            if len(content) > MAX_BYTES:
                return error_result(
                    "Response too large (max 2MB)",
                    TOOL_DEFINITION,
                    full_command,
                    partner_name,
                )

        content_type = resp.headers.get("Content-Type", "")
        size = len(content)

        if content_type.startswith("image/"):
            media_dir = _get_media_dir()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            ext = content_type.split("/")[-1].split(";")[0]
            filename = f"{timestamp}.{'jpg' if ext == 'jpeg' else ext}"
            filepath = os.path.join(media_dir, filename)

            with open(filepath, "wb") as f:
                f.write(content)

            return ok_result(
                {
                    "type": "image",
                    "path": f"static/media/{filename}",
                    "content_type": content_type,
                    "size_bytes": size,
                },
                TOOL_DEFINITION,
                full_command,
                partner_name,
            )

        try:
            text = content.decode("utf-8", errors="ignore")
            lines = text.splitlines()[:200]
        except Exception:
            lines = ["Binary content received (non-text, non-image)"]

        return ok_result(
            {
                "type": "text",
                "content": "\n".join(lines),
                "content_type": content_type,
                "size_bytes": size,
                "truncated": len(lines) >= 200,
            },
            TOOL_DEFINITION,
            full_command,
            partner_name,
        )

    except Exception as e:
        print(f"[request_tools] Exception during HTTP request: {e}")
        return error_result(
            "Request failed. Please check the URL or try again later.",
            TOOL_DEFINITION,
            full_command,
            partner_name,
        )
