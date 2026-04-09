from __future__ import annotations

from datetime import datetime, timezone

import dateparser
import discord
from discord import app_commands
from discord.ext import commands, tasks

from database import (
    add_quest, complete_quest, delete_quest,
    get_due_quests, get_quests, mark_notified,
)

QUEST_LOG_NAME = "xing-sect-quest-log"   # Discord channel name (lowercase/hyphenated)
QUEST_LOG_DISPLAY = "Xing Sect Quest Log"


# ── Helpers ───────────────────────────────────────────────────────────────────

async def ensure_quest_log(guild: discord.Guild) -> discord.TextChannel:
    """Return the quest log channel, creating it if it doesn't exist."""
    ch = discord.utils.get(guild.text_channels, name=QUEST_LOG_NAME)
    if ch:
        return ch
    ch = await guild.create_text_channel(
        QUEST_LOG_NAME,
        topic="Task list, reminders, and events managed by Xing Lite.",
        reason="Xing Lite quest log auto-created",
    )
    await ch.send(
        "📜 **Xing Sect Quest Log** — this channel tracks your tasks, "
        "reminders, and events. Use `/quest add` to get started."
    )
    return ch


def parse_due(text: str) -> datetime | None:
    """Parse a natural language time string into a UTC-aware datetime."""
    dt = dateparser.parse(
        text,
        settings={
            "RETURN_AS_TIMEZONE_AWARE": True,
            "PREFER_DATES_FROM": "future",
            "TO_TIMEZONE": "UTC",
        },
    )
    return dt


def fmt_dt(iso: str) -> str:
    """Convert stored ISO UTC string to a Discord timestamp tag."""
    try:
        dt = datetime.fromisoformat(iso)
        return f"<t:{int(dt.timestamp())}:F>"
    except Exception:
        return iso


def quest_embed(quests: list[dict], title: str) -> discord.Embed:
    """Build a nicely formatted embed for a list of quests."""
    now = datetime.now(timezone.utc)
    embed = discord.Embed(title=title, color=discord.Color.gold())

    overdue, upcoming, no_date = [], [], []
    for q in quests:
        if q["due_at"]:
            try:
                due = datetime.fromisoformat(q["due_at"])
                if due <= now:
                    overdue.append(q)
                else:
                    upcoming.append(q)
            except Exception:
                no_date.append(q)
        else:
            no_date.append(q)

    def fmt_q(q: dict) -> str:
        due_str = f" — due {fmt_dt(q['due_at'])}" if q["due_at"] else ""
        desc = f"\n  *{q['description']}*" if q["description"] else ""
        return f"`[{q['id']}]` **{q['title']}**{due_str}{desc}"

    if overdue:
        embed.add_field(
            name="🔴 Overdue",
            value="\n".join(fmt_q(q) for q in overdue),
            inline=False,
        )
    if upcoming:
        embed.add_field(
            name="🟡 Upcoming",
            value="\n".join(fmt_q(q) for q in upcoming),
            inline=False,
        )
    if no_date:
        embed.add_field(
            name="⚪ Tasks",
            value="\n".join(fmt_q(q) for q in no_date),
            inline=False,
        )
    if not quests:
        embed.description = "No active quests. Use `/quest add` to create one."

    embed.set_footer(text="Use /quest done <id> to complete • /quest delete <id> to remove")
    return embed


# ── Cog ───────────────────────────────────────────────────────────────────────

class QuestsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.reminder_loop.start()

    def cog_unload(self):
        self.reminder_loop.cancel()

    # ── /quest group ──────────────────────────────────────────────────────

    quest = app_commands.Group(name="quest", description="Manage your tasks, reminders, and events")

    @quest.command(name="add", description="Add a task, reminder, or event")
    @app_commands.describe(
        title="What needs to be done",
        when="When it's due — e.g. 'tomorrow at 3pm', 'in 2 hours', 'next Monday' (optional)",
        description="Extra details (optional)",
    )
    async def quest_add(
        self,
        interaction: discord.Interaction,
        title: str,
        when: str | None = None,
        description: str | None = None,
    ):
        due_dt = None
        due_iso = None
        if when:
            due_dt = parse_due(when)
            if not due_dt:
                return await interaction.response.send_message(
                    f"Couldn't parse **{when}** as a time. Try something like 'tomorrow at 3pm' or 'in 2 hours'.",
                    ephemeral=True,
                )
            due_iso = due_dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")

        quest_id = add_quest(
            str(interaction.guild_id),
            str(interaction.user.id),
            title,
            description,
            due_iso,
        )

        log = await ensure_quest_log(interaction.guild)
        embed = discord.Embed(
            title=f"📋 Quest Added — {title}",
            color=discord.Color.green(),
        )
        embed.add_field(name="ID", value=f"`{quest_id}`", inline=True)
        if due_dt:
            embed.add_field(name="Due", value=fmt_dt(due_iso), inline=True)
        if description:
            embed.add_field(name="Notes", value=description, inline=False)
        embed.set_footer(text=f"Added by {interaction.user.display_name}")

        await log.send(embed=embed)
        await interaction.response.send_message(
            f"Quest **{title}** added! (`/quest list` to view all)", ephemeral=True
        )

    @quest.command(name="list", description="View your active quests")
    async def quest_list(self, interaction: discord.Interaction):
        quests = get_quests(str(interaction.guild_id), str(interaction.user.id))
        embed = quest_embed(quests, f"📜 {interaction.user.display_name}'s Quest Log")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @quest.command(name="done", description="Mark a quest as complete")
    @app_commands.describe(id="Quest ID (shown in /quest list)")
    async def quest_done(self, interaction: discord.Interaction, id: int):
        if not complete_quest(id, str(interaction.user.id)):
            return await interaction.response.send_message(
                f"Quest `{id}` not found or doesn't belong to you.", ephemeral=True
            )
        log = await ensure_quest_log(interaction.guild)
        await log.send(
            f"✅ {interaction.user.mention} completed quest `[{id}]`!"
        )
        await interaction.response.send_message(f"Quest `{id}` marked complete!", ephemeral=True)

    @quest.command(name="delete", description="Delete a quest")
    @app_commands.describe(id="Quest ID (shown in /quest list)")
    async def quest_delete(self, interaction: discord.Interaction, id: int):
        if not delete_quest(id, str(interaction.user.id)):
            return await interaction.response.send_message(
                f"Quest `{id}` not found or doesn't belong to you.", ephemeral=True
            )
        await interaction.response.send_message(f"Quest `{id}` deleted.", ephemeral=True)

    # ── /remind shortcut ──────────────────────────────────────────────────

    @app_commands.command(name="remind", description="Set a quick reminder")
    @app_commands.describe(
        what="What to remind you about",
        when="When to remind you — e.g. 'in 30 minutes', 'tonight at 8pm'",
    )
    async def remind(self, interaction: discord.Interaction, what: str, when: str):
        due_dt = parse_due(when)
        if not due_dt:
            return await interaction.response.send_message(
                f"Couldn't parse **{when}**. Try 'in 30 minutes' or 'tomorrow at noon'.",
                ephemeral=True,
            )
        due_iso = due_dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")
        quest_id = add_quest(str(interaction.guild_id), str(interaction.user.id), what, None, due_iso)

        log = await ensure_quest_log(interaction.guild)
        await log.send(
            f"⏰ Reminder set for {interaction.user.mention}: "
            f"**{what}** at {fmt_dt(due_iso)} `[id: {quest_id}]`"
        )
        await interaction.response.send_message(
            f"Reminder set for {fmt_dt(due_iso)}!", ephemeral=True
        )

    # ── Background reminder check ─────────────────────────────────────────

    @tasks.loop(seconds=60)
    async def reminder_loop(self):
        due = get_due_quests()
        for q in due:
            guild = self.bot.get_guild(int(q["guild_id"]))
            if not guild:
                mark_notified(q["id"])
                continue

            log = await ensure_quest_log(guild)
            member = guild.get_member(int(q["user_id"]))
            mention = member.mention if member else f"<@{q['user_id']}>"

            embed = discord.Embed(
                title=f"⏰ {q['title']}",
                description=q["description"] or "",
                color=discord.Color.red(),
            )
            embed.set_footer(text=f"Quest ID: {q['id']} • Use /quest done {q['id']} when finished")

            await log.send(f"{mention}", embed=embed)
            mark_notified(q["id"])

    @reminder_loop.before_loop
    async def before_reminder_loop(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(QuestsCog(bot))
