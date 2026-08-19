# Debts Check Bot

Telegram-бот + Mini App для проверки задолженностей и банкротства.

## Что внутри
- 🤖 `main.py` — aiogram 3 (polling) + aiohttp HTTP API в одном процессе
- 🌐 Mini App — HTML-страница с WebApp-кнопкой (уже опубликована отдельно)
- 🕷 4 парсера: `fssprus.su`, `fssprus.net`, `e-dolgi.ru`, `ЕФРСБ`
- 🚫 Без логов — каждый запрос свежий, ничего не пишется на диск

## Запуск через Docker

```bash
# 1. Скопируйте .env.example → .env и вставьте токен бота
cp .env.example .env
nano .env

# 2. Запуск
docker compose up -d --build

# 3. Логи
docker compose logs -f
```

## Прямой запуск (без Docker)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env && nano .env
python main.py
```

## Где взять BOT_TOKEN
1. Открой @BotFather в Telegram
2. `/newbot` → задай имя и username
3. Скопируй токен в `.env`
4. В BotFather: `/setdomain` → укажи домен Mini App (`debts-check-m0fuc8hd.agent.mira.tg`)

## API

`POST /api/check`
```json
{ "fio": "Иванов Иван Иванович", "birth": "07.02.2001", "region": "Пермский край", "inn": "" }
```

Ответ:
```json
{
  "results": {
    "fssprus_su":  { "status": "clean|found|error", "found": 0, "total": 0, "items": [] },
    "fssprus_net": { "status": "...", "found": 0, "total": 0, "items": [] },
    "edolgi":      { "status": "...", "found": 0, "total": 0, "items": [] },
    "efrsb":       { "status": "...", "found": 0, "total": 0, "items": [] }
  }
}
```
