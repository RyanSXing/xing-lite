import anthropic
import config

_client = anthropic.AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY)

# Beta header required for Files API
_BETAS = ["files-api-2025-04-14"]


async def chat(messages: list) -> str:
    """Send messages to Claude (Opus 4.6) and return the text response."""
    response = await _client.beta.messages.create(
        model=config.MODEL,
        max_tokens=config.MAX_RESPONSE_TOKENS,
        system=config.SYSTEM_PROMPT,
        messages=messages,
        betas=_BETAS,
    )
    return next(b.text for b in response.content if b.type == "text")


async def plan_server_changes(server_info: str, prompt: str) -> dict:
    """Ask Claude to interpret a natural language prompt and return a JSON action plan."""
    import json

    response = await _client.messages.create(
        model=config.MODEL,
        max_tokens=2048,
        system="""\
You are a Discord server management assistant.
Given the current server structure and a user request, output a JSON plan of actions.

Respond with ONLY valid JSON — no markdown, no explanation — in this exact format:
{
  "summary": "one-line description of what will be done",
  "actions": [
    {"type": "create_category", "name": "..."},
    {"type": "rename_category", "old_name": "...", "new_name": "..."},
    {"type": "delete_category", "name": "..."},
    {"type": "create_channel", "name": "...", "category": "...", "channel_type": "text|voice", "topic": "..."},
    {"type": "rename_channel", "old_name": "...", "new_name": "..."},
    {"type": "set_topic", "channel_name": "...", "topic": "..."},
    {"type": "delete_channel", "name": "..."}
  ]
}

Rules:
- "category" and "topic" are optional on create_channel
- channel_type defaults to "text" if omitted
- Only include actions needed to fulfil the request
- Always create a category before creating channels inside it\
""",
        messages=[
            {
                "role": "user",
                "content": f"Current server structure:\n{server_info}\n\nRequest: {prompt}",
            }
        ],
    )

    text = next(b.text for b in response.content if b.type == "text").strip()
    # Strip markdown code fences if Claude wraps the JSON anyway
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.rsplit("```", 1)[0].strip()

    return json.loads(text)


async def route_message(content: str, channel_names: list[str]) -> list[str]:
    """Return which channel names this message is clearly relevant to."""
    import json

    if not channel_names or not content.strip():
        return []

    response = await _client.messages.create(
        model=config.MODEL,
        max_tokens=128,
        system="You route Discord messages to relevant channels based on content. Be conservative — only route when the relevance is clear.",
        messages=[{
            "role": "user",
            "content": (
                f'Message: "{content}"\n\n'
                f'Available channels: {", ".join(channel_names)}\n\n'
                "Which of these channels is this message clearly relevant to? "
                "Return ONLY a JSON array of matching channel names, e.g. [\"music\", \"news\"]. "
                "Return [] if none are clearly relevant."
            ),
        }],
    )

    text = next(b.text for b in response.content if b.type == "text").strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.rsplit("```", 1)[0].strip()

    try:
        result = json.loads(text)
        return [ch for ch in result if ch in channel_names]
    except Exception:
        return []


async def upload_file(data: bytes, filename: str, mime_type: str) -> str:
    """Upload bytes to the Claude Files API and return the file_id."""
    result = await _client.beta.files.upload(
        file=(filename, data, mime_type),
    )
    return result.id
