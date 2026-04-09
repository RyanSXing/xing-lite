import os
import aiohttp
import discord

import claude_client
from database import get_file_id, save_file_id

# Maps file extension → (MIME type, Claude block type)
_SUPPORTED: dict[str, tuple[str, str]] = {
    ".jpg":  ("image/jpeg",       "image"),
    ".jpeg": ("image/jpeg",       "image"),
    ".png":  ("image/png",        "image"),
    ".gif":  ("image/gif",        "image"),
    ".webp": ("image/webp",       "image"),
    ".pdf":  ("application/pdf",  "document"),
    ".txt":  ("text/plain",       "document"),
    ".md":   ("text/plain",       "document"),
    ".py":   ("text/plain",       "document"),
    ".js":   ("text/plain",       "document"),
    ".ts":   ("text/plain",       "document"),
    ".json": ("application/json", "document"),
    ".csv":  ("text/csv",         "document"),
    ".html": ("text/html",        "document"),
}


async def attachment_to_block(attachment: discord.Attachment) -> dict | None:
    """
    Convert a Discord attachment to a Claude content block using the Files API.
    Returns None if the file type is unsupported.
    Caches file_id in SQLite so the same file is never uploaded twice.
    """
    ext = os.path.splitext(attachment.filename.lower())[1]
    if ext not in _SUPPORTED:
        return None

    mime_type, block_type = _SUPPORTED[ext]

    # Return cached ID if available
    cached = get_file_id(attachment.url)
    if cached:
        file_id = cached
    else:
        async with aiohttp.ClientSession() as session:
            async with session.get(attachment.url) as resp:
                data = await resp.read()
        file_id = await claude_client.upload_file(data, attachment.filename, mime_type)
        save_file_id(attachment.url, file_id, attachment.filename, mime_type)

    if block_type == "image":
        return {"type": "image", "source": {"type": "file", "file_id": file_id}}

    return {
        "type": "document",
        "source": {"type": "file", "file_id": file_id},
        "title": attachment.filename,
    }
