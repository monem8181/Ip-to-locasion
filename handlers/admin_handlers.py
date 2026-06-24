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

    stats = db.get_stats()

    top_lines = []
    for query, count in stats["top_queries"]:
        top_lines.append(f"   `{query}` — {count}×")
    top_text = "\n".join(top_lines) if top_lines else "   (none yet)"

    type_lines = []
    for ltype, count in stats["type_breakdown"].items():
        emoji = "🌐" if ltype == "ip" else "📮"
        type_lines.append(f"   {emoji} {ltype}: {count}")
    type_text = "\n".join(type_lines) if type_lines else "   (none yet)"

    text = (
        "📊 *Bot Statistics*\n\n"
        f"👥 Total users: *{stats['total_users']}*\n"
        f"🔎 Total lookups: *{stats['total_lookups']}*\n"
        f"📅 Lookups today: *{stats['lookups_today']}*\n\n"
        "*Lookup breakdown:*\n"
        f"{type_text}\n\n"
        "*Top 5 queried:*\n"
        f"{top_text}"
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