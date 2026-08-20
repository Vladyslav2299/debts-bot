"""Парсер fssprus.net — агрегатор ФССП."""
import asyncio
import ssl
import aiohttp
from aiohttp_socks import ProxyConnector, ProxyType
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from urllib.parse import urlparse

UA = UserAgent()

def _make_connector(proxy_url):
    """Создаёт ProxyConnector. Если схема не указана — по умолчанию socks5."""
    if not proxy_url:
        return None
    if '://' not in proxy_url:
        proxy_url = 'socks5://' + proxy_url
    p = urlparse(proxy_url)
    if not p.hostname or not p.port:
        return None
    return ProxyConnector(
        proxy_type=ProxyType.SOCKS5 if p.scheme == 'socks5' else ProxyType.HTTP,
        host=p.hostname,
        port=p.port,
        username=p.username,
        password=p.password,
        ssl=False,
    )

async def check_fssprus_net(session, fio: str, birth: str, region: str, proxy=None):
    url = 'https://fssprus.net/'
    headers = {
        'User-Agent': UA.random,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'ru-RU,ru;q=0.9',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Origin': 'https://fssprus.net',
        'Referer': 'https://fssprus.net/',
    }

    try:
        d, m, y = birth.split('.')
    except Exception:
        return {'status': 'error', 'found': 0, 'total': 0, 'items': [], 'error': 'bad_birth'}

    data = {
        'fio': fio,
        'birthdate': f'{y}-{m}-{d}',
        'region': region,
        'search': 'Поиск',
    }

    try:
        own_session = False
        if session is None:
            connector = _make_connector(proxy)
            if connector:
                session = aiohttp.ClientSession(connector=connector, timeout=aiohttp.ClientTimeout(total=30))
            else:
                session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))
            own_session = True

        try:
            async with session.post(url, data=data, headers=headers, ssl=False) as r:
                if r.status != 200:
                    return {'status': 'error', 'found': 0, 'total': 0, 'items': [], 'error': f'http_{r.status}'}
                html = await r.text()
        finally:
            if own_session:
                await session.close()
    except asyncio.TimeoutError:
        return {'status': 'error', 'found': 0, 'total': 0, 'items': [], 'error': 'timeout'}
    except Exception as e:
        return {'status': 'error', 'found': 0, 'total': 0, 'items': [], 'error': str(e)[:120]}

    soup = BeautifulSoup(html, 'lxml')
    import re
    text = soup.get_text(' ', strip=True)
    found = 0
    total = 0.0
    items = []

    m = re.search(r'Найдено\s+==
