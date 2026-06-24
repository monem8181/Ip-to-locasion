import csv
import json
import os
import time
import logging
import tempfile

import httpx
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

import config
import services.database as db
import services.geolocation as geo
from utils.ratelimit import check_rate_limit


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
        "👋 Welcome to the **IP & Postal Code Lookup Bot**!\n\n"
        "I can tell you where an IP address is located (country, city, ISP, "
        "and more) and look up postal/zip codes around the world.\n\n"
        "📌 *Commands:*\n"
        "/ip `<ip>` — Geolocate an IP address\n"
        "/zip `<code>` — Look up a postal/zip code (defaults to US)\n"
        "/zip `<country> <code>` — Look up a code in a specific country\n"
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
        "/start — Welcome message & overview\n"
        "/help — This help screen\n"
        "/ip `<ip_address>` — Geolocate an IP address\n"
        "/zip `<postal_code>` — Look up a postal/zip code (US default)\n"
        "/zip `<country_code> <postal_code>` — Look up a code for another country\n"
        "/history — Your last 10 lookups\n"
        "/export — Download your full history as CSV\n"
        "/stats — (admin) Bot usage statistics\n"
        "/broadcast `<message>` — (admin) Message all users\n"
        "/ban `<user_id>` — (admin) Ban a user\n"
        "/unban `<user_id>` — (admin) Unban a user\n"
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

    # Rate limit
    allowed, remaining = check_rate_limit(user.id)
    if not allowed:
        await update.message.reply_text("⏳ Please wait a few seconds before your next lookup.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /ip <ip_address>")
        return

    ip = context.args[0].strip()

    # Validate
    if not geo.is_valid_ip(ip):
        await update.message.reply_text(
            f"❌ `{ip}` is not a valid IP address.\n"
            "Please provide a valid IPv4 or IPv6 address.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    cache_key = f"ip:{ip}"

    # Check cache
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

    # Handle API error status
    if result.get("status") != "success":
        msg = result.get("message", "Unknown error")
        await update.message.reply_text(
            f"❌ IP lookup failed: {msg}\n"
            "(This can happen with private/reserved IPs.)"
        )
        return

    text = _format_ip_result(ip, result)
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

    db.save_lookup(user.id, "ip", ip, json.dumps(result))


def _format_ip_result(ip: str, r: dict) -> str:
    return (
        "🌍 *IP Lookup Result*\n"
        f"📡 IP: `{ip}`\n"
        f"🏳️ Country: {r.get('country', 'N/A')} ({r.get('countryCode', 'N/A')})\n"
        f"🗺️ Region: {r.get('regionName', 'N/A')}\n"
        f"🏙️ City: {r.get('city', 'N/A')}\n"
        f"📮 Postal Code: {r.get('zip', 'N/A')}\n"
        f"🛰️ ISP: {r.get('isp', 'N/A')}\n"
        f"📍 Coordinates: {r.get('lat', 'N/A')}, {r.get('lon', 'N/A')}\n"
        f"🕐 Timezone: {r.get('timezone', 'N/A')}\n"
        "\n"
        "⚠️ _Note: IP geolocation is approximate (city-level) "
        "and does not reveal an exact street address._"
    )


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

    # Parse args: if 2 tokens, first is country; if 1 token and all digits,
    # default to "us"; if 1 token that's not all digits, treat as country+code
    # (we'll still try it as a single postal code for US).
    if len(context.args) == 2:
        country_code = context.args[0].strip().lower()
        postal_code = context.args[1].strip()
    else:
        postal_code = context.args[0].strip()
        if postal_code.isdigit():
            country_code = "us"
        else:
            # e.g. user sent "gb SW1A1AA" as a single arg — try to split
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

    text = _format_zip_result(country_code, postal_code, result)
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

    db.save_lookup(user.id, "zip", f"{country_code} {postal_code}", json.dumps(result))


def _format_zip_result(country_code: str, postal_code: str, result: dict) -> str:
    country = result.get("country", "N/A")
    country_abbrev = result.get("country abbreviation", country_code.upper())
    places = result.get("places", [])

    lines = [
        "📮 *Postal Code Lookup Result*",
        f"📮 Code: `{postal_code}`",
        f"🌍 Country: {country} ({country_abbrev})",
    ]

    if len(places) == 1:
        p = places[0]
        lines.append(f"🏙️ City/Place: {p.get('place name', 'N/A')}")
        lines.append(f"🗺️ State: {p.get('state', 'N/A')}")
        lines.append(f"📍 Coordinates: {p.get('latitude', 'N/A')}, {p.get('longitude', 'N/A')}")
    else:
        lines.append("\n*Multiple places found:*")
        for i, p in enumerate(places, 1):
            lines.append(f"\n{i}. {p.get('place name', 'N/A')}")
            lines.append(f"   🗺️ State: {p.get('state', 'N/A')}")
            lines.append(f"   📍 {p.get('latitude', 'N/A')}, {p.get('longitude', 'N/A')}")

    return "\n".join(lines)


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

    lines = ["📋 *Your last 10 lookups:*\n"]
    for i, row in enumerate(rows, 1):
        ltype = row["lookup_type"]
        query = row["query_value"]
        created = row["created_at"]
        emoji = "🌐" if ltype == "ip" else "📮"
        lines.append(f"{i}. {emoji} `{query}` — {created}")

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
                    else:
                        places = data.get("places", [])
                        names = [p.get("place name", "") for p in places]
                        result_summary = "; ".join(names)
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