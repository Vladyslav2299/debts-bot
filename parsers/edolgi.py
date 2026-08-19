"""
Парсер e-dolgi.ru — агрегатор задолженностей (ФССП, налоги, штрафы, ЖКХ).
"""
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from fake_useragent import UserAgent

UA = UserAgent()

async def check_edolgi(session, fio: str, birth: str, region: str, proxy=None):
    url = 'https://e-dolgi.ru/'
    headers = {
        'User-Agent': UA.random,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'ru-RU,ru;q=0.9',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Origin': 'https://e-dolgi.ru',
        'Referer': 'https://e-dolgi.ru/',
    }
    data = {
        'fio': fio,
        'birthdate': birth,
        'region': region,
        'action': 'search',
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
    import re
    text = soup.get_text(' ', strip=True)
    found = 0
    total = 0.0
    items = []

    m = re.search(r'Найдено\s+(\d+)\s+(?:задолженност|записей)', text, re.IGNORECASE)
    if m:
        found = int(m.group(1))
    m2 = re.search(r'на\s+сумму\s+([\d\s,.]+)\s*(?:руб|₽)', text, re.IGNORECASE)
    if m2:
        try:
            total = float(m2.group(1).replace(' ', '').replace(',', '.').rstrip('.'))
        except Exception:
            pass

    # Если счётчика нет — собираем блоки результата
    if not found:
        blocks = soup.select('.result, .debt, .item, li')
        for b in blocks:
            t = b.get_text(' ', strip=True)
            if t and any(kw in t.lower() for kw in ['долг', 'задолженность', 'штраф', 'налог']):
                items.append(t[:200])
        found = len(items)

    if not found:
        if any(p in text.lower() for p in ['не найдено', 'нет задолженност', 'по вашему запросу']):
            return {'status': 'clean', 'found': 0, 'total': 0, 'items': []}
        return {'status': 'clean', 'found': 0, 'total': 0, 'items': []}

    return {'status': 'found', 'found': found, 'total': total, 'items': items[:20]}
