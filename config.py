import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN', '')
WEBAPP_URL = os.getenv('WEBAPP_URL', 'https://debts-check-m0fuc8hd.agent.mira.tg')
PROXY_URL = os.getenv('PROXY_URL', '').strip() or None
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

# Таймауты HTTP
HTTP_TIMEOUT = 25
# Параллельных запросов на источник
MAX_CONCURRENCY = 4
