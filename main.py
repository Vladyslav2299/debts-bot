"""
Точка входа: Telegram-бот (aiogram 3) + HTTP API (aiohttp).
Один процесс, один event loop.
"""
import asyncio
import logging
import signal
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

    # --- Настройка graceful shutdown ---
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def request_shutdown(signame: str):
        log.info('Received signal %s, shutting down...', signame)
        stop_event.set()

    # Регистрируем обработчики для SIGINT и SIGTERM
    for signame in ('SIGINT', 'SIGTERM'):
        sig = getattr(signal, signame, None)
        if sig:
            loop.add_signal_handler(sig, request_shutdown, signame)

    # --- Запуск API в том же event loop ---
    api_app = build_app(proxy=PROXY_URL)
    runner = web.AppRunner(api_app)
    await runner.setup()
    port = int(os.getenv('PORT', os.getenv('WEBAPP_PORT', '8080')))
    site = web.TCPSite(runner, host='0.0.0.0', port=port)
    await site.start()

    log.info('Bot started, API on :%d, WEBAPP_URL=%s', port, WEBAPP_URL)

    # --- Запуск поллинга как отдельной задачи ---
    polling_task = asyncio.create_task(
        dp.start_polling(bot, handle_signals=False)
    )

    # Ждём либо сигнала остановки, либо завершения поллинга (например, из-за ошибки)
    stop_waiter = asyncio.create_task(stop_event.wait())
    await asyncio.wait(
        [polling_task, stop_waiter],
        return_when=asyncio.FIRST_COMPLETED,
    )

    # Если поллинг ещё работает, останавливаем его
    if not polling_task.done():
        log.info('Stopping polling...')
        await dp.stop_polling()
        try:
            await polling_task
        except Exception:
            log.exception('Error during polling shutdown')
    else:
        # Если поллинг завершился сам, проверяем наличие ошибки
        exc = polling_task.exception()
        if exc:
            log.exception('Polling stopped with error', exc_info=exc)

    # --- Закрытие ресурсов ---
    log.info('Closing bot session and API runner...')
    await bot.session.close()
    await runner.cleanup()

    log.info('Shutdown complete')


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info('Interrupted')
