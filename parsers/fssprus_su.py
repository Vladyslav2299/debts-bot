"""Парсер fssprus.su — агрегатор ФССП."""
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

async def check_fssprus_su(session, fio: str, birth: str, proxy=None):
    headers = {
        'User-Agent': UA.random,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'ru-RU,ru;q=0.9',
    }

    try:
        d, m, y = birth.split('.')
        birth_iso = f'{y}-{m}-{d}'
    except Exception:
        return {'status': 'error', 'found': 0, 'total': 0, 'items': [], 'error': 'bad_birth'}

    try:
        connector = _make_connector(proxy)
        if connector:
            s = aiohttp.ClientSession(connector=connector, timeout=aiohttp.ClientTimeout(total=30))
        else:
            s = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))

        try:
            # 1. GET — получить CSRF-токен
            async with s.get('https://fssprus.su/', headers=headers) as r:
                html = await r.text()
                soup = BeautifulSoup(html, 'lxml')
                csrf = soup.select_one('input[name="_csrf-frontend"]')
                csrf_token = csrf['value'] if csrf else ''

            if not csrf_token:
                await s.close()
                return {'status': 'error', 'found': 0, 'total': 0, 'items': [], 'error': 'no_csrf'}

            # 2. POST — поиск
            data = {
                '_csrf-frontend': csrf_token,
                'tabs': 'fiz',
                'fio': fio,
                'inputBirthDay': birth,
                'email': '',
                'regionNumberID': '',
            }
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
            headers['Referer'] = 'https://fssprus.su/'

            async with s.post('https://fssprus.su/iss', data=data, headers=headers) as r:
                if r.status != 200:
                    await s.close()
                    return {'status': 'error', 'found': 0, 'total': 0, 'items': [], 'error': f'http_{r.status}'}
                html = await r.text()
        finally:
            await s.close()
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

    # Ищем записи о задолженностях
    rows = soup.select('table tr, .result-item, .debt-item')
    for row in rows:
        t = row.get_text(' ', strip=True)
        if t and any(kw in t.lower() for kw in ['должник', 'задолженность', 'исполнительное', 'производство', 'сумма']):
            items.append(t[:200])

    # Попытка найти количество
    m = re.search(r'Найдено\s+(\d+)\s+(?:исполнительн|производств|записей)', text, re.IGNORECASE)
    if m:
        found = int(m.group(1))

    if not found:
        found = len(items)

    if found == 0 and not items:
        return {'status': 'clean', 'found': 0, 'total': 0, 'items': []}
    return {'status': 'found', 'found': found, 'total': total, 'items': items[:20]}
