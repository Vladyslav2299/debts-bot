"""
HTTP-сервер (aiohttp) с одним endpoint POST /api/check.
Запускается рядом с ботом на порту 8080 (или WEBAPP_PORT из .env).
Все запросы — без логов на диск, в памяти.
"""
import asyncio
import json
import logging
from aiohttp import web
import aiohttp

from config import HTTP_TIMEOUT
from parsers import check_fssprus_su, check_fssprus_net, check_edolgi, check_efrsb

log = logging.getLogger('api')


async def handle_check(request: web.Request) -> web.Response:
    try:
        data = await request.json()
    except Exception:
        return web.json_response({'error': 'bad_json'}, status=400)

    fio = (data.get('fio') or '').strip()
    birth = (data.get('birth') or '').strip()
    region = (data.get('region') or '').strip()
    inn = (data.get('inn') or '').strip()

    if not fio or not birth or not region:
        return web.json_response({'error': 'fio_birth_region_required'}, status=400)

    proxy = request.app['proxy']
    timeout = aiohttp.ClientTimeout(total=HTTP_TIMEOUT)
    conn = aiohttp.TCPConnector(limit=20, ssl=False)
    async with aiohttp.ClientSession(timeout=timeout, connector=conn) as session:
        results = await asyncio.gather(
            check_fssprus_su(session, fio, birth, proxy=proxy),
            check_fssprus_net(session, fio, birth, region, proxy=proxy),
            check_edolgi(session, fio, birth, region, proxy=proxy),
            check_efrsb(session, fio, birth, proxy=proxy),
            return_exceptions=True,
        )
    out = {}
    for key, res in zip(['fssprus_su', 'fssprus_net', 'edolgi', 'efrsb'], results):
        if isinstance(res, Exception):
            out[key] = {'status': 'error', 'found': 0, 'total': 0, 'items': [], 'error': str(res)[:120]}
        else:
            out[key] = res
    return web.json_response({'results': out})


async def handle_health(request: web.Request) -> web.Response:
    return web.json_response({'ok': True})


def build_app(proxy=None) -> web.Application:
    app = web.Application()
    app['proxy'] = proxy
    app.router.add_post('/api/check', handle_check)
    app.router.add_get('/health', handle_health)
    return app


def run_api(proxy=None, host='0.0.0.0', port=8080):
    logging.basicConfig(level=logging.INFO)
    app = build_app(proxy=proxy)
    web.run_app(app, host=host, port=port, print=lambda *a, **k: log.info(' '.join(str(x) for x in a)))
