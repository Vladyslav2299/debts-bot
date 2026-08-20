"""Парсер fssprus.net — агрегатор ФССП."""
import asyncio
import aiohttp
from aiohttp_socks import ProxyConnector, ProxyType
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from urllib.parse import urlparse

UA = UserAgent()

def _make_connector(proxy_url):
    if not proxy_url:
        return None
    p = urlparse(proxy_url)
    return ProxyConnector(
        proxy_type=ProxyType.SOCKS5 if p.scheme == 'socks5' else ProxyType.HTTP,
        host=p.hostname,
        port=p.port,
        username=p.username,
        password=p.password,
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
    data = {
        'fio': fio,
        'birthdate': birth,
        'region': region,
        'search': 'Поиск',
    }

    try:
        connector = _make_connector(proxy)
        if connector:
            async with aiohttp.ClientSession(connector=connector, timeout=aiohttp.ClientTimeout(total=25)) as s:
                async with s.post(url, data=data, headers=headers) as r:
                    if r.status != 200:
                        return {'status': 'error', 'found': 0, 'total': 0, 'items': [], 'error': f'http_{r.status}'}
                    html = await r.text()
        else:
            async with session.post(url, data=data, headers=headers, timeout=25) as r:
                if r.status != 200:
                    return {'status': 'error', 'found': 0, 'total': 0, 'items': [], 'error': f'http_{r.status}'}
                html = await r.text()
    except asyncio.TimeoutError:
        return {'status': 'error', 'found': 0, 'total': 0, 'items': [], 'error': 'timeout'}
    except Exception as e:
        return {'status': 'error', 'found': 0, 'total': 0, 'items': [], 'error': str(e)[:120]}

    soup = BeautifulSoup(html, 'lxml')
    items = []
    found = 0
    total = 0.0
    import re

    text = soup.get_text(' ', strip=True)
    m = re.search(r'Найдено\s+(\d+)\s+(?:исполнительн|производств)', text, re.IGNORECASE)
    if m:
        found = int(m.group(1))
    m2 = re.search(r'на\s+сумму\s+([\d\s,.]+)\s*(?:руб|₽)', text, re.IGNORECASE)
    if m2:
        try:
            total = float(m2.group(1).replace(' ', '').replace(',', '.').rstrip('.'))
        except Exception:
            pass

    if not found:
        rows = soup.select('table tr')
        for row in rows:
            t = row.get_text(' ', strip=True)
            if 'должник' in t.lower() or 'исполнительное производство' in t.lower():
                items.append(t[:200])
        found = len(items)

    if not found:
        if any(p in text.lower() for p in ['не найдено', 'по вашему запросу ничего', 'нет данных']):
            return {'status': 'clean', 'found': 0, 'total': 0, 'items': []}
        return {'status': 'clean', 'found': 0, 'total': 0, 'items': []}
    return {'status': 'found', 'found': found, 'total': total, 'items': items[:20]}
