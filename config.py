"""
Конфигурация ботов клана SILENT REQUIEM.

Значения читаются из переменных окружения. На Replit их нужно задать
во вкладке "Secrets" (значок замка в левой панели) — тогда токены не
хранятся в коде и не попадают в публичный репозиторий:

  BOT_TOKEN_ANKETA          — токен бота анкет (от @BotFather)
  MODERATOR_IDS             — chat_id модераторов анкет через запятую,
                              например: 111111111,222222222
                              (можно указать и одного: 111111111)
  BOT_TOKEN_COMPLAINTS      — токен бота жалоб (от @BotFather)
  MODERATOR_IDS_COMPLAINTS  — chat_id модераторов жалоб через запятую
  CLAN_INVITE_LINK          — (необязательно) ссылка-приглашение в чат клана,
                              отправляется одобренному участнику лично в боте.

Для обратной совместимости старые имена переменных MODERATOR_ID и
MODERATOR_ID_COMPLAINTS (в единственном числе, одно значение) тоже
поддерживаются, если MODERATOR_IDS / MODERATOR_IDS_COMPLAINTS не заданы.

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


def _parse_id_list(raw: str) -> list[int]:
    ids: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if not part.lstrip("-").isdigit():
            raise RuntimeError(
                f"Некорректный chat_id {part!r} — ожидалось целое число "
                f"(список id через запятую, например: 111111111,222222222)."
            )
        ids.append(int(part))
    if not ids:
        raise RuntimeError("Список chat_id модераторов пуст.")
    return ids


def _get_moderator_ids(plural_name: str, singular_name: str) -> list[int]:
    raw = os.environ.get(plural_name) or os.environ.get(singular_name)
    if not raw:
        raise RuntimeError(
            f"Не задана переменная окружения {plural_name!r} (или устаревшая {singular_name!r}). "
            f"На Replit добавьте её во вкладке Secrets — chat_id модератора(ов) через запятую, "
            f"либо создайте файл .env локально (см. .env.example)."
        )
    return _parse_id_list(raw)


# --- Бот анкет ---
BOT_TOKEN_ANKETA = _get_env("BOT_TOKEN_ANKETA")
MODERATOR_IDS = _get_moderator_ids("MODERATOR_IDS", "MODERATOR_ID")

# --- Бот жалоб ---
BOT_TOKEN_COMPLAINTS = _get_env("BOT_TOKEN_COMPLAINTS")
MODERATOR_IDS_COMPLAINTS = _get_moderator_ids("MODERATOR_IDS_COMPLAINTS", "MODERATOR_ID_COMPLAINTS")

# --- Необязательно: ссылка-приглашение в чат клана для одобренных участников ---
CLAN_INVITE_LINK = _get_env("CLAN_INVITE_LINK", required=False, default="")

# --- Общие настройки ---
CLAN_NAME = "SILENT REQUIEM"
MIN_AGE = 13
MIN_LEVEL = 40
