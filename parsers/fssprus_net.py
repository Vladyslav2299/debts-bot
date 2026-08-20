"""Парсер fssprus.net — агрегатор ФССП."""
import asyncio
import re
import aiohttp
from aiohttp_socks import ProxyConnector, ProxyType
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from urllib.parse import urlparse

# Fallback, чтобы не падать при первом запуске без сети
UA = UserAgent(fallback='Mozilla/5.0 (Windows NT 10.0; Win64; x64)')


def _make_connector(proxy_url):
    """Создаёт ProxyConnector. Если схема не указана — по умолчанию socks5."""
    if not proxy_url:
        return None

    if '://' not in proxy_url:
        proxy_url = 'socks5://' + proxy_url

    p = urlparse(proxy_url)
    if not p.hostname or not p.port:
        return None

    proxy_type_map = {
        'http': ProxyType.HTTP,
        'https': ProxyType.HTTP,
        'socks4': ProxyType.SOCKS4,
        'socks5': ProxyType.SOCKS5,
        'socks5h': ProxyType.SOCKS5H,
    }

    proxy_type = proxy_type_map.get(p.scheme)
    if proxy_type is None:
        return None

    return ProxyConnector(
        proxy_type=proxy_type,
        host=p.hostname,
        port=p.port,
        username=p.username,
        password=p.password,
    )


def _parse_amount(text):
    """Парсит сумму из строки вида '1 234,56', '1.234,56', '1234.56'."""
    if not text:
        return 0.0

    s = text.replace(' ', '').strip()

    # Если есть и точка, и запятая: точка - разделитель тысяч, запятая - десятичная
    if ',' in s and '.' in s:
        s = s.replace('.', '').replace(',', '.')
    elif ',' in s:
        s = s.replace(',', '.')
    elif '.' in s:
        # Проверяем, не является ли точка разделителем тысяч (1.234)
        parts = s.split('.')
        if len(parts) == 2 and len(parts[1]) == 3 and parts[1].isdigit():
            s = s.replace('.', '')
        # иначе считаем десятичной точкой
    try:
        return float(s)
    except ValueError:
        return 0.0


def _decode_response(content, headers):
    """Декодирует байтовый ответ с учётом заголовков charset и meta."""
    charset = None
    content_type = headers.get('Content-Type', '')
    if 'charset=' in content_type:
        charset = content_type.split('charset=')[-1].strip()
    if not charset:
        # пробуем найти charset в meta-тегах (для HTML)
        try:
            head = content[:2048].decode('utf-8', errors='ignore')
            m = re.search(r'charset=["\']?([\w-]+)', head, re.IGNORECASE)
            if m:
                charset = m.group(1)
        except Exception:
            pass
    if not charset:
        charset = 'utf-8'
    try:
        return content.decode(charset, errors='ignore')
    except LookupError:
        return content.decode('utf-8', errors='ignore')


async def check_fssprus_net(session, fio: str, birth: str, region: str, proxy=None, timeout: int = 30):
    """
    Проверка задолженностей на fssprus.net.

    :param session: aiohttp.ClientSession (может быть None, тогда создаётся новый)
    :param fio: ФИО
    :param birth: дата рождения в формате ДД.ММ.ГГГГ
    :param region: регион (как ожидает сайт)
    :param proxy: строка прокси (например, 'socks5://user:pass@host:port')
    :param timeout: таймаут запроса в секундах
    :return: dict со статусом, количеством, суммой и списком записей
    """
    url = 'https://fssprus.net/'
    headers = {
        'User-Agent': UA.random,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'ru-RU,ru;q=0.9',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Origin': 'https://fssprus.net',
        'Referer': 'https://fssprus.net/',
    }

    # Валидация входных данных
    if not fio or not fio.strip():
        return {'status': 'error', 'found': 0, 'total': 0, 'items': [], 'error': 'empty_fio'}
    if not region:
        return {'status': 'error', 'found': 0, 'total': 0, 'items': [], 'error': 'empty_region'}

    # Нормализация даты
    try:
        parts = [p.strip() for p in birth.split('.')]
        if len(parts) != 3:
            raise ValueError
        d, m, y = parts
        if len(y) != 4 or not (1 <= int(d) <= 31) or not (1 <= int(m) <= 12):
            raise ValueError
    except Exception:
        return {'status': 'error', 'found': 0, 'total': 0, 'items': [], 'error': 'bad_birth'}

    data = {
        'fio': fio.strip(),
        'birthdate': f'{y}-{m}-{d}',
        'region': region,
        'search': 'Поиск',
    }

    try:
        own_session = False
        if session is None:
            connector = _make_connector(proxy)
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
            # ssl=False оставлен намеренно — если у сайта проблемы с сертификатом
            async with session.post(url, data=data, headers=headers, ssl=False) as r:
                if r.status != 200:
                    return {
                        'status': 'error',
                        'found': 0,
                        'total': 0,
                        'items': [],
                        'error': f'http_{r.status}',
                    }
                content = await r.read()
                # Проверяем, не JSON ли ответ
                ct = r.headers.get('Content-Type', '')
                if 'application/json' in ct:
                    try:
                        import json
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
                        else:
                            return {'status': 'error', 'found': 0, 'total': 0, 'items': [], 'error': 'unexpected_json'}
                    except Exception:
                        pass  # fallback к HTML
                # Иначе декодируем как HTML
                html = _decode_response(content, r.headers)
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

    # 1. Явное количество найденных записей
    m = re.search(r'Найдено\s+(\d+)\s+(?:задолженност|записей)', text, re.IGNORECASE)
    if m:
        found = int(m.group(1))
        if found == 0:
            return {'status': 'clean', 'found': 0, 'total': 0, 'items': []}

    # 2. Сумма
    m2 = re.search(r'на\s+сумму\s+([\d\s,.]+)\s*(?:руб|₽)', text, re.IGNORECASE)
    if m2:
        total = _parse_amount(m2.group(1))

    # 3. Извлечение блоков с записями
    # Более точные селекторы, если известна структура. Пока используем общие.
    blocks = soup.select('.result, .debt, .item, tr[data-debt-id], div.debt-item')
    for b in blocks:
        t = b.get_text(' ', strip=True)
        if not t:
            continue
        # Фильтруем мусор: не добавляем общие заголовки
        if re.search(r'Найдено\s+\d+', t):
            continue
        if any(kw in t.lower() for kw in ['долг', 'задолженность', 'штраф', 'налог']):
            items.append(t[:200])

    # 4. Если регулярка не сработала, но блоки есть — считаем по ним
    if not m and items:
        found = len(items)

    # 5. Итоговый результат
    if found == 0 and not items:
        # Неважно, есть ли "не найдено" — возвращаем clean
        return {'status': 'clean', 'found': 0, 'total': 0, 'items': []}

    return {
        'status': 'found',
        'found': found,
        'total': total,
        'items': items[:20],
    }
