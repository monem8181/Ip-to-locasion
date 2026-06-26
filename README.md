# 🌍 IP Intelligence & OSINT Telegram Bot

A professional, production-ready Telegram bot for **IP intelligence**, **domain lookup**, **WHOIS/RDAP**, **reverse DNS**, **risk analysis**, **bulk IP scanning**, and **postal/zip code lookup** — with history tracking, rate limiting, caching, and an admin panel.

---

## ✨ Features

### 🔍 Lookup & Intelligence
- 🌐 **IP Intelligence** — country, region, city, postal, ISP, ASN, coordinates, timezone, reverse DNS, mobile/proxy/hosting flags
- 🖥️ **Domain Lookup** — DNS resolution (IPv4+IPv6), geolocation, reverse DNS, risk analysis
- 📇 **WHOIS / RDAP** — ASN, organization, netname, CIDR, abuse contact, registry, creation date (for IPs and domains)
- 🔁 **Reverse DNS** — PTR record lookup with graceful "no record" handling
- 📮 **Postal/Zip Lookup** — US, UK, Canada, and more (multi-place results)

### 🛡️ Risk Analysis
- 🟢🟡🔴 **Risk scoring** for every IP — detects private, loopback, reserved, multicast, proxy/VPN, hosting/datacenter, mobile, Tor exit node markers
- Explains *why* each score was assigned
- Never invents data — only uses reliable API responses

### 📂 Bulk Scanner
- 📄 **/scan** — upload a TXT or CSV file with one IP per line
- Generates a CSV report (IP, Country, City, ISP, ASN, Risk, Lat, Lon, Status)
- Cache-aware to minimize API calls
- Respects ip-api rate limits (45 req/min)

### 🗺️ Maps
- Every IP/domain result includes Google Maps and OpenStreetMap links

### 📜 History & Export
- /history — last 10 lookups with risk levels
- /export — full history as CSV download

### ⚡ Rate Limiting & Caching
- 3-second per-user cooldown
- 30-minute TTL SQLite cache (IP, zip, domain, whois, rdns)

### 🛡️ Admin Panel
- /stats — total users, lookups, top countries, top ISPs, top domains, daily graph, avg lookup time, cache hit ratio
- /broadcast, /ban, /unban

---

## 🛠️ Tech Stack

| Layer | Tech |
|-------|------|
| Language | Python 3.12+ |
| Bot framework | python-telegram-bot 21+ (async) |
| HTTP client | httpx (async) |
| DNS | asyncio + socket (stdlib) |
| WHOIS | RDAP (httpx) |
| Storage | SQLite (WAL mode) |
| Config | python-dotenv |
| Deployment | Railway (Pro, persistent volume) |

---

## 📁 Project Structure

```
.
├── main.py                     # Entry point — builds & starts the bot
├── config.py                   # Loads env vars & API URLs
├── handlers/
│   ├── __init__.py
│   ├── user_handlers.py        # /start /help /ip /domain /whois /rdns /scan /zip /history /export
│   └── admin_handlers.py       # /stats /broadcast /ban /unban
├── services/
│   ├── __init__.py
│   ├── database.py             # SQLite: init, migrations, users, lookups, cache, stats
│   └── geolocation.py          # ip-api, zippopotam, RDAP whois, DNS, risk analysis
├── utils/
│   ├── __init__.py
│   ├── ratelimit.py            # In-memory per-user cooldown
│   └── formatters.py           # Professional emoji-section message formatting
├── data/                       # SQLite DB lives here (mounted volume on Railway)
├── requirements.txt
├── Procfile
├── railway.toml
├── .env.example
├── .gitignore
├── README.md
└── FeatureList.md
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
   - Open a chat with @BotFather → `/newbot` → follow prompts → copy token

4. **Find your Telegram user ID** (for admin access)
   - Open [@userinfobot](https://t.me/userinfobot) → send any message → get your numeric ID

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
   Logs:
   ```
   [INFO] Database initialized at ./data/bot.db
   [INFO] Starting bot (long-polling)...
   ```

---

## 🚂 Deploy on Railway (Pro)

### 1. Create a new Railway project
- Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo**
- Select your repo

### 2. Set environment variables
In Railway → your service → **Variables** tab:

| Variable | Value |
|----------|-------|
| `BOT_TOKEN` | your Telegram bot token |
| `ADMIN_IDS` | comma-separated admin user IDs |
| `DB_PATH` | `/app/data/bot.db` |

### 3. Attach a persistent volume
- **Settings** → **Volumes** → **Add Volume**
- **Mount path:** `/app/data`
- This keeps the SQLite database across restarts

### 4. Deploy
Railway auto-detects the `Procfile`:
```
worker: python main.py
```
Logs appear in Railway's **Logs** tab.

---

## 📋 Command Reference

### User Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message & overview |
| `/help` | Show all commands |
| `/ip <ip>` | IP intelligence report (geo + ISP + ASN + risk + maps) |
| `/domain <domain>` | Resolve & geolocate a domain (IPv4/IPv6 + risk + maps) |
| `/whois <ip\|domain>` | WHOIS / RDAP lookup |
| `/rdns <ip>` | Reverse DNS (PTR record) |
| `/scan` | Bulk IP scan from TXT/CSV file → CSV report |
| `/zip <code>` | Postal/zip code lookup (US default) |
| `/zip <country> <code>` | Look up a code in a specific country |
| `/history` | View last 10 lookups (with risk levels) |
| `/export` | Download full history as CSV |

### Admin Commands
*(Restricted to user IDs in `ADMIN_IDS`)*

| Command | Description |
|---------|-------------|
| `/stats` | Full statistics: users, lookups, top countries/ISPs/domains, daily graph, avg time, cache ratio |
| `/broadcast <message>` | Message all users |
| `/ban <user_id>` | Ban a user |
| `/unban <user_id>` | Unban a user |

---

## 🌐 Data Sources

| Source | Use | Key needed |
|--------|-----|------------|
| [ip-api.com](http://ip-api.com) | IP geolocation + proxy/hosting/mobile flags + reverse DNS | No (free, 45 req/min) |
| [zippopotam.us](https://api.zippopotam.us) | Postal/zip code lookup | No |
| [RDAP](https://rdap.org) / [arin.net](https://rdap.arin.net) | WHOIS for IPs and domains | No |
| Python `socket` / `asyncio` | DNS resolution & reverse DNS | N/A (stdlib) |

⚠️ *IP geolocation is approximate (city-level) and does not reveal an exact street address. Risk analysis only uses reliable API data — never fabricated.*

---

## 🔒 Notes

- All SQL queries use parameterized statements (no injection risk)
- Per-user rate limit: 3 seconds between lookups (in-memory)
- Cache TTL: 30 minutes (SQLite `cache` table) — covers IP, zip, domain, whois, rdns
- Bot token read from `BOT_TOKEN` env var (never hardcoded)
- Logging at INFO (stdout) — Railway captures automatically
- Database migrations are non-destructive (`ALTER TABLE ADD COLUMN` guarded by PRAGMA checks)
- Bulk scan respects ip-api rate limits (pauses every 45 requests)