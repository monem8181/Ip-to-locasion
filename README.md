# 🌍 Postal & IP Geolocation Telegram Bot

A full-featured Telegram bot that looks up **IP geolocation** and **postal/zip codes** with history tracking, rate limiting, caching, and an admin panel.

---

## ✨ Features

- 🌐 **IP Geolocation** — country, region, city, postal code, ISP, coordinates, timezone
- 📮 **Postal/Zip Code Lookup** — supports US, UK, Canada, and more (multi-place results)
- 📜 **History** — view your last 10 lookups or export your full history as CSV
- ⚡ **Rate Limiting** — 3-second cooldown per user between lookups
- 💾 **Caching** — 30-minute TTL SQLite cache for both IP and postal lookups
- 🛡️ **Admin Panel** — `/stats`, `/broadcast`, `/ban`, `/unban`
- 🚫 **User Banning** — banned users are silently blocked
- 🚀 **Railway-ready** — long-polling worker with persistent volume support

---

## 🛠️ Tech Stack

| Layer | Tech |
|-------|------|
| Bot framework | python-telegram-bot 21+ (async) |
| HTTP client | httpx (async) |
| Storage | SQLite |
| Config | python-dotenv |
| Deployment | Railway (Pro, persistent volume) |

---

## 📁 Project Structure

```
.
├── main.py                     # Entry point — builds & starts the bot
├── config.py                   # Loads env vars
├── handlers/
│   ├── __init__.py
│   ├── user_handlers.py        # /start /help /ip /zip /history /export
│   └── admin_handlers.py       # /stats /broadcast /ban /unban
├── services/
│   ├── __init__.py
│   ├── database.py             # SQLite: init, users, lookups, cache, stats
│   └── geolocation.py          # ip-api.com & zippopotam.us API calls
├── utils/
│   ├── __init__.py
│   └── ratelimit.py            # In-memory per-user cooldown
├── data/                       # SQLite DB lives here (mounted volume on Railway)
├── requirements.txt
├── Procfile
├── railway.toml
├── .env.example
├── .gitignore
└── README.md
```

---

## 🚀 Setup (Local)

1. **Clone & enter the project**
   ```bash
   cd telegram-bot
   ```

2. **Create a virtual environment & install deps**
   ```bash
   python -m venv venv
   source venv/bin/activate        # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Get a bot token from [@BotFather](https://t.me/BotFather)**
   - Open a chat with @BotFather
   - Send `/newbot`
   - Follow the prompts to name it
   - Copy the token it gives you

4. **Find your Telegram user ID** (for admin access)
   - Open [@userinfobot](https://t.me/userinfobot) and send any message — it replies with your numeric user ID.

5. **Configure environment variables**
   ```bash
   cp .env.example .env
   ```
   Edit `.env`:
   ```
   BOT_TOKEN=123456:ABC-DEF_your_token_here
   ADMIN_IDS=123456789
   DB_PATH=./data/bot.db
   ```

6. **Run the bot**
   ```bash
   python main.py
   ```
   You should see logs like:
   ```
   [INFO] Initializing database...
   [INFO] Starting bot (long-polling)...
   ```

---

## 🚂 Deploy on Railway (Pro)

### 1. Create a new Railway project
- Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo**
- Point it to your repo containing this code.

### 2. Set environment variables
In Railway → your service → **Variables** tab, add:

| Variable | Value |
|----------|-------|
| `BOT_TOKEN` | your Telegram bot token |
| `ADMIN_IDS` | comma-separated admin user IDs |
| `DB_PATH` | `/app/data/bot.db` |

### 3. Attach a persistent volume
Because the bot uses SQLite, the database file must survive restarts.

- Go to **Settings** → **Volumes** → **Add Volume**
- **Mount path:** `/app/data`
- This ensures `DB_PATH=/app/data/bot.db` persists across deploys.

### 4. Deploy
Railway auto-detects the `Procfile` and runs:
```
worker: python main.py
```

The bot starts in long-polling mode. Logs go to stdout (visible in Railway's **Logs** tab).

---

## 📋 Command Reference

### User Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message & overview |
| `/help` | Show all commands |
| `/ip <ip>` | Geolocate an IP address (IPv4/IPv6) |
| `/zip <code>` | Look up a postal/zip code (defaults to US) |
| `/zip <country> <code>` | Look up a code in a specific country |
| `/history` | View your last 10 lookups |
| `/export` | Download your full history as a CSV file |

### Admin Commands
*(Restricted to user IDs in `ADMIN_IDS`)*

| Command | Description |
|---------|-------------|
| `/stats` | Bot usage statistics (users, lookups, top queries) |
| `/broadcast <message>` | Send a message to every registered user |
| `/ban <user_id>` | Ban a user from using the bot |
| `/unban <user_id>` | Unban a user |

---

## 🌐 Data Sources

- **IP Geolocation:** [ip-api.com](http://ip-api.com) (free tier, 45 req/min, no API key)
- **Postal/Zip Lookup:** [zippopotam.us](https://api.zippopotam.us) (free, no API key, supports US/CA/UK/etc.)

⚠️ *IP geolocation is approximate (city-level) and does not reveal an exact street address.*

---

## 🔒 Notes

- All SQL queries use parameterized statements (no injection risk).
- Per-user rate limit: 3 seconds between lookups (in-memory dict).
- Cache TTL: 30 minutes (stored in SQLite `cache` table).
- Bot token is never hardcoded — read from `BOT_TOKEN` env var.
- Logging at INFO (stdout) — Railway captures stdout automatically.