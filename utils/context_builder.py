import discord

import config
from utils.file_handler import attachment_to_block


async def build_messages(
    channel: discord.TextChannel,
    query: str,
    attachments: list[discord.Attachment] | None = None,
) -> list[dict]:
    """
    Build a single-turn Claude messages list from:
      - Recent channel history as a text context block
      - The user's query text
      - Any file attachments on the current message
    """
    # ── 1. Collect channel history as plain text ──────────────────────────
    lines: list[str] = []
    async for msg in channel.history(limit=config.MAX_CONTEXT_MESSAGES, oldest_first=True):
        if not msg.content and not msg.attachments:
            continue
        ts = msg.created_at.strftime("%Y-%m-%d %H:%M")
        name = msg.author.display_name
        text = msg.content or ""
        line = f"[{ts}] {name}: {text}"
        for att in msg.attachments:
            line += f"  [attached: {att.filename}]"
        lines.append(line)

    # ── 2. Assemble content blocks ────────────────────────────────────────
    content: list[dict] = []

    if lines:
        content.append({
            "type": "text",
            "text": "## Recent channel history\n\n" + "\n".join(lines) + "\n\n---\n",
        })

    content.append({"type": "text", "text": query})

    # ── 3. Attach files from the current message ──────────────────────────
    if attachments:
        for att in attachments:
            block = await attachment_to_block(att)
            if block:
                content.append(block)

    return [{"role": "user", "content": content}]
