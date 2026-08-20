"""
Точка входа: Telegram-бот (aiogram 3) + HTTP API (aiohttp).
Один процесс, один event loop.
"""
import asyncio
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton
from aiohttp import web

from config import BOT_TOKEN, WEBAPP_URL, PROXY_URL, LOG_LEVEL
from api import build_app


logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s %(levelname)s %(name)s | %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger('main')


async def main():
    if not BOT_TOKEN:
        raise SystemExit('BOT_TOKEN is empty. Set it in .env')

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    @dp.message(CommandStart())
    async def cmd_start(m: types.Message):
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='🔍 Открыть проверку', web_app=WebAppInfo(url=WEBAPP_URL))],
            [InlineKeyboardButton(text='ℹ️ Как это работает', callback_data='help')],
        ])
        await m.answer(
            '👋 Привет!\n\n'
            'Этот бот проверяет задолженности и банкротство по 4 источникам:\n'
            '• ФССП (fssprus.su)\n'
            '• ФССП (fssprus.net)\n'
            '• Е-Долги\n'
            '• ЕФРСБ\n\n'
            'Без логов, каждый запрос — свежий.\n\n'
            'Нажми кнопку ниже, чтобы открыть:',
            reply_markup=kb
        )

    @dp.callback_query(F.data == 'help')
    async def help_cb(c: types.CallbackQuery):
        await c.message.answer(
            '📋 Что делает бот:\n'
            '• Принимает ФИО + дату рождения + регион (+ ИНН опционально)\n'
            '• Параллельно опрашивает 4 источника\n'
            '• Показывает количество производств и суммы\n'
            '• НЕ сохраняет данные — всё в памяти, при перезагрузке чисто\n\n'
            '⚠️ Это неофициальный инструмент, данные могут расходиться с гос. источниками.'
        )
        await c.answer()

    @dp.message()
    async def fallback(m: types.Message):
        await m.answer('Нажми /start чтобы открыть проверку 👇')

    # API — в том же event loop, без to_thread
    api_app = build_app(proxy=PROXY_URL)
    runner = web.AppRunner(api_app)
    await runner.setup()
    port = int(os.getenv('WEBAPP_PORT', '8080'))
    site = web.TCPSite(runner, host='0.0.0.0', port=port)
    await site.start()

    log.info('Bot started, API on :%d, WEBAPP_URL=%s', port, WEBAPP_URL)

    try:
        await dp.start_polling(bot, handle_signals=False)
    except (KeyboardInterrupt, SystemExit):
        log.info('Shutting down...')
    finally:
        await bot.session.close()
        await runner.cleanup()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
