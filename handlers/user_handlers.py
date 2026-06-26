import csv
import json
import os
import time
import logging
import tempfile
import asyncio

import httpx
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

import config
import services.database as db
import services.geolocation as geo
from utils.ratelimit import check_rate_limit
from utils.formatters import (
    format_ip_result,
    format_zip_result,
    format_domain_result,
    format_whois_result,
    format_rdns_result,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cache_fresh(cached_at: float) -> bool:
    return (time.time() - cached_at) < config.CACHE_TTL_SECONDS


def _ensure_user(update: Update) -> bool:
    user = update.effective_user
    if not user:
        return False
    db.get_or_create_user(user.id, user.username)
    if db.is_banned(user.id):
        return False
    return True


async def _send_too_long(update: Update, text: str) -> None:
    """Send text, handling Telegram's 4096-char limit by splitting if needed."""
    if len(text) <= 4096:
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
        return
    # Split on section boundaries if possible
    parts = text.split("\n━━━")
    chunk = parts[0]
    for part in parts[1:]:
        candidate = chunk + "\n━━━" + part
        if len(candidate) > 4000:
            await update.message.reply_text(chunk, parse_mode=ParseMode.MARKDOWN)
            chunk = "━━━" + part
        else:
            chunk = candidate
    if chunk:
        await update.message.reply_text(chunk, parse_mode=ParseMode.MARKDOWN)


# ---------------------------------------------------------------------------
# /start
# ---------------------------------------------------------------------------

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user:
        db.get_or_create_user(user.id, user.username)
        if db.is_banned(user.id):
            await update.message.reply_text("You are banned from using this bot.")
            return

    text = (
        "👋 Welcome to the **IP Intelligence & OSINT Bot**!\n\n"
        "I perform IP geolocation, domain resolution, WHOIS/RDAP lookups, "
        "reverse DNS, risk analysis, and postal/zip code lookups — with "
        "maps, bulk scanning, history, and CSV export.\n\n"
        "📌 *Commands:*\n"
        "/ip `<ip>` — IP intelligence report (geo + risk + maps)\n"
        "/domain `<domain>` — Domain lookup (DNS + geo + risk)\n"
        "/whois `<ip|domain>` — WHOIS / RDAP lookup\n"
        "/rdns `<ip>` — Reverse DNS (PTR record)\n"
        "/scan — Bulk IP scan from a TXT/CSV file\n"
        "/zip `<code>` — Postal/zip code lookup (defaults to US)\n"
        "/zip `<country> <code>` — Postal code for another country\n"
        "/history — View your last 10 lookups\n"
        "/export — Download your full history as a CSV\n"
        "/help — Show all commands\n\n"
        "Type /help anytime to see this list again. 🚀"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


# ---------------------------------------------------------------------------
# /help
# ---------------------------------------------------------------------------

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _ensure_user(update):
        await update.message.reply_text("You are banned from using this bot.")
        return

    text = (
        "📖 *Command reference:*\n\n"
        "━━━ 🔍 *Lookup* ━━━\n"
        "/ip `<ip>` — IP intelligence report (geo, ISP, ASN, risk, maps)\n"
        "/domain `<domain>` — Resolve & geolocate a domain\n"
        "/whois `<ip|domain>` — WHOIS / RDAP records\n"
        "/rdns `<ip>` — Reverse DNS (PTR record)\n"
        "/zip `<postal_code>` — Postal/zip code lookup (US default)\n"
        "/zip `<country_code> <postal_code>` — Another country\n\n"
        "━━━ 📂 *Bulk* ━━━\n"
        "/scan — Upload a TXT/CSV file with IPs (one per line)\n\n"
        "━━━ 📜 *History* ━━━\n"
        "/history — Your last 10 lookups\n"
        "/export — Full history as CSV download\n\n"
        "━━━ 🛡️ *Admin* (restricted) ━━━\n"
        "/stats — Bot usage statistics\n"
        "/broadcast `<message>` — Message all users\n"
        "/ban `<user_id>` — Ban a user\n"
        "/unban `<user_id>` — Unban a user\n"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


# ---------------------------------------------------------------------------
# /ip
# ---------------------------------------------------------------------------

async def ip_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _ensure_user(update):
        await update.message.reply_text("You are banned from using this bot.")
        return

    user = update.effective_user

    allowed, remaining = check_rate_limit(user.id)
    if not allowed:
        await update.message.reply_text("⏳ Please wait a few seconds before your next lookup.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /ip <ip_address>")
        return

    ip = context.args[0].strip()

    if not geo.is_valid_ip(ip):
        await update.message.reply_text(
            f"❌ `{ip}` is not a valid IP address.\n"
            "Please provide a valid IPv4 or IPv6 address.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    t0 = time.monotonic()
    cache_key = f"ip:{ip}"

    cached_json, cached_at = db.get_cache(cache_key)
    if cached_json is not None and _cache_fresh(cached_at):
        logging.info("Cache hit for %s", cache_key)
        result = json.loads(cached_json)
    else:
        try:
            result = await geo.lookup_ip(ip)
        except httpx.TimeoutException:
            await update.message.reply_text("⌛ The IP lookup service timed out. Please try again later.")
            logging.error("ip-api timeout for %s", ip)
            return
        except httpx.HTTPError as e:
            await update.message.reply_text("⚠️ Could not reach the IP lookup service. Please try again later.")
            logging.error("ip-api HTTP error for %s: %s", ip, e)
            return
        except Exception as e:
            await update.message.reply_text("⚠️ An unexpected error occurred.")
            logging.error("ip-api unexpected error for %s: %s", ip, e)
            return

        db.set_cache(cache_key, json.dumps(result))

    # Handle API error status (private/reserved IP)
    if result.get("status") != "success":
        msg = result.get("message", "Unknown error")
        await update.message.reply_text(
            f"❌ IP lookup failed: {msg}\n"
            "(This can happen with private/reserved IPs.)"
        )
        return

    # Risk analysis (uses ip-api flags + ipaddress classification)
    risk = await geo.analyze_ip_risk(ip, result)

    elapsed_ms = int((time.monotonic() - t0) * 1000)

    text = format_ip_result(ip, result, risk)
    await _send_too_long(update, text)

    db.save_lookup(
        user.id, "ip", ip, json.dumps(result),
        country=result.get("country"),
        city=result.get("city"),
        isp=result.get("isp"),
        asn=result.get("as"),
        lat=result.get("lat"),
        lon=result.get("lon"),
        risk_level=risk.get("level"),
        lookup_time_ms=elapsed_ms,
    )


# ---------------------------------------------------------------------------
# /domain
# ---------------------------------------------------------------------------

async def domain_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _ensure_user(update):
        await update.message.reply_text("You are banned from using this bot.")
        return

    user = update.effective_user

    allowed, _ = check_rate_limit(user.id)
    if not allowed:
        await update.message.reply_text("⏳ Please wait a few seconds before your next lookup.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /domain <domain>\nExample: /domain google.com")
        return

    domain = context.args[0].strip().lower().rstrip(".")

    if not geo.is_valid_domain(domain):
        await update.message.reply_text(
            f"❌ `{domain}` is not a valid domain name.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    t0 = time.monotonic()
    cache_key = f"domain:{domain}"

    cached_json, cached_at = db.get_cache(cache_key)
    if cached_json is not None and _cache_fresh(cached_at):
        logging.info("Cache hit for %s", cache_key)
        result = json.loads(cached_json)
    else:
        try:
            result = await geo.lookup_domain(domain)
        except httpx.TimeoutException:
            await update.message.reply_text("⌛ Domain lookup timed out. Please try again later.")
            logging.error("domain lookup timeout for %s", domain)
            return
        except httpx.HTTPError as e:
            await update.message.reply_text("⚠️ Could not reach the lookup service. Please try again later.")
            logging.error("domain lookup HTTP error for %s: %s", domain, e)
            return
        except (socket_gaierror := __import__("socket").gaierror) as e:
            await update.message.reply_text(
                f"❌ Could not resolve domain `{domain}`.\n"
                "DNS resolution failed — check the domain spelling.",
                parse_mode=ParseMode.MARKDOWN,
            )
            logging.error("DNS resolution failed for %s: %s", domain, e)
            return
        except Exception as e:
            await update.message.reply_text("⚠️ An unexpected error occurred.")
            logging.error("domain lookup unexpected error for %s: %s", domain, e)
            return

        db.set_cache(cache_key, json.dumps(result))

    elapsed_ms = int((time.monotonic() - t0) * 1000)
    text = format_domain_result(result)
    await _send_too_long(update, text)

    geo_data = result.get("geo") or {}
    risk = result.get("risk") or {}
    db.save_lookup(
        user.id, "domain", domain, json.dumps(result),
        country=geo_data.get("country"),
        city=geo_data.get("city"),
        isp=geo_data.get("isp"),
        asn=geo_data.get("as"),
        lat=geo_data.get("lat"),
        lon=geo_data.get("lon"),
        risk_level=risk.get("level"),
        lookup_time_ms=elapsed_ms,
    )


# ---------------------------------------------------------------------------
# /whois
# ---------------------------------------------------------------------------

async def whois_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _ensure_user(update):
        await update.message.reply_text("You are banned from using this bot.")
        return

    user = update.effective_user

    allowed, _ = check_rate_limit(user.id)
    if not allowed:
        await update.message.reply_text("⏳ Please wait a few seconds before your next lookup.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /whois <ip or domain>\nExample: /whois 8.8.8.8")
        return

    query = context.args[0].strip()
    is_domain = not geo.is_valid_ip(query)

    if is_domain:
        normalized = query.lower().rstrip(".")
        if not geo.is_valid_domain(normalized):
            await update.message.reply_text(
                f"❌ `{query}` is neither a valid IP nor a valid domain.",
                parse_mode=ParseMode.MARKDOWN,
            )
            return
        query = normalized

    cache_key = f"whois:{query}"

    cached_json, cached_at = db.get_cache(cache_key)
    if cached_json is not None and _cache_fresh(cached_at):
        logging.info("Cache hit for %s", cache_key)
        result = json.loads(cached_json)
    else:
        try:
            if is_domain:
                result = await geo.lookup_whois_domain(query)
            else:
                result = await geo.lookup_whois_ip(query)
        except httpx.TimeoutException:
            await update.message.reply_text("⌛ WHOIS lookup timed out. Please try again later.")
            logging.error("whois timeout for %s", query)
            return
        except httpx.HTTPError as e:
            await update.message.reply_text("⚠️ Could not reach the WHOIS service. Please try again later.")
            logging.error("whois HTTP error for %s: %s", query, e)
            return
        except Exception as e:
            await update.message.reply_text("⚠️ An unexpected error occurred.")
            logging.error("whois unexpected error for %s: %s", query, e)
            return

        if result is None:
            await update.message.reply_text(
                f"❌ No WHOIS/RDAP records found for `{query}`.",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        db.set_cache(cache_key, json.dumps(result))

    text = format_whois_result(query, result, is_domain=is_domain)
    await _send_too_long(update, text)

    db.save_lookup(user.id, "whois", query, json.dumps(result))


# ---------------------------------------------------------------------------
# /rdns
# ---------------------------------------------------------------------------

async def rdns_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _ensure_user(update):
        await update.message.reply_text("You are banned from using this bot.")
        return

    user = update.effective_user

    allowed, _ = check_rate_limit(user.id)
    if not allowed:
        await update.message.reply_text("⏳ Please wait a few seconds before your next lookup.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /rdns <ip>\nExample: /rdns 8.8.8.8")
        return

    ip = context.args[0].strip()

    if not geo.is_valid_ip(ip):
        await update.message.reply_text(
            f"❌ `{ip}` is not a valid IP address.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    cache_key = f"rdns:{ip}"

    cached_json, cached_at = db.get_cache(cache_key)
    if cached_json is not None and _cache_fresh(cached_at):
        logging.info("Cache hit for %s", cache_key)
        hostname = json.loads(cached_json).get("hostname")
    else:
        try:
            hostname = await geo.reverse_dns(ip)
        except Exception as e:
            await update.message.reply_text("⚠️ Reverse DNS lookup failed.")
            logging.error("rdns error for %s: %s", ip, e)
            return

        db.set_cache(cache_key, json.dumps({"hostname": hostname}))

    text = format_rdns_result(ip, hostname)
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

    db.save_lookup(user.id, "rdns", ip, json.dumps({"hostname": hostname}))


# ---------------------------------------------------------------------------
# /scan — bulk IP scanner
# ---------------------------------------------------------------------------

async def scan_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _ensure_user(update):
        await update.message.reply_text("You are banned from using this bot.")
        return

    user = update.effective_user

    if not update.message or not update.message.document:
        await update.message.reply_text(
            "📂 Send a TXT or CSV file with one IP per line.\n"
            "Usage: reply with /scan and attach a file, or send the file then /scan."
        )
        return

    document = update.message.document
    file_obj = await document.get_file()
    file_bytes = await file_obj.download_as_bytearray()

    try:
        raw = file_bytes.decode("utf-8", errors="replace")
    except Exception:
        raw = file_bytes.decode("latin-1", errors="replace")

    # Extract IPs: handle CSV (find IP-like column) and plain TXT
    ips: list[str] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # If it looks like CSV, try each comma-separated cell
        if "," in line:
            for cell in line.split(","):
                cell = cell.strip().strip('"').strip("'")
                if cell and geo.is_valid_ip(cell):
                    ips.append(cell)
        else:
            if geo.is_valid_ip(line):
                ips.append(line)

    # Deduplicate while preserving order
    seen = set()
    unique_ips = []
    for ip in ips:
        if ip not in seen:
            seen.add(ip)
            unique_ips.append(ip)

    if not unique_ips:
        await update.message.reply_text("❌ No valid IP addresses found in the file.")
        return

    if len(unique_ips) > config.BULK_MAX_IPS:
        await update.message.reply_text(
            f"⚠️ Found {len(unique_ips)} IPs. Limit is {config.BULK_MAX_IPS}. "
            f"Only the first {config.BULK_MAX_IPS} will be scanned."
        )
        unique_ips = unique_ips[: config.BULK_MAX_IPS]

    await update.message.reply_text(
        f"🔍 Scanning {len(unique_ips)} IP(s)… This may take a moment."
    )

    rows: list[dict] = []
    for i, ip in enumerate(unique_ips):
        # Check cache first
        cache_key = f"ip:{ip}"
        cached_json, cached_at = db.get_cache(cache_key)
        result = None
        if cached_json is not None and _cache_fresh(cached_at):
            result = json.loads(cached_json)
        else:
            try:
                result = await geo.lookup_ip(ip)
                if result.get("status") == "success":
                    db.set_cache(cache_key, json.dumps(result))
            except Exception as e:
                logging.warning("Bulk scan error for %s: %s", ip, e)
                result = None

        if result and result.get("status") == "success":
            risk = await geo.analyze_ip_risk(ip, result)
            rows.append({
                "IP": ip,
                "Country": result.get("country", ""),
                "City": result.get("city", ""),
                "ISP": result.get("isp", ""),
                "ASN": result.get("as", ""),
                "Risk": risk.get("level", ""),
                "Latitude": result.get("lat", ""),
                "Longitude": result.get("lon", ""),
                "Status": "OK",
            })
        else:
            rows.append({
                "IP": ip,
                "Country": "",
                "City": "",
                "ISP": "",
                "ASN": "",
                "Risk": "",
                "Latitude": "",
                "Longitude": "",
                "Status": "FAIL",
            })

        # Small delay to respect ip-api rate limits
        if (i + 1) % 45 == 0:
            await asyncio.sleep(1)
        else:
            await asyncio.sleep(config.BULK_BATCH_DELAY)

    # Generate CSV report
    tmp_path = None
    try:
        fd, tmp_path = tempfile.mkstemp(suffix=".csv", prefix="bulk_scan_")
        os.close(fd)
        with open(tmp_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "IP", "Country", "City", "ISP", "ASN",
                    "Risk", "Latitude", "Longitude", "Status",
                ],
            )
            writer.writeheader()
            writer.writerows(rows)

        with open(tmp_path, "rb") as f:
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=f,
                filename="bulk_scan_report.csv",
                caption=f"📊 Bulk scan complete: {len(rows)} IPs scanned.\n"
                        f"✅ OK: {sum(1 for r in rows if r['Status'] == 'OK')}\n"
                        f"❌ FAIL: {sum(1 for r in rows if r['Status'] == 'FAIL')}",
            )
    except Exception as e:
        logging.error("Bulk scan CSV generation failed: %s", e)
        await update.message.reply_text("⚠️ Could not generate the scan report.")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


# ---------------------------------------------------------------------------
# /zip
# ---------------------------------------------------------------------------

async def zip_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _ensure_user(update):
        await update.message.reply_text("You are banned from using this bot.")
        return

    user = update.effective_user

    allowed, remaining = check_rate_limit(user.id)
    if not allowed:
        await update.message.reply_text("⏳ Please wait a few seconds before your next lookup.")
        return

    if not context.args:
        await update.message.reply_text(
            "Usage: /zip <postal_code>\n"
            "Or: /zip <country_code> <postal_code>"
        )
        return

    if len(context.args) == 2:
        country_code = context.args[0].strip().lower()
        postal_code = context.args[1].strip()
    else:
        postal_code = context.args[0].strip()
        if postal_code.isdigit():
            country_code = "us"
        else:
            parts = postal_code.split(maxsplit=1)
            if len(parts) == 2:
                country_code = parts[0].lower()
                postal_code = parts[1].strip()
            else:
                country_code = "us"

    cache_key = f"zip:{country_code}:{postal_code}"

    cached_json, cached_at = db.get_cache(cache_key)
    if cached_json is not None and _cache_fresh(cached_at):
        logging.info("Cache hit for %s", cache_key)
        result = json.loads(cached_json)
    else:
        try:
            result = await geo.lookup_zip(country_code, postal_code)
        except httpx.TimeoutException:
            await update.message.reply_text("⌛ The postal code lookup service timed out. Please try again later.")
            logging.error("zippopotam timeout for %s/%s", country_code, postal_code)
            return
        except httpx.HTTPError as e:
            await update.message.reply_text("⚠️ Could not reach the postal code lookup service. Please try again later.")
            logging.error("zippopotam HTTP error for %s/%s: %s", country_code, postal_code, e)
            return
        except Exception as e:
            await update.message.reply_text("⚠️ An unexpected error occurred.")
            logging.error("zippopotam unexpected error for %s/%s: %s", country_code, postal_code, e)
            return

        if result is None:
            await update.message.reply_text(
                f"❌ No results found for postal code `{postal_code}` "
                f"({country_code.upper()}).",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        db.set_cache(cache_key, json.dumps(result))

    text = format_zip_result(country_code, postal_code, result)
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

    db.save_lookup(user.id, "zip", f"{country_code} {postal_code}", json.dumps(result))


# ---------------------------------------------------------------------------
# /history
# ---------------------------------------------------------------------------

async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _ensure_user(update):
        await update.message.reply_text("You are banned from using this bot.")
        return

    user = update.effective_user
    rows = db.get_user_history(user.id, limit=10)

    if not rows:
        await update.message.reply_text("📭 You have no lookup history yet. Try /ip or /zip to get started!")
        return

    emoji_map = {
        "ip": "🌐", "zip": "📮", "domain": "🌐", "whois": "📇",
        "rdns": "🔁", "scan": "📂",
    }
    lines = ["📋 *Your last 10 lookups:*\n"]
    for i, row in enumerate(rows, 1):
        ltype = row["lookup_type"]
        query = row["query_value"]
        created = row["created_at"]
        emoji = emoji_map.get(ltype, "🔎")
        risk = row["risk_level"] if "risk_level" in row.keys() else None
        risk_str = f" [{risk}]" if risk else ""
        lines.append(f"{i}. {emoji} `{query}` — {created}{risk_str}")

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


# ---------------------------------------------------------------------------
# /export
# ---------------------------------------------------------------------------

async def export_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _ensure_user(update):
        await update.message.reply_text("You are banned from using this bot.")
        return

    user = update.effective_user
    rows = db.get_user_history_all(user.id)

    if not rows:
        await update.message.reply_text("📭 You have no lookup history to export.")
        return

    tmp_path = None
    try:
        fd, tmp_path = tempfile.mkstemp(suffix=".csv", prefix="bot_history_")
        os.close(fd)

        with open(tmp_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["type", "query", "result_summary", "timestamp"])
            for row in rows:
                result_summary = ""
                try:
                    data = json.loads(row["result_json"]) if row["result_json"] else {}
                    if row["lookup_type"] == "ip":
                        result_summary = f"{data.get('city', '')}, {data.get('country', '')}"
                    elif row["lookup_type"] == "domain":
                        geo_data = data.get("geo", {})
                        result_summary = f"{geo_data.get('city', '')}, {geo_data.get('country', '')}"
                    elif row["lookup_type"] == "zip":
                        places = data.get("places", [])
                        names = [p.get("place name", "") for p in places]
                        result_summary = "; ".join(names)
                    elif row["lookup_type"] == "whois":
                        result_summary = data.get("organization", "") or data.get("netname", "")
                    elif row["lookup_type"] == "rdns":
                        result_summary = data.get("hostname", "") or "no PTR"
                    else:
                        result_summary = ""
                except (json.JSONDecodeError, TypeError):
                    pass

                writer.writerow([
                    row["lookup_type"],
                    row["query_value"],
                    result_summary,
                    row["created_at"],
                ])

        with open(tmp_path, "rb") as f:
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=f,
                filename=f"history_{user.id}.csv",
                caption="📎 Your full lookup history (CSV).",
            )
    except Exception as e:
        logging.error("Export failed for user %s: %s", user.id, e)
        await update.message.reply_text("⚠️ Could not export your history. Please try again later.")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)