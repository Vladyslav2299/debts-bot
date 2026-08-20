"""Парсер bankrot.fedresurs.ru — ЕФРСБ."""
import asyncio
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
    )

async def check_efrsb(session, fio: str, birth: str, proxy=None):
    url = 'https://bankrot.fedresurs.ru/search'
    headers = {
        'User-Agent': UA.random,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'ru-RU,ru;q=0.9',
        'Referer': 'https://bankrot.fedresurs.ru/',
    }
    params = {
        'searchString': fio,
        'category': 'fiz',
    }

    try:
        own_session = False
        if session is None:
            connector = _make_connector(proxy)
            if connector:
                session = aiohttp.ClientSession(connector=connector, timeout=aiohttp.ClientTimeout(total=25))
            else:
                session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=25))
            own_session = True

        try:
            async with session.get(url, params=params, headers=headers) as r:
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
    items = []

    m = re.search(r'Найдено\s+(\d+)\s+(?:записей|результат)', text, re.IGNORECASE)
    if m:
        found = int(m.group(1))

    if not found:
        cards = soup.select('.card, .result, .search-result, tr')
        for c in cards:
            t = c.get_text(' ', strip=True)
            if t and any(kw in t.lower() for kw in ['должник', 'банкрот', 'арбитражный управляющий']):
                items.append(t[:200])
        found = len(items)

    if 'captcha' in html.lower() or 'введите символы' in html.lower():
        return {'status': 'error', 'found': 0, 'total': 0, 'items': [],==
