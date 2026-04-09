import discord
from discord import app_commands
from discord.ext import commands

import claude_client


def _check_manage(interaction: discord.Interaction) -> bool:
    return interaction.user.guild_permissions.manage_channels


def _server_structure(guild: discord.Guild) -> str:
    """Describe the current server layout as plain text for Claude."""
    lines: list[str] = []
    uncategorised = [
        ch for ch in guild.channels
        if ch.category is None and not isinstance(ch, discord.CategoryChannel)
    ]
    if uncategorised:
        lines.append("(no category):")
        for ch in uncategorised:
            kind = "voice" if isinstance(ch, discord.VoiceChannel) else "text"
            lines.append(f"  [{kind}] #{ch.name}")

    for cat in guild.categories:
        lines.append(f"\n[{cat.name}]")
        for ch in cat.channels:
            kind = "voice" if isinstance(ch, discord.VoiceChannel) else "text"
            topic = f" — {ch.topic}" if getattr(ch, "topic", None) else ""
            lines.append(f"  [{kind}] #{ch.name}{topic}")

    return "\n".join(lines) or "(empty server)"


async def _execute(guild: discord.Guild, action: dict) -> str:
    """Execute a single action dict and return a human-readable result string."""
    t = action.get("type", "")

    if t == "create_category":
        cat = await guild.create_category(action["name"])
        return f"Created category **{cat.name}**"

    elif t == "rename_category":
        cat = discord.utils.get(guild.categories, name=action["old_name"])
        if not cat:
            return f"⚠ Category **{action['old_name']}** not found"
        await cat.edit(name=action["new_name"])
        return f"Renamed category **{action['old_name']}** → **{action['new_name']}**"

    elif t == "delete_category":
        cat = discord.utils.get(guild.categories, name=action["name"])
        if not cat:
            return f"⚠ Category **{action['name']}** not found"
        await cat.delete()
        return f"Deleted category **{action['name']}**"

    elif t == "create_channel":
        cat = discord.utils.get(guild.categories, name=action.get("category")) if action.get("category") else None
        topic = action.get("topic") or ""
        if action.get("channel_type") == "voice":
            ch = await guild.create_voice_channel(action["name"], category=cat)
        else:
            ch = await guild.create_text_channel(action["name"], category=cat, topic=topic)
        return f"Created {ch.mention}"

    elif t == "rename_channel":
        ch = discord.utils.get(guild.channels, name=action["old_name"])
        if not ch:
            return f"⚠ Channel **#{action['old_name']}** not found"
        await ch.edit(name=action["new_name"])
        return f"Renamed **#{action['old_name']}** → **#{action['new_name']}**"

    elif t == "set_topic":
        ch = discord.utils.get(guild.text_channels, name=action["channel_name"])
        if not ch:
            return f"⚠ Channel **#{action['channel_name']}** not found"
        await ch.edit(topic=action["topic"])
        return f"Set topic for **#{action['channel_name']}**"

    elif t == "delete_channel":
        ch = discord.utils.get(guild.channels, name=action["name"])
        if not ch:
            return f"⚠ Channel **#{action['name']}** not found"
        await ch.delete()
        return f"Deleted **#{action['name']}**"

    return f"⚠ Unknown action type: {t}"


class AdminCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── /channel group ────────────────────────────────────────────────────

    channel = app_commands.Group(name="channel", description="Manage server channels")

    @channel.command(name="create", description="Create a new text channel")
    @app_commands.describe(name="Channel name", category="Existing category name (optional)")
    async def channel_create(
        self,
        interaction: discord.Interaction,
        name: str,
        category: str | None = None,
    ):
        if not _check_manage(interaction):
            return await interaction.response.send_message(
                "You need **Manage Channels** permission.", ephemeral=True
            )
        cat_obj: discord.CategoryChannel | None = None
        if category:
            cat_obj = discord.utils.get(interaction.guild.categories, name=category)
            if not cat_obj:
                return await interaction.response.send_message(
                    f"Category **{category}** not found.", ephemeral=True
                )
        ch = await interaction.guild.create_text_channel(name, category=cat_obj)
        await interaction.response.send_message(f"Created {ch.mention}", ephemeral=True)

    @channel.command(name="rename", description="Rename a channel")
    @app_commands.describe(channel="Channel to rename", new_name="New name")
    async def channel_rename(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        new_name: str,
    ):
        if not _check_manage(interaction):
            return await interaction.response.send_message(
                "You need **Manage Channels** permission.", ephemeral=True
            )
        old = channel.name
        await channel.edit(name=new_name)
        await interaction.response.send_message(
            f"Renamed **#{old}** → **#{new_name}**", ephemeral=True
        )

    @channel.command(name="topic", description="Set the topic of a channel")
    @app_commands.describe(channel="Target channel", topic="New topic text")
    async def channel_topic(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        topic: str,
    ):
        if not _check_manage(interaction):
            return await interaction.response.send_message(
                "You need **Manage Channels** permission.", ephemeral=True
            )
        await channel.edit(topic=topic)
        await interaction.response.send_message(
            f"Topic updated for {channel.mention}", ephemeral=True
        )

    @channel.command(name="delete", description="Delete a channel")
    @app_commands.describe(channel="Channel to delete")
    async def channel_delete(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
    ):
        if not _check_manage(interaction):
            return await interaction.response.send_message(
                "You need **Manage Channels** permission.", ephemeral=True
            )
        name = channel.name
        await channel.delete(reason=f"Deleted by {interaction.user}")
        await interaction.response.send_message(f"Deleted **#{name}**", ephemeral=True)

    # ── /category group ───────────────────────────────────────────────────

    category = app_commands.Group(name="category", description="Manage server categories")

    @category.command(name="create", description="Create a new category")
    @app_commands.describe(name="Category name")
    async def category_create(self, interaction: discord.Interaction, name: str):
        if not _check_manage(interaction):
            return await interaction.response.send_message(
                "You need **Manage Channels** permission.", ephemeral=True
            )
        cat = await interaction.guild.create_category(name)
        await interaction.response.send_message(
            f"Created category **{cat.name}**", ephemeral=True
        )

    @category.command(name="rename", description="Rename a category")
    @app_commands.describe(name="Current category name", new_name="New name")
    async def category_rename(
        self,
        interaction: discord.Interaction,
        name: str,
        new_name: str,
    ):
        if not _check_manage(interaction):
            return await interaction.response.send_message(
                "You need **Manage Channels** permission.", ephemeral=True
            )
        cat = discord.utils.get(interaction.guild.categories, name=name)
        if not cat:
            return await interaction.response.send_message(
                f"Category **{name}** not found.", ephemeral=True
            )
        await cat.edit(name=new_name)
        await interaction.response.send_message(
            f"Renamed **{name}** → **{new_name}**", ephemeral=True
        )


    # ── /server ───────────────────────────────────────────────────────────

    @app_commands.command(
        name="server",
        description="Make changes to the server by describing what you want in plain English",
    )
    @app_commands.describe(prompt="Describe the changes you want — e.g. 'add a Projects section with channels for work and personal'")
    async def server_manage(self, interaction: discord.Interaction, prompt: str):
        if not _check_manage(interaction):
            return await interaction.response.send_message(
                "You need **Manage Channels** permission.", ephemeral=True
            )

        await interaction.response.defer()

        structure = _server_structure(interaction.guild)
        plan = await claude_client.plan_server_changes(structure, prompt)

        results: list[str] = []
        for action in plan.get("actions", []):
            result = await _execute(interaction.guild, action)
            results.append(result)

        summary = plan.get("summary", "Done.")
        body = "\n".join(f"• {r}" for r in results) if results else "No changes made."
        await interaction.followup.send(f"**{summary}**\n\n{body}")


async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCog(bot))
