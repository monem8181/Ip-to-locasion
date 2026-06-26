# 🌍 Feature List — IP & Postal Code Geolocation Telegram Bot

A complete list of every feature built into this bot.

---

## 🌐 IP Geolocation

- ✅ `/ip <address>` — geolocate any IPv4 or IPv6 address
- ✅ Returns: country, country code, region, city, postal code, ISP, coordinates (lat/lon), timezone
- ✅ IPv4 and IPv6 validation (rejects invalid addresses before calling the API)
- ✅ Graceful error handling for private/reserved IPs
- ✅ Data source: ip-api.com (free, no API key, 45 req/min)
- ✅ Accuracy disclaimer appended to every result
- ✅ Emoji-formatted, readable output

## 📮 Postal / Zip Code Lookup

- ✅ `/zip <code>` — look up a postal code (defaults to US for digit-only codes)
- ✅ `/zip <country> <code>` — look up codes in any supported country (US, CA, UK, etc.)
- ✅ Handles multi-place results (lists all matching places with name, state, coordinates)
- ✅ Clean 404 handling when a postal code isn't found
- ✅ Data source: zippopotam.us (free, no API key)
- ✅ Emoji-formatted output

## 📜 History & Export

- ✅ `/history` — shows the user's last 10 lookups (most recent first)
- ✅ Numbered list with type (🌐 IP / 📮 zip), query value, and timestamp
- ✅ Polite "no history" message when empty
- ✅ `/export` — downloads the user's full lookup history as a CSV file
- ✅ CSV columns: type, query, result_summary, timestamp
- ✅ Sent as a Telegram document attachment
- ✅ Temp file cleaned up automatically after sending

## ⚡ Rate Limiting

- ✅ Per-user cooldown: 3 seconds between `/ip` and `/zip` commands
- ✅ In-memory tracking (no Redis needed)
- ✅ Friendly cooldown message: "⏳ Please wait a few seconds before your next lookup."

## 💾 Caching

- ✅ SQLite-based cache for both IP and zip lookups
- ✅ Cache TTL: 30 minutes (expired entries are re-fetched)
- ✅ Cache keys: `ip:<ip>` and `zip:<country>:<code>`
- ✅ Reduces external API calls and speeds up repeat lookups

## 🛡️ Admin Panel

- ✅ Admin-only access (restricted to `ADMIN_IDS` env var)
- ✅ Non-admins get "⛔ Admin only command." response
- ✅ `/stats` — total users, total lookups, lookups today, lookup type breakdown, top 5 most-queried IPs/zips
- ✅ `/broadcast <message>` — send a message to every registered user
  - 0.05s delay between sends (avoids Telegram rate limits)
  - Per-user try/except (one blocked user won't crash the loop)
  - Reports success/fail counts back to the admin
- ✅ `/ban <user_id>` — ban a user from using the bot
- ✅ `/unban <user_id>` — lift a ban

## 🚫 User Management

- ✅ Auto-registration: every user is inserted into the `users` table on `/start` or first interaction
- ✅ Banned users are blocked from all commands
- ✅ Banned users receive "You are banned from using this bot."
- ✅ Username tracking and updates

## 🗄️ Database (SQLite)

- ✅ Three tables: `users`, `lookups`, `cache`
- ✅ Auto-created on startup (`CREATE TABLE IF NOT EXISTS`)
- ✅ `data/` directory auto-created if missing
- ✅ WAL journal mode for concurrent read/write safety
- ✅ Parameterized SQL queries everywhere (no injection risk)
- ✅ Thread-safe access with a threading lock

## 🔄 Async & Error Handling

- ✅ Fully async handlers (python-telegram-bot v21, async/await)
- ✅ Async HTTP client (httpx)
- ✅ Catches `httpx.TimeoutException` — shows timeout message
- ✅ Catches `httpx.HTTPError` — shows service-unreachable message
- ✅ Generic exception fallback for unexpected errors
- ✅ All exceptions logged at ERROR level

## 📝 Logging

- ✅ Python `logging` module at INFO level (stdout)
- ✅ Command usage logged at INFO
- ✅ Exceptions logged at ERROR
- ✅ Captured by Railway's log viewer automatically

## 🔒 Security

- ✅ Bot token read from `BOT_TOKEN` env var (never hardcoded)
- ✅ Admin IDs parsed from `ADMIN_IDS` env var (comma-separated → set of ints)
- ✅ `.env` in `.gitignore` (secrets never committed)
- ✅ No SQL string formatting (parameterized queries only)

## 🚂 Deployment (Railway)

- ✅ `Procfile` with `worker: python main.py`
- ✅ `railway.toml` with restart-on-failure policy (max 5 retries)
- ✅ Persistent volume support (`DB_PATH` → `/app/data/bot.db`)
- ✅ `requirements.txt` with pinned versions
- ✅ `.env.example` with all required variables documented
- ✅ Long-polling mode (no webhook setup needed)
- ✅ `README.md` with full deployment guide

## 📁 Project Structure

- ✅ Clean multi-file layout (not one giant script)
- ✅ `config.py` — env var loading
- ✅ `handlers/user_handlers.py` — all user commands
- ✅ `handlers/admin_handlers.py` — all admin commands
- ✅ `services/geolocation.py` — external API calls + IP validation
- ✅ `services/database.py` — all SQLite operations
- ✅ `utils/ratelimit.py` — cooldown logic
- ✅ `main.py` — entry point, handler registration, polling start

---

## 📋 Full Command Reference

| Command | Access | Description |
|---------|--------|-------------|
| `/start` | All users | Welcome message & overview |
| `/help` | All users | List all commands |
| `/ip <ip>` | All users | Geolocate an IP address |
| `/zip <code>` | All users | Look up a postal code (US default) |
| `/zip <country> <code>` | All users | Look up a code in a specific country |
| `/history` | All users | View last 10 lookups |
| `/export` | All users | Download full history as CSV |
| `/stats` | Admin only | Bot usage statistics |
| `/broadcast <msg>` | Admin only | Message all users |
| `/ban <user_id>` | Admin only | Ban a user |
| `/unban <user_id>` | Admin only | Unban a user |