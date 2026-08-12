"""
SILENT REQUIEM — бот приёма анкет в клан.

Сценарий подачи анкеты:
1. Имя/псевдоним
2. Возраст (минимум 13)
3. Скин (фото)
4. Уровень / лвл (минимум 40)
5. Часовой пояс (ЧП)

Готовая анкета уходит СРАЗУ ВСЕМ модераторам (MODERATOR_IDS) — каждому
отдельным сообщением с кнопками «✅ Принять» / «❌ Отклонить» / «🚫 Забанить».
Решение принимает тот, кто нажал кнопку первым:
- у всех остальных модераторов их копии сообщения автоматически
  обновляются («уже обработано модератором Х»), повторно нажать нельзя;
- заявителю приходит уведомление о решении (при одобрении — ссылка на
  чат клана, если задан CLAN_INVITE_LINK);
- анкета и решение сохраняются в историю (data/anketa_history.json).

Бан пользователей:
- Кнопка «🚫 Забанить» под анкетой сразу банит автора и отклоняет анкету.
- Команды /ban <user_id> [причина], /unban <user_id>, /banlist — доступны
  только модераторам (могут применяться и без готовой анкеты, если знаете id).
- Забаненный пользователь не может подать новую анкету, пока его не разбанят.
- Список банов хранится в data/anketa_banned.json (переживает перезапуск).

Команда /history показывает историю всех анкет и доступна ЛЮБОМУ
модератору из MODERATOR_IDS — остальным бот вежливо откажет. В меню
команд Telegram эта команда видна только в чатах с модераторами.

UX:
- Внизу экрана постоянная reply-клавиатура с кнопкой «📋 Оставить анкету».
- Команда /cancel отменяет заполнение анкеты на любом шаге.
- Если нажать кнопку «Оставить анкету» посреди заполнения — анкета
  начнётся заново (старый прогресс сбрасывается).

История анкет хранится в JSON-файле на диске (переживает перезапуск
бота), поэтому даже уже отправленные модераторам анкеты с кнопками
«Принять/Отклонить/Забанить» продолжают работать после рестарта бота.
"""

import asyncio
import logging
import uuid

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, StateFilter, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message,
    CallbackQuery,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    BotCommand,
    BotCommandScopeDefault,
    BotCommandScopeChat,
)

import storage
from config import (
    BOT_TOKEN_ANKETA,
    MODERATOR_IDS,
    CLAN_NAME,
    CLAN_INVITE_LINK,
    MIN_AGE,
    MIN_LEVEL,
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("anketa_bot")

bot = Bot(token=BOT_TOKEN_ANKETA)
dp = Dispatcher(storage=MemoryStorage())

MODERATOR_IDS_SET = set(MODERATOR_IDS)

BTN_START_ANKETA = "📋 Оставить анкету"

MAIN_KEYBOARD = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text=BTN_START_ANKETA)]],
    resize_keyboard=True,
)

# --- Персистентная история анкет ---
HISTORY_PATH = storage.data_path("anketa_history.json")
HISTORY: dict[str, dict] = storage.load_json(HISTORY_PATH, {})
HISTORY_PAGE_SIZE = 20
STATUS_EMOJI = {"pending": "⏳", "approved": "✅", "declined": "❌", "banned": "🚫"}
STATUS_LABEL = {"pending": "на рассмотрении", "approved": "принята", "declined": "отклонена", "banned": "автор забанен"}


def _save_history():
    storage.save_json(HISTORY_PATH, HISTORY)


# --- Персистентный список банов ---
BANNED_PATH = storage.data_path("anketa_banned.json")
BANNED: dict[str, dict] = storage.load_json(BANNED_PATH, {})


def _save_banned():
    storage.save_json(BANNED_PATH, BANNED)


def _is_banned(user_id: int) -> bool:
    return str(user_id) in BANNED


def _ban_user(user_id: int, username: str, banned_by: str, reason: str = ""):
    BANNED[str(user_id)] = {
        "user_id": user_id,
        "username": username,
        "banned_at": storage.now_iso(),
        "banned_by": banned_by,
        "reason": reason or "не указана",
    }
    _save_banned()


def _unban_user(user_id: int) -> bool:
    if str(user_id) in BANNED:
        del BANNED[str(user_id)]
        _save_banned()
        return True
    return False


class Anketa(StatesGroup):
    name = State()
    age = State()
    skin = State()
    level = State()
    timezone = State()


async def _start_anketa(message: Message, state: FSMContext):
    if _is_banned(message.from_user.id):
        await state.clear()
        await message.answer(
            "🚫 Вы забанены в этом боте и не можете подавать анкеты.\n"
            "Если считаете это ошибкой — свяжитесь с модератором клана напрямую.",
            reply_markup=MAIN_KEYBOARD,
        )
        return

    await state.clear()
    await message.answer(
        f"Добро пожаловать в анкету клана {CLAN_NAME}!\n\n"
        f"Шаг 1/5. Введите ваше имя/псевдоним.\n"
        f"Отменить заполнение в любой момент можно командой /cancel.",
        reply_markup=MAIN_KEYBOARD,
    )
    await state.set_state(Anketa.name)


@dp.message(Command("start"))
async def start(message: Message, state: FSMContext):
    await state.clear()
    if _is_banned(message.from_user.id):
        await message.answer(
            "🚫 Вы забанены в этом боте и не можете подавать анкеты.\n"
            "Если считаете это ошибкой — свяжитесь с модератором клана напрямую."
        )
        return
    await message.answer(
        f"Привет! Это бот приёма анкет в клан {CLAN_NAME}.\n\n"
        f"Нажмите кнопку ниже, чтобы подать анкету.",
        reply_markup=MAIN_KEYBOARD,
    )


@dp.message(Command("cancel"))
async def cancel(message: Message, state: FSMContext):
    current = await state.get_state()
    if current is None:
        await message.answer("Сейчас нечего отменять.", reply_markup=MAIN_KEYBOARD)
        return
    await state.clear()
    await message.answer(
        "Заполнение анкеты отменено.\nМожете начать заново в любой момент:",
        reply_markup=MAIN_KEYBOARD,
    )


# Кнопка запуска анкеты работает в любом состоянии (в т.ч. посреди заполнения —
# в этом случае анкета начинается заново). Регистрируем раньше остальных
# обработчиков состояний, чтобы текст кнопки не воспринимался как ответ.
@dp.message(StateFilter("*"), F.text == BTN_START_ANKETA)
async def start_anketa_button(message: Message, state: FSMContext):
    await _start_anketa(message, state)


# --- Команды модерации: /ban, /unban, /banlist ---

@dp.message(Command("ban"))
async def ban_cmd(message: Message, command: CommandObject):
    if message.from_user.id not in MODERATOR_IDS_SET:
        await message.answer("⛔ Эта команда доступна только модератору.")
        return

    if not command.args:
        await message.answer("Использование: /ban <user_id> [причина]\nНапример: /ban 123456789 спам")
        return

    parts = command.args.split(maxsplit=1)
    target_id_str = parts[0]
    reason = parts[1] if len(parts) > 1 else ""

    if not target_id_str.isdigit():
        await message.answer("user_id должен быть числом. Использование: /ban <user_id> [причина]")
        return

    target_id = int(target_id_str)
    banned_by = message.from_user.full_name or str(message.from_user.id)
    _ban_user(target_id, username="", banned_by=banned_by, reason=reason)

    try:
        await bot.send_message(
            chat_id=target_id,
            text="🚫 Вы были забанены в боте анкет клана SILENT REQUIEM и больше не можете подавать анкеты.",
        )
    except Exception:
        log.warning("Не удалось уведомить пользователя id=%s о бане", target_id)

    await message.answer(f"✅ Пользователь {target_id} забанен." + (f"\nПричина: {reason}" if reason else ""))


@dp.message(Command("unban"))
async def unban_cmd(message: Message, command: CommandObject):
    if message.from_user.id not in MODERATOR_IDS_SET:
        await message.answer("⛔ Эта команда доступна только модератору.")
        return

    if not command.args or not command.args.strip().isdigit():
        await message.answer("Использование: /unban <user_id>")
        return

    target_id = int(command.args.strip())
    if _unban_user(target_id):
        await message.answer(f"✅ Пользователь {target_id} разбанен.")
        try:
            await bot.send_message(
                chat_id=target_id,
                text="✅ Вы разбанены и снова можете подавать анкеты в клан SILENT REQUIEM.",
            )
        except Exception:
            pass
    else:
        await message.answer(f"Пользователь {target_id} не найден в списке забаненных.")


@dp.message(Command("banlist"))
async def banlist_cmd(message: Message):
    if message.from_user.id not in MODERATOR_IDS_SET:
        await message.answer("⛔ Эта команда доступна только модератору.")
        return

    if not BANNED:
        await message.answer("Список банов пуст.")
        return

    lines = [f"🚫 Забаненные пользователи ({len(BANNED)}):\n"]
    for entry in sorted(BANNED.values(), key=lambda e: e["banned_at"], reverse=True):
        ts = storage.format_ts(entry["banned_at"])
        name = f" ({entry['username']})" if entry.get("username") else ""
        lines.append(f"• {entry['user_id']}{name} — {ts}, причина: {entry['reason']}")

    text = "\n".join(lines)
    for chunk_start in range(0, len(text), 3500):
        await message.answer(text[chunk_start:chunk_start + 3500])


@dp.message(Anketa.name)
async def get_name(message: Message, state: FSMContext):
    name = (message.text or "").strip()
    if not name:
        await message.answer("Имя должно быть текстом и не может быть пустым. Введите имя/псевдоним:")
        return
    if len(name) > 64:
        await message.answer("Слишком длинное имя, введите покороче (до 64 символов):")
        return
    await state.update_data(name=name)
    await message.answer(f"Шаг 2/5. Сколько вам лет? (минимум {MIN_AGE})")
    await state.set_state(Anketa.age)


@dp.message(Anketa.age)
async def get_age(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text.isdigit():
        await message.answer("Введите возраст числом, например: 16")
        return

    age = int(text)
    if age < MIN_AGE:
        await message.answer(
            f"К сожалению, минимальный возраст для вступления в {CLAN_NAME} — "
            f"{MIN_AGE} лет. Анкета не отправлена.",
            reply_markup=MAIN_KEYBOARD,
        )
        await state.clear()
        return
    if age > 99:
        await message.answer("Проверьте возраст, введите реалистичное число:")
        return

    await state.update_data(age=age)
    await message.answer("Шаг 3/5. Отправьте фото/скриншот вашего скина (в игре):")
    await state.set_state(Anketa.skin)


@dp.message(Anketa.skin, F.photo)
async def get_skin(message: Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    await state.update_data(skin=photo_id)
    await message.answer(f"Шаг 4/5. Какой у вас уровень (лвл)? (минимум {MIN_LEVEL})")
    await state.set_state(Anketa.level)


@dp.message(Anketa.skin, F.document)
async def get_skin_document(message: Message, state: FSMContext):
    mime = (message.document.mime_type or "")
    if not mime.startswith("image/"):
        await message.answer(
            "Файл не похож на изображение. Пришлите фото/скриншот как обычное фото, "
            "а не файлом-документом другого формата."
        )
        return
    await state.update_data(skin=message.document.file_id)
    await message.answer(f"Шаг 4/5. Какой у вас уровень (лвл)? (минимум {MIN_LEVEL})")
    await state.set_state(Anketa.level)


@dp.message(Anketa.skin)
async def get_skin_invalid(message: Message):
    await message.answer("Нужно отправить именно фото (скриншот скина), а не текст.")


@dp.message(Anketa.level)
async def get_level(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text.isdigit():
        await message.answer("Введите уровень числом, например: 45")
        return

    level = int(text)
    if level < MIN_LEVEL:
        await message.answer(
            f"К сожалению, минимальный уровень для вступления в {CLAN_NAME} — "
            f"{MIN_LEVEL}. Анкета не отправлена.",
            reply_markup=MAIN_KEYBOARD,
        )
        await state.clear()
        return
    if level > 10000:
        await message.answer("Проверьте уровень, введите реалистичное число:")
        return

    await state.update_data(level=level)
    await message.answer("Шаг 5/5. Укажите ваш часовой пояс (например, UTC+3 / МСК):")
    await state.set_state(Anketa.timezone)


def _build_moderator_keyboard(app_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Принять", callback_data=f"approve:{app_id}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"decline:{app_id}"),
            ],
            [
                InlineKeyboardButton(text="🚫 Забанить автора", callback_data=f"banuser:{app_id}"),
            ],
        ]
    )


@dp.message(Anketa.timezone)
async def get_timezone(message: Message, state: FSMContext):
    if _is_banned(message.from_user.id):
        await message.answer(
            "🚫 Вы забанены в этом боте и не можете подавать анкеты.",
            reply_markup=MAIN_KEYBOARD,
        )
        await state.clear()
        return

    timezone = (message.text or "").strip()
    if not timezone:
        await message.answer("Укажите часовой пояс текстом, например: UTC+3")
        return
    if len(timezone) > 32:
        await message.answer("Слишком длинное значение, укажите покороче, например: UTC+3")
        return

    await state.update_data(timezone=timezone)
    data = await state.get_data()

    username = f"@{message.from_user.username}" if message.from_user.username else "нет username"

    app_id = uuid.uuid4().hex[:12]
    caption = (
        f"📋 Новая анкета в клан {CLAN_NAME}\n\n"
        f"👤 Имя/псевдоним: {data['name']}\n"
        f"🎂 Возраст: {data['age']}\n"
        f"⭐ Уровень: {data['level']}\n"
        f"🌍 Часовой пояс: {data['timezone']}\n"
        f"🆔 Telegram: {username} (id: {message.from_user.id})"
    )

    # Рассылаем анкету всем модераторам, запоминаем id их сообщений,
    # чтобы потом синхронно обновить все копии после решения.
    moderator_messages = []
    for mod_id in MODERATOR_IDS:
        try:
            sent = await bot.send_photo(
                chat_id=mod_id,
                photo=data["skin"],
                caption=caption,
                reply_markup=_build_moderator_keyboard(app_id),
            )
            moderator_messages.append({"chat_id": mod_id, "message_id": sent.message_id})
        except Exception:
            log.exception("Не удалось отправить анкету модератору id=%s", mod_id)

    if not moderator_messages:
        await message.answer(
            "⚠️ Не удалось отправить анкету ни одному модератору. Попробуйте позже.",
            reply_markup=MAIN_KEYBOARD,
        )
        await state.clear()
        return

    HISTORY[app_id] = {
        "id": app_id,
        "submitted_at": storage.now_iso(),
        "user_id": message.from_user.id,
        "username": username,
        "name": data["name"],
        "age": data["age"],
        "level": data["level"],
        "timezone": data["timezone"],
        "status": "pending",
        "decided_at": None,
        "decided_by": None,
        "caption": caption,
        "moderator_messages": moderator_messages,
    }
    _save_history()

    await message.answer(
        f"✅ Ваша анкета отправлена модераторам клана {CLAN_NAME}! Ожидайте решения.",
        reply_markup=MAIN_KEYBOARD,
    )
    await state.clear()


async def _update_moderator_copies(application: dict, decision_text: str):
    base_caption = application.get("caption") or ""
    for ref in application.get("moderator_messages", []):
        try:
            await bot.edit_message_caption(
                chat_id=ref["chat_id"],
                message_id=ref["message_id"],
                caption=f"{base_caption}\n\n— Статус: {decision_text}",
                reply_markup=None,
            )
        except Exception:
            log.debug("Не удалось обновить копию сообщения у chat_id=%s", ref["chat_id"])


@dp.callback_query(F.data.startswith("approve:") | F.data.startswith("decline:"))
async def handle_decision(callback: CallbackQuery):
    if callback.from_user.id not in MODERATOR_IDS_SET:
        await callback.answer("У вас нет прав принимать решения по анкетам.", show_alert=True)
        return

    action, app_id = callback.data.split(":", 1)
    application = HISTORY.get(app_id)

    if application is None:
        await callback.answer("Анкета не найдена в истории.", show_alert=True)
        return

    if application["status"] != "pending":
        decided_by = application.get("decided_by") or "другим модератором"
        await callback.answer(
            f"Эта анкета уже обработана ({STATUS_LABEL[application['status']]}, {decided_by}).",
            show_alert=True,
        )
        return

    approved = action == "approve"
    decider_name = callback.from_user.full_name or str(callback.from_user.id)

    application["status"] = "approved" if approved else "declined"
    application["decided_at"] = storage.now_iso()
    application["decided_by"] = decider_name
    _save_history()

    decision_text = (
        f"✅ ПРИНЯТА (модератор: {decider_name})"
        if approved
        else f"❌ ОТКЛОНЕНА (модератор: {decider_name})"
    )
    await _update_moderator_copies(application, decision_text)

    # Уведомляем заявителя.
    try:
        if approved:
            text = (
                f"🎉 Поздравляем! Ваша анкета в клан {CLAN_NAME} одобрена!\n"
                f"Добро пожаловать в клан!"
            )
            if CLAN_INVITE_LINK:
                text += f"\n\nСсылка на чат клана: {CLAN_INVITE_LINK}"
        else:
            text = (
                f"😔 К сожалению, ваша анкета в клан {CLAN_NAME} была отклонена модератором."
            )
        await bot.send_message(chat_id=application["user_id"], text=text)
    except Exception:
        log.exception("Не удалось уведомить заявителя о решении")

    await callback.answer("Решение сохранено." if approved else "Анкета отклонена.")


@dp.callback_query(F.data.startswith("banuser:"))
async def handle_ban_from_anketa(callback: CallbackQuery):
    if callback.from_user.id not in MODERATOR_IDS_SET:
        await callback.answer("У вас нет прав банить пользователей.", show_alert=True)
        return

    _, app_id = callback.data.split(":", 1)
    application = HISTORY.get(app_id)

    if application is None:
        await callback.answer("Анкета не найдена в истории.", show_alert=True)
        return

    decider_name = callback.from_user.full_name or str(callback.from_user.id)
    target_id = application["user_id"]

    _ban_user(target_id, username=application.get("username", ""), banned_by=decider_name, reason="через анкету")

    if application["status"] == "pending":
        application["status"] = "banned"
        application["decided_at"] = storage.now_iso()
        application["decided_by"] = decider_name
        _save_history()
        decision_text = f"🚫 АВТОР ЗАБАНЕН (модератор: {decider_name})"
        await _update_moderator_copies(application, decision_text)
    else:
        await callback.answer(
            f"Пользователь {target_id} забанен (анкета уже была обработана ранее).",
            show_alert=True,
        )

    try:
        await bot.send_message(
            chat_id=target_id,
            text=f"🚫 Вы были забанены в боте анкет клана {CLAN_NAME} и больше не можете подавать анкеты.",
        )
    except Exception:
        log.warning("Не удалось уведомить пользователя id=%s о бане", target_id)

    await callback.answer(f"Пользователь {target_id} забанен.")


@dp.message(Command("history"))
async def history_cmd(message: Message):
    if message.from_user.id not in MODERATOR_IDS_SET:
        await message.answer("⛔ Эта команда доступна только модератору.")
        return

    if not HISTORY:
        await message.answer("История анкет пока пуста.")
        return

    entries = sorted(HISTORY.values(), key=lambda e: e["submitted_at"], reverse=True)
    total = len(entries)
    shown = entries[:HISTORY_PAGE_SIZE]

    lines = [f"📜 История анкет (показаны последние {len(shown)} из {total}):\n"]
    for e in shown:
        emoji = STATUS_EMOJI.get(e["status"], "•")
        submitted = storage.format_ts(e["submitted_at"])
        who = f", {e['decided_by']}" if e.get("decided_by") else ""
        lines.append(
            f"{emoji} {submitted} — {e['name']} (ур.{e['level']}, {e['timezone']}) {e['username']}{who}"
        )

    text = "\n".join(lines)
    for chunk_start in range(0, len(text), 3500):
        await message.answer(text[chunk_start:chunk_start + 3500])


# Фолбэк на случай, если пользователь пишет что-то вне сценария (нет активного
# состояния и это не команда/кнопка).
@dp.message(StateFilter(None))
async def fallback(message: Message):
    if _is_banned(message.from_user.id):
        await message.answer("🚫 Вы забанены в этом боте и не можете подавать анкеты.")
        return
    await message.answer(
        "Нажмите кнопку ниже, чтобы подать анкету, либо используйте /start.",
        reply_markup=MAIN_KEYBOARD,
    )


async def _set_commands():
    default_commands = [
        BotCommand(command="start", description="Начать / показать меню"),
        BotCommand(command="cancel", description="Отменить заполнение анкеты"),
    ]
    await bot.set_my_commands(default_commands, scope=BotCommandScopeDefault())

    # Расширенное меню видно в автодополнении команд только у модераторов.
    moderator_commands = default_commands + [
        BotCommand(command="history", description="История анкет (модератор)"),
        BotCommand(command="ban", description="Забанить пользователя (модератор)"),
        BotCommand(command="unban", description="Разбанить пользователя (модератор)"),
        BotCommand(command="banlist", description="Список забаненных (модератор)"),
    ]
    for mod_id in MODERATOR_IDS:
        try:
            await bot.set_my_commands(
                moderator_commands, scope=BotCommandScopeChat(chat_id=mod_id)
            )
        except Exception:
            log.warning(
                "Не удалось задать команды для чата модератора id=%s "
                "(возможно, он ещё не писал боту).", mod_id
            )


async def main():
    log.info("Anketa bot запущен (модераторов: %d)", len(MODERATOR_IDS))
    await _set_commands()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
