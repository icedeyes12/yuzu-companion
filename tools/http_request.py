import os
import json
import socket
import ipaddress
import requests
from urllib.parse import urlparse
from datetime import datetime
import secrets

# ==========================================================
# HTTP REQUEST TOOL
# Production-safe pure backend execution tool
# ==========================================================

MAX_RESPONSE_SIZE = 2 * 1024 * 1024  # 2MB
TIMEOUT_SECONDS = 90

SCHEMA = {
    "type": "function",
    "function": {
        "name": "http_request",
        "description": "Perform a secure HTTPS GET request",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "HTTPS URL to request"
                }
            },
            "required": ["url"]
        }
    }
}

# ==========================================================
# Utility: Validate URL
# ==========================================================

def _is_public_ip(hostname: str) -> bool:
    try:
        ip = socket.gethostbyname(hostname)
        ip_obj = ipaddress.ip_address(ip)

        if (
            ip_obj.is_private
            or ip_obj.is_loopback
            or ip_obj.is_link_local
            or ip_obj.is_reserved
            or ip_obj.is_multicast
        ):
            return False

        return True
    except Exception:
        return False


def _validate_url(url: str):
    parsed = urlparse(url)

    if parsed.scheme != "https":
        return False, "[ERROR:TOOL_UNSAFE_URL] HTTPS only allowed"

    if not parsed.hostname:
        return False, "[ERROR:TOOL_UNSAFE_URL] Invalid hostname"

    if not _is_public_ip(parsed.hostname):
        return False, "[ERROR:TOOL_UNSAFE_URL] Private or unsafe IP blocked"

    return True, None


# ==========================================================
# Utility: Save image
# ==========================================================

def _save_image(content: bytes, content_type: str) -> str:
    project_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..")
    )
    media_dir = os.path.join(project_root, "static", "media")

    os.makedirs(media_dir, exist_ok=True)

    extension = "jpg"
    if "png" in content_type:
        extension = "png"
    elif "webp" in content_type:
        extension = "webp"

    filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{secrets.token_hex(4)}.{extension}"
    file_path = os.path.join(media_dir, filename)

    with open(file_path, "wb") as f:
        f.write(content)

    return f"static/media/{filename}"


# ==========================================================
# MAIN EXECUTION
# ==========================================================

def execute(arguments, **kwargs):
    url = arguments.get("url")

    if not url:
        return "[ERROR:HTTP_400] No URL provided"

    is_valid, error = _validate_url(url)
    if not is_valid:
        return error

    try:
        response = requests.get(
            url,
            timeout=TIMEOUT_SECONDS,
            allow_redirects=False,
            stream=True
        )

        # Redirect validation
        if 300 <= response.status_code < 400:
            location = response.headers.get("Location")
            if not location:
                return "[ERROR:HTTP_REDIRECT_INVALID] Missing redirect location"

            is_valid, error = _validate_url(location)
            if not is_valid:
                return "[ERROR:HTTP_REDIRECT_BLOCKED] Unsafe redirect target"

            response = requests.get(
                location,
                timeout=TIMEOUT_SECONDS,
                stream=True
            )

        # HTTP status handling
        if response.status_code == 404:
            return "[ERROR:HTTP_404]"
        if response.status_code == 403:
            return "[ERROR:HTTP_403]"
        if response.status_code == 429:
            return "[ERROR:HTTP_429]"
        if response.status_code >= 500:
            return f"[ERROR:HTTP_{response.status_code}]"

        # Size validation
        content_length = response.headers.get("Content-Length")
        if content_length and int(content_length) > MAX_RESPONSE_SIZE:
            return "[ERROR:TOOL_RESPONSE_TOO_LARGE]"

        content = response.content

        if len(content) > MAX_RESPONSE_SIZE:
            return "[ERROR:TOOL_RESPONSE_TOO_LARGE]"

        content_type = response.headers.get("Content-Type", "")

        # ======================================================
        # JSON
        # ======================================================
        if "application/json" in content_type:
            try:
                parsed = response.json()
                return json.dumps(parsed, indent=2)
            except Exception:
                return "[ERROR:INVALID_JSON_RESPONSE]"

        # ======================================================
        # TEXT
        # ======================================================
        if "text/" in content_type:
            return content.decode(errors="ignore")

        # ======================================================
        # IMAGE
        # ======================================================
        if "image/" in content_type:
            image_path = _save_image(content, content_type)
            return json.dumps({
                "image_path": image_path,
                "content_type": content_type,
                "size_bytes": len(content)
            })

        # ======================================================
        # BINARY
        # ======================================================
        return json.dumps({
            "content_type": content_type,
            "size_bytes": len(content)
        })

    except requests.exceptions.Timeout:
        return "[ERROR:NETWORK_TIMEOUT]"
    except requests.exceptions.ConnectionError:
        return "[ERROR:NETWORK_DNS_FAILURE]"
    except Exception as e:
        return f"[ERROR:TOOL_EXECUTION_FAILED] {str(e)}"