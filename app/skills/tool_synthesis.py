# FILE: app/skills/tool_synthesis.py
# DESCRIPTION: Skill helper for the post-tool synthesis pass.

from app.tools.schemas import GenerateResult


def run_tool_synthesis(
    profile,
    interface: str,
    session_id,
    image_content_for_context=None,
):
    """Run the post-tool synthesis pass.

    This is a small skill-style workflow that reuses the main response
    generator to turn tool output into a natural language follow-up.
    """
    from app.app import generate_ai_response

    second_result = generate_ai_response(
        profile,
        "",
        interface,
        session_id,
        image_content_for_context=image_content_for_context,
        tools=None,
    )

    if isinstance(second_result, GenerateResult):
        return second_result.text or ""

    return (second_result or "").strip()
