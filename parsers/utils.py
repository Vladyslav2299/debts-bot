"""Общие утилиты для парсеров."""
import re
from urllib.parse import urlparse

from aiohttp_socks import ProxyConnector, ProxyType


def make_connector(proxy_url):
    """Создаёт ProxyConnector. Если схема не указана — по умолчанию socks5."""
    if not proxy_url:
        return None

    if '://' not in proxy_url:
        proxy_url = 'socks5://' + proxy_url

    p = urlparse(proxy_url)
    if not p.hostname or not p.port:
        return None

    proxy_type_map = {
        'http': ProxyType.HTTP,
        'https': ProxyType.HTTP,
        'socks4': ProxyType.SOCKS4,
        'socks5': ProxyType.SOCKS5,
        'socks5h': ProxyType.SOCKS5H,
    }

    proxy_type = proxy_type_map.get(p.scheme)
    if proxy_type is None:
        return None

    return ProxyConnector(
        proxy_type=proxy_type,
        host=p.hostname,
        port=p.port,
        username=p.username,
        password=p.password,
    )


def parse_amount(text):
    """Парсит сумму из строки вида '1 234,56', '1.234,56', '1234.56'."""
    if not text:
        return 0.0

    s = text.replace(' ', '').strip()

    if ',' in s and '.' in s:
        s = s.replace('.', '').replace(',', '.')
    elif ',' in s:
        s = s.replace(',', '.')
    elif '.' in s:
        parts = s.split('.')
        if len(parts) == 2 and len(parts[1]) == 3 and parts[1].isdigit():
            s = s.replace('.', '')
    try:
        return float(s)
    except ValueError:
        return 0.0


def decode_response(content, headers):
    """Декодирует байтовый ответ с учётом charset."""
    charset = None
    content_type = headers.get('Content-Type', '')
    if 'charset=' in content_type:
        charset = content_type.split('charset=')[-1].strip()

    if not charset:
        try:
            head = content[:2048].decode('utf-8', errors='ignore')
            m = re.search(r'charset=["\']?([\w-]+)', head, re.IGNORECASE)
            if m:
                charset = m.group(1)
        except Exception:
            pass

    if not charset:
        charset = 'utf-8'

    try:
        return content.decode(charset, errors='ignore')
    except LookupError:
        return content.decode('utf-8', errors='ignore')


def normalize_date(birth):
    """Нормализует дату рождения, возвращает (d, m, y) или None."""
    try:
        parts = [p.strip() for p in birth.split('.')]
        if len(parts) != 3:
            return None
        d, m, y = parts
        if len(y) != 4 or not (1 <= int(d) <= 31) or not (1 <= int(m) <= 12):
            return None
        return d, m, y
    except Exception:
        return None
