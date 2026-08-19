"""
Парсер fssp.gov.ru (fssprus.su).
Использует публичную форму поиска по физ. лицам.
Возвращает: {status, found, total, items, error}
"""
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from fake_useragent import UserAgent

UA = UserAgent()

async def check_fssprus_su(session, fio: str, birth: str, proxy=None):
    url = 'https://fssp.gov.ru/iss/siteml'
    headers = {
        'User-Agent': UA.random,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'ru-RU,ru;q=0.9',
        'Referer': 'https://fssp.gov.ru/iss/',
        'Content-Type': 'application/x-www-form-urlencoded',
    }
    # Преобразуем дату 07.02.2001 -> 2001-02-07
    try:
        d, m, y = birth.split('.')
        birth_iso = f'{y}-{m}-{d}'
    except Exception:
        return {'status': 'error', 'found': 0, 'total': 0, 'items': [], 'error': 'bad_birth'}

    parts = fio.split()
    last = parts[0] if len(parts) > 0 else ''
    first = parts[1] if len(parts) > 1 else ''
    middle = parts[2] if len(parts) > 2 else ''

    data = {
        'is': '',
        'dosubs': '1',
        'name': last,
        'firstname': first,
        'secondname': middle,
        'birthdate': birth_iso,
        'region_id': '-1',
        'search_type': 'fiz',
    }
    try:
        async with session.post(url, data=data, headers=headers, proxy=proxy, timeout=25) as r:
            if r.status != 200:
                return {'status': 'error', 'found': 0, 'total': 0, 'items': [], 'error': f'http_{r.status}'}
            html = await r.text()
    except asyncio.TimeoutError:
        return {'status': 'error', 'found': 0, 'total': 0, 'items': [], 'error': 'timeout'}
    except Exception as e:
        return {'status': 'error', 'found': 0, 'total': 0, 'items': [], 'error': str(e)[:120]}

    soup = BeautifulSoup(html, 'lxml')

    # Капча
    if 'captcha' in html.lower() or 'введите символы' in html.lower():
        return {'status': 'error', 'found': 0, 'total': 0, 'items': [], 'error': 'captcha'}

    # Счётчик
    found = 0
    total = 0
    items = []

    # Ищем строки таблицы исполнительных производств
    rows = soup.select('table.search-results tr') or soup.select('tr[class*="result"]')
    for row in rows:
        text = row.get_text(' ', strip=True)
        if not text or 'Найдено' in text:
            continue
        if any(kw in text for kw in ['Исполнительное производство', 'Должник', 'Задолженность']):
            items.append(text[:200])
            found += 1

    # Альтернативно: блок с количеством
    cnt_block = soup.find(string=lambda s: s and 'Найдено' in s and 'производств' in s)
    if cnt_block:
        import re
        m = re.search(r'Найдено\s+(\d+)\s+производств', cnt_block)
        if m:
            found = int(m.group(1))

    # Сумма
    sum_block = soup.find(string=lambda s: s and 'сумма' in s.lower())
    if sum_block:
        import re
        m = re.search(r'([\d\s]+(?:[.,]\d+)?)\s*(?:руб|₽)', sum_block)
        if m:
            try:
                total = float(m.group(1).replace(' ', '').replace(',', '.'))
            except Exception:
                pass

    if found == 0 and not items:
        return {'status': 'clean', 'found': 0, 'total': 0, 'items': []}
    return {'status': 'found', 'found': found or len(items), 'total': total, 'items': items[:20]}
