import os
import logging
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

_admin_ids_raw = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = set()
for _id in _admin_ids_raw.split(","):
    _id = _id.strip()
    if _id:
        try:
            ADMIN_IDS.add(int(_id))
        except ValueError:
            logging.warning("Invalid ADMIN_IDS entry ignored: %s", _id)

DB_PATH = os.getenv("DB_PATH", "./data/bot.db")

CACHE_TTL_SECONDS = 30 * 60
RATE_LIMIT_SECONDS = 3

IP_API_URL = "http://ip-api.com/json/{ip}?fields=status,message,country,countryCode,region,regionName,city,zip,lat,lon,isp,org,timezone,query"
ZIP_API_URL = "https://api.zippopotam.us/{country_code}/{postal_code}"