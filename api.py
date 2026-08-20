"""
HTTP-сервер (aiohttp) с одним endpoint POST /api/check.
Запускается рядом с ботом на порту 8080 (или WEBAPP_PORT из .env).
Все запросы — без логов на диск, в памяти.
"""
import asyncio
import json
import logging
from urllib.parse import urlparse

from aiohttp import web, ClientSession, ClientTimeout, TCPConnector
from aiohttp_socks import ProxyConnector, ProxyType

from config import HTTP_TIMEOUT
from parsers import check_fssprus_su, check_fssprus_net, check_edolgi, check_efrsb

log = logging.getLogger('api')

CORS_HEADERS = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
}


def _create_connector(proxy: str | None):
    """Создаёт коннектор для aiohttp с учётом прокси и отключенной проверкой SSL."""
    ssl = False  # Для совместимости с сайтами, имеющими проблемы с сертификатами
    limit = 20

    if not proxy:
        return TCPConnector(limit=limit, ssl=ssl)

    # Нормализация URL прокси
    if '://' not in proxy:
        proxy = 'socks5://' + proxy
    p = urlparse(proxy)

    if not p.hostname or not p.port:
        # Если прокси битый, возвращаем обычный коннектор
        return TCPConnector(limit=limit, ssl=ssl)

    proxy_type_map = {
        'http': ProxyType.HTTP,
        'https': ProxyType.HTTP,
        'socks4': ProxyType.SOCKS4,
        'socks5': ProxyType.SOCKS5,
        'socks5h': ProxyType.SOCKS5H,
    }
    proxy_type = proxy_type_map.get(p.scheme)
    if proxy_type is None:
        return TCPConnector(limit=limit, ssl=ssl)

    return ProxyConnector(
        proxy_type=proxy_type,
        host=p.hostname,
        port=p.port,
        username=p.username,
        password=p.password,
        ssl=ssl,          # важно: чтобы работал ssl=False
        limit=limit,      # ограничение на одновременные соединения
    )


async def handle_check(request: web.Request) -> web.Response:
    if request.method == 'OPTIONS':
        return web.Response(status=204, headers=CORS_HEADERS)

    try:
        data = await request.json()
    except Exception:
        return web.json_response({'error': 'bad_json'}, status=400, headers=CORS_HEADERS)

    fio = (data.get('fio') or '').strip()
    birth = (data.get('birth') or '').strip()
    region = (data.get('region') or '').strip()
    inn = (data.get('inn') or '').strip()  # не используется, но оставлено

    if not fio or not birth or not region:
        return web.json_response(
            {'error': 'fio_birth_region_required'},
            status=400,
            headers=CORS_HEADERS,
        )

    proxy = request.app['proxy']
    timeout = ClientTimeout(total=HTTP_TIMEOUT)
    connector = _create_connector(proxy)

    async with ClientSession(timeout=timeout, connector=connector) as session:
        results = await asyncio.gather(
            check_fssprus_su(session, fio, birth, proxy=None, timeout=HTTP_TIMEOUT),
            check_fssprus_net(session, fio, birth, region, proxy=None, timeout=HTTP_TIMEOUT),
            check_edolgi(session, fio, birth, region, proxy=None, timeout=HTTP_TIMEOUT),
            check_efrsb(session, fio, birth, region, proxy=None, timeout=HTTP_TIMEOUT),
            return_exceptions=True,
        )

    out = {}
    keys = ['fssprus_su', 'fssprus_net', 'edolgi', 'efrsb']
    for key, res in zip(keys, results):
        if isinstance(res, BaseException):
            log.exception(f"Ошибка в парсере {key}: {res}")
            out[key] = {
                'status': 'error',
                'found': 0,
                'total': 0,
                'items': [],
                'error': str(res)[:120],
            }
        elif res is None:
            out[key] = {
                'status': 'error',
                'found': 0,
                'total': 0,
                'items': [],
                'error': 'no_result',
            }
        else:
            out[key] = res

    return web.json_response({'results': out}, headers=CORS_HEADERS)


async def handle_health(request: web.Request) -> web.Response:
    if request.method == 'OPTIONS':
        return web.Response(status=204, headers=CORS_HEADERS)
    return web.json_response({'ok': True}, headers=CORS_HEADERS)


def build_app(proxy=None) -> web.Application:
    app = web.Application()
    app['proxy'] = proxy

    app.router.add_post('/api/check', handle_check)
    app.router.add_get('/health', handle_health)
    app.router.add_route('OPTIONS', '/api/check', handle_check)
    app.router.add_route('OPTIONS', '/health', handle_health)

    return app


def run_api(proxy=None, host='0.0.0.0', port=8080):
    logging.basicConfig(level=logging.INFO)
    app = build_app(proxy=proxy)
    web.run_app(
        app,
        host=host,
        port=port,
        print=lambda *a, **k: log.info(' '.join(str(x) for x in a)),
    )
