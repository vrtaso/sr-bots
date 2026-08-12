"""
Точка входа для Replit: запускает бота анкет и бота жалоб одновременно
в одном процессе, плюс keep-alive веб-сервер (чтобы Repl не засыпал).

Локально можно запускать так же (python3 main.py), либо каждый бот
по отдельности: python3 anketa_bot.py / python3 complaint_bot.py
"""

import asyncio
import logging

from keep_alive import keep_alive

import anketa_bot
import complaint_bot

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("main")


async def main():
    log.info("Запуск ботов клана %s...", anketa_bot.CLAN_NAME)
    await anketa_bot._set_commands()
    await complaint_bot._set_commands()
    await asyncio.gather(
        anketa_bot.dp.start_polling(anketa_bot.bot),
        complaint_bot.dp.start_polling(complaint_bot.bot),
    )


if __name__ == "__main__":
    keep_alive()
    asyncio.run(main())
