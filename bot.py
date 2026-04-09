import asyncio
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

from database import init_db

load_dotenv()


class XingLite(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.members = True
        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=intents,
            description="Xing Lite — personal Discord AI assistant",
        )

    async def setup_hook(self):
        init_db()
        await self.load_extension("cogs.chat")
        await self.load_extension("cogs.admin")
        await self.load_extension("cogs.router")
        await self.load_extension("cogs.quests")
        await self.tree.sync()
        print("Slash commands synced.")

    async def on_ready(self):
        print(f"Logged in as {self.user} (ID: {self.user.id})")
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="your server | /chat",
            )
        )


async def main():
    async with XingLite() as bot:
        await bot.start(os.environ["DISCORD_TOKEN"])


if __name__ == "__main__":
    asyncio.run(main())
