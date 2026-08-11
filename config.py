"""
Конфигурация ботов клана SILENT REQUIEM.

Значения читаются из переменных окружения. На Replit их нужно задать
во вкладке "Secrets" (значок замка в левой панели) — тогда токены не
хранятся в коде и не попадают в публичный репозиторий:

  BOT_TOKEN_ANKETA          — токен бота анкет (от @BotFather)
  MODERATOR_ID              — chat_id модератора анкет (число)
  BOT_TOKEN_COMPLAINTS      — токен бота жалоб (от @BotFather)
  MODERATOR_ID_COMPLAINTS   — chat_id модератора жалоб (число)
  CLAN_INVITE_LINK          — (необязательно) ссылка-приглашение в чат клана,
                              отправляется одобренному участнику лично в боте.

При локальном запуске (не на Replit) можно вместо Secrets создать файл
.env в этой же папке (см. .env.example) — он подхватится автоматически.

Chat_id модератора можно узнать, например, через бота @userinfobot —
модератор должен написать этому боту /start, и бот покажет его id.
"""

import os

# Пытаемся подхватить .env для локального запуска (на Replit не нужно —
# там переменные окружения приходят из Secrets напрямую).
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def _get_env(name: str, required: bool = True, default=None):
    value = os.environ.get(name, default)
    if required and not value:
        raise RuntimeError(
            f"Не задана переменная окружения {name!r}. "
            f"На Replit добавьте её во вкладке Secrets, "
            f"либо создайте файл .env локально (см. .env.example)."
        )
    return value


# --- Бот анкет ---
BOT_TOKEN_ANKETA = _get_env("BOT_TOKEN_ANKETA")
MODERATOR_ID = int(_get_env("MODERATOR_ID"))

# --- Бот жалоб ---
BOT_TOKEN_COMPLAINTS = _get_env("BOT_TOKEN_COMPLAINTS")
MODERATOR_ID_COMPLAINTS = int(_get_env("MODERATOR_ID_COMPLAINTS"))

# --- Необязательно: ссылка-приглашение в чат клана для одобренных участников ---
CLAN_INVITE_LINK = _get_env("CLAN_INVITE_LINK", required=False, default="")

# --- Общие настройки ---
CLAN_NAME = "SILENT REQUIEM"
MIN_AGE = 13
MIN_LEVEL = 40
