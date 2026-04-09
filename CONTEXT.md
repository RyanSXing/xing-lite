# Xing Lite — Project Context

Personal Discord bot that uses Claude (Opus 4.6) as its AI backbone. Built for a private Discord server used as a personal knowledge base — storing links, files, notes, and anything important accessible across devices.

---

## Stack

- **Language:** Python 3.13+
- **Discord library:** discord.py 2.7+
- **AI:** Anthropic SDK (`anthropic>=0.50.0`) — model `claude-opus-4-6`
- **Database:** SQLite (`xing_lite.db`) via stdlib `sqlite3`
- **Time parsing:** `dateparser>=1.2.0`
- **File downloads:** `aiohttp>=3.9.0`
- **Env vars:** `python-dotenv`

---

## Project Structure

```
xing_lite/
├── bot.py                  # Entry point, bot class, extension loader
├── config.py               # Constants: model, token limits, system prompt
├── database.py             # SQLite helpers: file cache + quest CRUD
├── claude_client.py        # All Anthropic API calls
├── cogs/
│   ├── chat.py             # /chat, /summarize, /search, @mention handler
│   ├── admin.py            # /channel, /category, /server commands
│   ├── router.py           # Auto-forward messages from #main
│   └── quests.py           # /quest, /remind, background reminder loop
├── utils/
│   ├── context_builder.py  # Discord history → Claude message format
│   └── file_handler.py     # Discord attachment → Claude Files API block
├── requirements.txt
├── .env                    # DISCORD_TOKEN, ANTHROPIC_API_KEY (not in git)
└── xing_lite.db            # SQLite database (auto-created on first run)
```

---

## Running the Bot

```bash
cd /Users/rsxing/xing_lite
source .venv/bin/activate
python3 bot.py
```

The `.venv` was created with `python3 -m venv .venv` because the system Python is externally managed (Homebrew). Always use `.venv/bin/python3` or activate first.

**On startup the bot:**
1. Calls `init_db()` — creates SQLite tables if missing
2. Loads all 4 cogs
3. Syncs slash commands to Discord (`tree.sync()`)

---

## Environment Variables (`.env`)

```
DISCORD_TOKEN=...
ANTHROPIC_API_KEY=...
```

---

## Discord Bot Settings (Developer Portal)

Required privileged intents (must be enabled at discord.com/developers/applications):
- **Message Content Intent** ✅
- **Server Members Intent** ✅
- **Presence Intent** ✅

Required bot permissions: `Send Messages`, `Read Message History`, `View Channels`, `Manage Channels`, `Manage Guild`, `Embed Links`

---

## Database Schema (`xing_lite.db`)

### `file_cache`
Caches Discord attachment URL → Claude Files API `file_id` so files are never uploaded twice.

| Column | Type | Notes |
|---|---|---|
| discord_url | TEXT PK | Full Discord CDN URL |
| claude_file_id | TEXT | Anthropic Files API ID |
| filename | TEXT | Original filename |
| mime_type | TEXT | e.g. `image/png` |
| created_at | TIMESTAMP | |

### `quests`
Stores tasks, reminders, and events.

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | Auto-increment |
| guild_id | TEXT | Discord guild snowflake |
| user_id | TEXT | Discord user snowflake |
| title | TEXT | Quest title |
| description | TEXT | Optional notes |
| due_at | TEXT | ISO UTC string e.g. `2026-04-09T15:00:00+00:00`, nullable |
| notified | INTEGER | 0/1 — has reminder been sent |
| completed | INTEGER | 0/1 |
| created_at | TEXT | ISO UTC string |

---

## Claude API Usage (`claude_client.py`)

All calls use `claude-opus-4-6`. Four functions:

| Function | Purpose | Endpoint |
|---|---|---|
| `chat(messages)` | Main chatbot response | `client.beta.messages.create` + Files API beta header |
| `plan_server_changes(server_info, prompt)` | Parse natural language → JSON action plan | `client.messages.create` |
| `route_message(content, channel_names)` | Decide which channels a message belongs in | `client.messages.create` |
| `upload_file(data, filename, mime_type)` | Upload file to Anthropic Files API | `client.beta.files.upload` |

The Files API requires `betas=["files-api-2025-04-14"]` on `messages.create` calls that reference file IDs.

---

## Cog Reference

### `cogs/chat.py` — Chatbot
- **`/chat <message>`** — Asks Claude using last 40 channel messages as context
- **`/summarize`** — Summarises recent channel activity
- **`/search <query>`** — Finds relevant content in channel history
- **`@Xing Lite <message>`** — Mention handler; supports file attachments in the mention message

Context is built by `utils/context_builder.py`: fetches last 40 messages, formats as a text block prepended to the user's query. File attachments on the *current* message are included as Claude content blocks.

Responses longer than 1990 chars are split into multiple messages, breaking at newlines.

### `cogs/admin.py` — Server Management

Manual commands:
- **`/channel create <name> [category]`**
- **`/channel rename <channel> <new_name>`**
- **`/channel topic <channel> <topic>`**
- **`/channel delete <channel>`**
- **`/category create <name>`**
- **`/category rename <name> <new_name>`**

AI-powered command:
- **`/server <prompt>`** — Describe changes in plain English. Claude reads the full server structure, returns a JSON action plan, bot executes it. Example: *"add a Projects section with channels for work, personal, and side-projects"*

All commands require `Manage Channels` permission.

### `cogs/router.py` — Auto-Forwarding

Watches **`#main`** only. When a message is posted there:

1. **Hard rules (regex/MIME):**
   - YouTube URL → forwards to `#youtube-videos`
   - Image attachment → forwards to `#images`
   - Video attachment → forwards to `#videos`

2. **Claude semantic routing:** Asks Claude if the message content is relevant to any other channel by name. Only routes when relevance is clear.

Forwarded messages appear as Discord embeds showing the original author, timestamp, and a "Jump to original" link. If target channel doesn't exist, it's silently skipped.

**Configurable constants in `router.py`:**
```python
SOURCE_CHANNEL = "main"
YOUTUBE_CHANNEL = "youtube-videos"
IMAGES_CHANNEL  = "images"
VIDEOS_CHANNEL  = "videos"
```

### `cogs/quests.py` — Tasks & Reminders

Auto-creates **`#xing-sect-quest-log`** channel on first use.

Commands:
- **`/quest add <title> [when] [description]`** — Add a task/reminder/event. `when` is natural language: *"tomorrow at 3pm"*, *"in 2 hours"*, *"next Monday"*
- **`/quest list`** — Shows active quests grouped: 🔴 Overdue / 🟡 Upcoming / ⚪ No date
- **`/quest done <id>`** — Mark complete, posts to quest log
- **`/quest delete <id>`** — Remove quest
- **`/remind <what> <when>`** — Shortcut for quick time-based reminders

**Background loop** runs every 60 seconds, checks for quests where `due_at <= now` and `notified=0`, pings the user in `#xing-sect-quest-log`, then marks `notified=1`.

Times stored as UTC ISO strings. Displayed using Discord timestamp tags (`<t:UNIX:F>`) which render in the user's local timezone automatically.

---

## Utils

### `utils/context_builder.py`
`build_messages(channel, query, attachments=None) → list`

Fetches last `MAX_CONTEXT_MESSAGES` (40) from the channel, formats as:
```
## Recent channel history
[2026-04-08 14:30] Ryan: some message  [attached: file.pdf]
...
---
<user query>
[optional file content blocks]
```
Returns a single-turn `[{"role": "user", "content": [...]}]` list ready for Claude.

### `utils/file_handler.py`
`attachment_to_block(attachment) → dict | None`

Supported types: `.jpg .jpeg .png .gif .webp` (image blocks) and `.pdf .txt .md .py .js .ts .json .csv .html` (document blocks).

Flow:
1. Check SQLite cache for existing `claude_file_id`
2. If miss: download from Discord CDN via `aiohttp`, upload to Claude Files API, cache the ID
3. Return Claude content block: `{"type": "image", "source": {"type": "file", "file_id": "..."}}` or `{"type": "document", ...}`

---

## Key Design Decisions

- **Single-turn context:** Every `/chat` call is a fresh conversation with history injected as text. No multi-turn session state is maintained between slash command invocations.
- **Files API caching:** Files are uploaded once per Discord URL and reused by ID. The SQLite cache is keyed on the full Discord CDN URL.
- **Beta endpoint for chat:** `client.beta.messages.create` is used for the main chat function because file_id references in content blocks require the Files API beta header.
- **No adaptive thinking:** Intentionally excluded to keep response times fast for a chatbot use case.
- **Reminder granularity:** The reminder loop runs every 60 seconds, so reminders fire within ~1 minute of their due time.

---

## Suggested Future Features (discussed but not built)

- `/save <url>` — fetch, summarise, and store web pages tagged by topic
- `/recall <topic>` — retrieve saved content by topic
- Daily digest in `#daily-brief` — morning summary of overdue quests + yesterday's activity
- Bookmark emoji reaction — react with 🔖 to auto-save any message to `#bookmarks`
- `/find <query>` — semantic search across bookmarks
- `/recap [days]` — Claude summary of server activity over N days
- Auto-summarise PDFs/articles dropped in any channel
- `/export` — compile a channel into a markdown or PDF file
- `/watch <topic>` — ping when matching content is posted anywhere
