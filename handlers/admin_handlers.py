import asyncio
import logging

from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

import config
import services.database as db


def is_admin(user_id: int) -> bool:
    return user_id in config.ADMIN_IDS


async def _admin_only(update: Update) -> bool:
    user = update.effective_user
    if not user or not is_admin(user.id):
        await update.message.reply_text("⛔ Admin only command.")
        return False
    return True


# ---------------------------------------------------------------------------
# /stats
# ---------------------------------------------------------------------------

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _admin_only(update):
        return

    stats = db.get_advanced_stats()

    # Type breakdown
    emoji_map = {
        "ip": "🌐", "zip": "📮", "domain": "🖥️", "whois": "📇",
        "rdns": "🔁", "scan": "📂",
    }
    type_lines = []
    for ltype, count in stats["type_breakdown"].items():
        emoji = emoji_map.get(ltype, "🔎")
        type_lines.append(f"   {emoji} {ltype}: {count}")
    type_text = "\n".join(type_lines) if type_lines else "   (none yet)"

    # Top queries
    top_lines = []
    for query, count in stats["top_queries"]:
        top_lines.append(f"   `{query}` — {count}×")
    top_text = "\n".join(top_lines) if top_lines else "   (none yet)"

    # Top countries
    country_lines = []
    for country, count in stats["top_countries"]:
        country_lines.append(f"   🏳️ {country} — {count}×")
    country_text = "\n".join(country_lines) if country_lines else "   (none yet)"

    # Top ISPs
    isp_lines = []
    for isp, count in stats["top_isps"]:
        isp_lines.append(f"   🏢 {isp} — {count}×")
    isp_text = "\n".join(isp_lines) if isp_lines else "   (none yet)"

    # Top domains
    domain_lines = []
    for domain, count in stats["top_domains"]:
        domain_lines.append(f"   🖥️ `{domain}` — {count}×")
    domain_text = "\n".join(domain_lines) if domain_lines else "   (none yet)"

    # Daily graph (text-based bar chart for last 14 days)
    graph_lines = []
    if stats["daily_graph"]:
        max_count = max(c for _, c in stats["daily_graph"]) or 1
        for day, count in stats["daily_graph"]:
            bar_len = max(1, int((count / max_count) * 20))
            graph_lines.append(f"   {day} {'█' * bar_len} {count}")
    graph_text = "\n".join(graph_lines) if graph_lines else "   (no data yet)"

    text = (
        "📊 *Bot Statistics*\n\n"
        "━━━ 📈 *Overview* ━━━\n"
        f"👥 Total users: *{stats['total_users']}*\n"
        f"🔎 Total lookups: *{stats['total_lookups']}*\n"
        f"📅 Lookups today: *{stats['lookups_today']}*\n"
        f"⏱️ Avg lookup time: *{stats['avg_lookup_time_ms']} ms*\n"
        f"💾 Cache entries: *{stats['cache_count']}*\n"
        f"📊 Cache ratio: *{stats['cache_ratio']}%*\n\n"
        "━━━ 🔍 *Lookup breakdown* ━━━\n"
        f"{type_text}\n\n"
        "━━━ 🏆 *Top 5 queried* ━━━\n"
        f"{top_text}\n\n"
        "━━━ 🏳️ *Top countries* ━━━\n"
        f"{country_text}\n\n"
        "━━━ 🏢 *Top ISPs* ━━━\n"
        f"{isp_text}\n\n"
        "━━━ 🖥️ *Top domains* ━━━\n"
        f"{domain_text}\n\n"
        "━━━ 📅 *Daily lookups (14d)* ━━━\n"
        f"{graph_text}"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


# ---------------------------------------------------------------------------
# /broadcast
# ---------------------------------------------------------------------------

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _admin_only(update):
        return

    if not context.args:
        await update.message.reply_text("Usage: /broadcast <message>")
        return

    message = " ".join(context.args)
    user_ids = db.get_all_user_ids()

    await update.message.reply_text(
        f"📢 Broadcasting to {len(user_ids)} users..."
    )

    success = 0
    failed = 0

    for uid in user_ids:
        try:
            await context.bot.send_message(chat_id=uid, text=message)
            success += 1
        except Exception as e:
            logging.warning("Broadcast failed for user %s: %s", uid, e)
            failed += 1
        await asyncio.sleep(0.05)

    await update.message.reply_text(
        f"✅ Broadcast complete.\n"
        f"Sent: {success}\n"
        f"Failed: {failed}"
    )


# ---------------------------------------------------------------------------
# /ban
# ---------------------------------------------------------------------------

async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _admin_only(update):
        return

    if not context.args:
        await update.message.reply_text("Usage: /ban <user_id>")
        return

    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ User ID must be a number.")
        return

    db.set_banned(target_id, True)
    logging.info("Admin %s banned user %s", update.effective_user.id, target_id)
    await update.message.reply_text(f"✅ User {target_id} has been banned.")


# ---------------------------------------------------------------------------
# /unban
# ---------------------------------------------------------------------------

async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _admin_only(update):
        return

    if not context.args:
        await update.message.reply_text("Usage: /unban <user_id>")
        return

    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ User ID must be a number.")
        return

    db.set_banned(target_id, False)
    logging.info("Admin %s unbanned user %s", update.effective_user.id, target_id)
    await update.message.reply_text(f"✅ User {target_id} has been unbanned.")