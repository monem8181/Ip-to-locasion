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

# Extended ip-api fields: includes AS, reverse DNS, mobile/proxy/hosting flags.
IP_API_URL = (
    "http://ip-api.com/json/{ip}?fields=status,message,continent,country,"
    "countryCode,region,regionName,city,zip,lat,lon,isp,org,as,asname,"
    "reverse,mobile,proxy,hosting,timezone,query"
)
ZIP_API_URL = "https://api.zippopotam.us/{country_code}/{postal_code}"

# RDAP endpoints used for whois lookups.  We try the bootstrap then fall back
# to the RIR lookups.  ip-api.com exposes a handy rdap redirect.
RDAP_IP_URL = "https://rdap.arin.net/registry/ip/{ip}"
RDAP_BOOTSTRAP_URL = "https://rdap.org/ip/{ip}"

HTTP_TIMEOUT = 10
DNS_TIMEOUT = 5

# Bulk scan limits
BULK_MAX_IPS = 500
BULK_BATCH_DELAY = 0.2