import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
WEBAPP_URL = os.getenv('WEBAPP_URL', '')
PROXY_URL = os.getenv('PROXY_URL', '')
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
HTTP_TIMEOUT = int(os.getenv('HTTP_TIMEOUT', '30'))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is required")
