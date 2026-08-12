"""
Небольшой веб-сервер на Flask, который держит Repl "живым".

Бесплатные Repl'ы засыпают после периода бездействия. Если открыть URL
этого Repl'а в браузере — увидите страницу-заглушку. Чтобы бот работал
24/7, настройте внешний пинг этого URL каждые 5 минут, например через
https://uptimerobot.com (бесплатно) — добавьте туда "HTTP(s)" монитор
с адресом вашего Repl'а.

Примечание: для по-настоящему стабильной работы 24/7 лучше подходит
платный "Reserved VM" / "Always On" на Replit, либо обычный VPS.
"""

from flask import Flask
from threading import Thread

app = Flask("")


@app.route("/")
def home():
    return "SILENT REQUIEM боты запущены и работают ✅"


def _run():
    app.run(host="0.0.0.0", port=8080)


def keep_alive():
    t = Thread(target=_run)
    t.daemon = True
    t.start()
