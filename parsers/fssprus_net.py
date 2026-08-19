"""
Парсер fssprus.net — агрегатор ФССП, обычно проще и без капчи.
"""
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from fake_useragent import UserAgent

UA = UserAgent()

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
        async with session.post(url, data=data, headers=headers, proxy=proxy, timeout=25) as r:
            if r.status != 200:
                return {'status': 'error', 'found': 0, 'total': 0, 'items': [], 'error': f'http_{r.status}'}
            html = await r.text()
    except asyncio.TimeoutError:
        return {'status': 'error', 'found': 0, 'total': 0, 'items': [], 'error': 'timeout'}
    except Exception as e:
        return {'status': 'error', 'found': 0, 'total': 0, 'items': [], 'error': str(e)[:120]}

    soup = BeautifulSoup(html, 'lxml')

    # Обычно результат в блоке .result или таблице
    items = []
    found = 0
    total = 0.0

    import re
    # Сначала ищем счётчик
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

    # Если счётчика нет — пробуем строки
    if not found:
        rows = soup.select('table tr')
        for row in rows:
            t = row.get_text(' ', strip=True)
            if 'должник' in t.lower() or 'исполнительное производство' in t.lower():
                items.append(t[:200])
        found = len(items)

    if not found:
        # Проверим явный «не найдено»
        if any(p in text.lower() for p in ['не найдено', 'по вашему запросу ничего', 'нет данных']):
            return {'status': 'clean', 'found': 0, 'total': 0, 'items': []}
        return {'status': 'clean', 'found': 0, 'total': 0, 'items': []}

    return {'status': 'found', 'found': found, 'total': total, 'items': items[:20]}
