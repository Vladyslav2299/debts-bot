"""Парсер fssprus.su — агрегатор ФССП."""
import asyncio
import re
import aiohttp
from bs4 import BeautifulSoup
from fake_useragent import UserAgent

from .utils import make_connector, decode_response, normalize_date, parse_amount

UA = UserAgent(fallback='Mozilla/5.0 (Windows NT 10.0; Win64; x64)')


async def check_fssprus_su(session, fio: str, birth: str, proxy=None, timeout: int = 30):
    headers = {
        'User-Agent': UA.random,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'ru-RU,ru;q=0.9',
    }

    if not fio or not fio.strip():
        return {'status': 'error', 'found': 0, 'total': 0, 'items': [], 'error': 'empty_fio'}

    date_parts = normalize_date(birth)
    if not date_parts:
        return {'status': 'error', 'found': 0, 'total': 0, 'items': [], 'error': 'bad_birth'}
    birth_clean = birth.strip()

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
            # 1. GET — получаем CSRF-токен
            async with session.get('https://fssprus.su/', headers=headers, ssl=False) as r:
                if r.status != 200:
                    return {'status': 'error', 'found': 0, 'total': 0, 'items': [], 'error': f'http_{r.status}'}
                content = await r.read()
                html = decode_response(content, r.headers)

            soup = BeautifulSoup(html, 'html.parser')
            csrf = soup.select_one('input[name="_csrf-frontend"]')
            csrf_token = csrf['value'] if csrf else ''

            if not csrf_token:
                return {'status': 'error', 'found': 0, 'total': 0, 'items': [], 'error': 'no_csrf'}

            # 2. POST — поиск
            data = {
                '_csrf-frontend': csrf_token,
                'tabs': 'fiz',
                'fio': fio.strip(),
                'inputBirthDay': birth_clean,
                'email': '',
                'regionNumberID': '',
            }
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
            headers['Referer'] = 'https://fssprus.su/'

            async with session.post('https://fssprus.su/iss', data=data, headers=headers, ssl=False) as r:
                if r.status != 200:
                    return {'status': 'error', 'found': 0, 'total': 0, 'items': [], 'error': f'http_{r.status}'}
                content = await r.read()

                # Если ответ JSON
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

    # Явное количество найденных
    m = re.search(r'Найдено\s+(\d+)\s+(?:исполнительн|производств|записей)', text, re.IGNORECASE)
    if m:
        found = int(m.group(1))
        if found == 0:
            return {'status': 'clean', 'found': 0, 'total': 0, 'items': []}

    # Сумма (если есть)
    m2 = re.search(r'на\s+сумму\s+([\d\s,.]+)\s*(?:руб|₽)', text, re.IGNORECASE)
    if m2:
        total = parse_amount(m2.group(1))

    # Извлекаем записи
    rows = soup.select('table tr, .result-item, .debt-item')
    for row in rows:
        t = row.get_text(' ', strip=True)
        if not t or re.search(r'Найдено\s+\d+', t):
            continue
        if any(kw in t.lower() for kw in ['должник', 'задолженность', 'исполнительное', 'производство', 'сумма']):
            items.append(t[:200])

    # Если количество не было указано, но блоки есть
    if not m and items:
        found = len(items)

    if found == 0 and not items:
        return {'status': 'clean', 'found': 0, 'total': 0, 'items': []}

    return {'status': 'found', 'found': found, 'total': total, 'items': items[:20]}
