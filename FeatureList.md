# 🌍 Feature List — IP Intelligence & OSINT Telegram Bot

A complete list of every feature built into this bot.

---

## 🌐 IP Intelligence (upgraded)

- ✅ `/ip <address>` — full IP intelligence report
- ✅ Returns: country, country code, region, city, postal code, ISP, org, ASN, AS name, coordinates, timezone, reverse DNS
- ✅ IPv4 and IPv6 validation (rejects invalid addresses)
- ✅ Graceful error handling for private/reserved IPs
- ✅ **Risk analysis** on every IP (see Risk Analysis section)
- ✅ **Google Maps & OpenStreetMap links** on every successful lookup
- ✅ Data source: ip-api.com (extended fields: as, asname, reverse, mobile, proxy, hosting)
- ✅ Accuracy disclaimer appended to every result
- ✅ Professional emoji-section formatting (Location, Network, ISP, ASN, Coordinates, Risk, Maps, Notes)

## 🖥️ Domain Lookup (NEW)

- ✅ `/domain <domain>` — resolve & geolocate a domain
- ✅ DNS resolution: IPv4 and IPv6 addresses (if available)
- ✅ Primary IP identification (first IPv4, fallback to IPv6)
- ✅ Reverse DNS (PTR) for the resolved IP
- ✅ Geolocation of the primary IP (reuses ip-api service)
- ✅ Country, region, city, ISP, ASN, coordinates, timezone
- ✅ Risk analysis (reuses the IP risk engine)
- ✅ Google Maps & OpenStreetMap links
- ✅ Domain name validation (RFC-compliant regex)
- ✅ Graceful DNS-failure handling
- ✅ Cached (`domain:<name>` key, 30-min TTL)

## 📇 WHOIS / RDAP (NEW)

- ✅ `/whois <ip or domain>` — WHOIS/RDAP lookup
- ✅ Works for both IPs and domain names (auto-detected)
- ✅ Returns: ASN, organization, netname, CIDR, abuse contact, country, registry, creation date
- ✅ Uses RDAP protocol (rdap.org bootstrap + ARIN fallback)
- ✅ Never fabricates missing fields — shows "N/A" instead
- ✅ Cached (`whois:<query>` key, 30-min TTL)
- ✅ Graceful "no records found" handling

## 🔁 Reverse DNS (NEW)

- ✅ `/rdns <ip>` — PTR record lookup
- ✅ Uses asyncio `getnameinfo` with executor fallback (`gethostbyaddr`)
- ✅ Graceful "No PTR record found" when none exists
- ✅ Handles timeouts and DNS errors without crashing
- ✅ Cached (`rdns:<ip>` key, 30-min TTL)

## 📂 Bulk IP Scanner (NEW)

- ✅ `/scan` — upload a TXT or CSV file with IPs (one per line)
- ✅ Parses both plain-text and CSV formats (auto-detects IP columns)
- ✅ Deduplicates IPs
- ✅ Max 500 IPs per scan (configurable via `BULK_MAX_IPS`)
- ✅ Cache-aware — reuses fresh cached results to minimize API calls
- ✅ Respects ip-api rate limits (pauses every 45 requests)
- ✅ Generates a CSV report with columns: IP, Country, City, ISP, ASN, Risk, Latitude, Longitude, Status
- ✅ Sends CSV as a Telegram document with success/fail summary
- ✅ Temp file cleaned up automatically

## 🛡️ IP Risk Analysis (NEW)

- ✅ Analyzes every IP (standalone via `/ip`, embedded in `/domain` and `/scan`)
- ✅ Detects:
  - Private IP (RFC 1918 / RFC 4193)
  - Loopback (127.0.0.0/8, ::1)
  - Reserved ranges
  - Multicast
  - Proxy/VPN (ip-api flag)
  - Hosting/Datacenter (ip-api flag)
  - Mobile network (ip-api flag)
  - Tor exit node (detected via ISP/org/AS name markers)
  - VPN/anonymizer (detected via ISP/org name markers)
- ✅ Risk levels: 🟢 Low, 🟡 Medium, 🔴 High
- ✅ Explains WHY the score was assigned (bullet-point reasons)
- ✅ Never invents data — only uses reliable API responses and IANA classification

## 🗺️ Maps (NEW)

- ✅ Every successful IP and domain lookup includes:
  - 📍 Google Maps link: `https://maps.google.com/?q=<lat>,<lon>`
  - 🗺 OpenStreetMap link: `https://www.openstreetmap.org/?mlat=<lat>&mlon=<lon>`

## 📮 Postal / Zip Code Lookup

- ✅ `/zip <code>` — look up a postal code (defaults to US for digit-only codes)
- ✅ `/zip <country> <code>` — look up codes in any supported country (US, CA, UK, etc.)
- ✅ Handles multi-place results (lists all matching places with name, state, coordinates)
- ✅ Clean 404 handling when a postal code isn't found
- ✅ Data source: zippopotam.us (free, no API key)
- ✅ Emoji-formatted output

## 📜 History & Export

- ✅ `/history` — shows the user's last 10 lookups (most recent first)
- ✅ Numbered list with type-specific emojis (🌐 IP, 📮 zip, 🖥️ domain, 📇 whois, 🔁 rdns, 📂 scan)
- ✅ Includes risk level where available
- ✅ Polite "no history" message when empty
- ✅ `/export` — downloads the user's full lookup history as a CSV file
- ✅ CSV columns: type, query, result_summary, timestamp
- ✅ Result summaries adapted per lookup type (ip, domain, zip, whois, rdns)
- ✅ Sent as a Telegram document attachment
- ✅ Temp file cleaned up automatically after sending

## ⚡ Rate Limiting

- ✅ Per-user cooldown: 3 seconds between all lookup commands (/ip, /zip, /domain, /whois, /rdns)
- ✅ In-memory tracking (no Redis needed)
- ✅ Friendly cooldown message: "⏳ Please wait a few seconds before your next lookup."

## 💾 Caching

- ✅ SQLite-based cache for all lookup types:
  - `ip:<ip>` — IP geolocation
  - `zip:<country>:<code>` — postal code lookup
  - `domain:<name>` — domain lookup (DNS + geo + risk)
  - `whois:<query>` — WHOIS/RDAP
  - `rdns:<ip>` — reverse DNS
- ✅ Cache TTL: 30 minutes (expired entries are re-fetched)
- ✅ Reduces external API calls and speeds up repeat lookups

## 🛡️ Admin Panel

- ✅ Admin-only access (restricted to `ADMIN_IDS` env var)
- ✅ Non-admins get "⛔ Admin only command." response
- ✅ `/stats` — enhanced statistics:
  - Total users, total lookups, lookups today
  - Lookup type breakdown (ip, zip, domain, whois, rdns, scan)
  - Top 5 most-queried IPs/zips
  - **Top 5 countries searched** (NEW)
  - **Top 5 ISPs searched** (NEW)
  - **Top 5 most searched domains** (NEW)
  - **Daily lookup graph** (last 14 days, text-based bar chart) (NEW)
  - **Average lookup time** (ms) (NEW)
  - **Cache hit ratio** (cache entries vs total lookups) (NEW)
- ✅ `/broadcast <message>` — send a message to every registered user
  - 0.05s delay between sends
  - Per-user try/except
  - Reports success/fail counts
- ✅ `/ban <user_id>` — ban a user
- ✅ `/unban <user_id>` — unban a user

## 🚫 User Management

- ✅ Auto-registration on `/start` or first interaction
- ✅ Banned users are blocked from all commands
- ✅ Banned users receive "You are banned from using this bot."
- ✅ Username tracking and updates

## 🗄️ Database (SQLite)

- ✅ Three tables: `users`, `lookups`, `cache`
- ✅ **Extended `lookups` table** with columns: country, city, isp, asn, lat, lon, risk_level, lookup_time_ms (NEW)
- ✅ Non-destructive migrations (`ALTER TABLE ADD COLUMN` guarded by PRAGMA checks)
- ✅ Indexes on (user_id, id DESC) and (created_at) for faster queries
- ✅ Auto-created on startup (`CREATE TABLE IF NOT EXISTS`)
- ✅ `data/` directory auto-created if missing
- ✅ WAL journal mode for concurrent read/write safety
- ✅ Parameterized SQL queries everywhere (no injection risk)
- ✅ Thread-safe access with a threading lock

## 🎨 Output Formatting (NEW)

- ✅ Professional emoji-section layout for all responses
- ✅ Sections: 🌍 Location, 🛰️ Network, 🏢 ISP, 📡 ASN, 📍 Coordinates, ⚠️ Risk Analysis, 🗺️ Maps, 📝 Notes
- ✅ Consistent visual style across /ip, /domain, /whois, /rdns
- ✅ Handles Telegram's 4096-char limit by splitting on section boundaries

## 🔄 Async & Error Handling

- ✅ Fully async handlers (python-telegram-bot v21, async/await)
- ✅ Async HTTP client (httpx)
- ✅ Async DNS resolution (asyncio + socket)
- ✅ Catches `httpx.TimeoutException` — shows timeout message
- ✅ Catches `httpx.HTTPError` — shows service-unreachable message
- ✅ Catches `socket.gaierror` — shows DNS-failure message
- ✅ Generic exception fallback for unexpected errors
- ✅ All exceptions logged at ERROR level
- ✅ Bot never crashes on API failures, DNS failures, invalid input, or rate limits

## 📝 Logging

- ✅ Python `logging` module at INFO level (stdout)
- ✅ Command usage logged at INFO
- ✅ Exceptions logged at ERROR
- ✅ Cache hits logged at INFO
- ✅ Captured by Railway's log viewer automatically

## 🔒 Security

- ✅ Bot token read from `BOT_TOKEN` env var (never hardcoded)
- ✅ Admin IDs parsed from `ADMIN_IDS` env var
- ✅ `.env` in `.gitignore` (secrets never committed)
- ✅ No SQL string formatting (parameterized queries only)
- ✅ WHOIS data never fabricated — missing fields shown as N/A

## 🚂 Deployment (Railway)

- ✅ `Procfile` with `worker: python main.py`
- ✅ `railway.toml` with restart-on-failure policy (max 5 retries)
- ✅ Persistent volume support (`DB_PATH` → `/app/data/bot.db`)
- ✅ `requirements.txt` with pinned versions
- ✅ `.env.example` with all variables documented
- ✅ Long-polling mode (no webhook setup needed)
- ✅ `README.md` with full deployment guide

## 📁 Project Structure

- ✅ Clean multi-file layout (not one giant script)
- ✅ `config.py` — env var loading & API URL templates
- ✅ `handlers/user_handlers.py` — all user commands
- ✅ `handlers/admin_handlers.py` — all admin commands
- ✅ `services/geolocation.py` — ip-api, zippopotam, RDAP, DNS, risk analysis
- ✅ `services/database.py` — all SQLite operations + migrations + stats
- ✅ `utils/ratelimit.py` — cooldown logic
- ✅ `utils/formatters.py` — professional message formatting (NEW)
- ✅ `main.py` — entry point, handler registration, polling start

## ⚡ Performance

- ✅ Cache-first strategy for all lookup types
- ✅ Bulk scanner reuses cached IP results
- ✅ Rate-limit pauses in bulk scan (every 45 IPs)
- ✅ Async I/O throughout (no blocking calls)
- ✅ SQLite WAL mode for concurrent reads
- ✅ Indexes on frequently queried columns

---

## 📋 Full Command Reference

| Command | Access | Description |
|---------|--------|-------------|
| `/start` | All users | Welcome message & overview |
| `/help` | All users | List all commands |
| `/ip <ip>` | All users | IP intelligence report (geo + risk + maps) |
| `/domain <domain>` | All users | Domain lookup (DNS + geo + risk + maps) |
| `/whois <ip\|domain>` | All users | WHOIS / RDAP lookup |
| `/rdns <ip>` | All users | Reverse DNS (PTR record) |
| `/scan` | All users | Bulk IP scan from TXT/CSV → CSV report |
| `/zip <code>` | All users | Look up a postal code (US default) |
| `/zip <country> <code>` | All users | Look up a code in a specific country |
| `/history` | All users | View last 10 lookups |
| `/export` | All users | Download full history as CSV |
| `/stats` | Admin only | Full bot statistics |
| `/broadcast <msg>` | Admin only | Message all users |
| `/ban <user_id>` | Admin only | Ban a user |
| `/unban <user_id>` | Admin only | Unban a user |