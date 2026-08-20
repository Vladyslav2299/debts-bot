"""
Парсеры 4 источников: ФССП (2 зеркала), Е-Долги, ЕФРСБ.
"""
import logging
from urllib.parse import urlparse
import aiohttp
from aiohttp_socks import ProxyConnector

log = logging.getLogger('parsers')
TIMEOUT = aiohttp.ClientTimeout(total=25)

def _make_connector(proxy_url):
    if not proxy_url:
        return aiohttp.TCPConnector(ssl=False, limit=10)
    p = urlparse(proxy_url)
    if p.scheme in ('socks5', 'socks5h'):
        return ProxyConnector.from_url(proxy_url)
    return aiohttp.TCPConnector(ssl=False, limit=10)

async def _post(session, url, data, proxy_url):
    connector = _make_connector(proxy_url)
    async with aiohttp.ClientSession(timeout=TIMEOUT, connector=connector) as s:
        async with s.post(url, data=data, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Content-Type': 'application/x-www-form-urlencoded',
        }) as resp:
            return await resp.text()

async def check_fssprus_su(session, fio, birth, proxy=None):
    parts = fio.split()
    data = {'lastname': parts[0], 'firstname': parts[1] if len(parts)>1 else '',
            'middlename': parts[2] if len(parts)>2 else '', 'birthdate': birth, 'region': '-1'}
    try:
        html = await _post(session, 'https://fssprus.su/search/', data, proxy)
        return {'status': 'ok', 'found': html.count('руб.'), 'total': 0, 'items': []}
    except Exception as e:
        return {'status': 'error', 'found': 0, 'total': 0, 'items': [], 'error': str(e)[:120]}

async def check_fssprus_net(session, fio, birth, region, proxy=None):
    parts = fio.split()
    data = {'lastname': parts[0], 'firstname': parts[1] if len(parts)>1 else '',
            'middlename': parts[2] if len(parts)>2 else '', 'birthdate': birth, 'region': region}
    try:
        html = await _post(session, 'https://fssprus.net/search/', data, proxy)
        return {'status': 'ok', 'found': html.count('руб.'), 'total': 0, 'items': []}
    except Exception as e:
        return {'status': 'error', 'found': 0, 'total': 0, 'items': [], 'error': str(e)[:120]}

async def check_edolgi(session, fio, birth, region, proxy=None):
    parts = fio.split()
    data = {'lastname': parts[0], 'firstname': parts[1] if len(parts)>1 else '',
            'middlename': parts[2] if len(parts)>2 else '', 'birthdate': birth, 'region': region}
    try:
        html = await _post(session, 'https://edolgi.ru/search/', data, proxy)
        return {'status': 'ok', 'found': html.count('руб.'), 'total': 0, 'items': []}
    except Exception as e:
        return {'status': 'error', 'found': 0, 'total': 0, 'items': [], 'error': str(e)[:120]}

async def check_efrsb(session, fio, birth, proxy=None):
    parts = fio.split()
    data = {'lastname': parts[0], 'firstname': parts[1] if len(parts)>1 else '',
            'middlename': parts[2] if len(parts)>2 else '', 'birthdate': birth}
    try:
        html = await _post(session, 'https://bankrot.fedresurs.ru/search/', data, proxy)
        return {'status': 'ok', 'found': html.count('банкрот'), 'total': 0, 'items': []}
    except Exception as e:
        return {'status': 'error', 'found': 0, 'total': 0, 'items': [], 'error': str(e)[:120]}
