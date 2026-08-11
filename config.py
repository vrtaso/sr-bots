"""
Конфигурация ботов клана SILENT REQUIEM.

Значения читаются из переменных окружения. На Replit их нужно задать
во вкладке "Secrets" (значок замка в левой панели) — тогда токены не
хранятся в коде и не попадают в публичный репозиторий:

  BOT_TOKEN_ANKETA          — токен бота анкет (от @BotFather)
  MODERATOR_ID              — chat_id модератора анкет (число)
  BOT_TOKEN_COMPLAINTS      — токен бота жалоб (от @BotFather)
  MODERATOR_ID_COMPLAINTS   — chat_id модератора жалоб (число)
  CLAN_CHAT_ID              — chat_id общего чата клана (число, для групп
                              обычно отрицательное, например -1001234567890).
                              Бот anketa_bot должен быть добавлен в этот чат.
  CLAN_INVITE_LINK          — (необязательно) ссылка-приглашение в чат клана,
                              отправляется одобренному участнику.

При локальном запуске (не на Replit) можно вместо Secrets создать файл
.env в этой же папке (см. .env.example) — он подхватится автоматически.

Chat_id модератора можно узнать, например, через бота @userinfobot —
модератор должен написать этому боту /start, и бот покажет его id.

Chat_id группового чата клана можно узнать так: добавьте в группу бота
@userinfobot (или @RawDataBot) — он пришлёт id чата (число со знаком минус).
После этого @userinfobot/@RawDataBot можно удалить из группы.
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

# --- Общий чат клана (для уведомлений о новых участниках) ---
CLAN_CHAT_ID = int(_get_env("CLAN_CHAT_ID"))
CLAN_INVITE_LINK = _get_env("CLAN_INVITE_LINK", required=False, default="")

# --- Общие настройки ---
CLAN_NAME = "SILENT REQUIEM"
MIN_AGE = 13
MIN_LEVEL = 40
