import discord
from discord import app_commands
from discord.ext import commands

import claude_client
from utils.context_builder import build_messages


def _split(text: str, max_len: int = 1990) -> list[str]:
    """Split a long response into Discord-safe chunks, breaking at newlines."""
    if len(text) <= max_len:
        return [text]
    parts: list[str] = []
    while text:
        if len(text) <= max_len:
            parts.append(text)
            break
        cut = text.rfind("\n", 0, max_len)
        if cut == -1:
            cut = max_len
        parts.append(text[:cut])
        text = text[cut:].lstrip("\n")
    return parts


async def _send_chunks(
    chunks: list[str],
    channel: discord.TextChannel,
    first_send,           # coroutine that sends/replies the first chunk
) -> None:
    await first_send(chunks[0])
    for chunk in chunks[1:]:
        await channel.send(chunk)


class ChatCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── /chat ─────────────────────────────────────────────────────────────

    @app_commands.command(name="chat", description="Chat with Xing Lite using this channel as context")
    @app_commands.describe(message="Your message or question")
    async def chat(self, interaction: discord.Interaction, message: str):
        await interaction.response.defer()
        messages = await build_messages(interaction.channel, message)
        response = await claude_client.chat(messages)
        chunks = _split(response)
        await interaction.followup.send(chunks[0])
        for chunk in chunks[1:]:
            await interaction.channel.send(chunk)

    # ── /summarize ────────────────────────────────────────────────────────

    @app_commands.command(name="summarize", description="Summarise recent messages in this channel")
    async def summarize(self, interaction: discord.Interaction):
        await interaction.response.defer()
        query = (
            "Summarise the recent messages in this channel. "
            "Highlight key topics, important links, and any files that were shared."
        )
        messages = await build_messages(interaction.channel, query)
        response = await claude_client.chat(messages)
        chunks = _split(response)
        await interaction.followup.send(chunks[0])
        for chunk in chunks[1:]:
            await interaction.channel.send(chunk)

    # ── /search ───────────────────────────────────────────────────────────

    @app_commands.command(name="search", description="Search this channel's history for something")
    @app_commands.describe(query="What to look for")
    async def search(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()
        prompt = (
            f"Search the channel history and find everything related to: {query}\n\n"
            "List each relevant item with its timestamp, who shared it, and a brief description."
        )
        messages = await build_messages(interaction.channel, prompt)
        response = await claude_client.chat(messages)
        chunks = _split(response)
        await interaction.followup.send(chunks[0])
        for chunk in chunks[1:]:
            await interaction.channel.send(chunk)

    # ── @mention handler ──────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if self.bot.user not in message.mentions:
            return

        # Strip the mention tokens from the content
        query = message.content
        for token in (f"<@{self.bot.user.id}>", f"<@!{self.bot.user.id}>"):
            query = query.replace(token, "").strip()

        if not query and not message.attachments:
            await message.reply("Hey! Ask me anything or share a file and I'll help.")
            return

        async with message.channel.typing():
            messages = await build_messages(
                message.channel,
                query or "Describe the file(s) I just shared.",
                list(message.attachments),
            )
            response = await claude_client.chat(messages)

        chunks = _split(response)
        await message.reply(chunks[0])
        for chunk in chunks[1:]:
            await message.channel.send(chunk)


async def setup(bot: commands.Bot):
    await bot.add_cog(ChatCog(bot))
