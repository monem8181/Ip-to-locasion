import logging

from telegram.ext import Application, CommandHandler

import config
import services.database as db
from handlers import user_handlers, admin_handlers


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def build_application() -> Application:
    if not config.BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not set. Please configure your environment.")

    application = Application.builder().token(config.BOT_TOKEN).build()

    # User commands
    application.add_handler(CommandHandler("start", user_handlers.start_command))
    application.add_handler(CommandHandler("help", user_handlers.help_command))
    application.add_handler(CommandHandler("ip", user_handlers.ip_command))
    application.add_handler(CommandHandler("zip", user_handlers.zip_command))
    application.add_handler(CommandHandler("history", user_handlers.history_command))
    application.add_handler(CommandHandler("export", user_handlers.export_command))

    # Admin commands
    application.add_handler(CommandHandler("stats", admin_handlers.stats_command))
    application.add_handler(CommandHandler("broadcast", admin_handlers.broadcast_command))
    application.add_handler(CommandHandler("ban", admin_handlers.ban_command))
    application.add_handler(CommandHandler("unban", admin_handlers.unban_command))

    return application


def main() -> None:
    logger.info("Initializing database...")
    db.init_db()
    logger.info("Admin IDs: %s", config.ADMIN_IDS)
    logger.info("DB path: %s", config.DB_PATH)

    application = build_application()

    logger.info("Starting bot (long-polling)...")
    application.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()