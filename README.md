# Xing Lite

A personal Discord bot backed by Claude AI. Turns a private Discord server into an AI-powered knowledge base — store links, files, and notes, then query them in natural language.

## Features

### Chat (`cogs/chat.py`)
Interact with Claude using the channel's message history as context.

| Command | Description |
|---|---|
| `/chat <message>` | Ask anything; Claude sees recent channel history |
| `/summarize` | Summarise recent messages, links, and files |
| `/search <query>` | Find relevant items in channel history |
| `@Xing Lite <message>` | Mention the bot directly; supports file attachments |

### Admin (`cogs/admin.py`)
Manage server structure via slash commands or plain English.

| Command | Description |
|---|---|
| `/channel create/rename/topic/delete` | Manage text channels |
| `/category create/rename` | Manage categories |
| `/server <prompt>` | Describe changes in plain English; Claude plans and executes them |

Requires **Manage Channels** permission.

### Router (`cogs/router.py`)
Automatically cross-posts messages from `#main` to relevant channels.

- YouTube links → `#youtube-videos`
- Image attachments → `#images`
- Video attachments → `#videos`
- Everything else → Claude semantically routes to matching channels

### Quests (`cogs/quests.py`)
Task tracker and reminder system with a dedicated quest log channel.

| Command | Description |
|---|---|
| `/quest add <title> [when] [description]` | Add a task or event |
| `/quest list` | View active quests (overdue / upcoming / tasks) |
| `/quest done <id>` | Mark a quest complete |
| `/quest delete <id>` | Delete a quest |
| `/remind <what> <when>` | Quick reminder shortcut |

Supports natural language dates (`"tomorrow at 3pm"`, `"in 2 hours"`). Reminders fire via a background loop that checks every 60 seconds.

## Setup

**Prerequisites:** Python 3.11+, a Discord bot token, an Anthropic API key.

```bash
git clone <repo>
cd xing_lite
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file:

```env
DISCORD_TOKEN=your_discord_bot_token
ANTHROPIC_API_KEY=your_anthropic_api_key
```

Run the bot:

```bash
python bot.py
```

## Discord Bot Permissions

Required intents: `message_content`, `guilds`, `members`

Required permissions: `Send Messages`, `Embed Links`, `Read Message History`, `Manage Channels` (for admin features)

## Project Structure

```
xing_lite/
├── bot.py              # Entry point
├── config.py           # Model, token limits, system prompt
├── database.py         # SQLite helpers (files cache + quests)
├── claude_client.py    # Anthropic API wrapper
├── requirements.txt
├── cogs/
│   ├── chat.py         # /chat, /summarize, /search, @mention
│   ├── admin.py        # /channel, /category, /server
│   ├── router.py       # Auto-routing from #main
│   └── quests.py       # /quest, /remind, reminder loop
└── utils/
    ├── context_builder.py  # Builds Claude message payloads from channel history
    └── file_handler.py     # Uploads attachments via Claude Files API with SQLite cache
```

## Configuration

Edit `config.py` to change:

| Setting | Default | Description |
|---|---|---|
| `MODEL` | `claude-opus-4-6` | Claude model |
| `MAX_CONTEXT_MESSAGES` | `40` | Channel history window |
| `MAX_RESPONSE_TOKENS` | `4096` | Max tokens per response |
| `SYSTEM_PROMPT` | see file | Bot persona and instructions |
