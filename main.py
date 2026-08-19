"""
Точка входа: запуск Telegram-бота (aiogram 3) + HTTP-сервера для Mini App.
Один процесс, asyncio. Без логов на диск — всё в stdout.
"""
import asyncio
import logging
import sys
import os

# Фикс: добавляем корень проекта в sys.path для импорта config/parsers
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton

from config import BOT_TOKEN, WEBAPP_URL, PROXY_URL, LOG_LEVEL
from api import run_api


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

    # Параллельно: бот + HTTP API
    api_task = asyncio.create_task(asyncio.to_thread(run_api, proxy=PROXY_URL, host='0.0.0.0', port=int(os.getenv('WEBAPP_PORT', '8080'))))
    polling_task = asyncio.create_task(dp.start_polling(bot, handle_signals=False))

    log.info('Bot started, API on :8080, WEBAPP_URL=%s', WEBAPP_URL)
    try:
        await asyncio.gather(api_task, polling_task)
    except (KeyboardInterrupt, SystemExit):
        log.info('Shutting down...')
    finally:
        await bot.session.close()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
