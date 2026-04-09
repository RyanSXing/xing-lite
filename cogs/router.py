import os
import re

import discord
from discord.ext import commands

import claude_client

# Channel where auto-routing is triggered
SOURCE_CHANNEL = "main"

# Hard-coded destination channels (created if they exist, silently skipped if not)
YOUTUBE_CHANNEL = "youtube-videos"
IMAGES_CHANNEL  = "images"
VIDEOS_CHANNEL  = "videos"

YOUTUBE_RE = re.compile(
    r"https?://(www\.)?(youtube\.com/watch|youtu\.be/)\S+", re.IGNORECASE
)

IMAGE_MIMES = {"image/jpeg", "image/png", "image/gif", "image/webp", "image/bmp"}
VIDEO_MIMES = {"video/mp4", "video/quicktime", "video/x-msvideo",
               "video/webm", "video/x-matroska", "video/mpeg"}

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".flv", ".wmv", ".m4v"}


def _get_channel(guild: discord.Guild, name: str) -> discord.TextChannel | None:
    return discord.utils.get(guild.text_channels, name=name)


def _classify_attachment(att: discord.Attachment) -> str | None:
    """Return 'image', 'video', or None based on the attachment."""
    mime = (att.content_type or "").split(";")[0].strip().lower()
    if mime in IMAGE_MIMES:
        return "image"
    if mime in VIDEO_MIMES:
        return "video"
    ext = os.path.splitext(att.filename.lower())[1]
    if ext in IMAGE_EXTS:
        return "image"
    if ext in VIDEO_EXTS:
        return "video"
    return None


def _make_embed(message: discord.Message, reason: str) -> discord.Embed:
    embed = discord.Embed(
        description=message.content or "",
        color=discord.Color.blurple(),
        timestamp=message.created_at,
    )
    embed.set_author(
        name=message.author.display_name,
        icon_url=message.author.display_avatar.url,
    )
    embed.set_footer(text=f"Auto-forwarded from #{message.channel.name} · {reason}")
    embed.add_field(name="", value=f"[Jump to original]({message.jump_url})", inline=False)
    return embed


class RouterCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Only act on messages in the source channel, from real users
        if message.author.bot:
            return
        if not isinstance(message.channel, discord.TextChannel):
            return
        if message.channel.name != SOURCE_CHANNEL:
            return

        guild = message.guild
        targets: dict[str, str] = {}  # channel_name → reason

        # ── Hard rules ────────────────────────────────────────────────────

        # YouTube links
        if YOUTUBE_RE.search(message.content or ""):
            targets[YOUTUBE_CHANNEL] = "YouTube link"

        # Attachments
        for att in message.attachments:
            kind = _classify_attachment(att)
            if kind == "image":
                targets[IMAGES_CHANNEL] = "image"
            elif kind == "video":
                targets[VIDEOS_CHANNEL] = "video"

        # ── Claude semantic routing ───────────────────────────────────────

        # Build candidate list: all text channels except main and already-targeted ones
        candidates = [
            ch.name for ch in guild.text_channels
            if ch.name != SOURCE_CHANNEL and ch.name not in targets
        ]

        if candidates and (message.content or "").strip():
            routed = await claude_client.route_message(message.content, candidates)
            for name in routed:
                targets[name] = "related content"

        if not targets:
            return

        # ── Forward ───────────────────────────────────────────────────────

        for ch_name, reason in targets.items():
            dest = _get_channel(guild, ch_name)
            if not dest:
                continue

            embed = _make_embed(message, reason)

            # Attach the first image inline if forwarding to images channel
            first_image = next(
                (att for att in message.attachments if _classify_attachment(att) == "image"),
                None,
            )
            if first_image and ch_name == IMAGES_CHANNEL:
                embed.set_image(url=first_image.url)

            await dest.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(RouterCog(bot))
