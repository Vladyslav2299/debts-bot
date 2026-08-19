"""
Парсер bankrot.fedresurs.ru — Единый федеральный реестр сведений о банкротстве.
Поиск по физ. лицам.
"""
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from fake_useragent import UserAgent

UA = UserAgent()

async def check_efrsb(session, fio: str, birth: str, proxy=None):
    url = 'https://bankrot.fedresurs.ru/search?searchString='
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
        async with session.get(url, params=params, headers=headers, proxy=proxy, timeout=25) as r:
            if r.status != 200:
                return {'status': 'error', 'found': 0, 'total': 0, 'items': [], 'error': f'http_{r.status}'}
            html = await r.text()
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

    # Капча
    if 'captcha' in html.lower() or 'введите символы' in html.lower():
        return {'status': 'error', 'found': 0, 'total': 0, 'items': [], 'error': 'captcha'}

    if not found:
        if any(p in text.lower() for p in ['не найдено', 'нет данных', 'по вашему запросу']):
            return {'status': 'clean', 'found': 0, 'total': 0, 'items': []}
        return {'status': 'clean', 'found': 0, 'total': 0, 'items': []}

    return {'status': 'found', 'found': found, 'total': 0, 'items': items[:20]}
