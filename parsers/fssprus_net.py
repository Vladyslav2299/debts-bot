"""Парсер fssprus.net — агрегатор ФССП."""
import asyncio
import re
import aiohttp
from bs4 import BeautifulSoup
from fake_useragent import UserAgent

from .utils import make_connector, parse_amount, decode_response, normalize_date

UA = UserAgent(fallback='Mozilla/5.0 (Windows NT 10.0; Win64; x64)')


async def check_fssprus_net(session, fio: str, birth: str, region: str, proxy=None, timeout: int = 30):
    url = 'https://fssprus.net/'
    headers = {
        'User-Agent': UA.random,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'ru-RU,ru;q=0.9',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Origin': 'https://fssprus.net',
        'Referer': 'https://fssprus.net/',
    }

    if not fio or not fio.strip():
        return {'status': 'error', 'found': 0, 'total': 0, 'items': [], 'error': 'empty_fio'}
    if not region:
        return {'status': 'error', 'found': 0, 'total': 0, 'items': [], 'error': 'empty_region'}

    date_parts = normalize_date(birth)
    if not date_parts:
        return {'status': 'error', 'found': 0, 'total': 0, 'items': [], 'error': 'bad_birth'}
    d, m, y = date_parts

    data = {
        'fio': fio.strip(),
        'birthdate': f'{y}-{m}-{d}',
        'region': region,
        'search': 'Поиск',
    }

    try:
        own_session = False
        if session is None:
            connector = make_connector(proxy)
            if connector:
                session = aiohttp.ClientSession(
                    connector=connector,
                    timeout=aiohttp.ClientTimeout(total=timeout)
                )
            else:
                session = aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=timeout)
                )
            own_session = True

        try:
            async with session.post(url, data=data, headers=headers, ssl=False) as r:
                if r.status != 200:
                    return {'status': 'error', 'found': 0, 'total': 0, 'items': [], 'error': f'http_{r.status}'}
                content = await r.read()

                ct = r.headers.get('Content-Type', '')
                if 'application/json' in ct:
                    import json
                    try:
                        resp_json = json.loads(content.decode('utf-8', errors='ignore'))
                        if isinstance(resp_json, dict):
                            found = int(resp_json.get('found', 0))
                            total = float(resp_json.get('total', 0))
                            items = resp_json.get('items', [])
                            return {
                                'status': 'found' if found else 'clean',
                                'found': found,
                                'total': total,
                                'items': items[:20],
                            }
                    except Exception:
                        pass

                html = decode_response(content, r.headers)
        finally:
            if own_session:
                await session.close()
    except asyncio.TimeoutError:
        return {'status': 'error', 'found': 0, 'total': 0, 'items': [], 'error': 'timeout'}
    except Exception as e:
        return {'status': 'error', 'found': 0, 'total': 0, 'items': [], 'error': str(e)[:120]}

    soup = BeautifulSoup(html, 'html.parser')
    text = soup.get_text(' ', strip=True)

    found = 0
    total = 0.0
    items = []

    m = re.search(r'Найдено\s+(\d+)\s+(?:задолженност|записей)', text, re.IGNORECASE)
    if m:
        found = int(m.group(1))
        if found == 0:
            return {'status': 'clean', 'found': 0, 'total': 0, 'items': []}

    m2 = re.search(r'на\s+сумму\s+([\d\s,.]+)\s*(?:руб|₽)', text, re.IGNORECASE)
    if m2:
        total = parse_amount(m2.group(1))

    blocks = soup.select('.result, .debt, .item, tr[data-debt-id], div.debt-item')
    for b in blocks:
        t = b.get_text(' ', strip=True)
        if not t or re.search(r'Найдено\s+\d+', t):
            continue
        if any(kw in t.lower() for kw in ['долг', 'задолженность', 'штраф', 'налог']):
            items.append(t[:200])

    if not m and items:
        found = len(items)

    if found == 0 and not items:
        return {'status': 'clean', 'found': 0, 'total': 0, 'items': []}

    return {'status': 'found', 'found': found, 'total': total, 'items': items[:20]}
