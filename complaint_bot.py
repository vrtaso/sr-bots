"""
SILENT REQUIEM — бот приёма жалоб.

Сценарий:
1. Пользователь описывает суть жалобы текстом.
2. Опционально прикладывает доказательство (фото/скриншот).
3. Жалоба уходит СРАЗУ ВСЕМ модераторам (MODERATOR_IDS_COMPLAINTS), под ней —
   кнопка «🚫 Забанить автора», и сохраняется в историю
   (data/complaints_history.json).

Бан пользователей:
- Кнопка «🚫 Забанить автора» под жалобой сразу банит того, кто её подал
  (например, за спам или заведомо ложные жалобы).
- Команды /ban <user_id> [причина], /unban <user_id>, /banlist — доступны
  только модераторам (могут применяться и без готовой жалобы, если знаете id).
- Забаненный пользователь не может подать новую жалобу, пока его не разбанят.
- Список банов хранится в data/complaints_banned.json (переживает перезапуск).

Команда /history показывает историю всех жалоб и доступна ЛЮБОМУ
модератору из MODERATOR_IDS_COMPLAINTS — остальным бот вежливо откажет.
В меню команд Telegram эта команда видна только в чатах с модераторами.

UX:
- Внизу экрана постоянная reply-клавиатура с кнопкой «⚠️ Оставить жалобу».
- Команда /cancel отменяет заполнение жалобы на любом шаге.
- Если нажать кнопку «Оставить жалобу» посреди заполнения — жалоба
  начнётся заново (старый прогресс сбрасывается).
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
from config import BOT_TOKEN_COMPLAINTS, MODERATOR_IDS_COMPLAINTS, CLAN_NAME

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("complaint_bot")

bot = Bot(token=BOT_TOKEN_COMPLAINTS)
dp = Dispatcher(storage=MemoryStorage())

MODERATOR_IDS_SET = set(MODERATOR_IDS_COMPLAINTS)

BTN_START_COMPLAINT = "⚠️ Оставить жалобу"

MAIN_KEYBOARD = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text=BTN_START_COMPLAINT)]],
    resize_keyboard=True,
)

# --- Персистентная история жалоб ---
HISTORY_PATH = storage.data_path("complaints_history.json")
HISTORY: dict[str, dict] = storage.load_json(HISTORY_PATH, {})
HISTORY_PAGE_SIZE = 20


def _save_history():
    storage.save_json(HISTORY_PATH, HISTORY)


# --- Персистентный список банов ---
BANNED_PATH = storage.data_path("complaints_banned.json")
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


class Complaint(StatesGroup):
    text = State()
    proof = State()


async def _start_complaint(message: Message, state: FSMContext):
    if _is_banned(message.from_user.id):
        await state.clear()
        await message.answer(
            "🚫 Вы забанены в этом боте и не можете оставлять жалобы.\n"
            "Если считаете это ошибкой — свяжитесь с модератором клана напрямую.",
            reply_markup=MAIN_KEYBOARD,
        )
        return

    await state.clear()
    await message.answer(
        f"📮 Жалоба в клан {CLAN_NAME}\n\n"
        f"Опишите суть жалобы: на кого жалуетесь и что произошло.\n"
        f"Отменить в любой момент можно командой /cancel.",
        reply_markup=MAIN_KEYBOARD,
    )
    await state.set_state(Complaint.text)


@dp.message(Command("start"))
async def start(message: Message, state: FSMContext):
    await state.clear()
    if _is_banned(message.from_user.id):
        await message.answer(
            "🚫 Вы забанены в этом боте и не можете оставлять жалобы.\n"
            "Если считаете это ошибкой — свяжитесь с модератором клана напрямую."
        )
        return
    await message.answer(
        f"Привет! Это бот приёма жалоб клана {CLAN_NAME}.\n\n"
        f"Нажмите кнопку ниже, чтобы оставить жалобу.",
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
        "Заполнение жалобы отменено.\nМожете начать заново в любой момент:",
        reply_markup=MAIN_KEYBOARD,
    )


# Кнопка запуска жалобы работает в любом состоянии (в т.ч. посреди заполнения —
# в этом случае жалоба начинается заново). Регистрируем раньше остальных
# обработчиков состояний, чтобы текст кнопки не воспринимался как ответ.
@dp.message(StateFilter("*"), F.text == BTN_START_COMPLAINT)
async def start_complaint_button(message: Message, state: FSMContext):
    await _start_complaint(message, state)


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
            text="🚫 Вы были забанены в боте жалоб клана SILENT REQUIEM и больше не можете отправлять жалобы.",
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
                text="✅ Вы разбанены и снова можете отправлять жалобы в клан SILENT REQUIEM.",
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


@dp.message(Complaint.text)
async def get_text(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text:
        await message.answer("Жалоба должна быть текстом и не может быть пустой. Опишите ситуацию:")
        return
    if len(text) > 2000:
        await message.answer("Слишком длинный текст, сократите описание (до 2000 символов):")
        return

    await state.update_data(text=text)
    await message.answer(
        "Приложите доказательства (фото/скриншот), если есть.\n"
        "Если доказательств нет — отправьте символ «-»."
    )
    await state.set_state(Complaint.proof)


def _build_header(message: Message) -> str:
    username = f"@{message.from_user.username}" if message.from_user.username else "нет username"
    return f"🆔 От: {username} (id: {message.from_user.id})"


def _build_complaint_keyboard(complaint_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚫 Забанить автора", callback_data=f"banuser:{complaint_id}")],
        ]
    )


async def _broadcast_to_moderators(caption: str, photo_file_id, reply_markup):
    """Рассылает жалобу всем модераторам. Возвращает список отправленных сообщений."""
    sent_refs = []
    for mod_id in MODERATOR_IDS_COMPLAINTS:
        try:
            if photo_file_id:
                sent = await bot.send_photo(
                    chat_id=mod_id, photo=photo_file_id, caption=caption, reply_markup=reply_markup
                )
            else:
                sent = await bot.send_message(chat_id=mod_id, text=caption, reply_markup=reply_markup)
            sent_refs.append({"chat_id": mod_id, "message_id": sent.message_id})
        except Exception:
            log.exception("Не удалось отправить жалобу модератору id=%s", mod_id)
    return sent_refs


def _finalize_complaint(complaint_id: str, message: Message, text: str, proof: str, moderator_messages: list):
    HISTORY[complaint_id] = {
        "id": complaint_id,
        "submitted_at": storage.now_iso(),
        "user_id": message.from_user.id,
        "username": f"@{message.from_user.username}" if message.from_user.username else "нет username",
        "text": text,
        "proof": proof,
        "moderator_messages": moderator_messages,
    }
    _save_history()


@dp.message(Complaint.proof, F.photo)
async def get_proof_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    complaint_id = uuid.uuid4().hex[:12]
    caption = (
        f"⚠️ Новая жалоба ({CLAN_NAME})\n\n"
        f"📝 Текст: {data['text']}\n"
        f"{_build_header(message)}"
    )
    refs = await _broadcast_to_moderators(caption, message.photo[-1].file_id, _build_complaint_keyboard(complaint_id))
    if refs:
        _finalize_complaint(complaint_id, message, data["text"], "фото приложено", refs)
        await message.answer("✅ Жалоба отправлена модератору(ам).", reply_markup=MAIN_KEYBOARD)
    else:
        await message.answer(
            "⚠️ Не удалось отправить жалобу. Попробуйте позже.", reply_markup=MAIN_KEYBOARD
        )
    await state.clear()


@dp.message(Complaint.proof, F.document)
async def get_proof_document(message: Message, state: FSMContext):
    mime = (message.document.mime_type or "")
    data = await state.get_data()

    if mime.startswith("image/"):
        complaint_id = uuid.uuid4().hex[:12]
        caption = (
            f"⚠️ Новая жалоба ({CLAN_NAME})\n\n"
            f"📝 Текст: {data['text']}\n"
            f"{_build_header(message)}"
        )
        refs = await _broadcast_to_moderators(
            caption, message.document.file_id, _build_complaint_keyboard(complaint_id)
        )
        if refs:
            _finalize_complaint(complaint_id, message, data["text"], "файл-изображение приложен", refs)
            await message.answer("✅ Жалоба отправлена модератору(ам).", reply_markup=MAIN_KEYBOARD)
        else:
            await message.answer(
                "⚠️ Не удалось отправить жалобу. Попробуйте позже.", reply_markup=MAIN_KEYBOARD
            )
        await state.clear()
        return

    await message.answer(
        "Этот файл не похож на изображение. Пришлите скриншот как фото, "
        "либо отправьте «-», если доказательств нет."
    )


@dp.message(Complaint.proof)
async def get_proof_text(message: Message, state: FSMContext):
    data = await state.get_data()
    proof_text = (message.text or "").strip()
    if not proof_text:
        await message.answer("Пришлите скриншот как фото, либо отправьте «-», если доказательств нет.")
        return

    complaint_id = uuid.uuid4().hex[:12]
    caption = (
        f"⚠️ Новая жалоба ({CLAN_NAME})\n\n"
        f"📝 Текст: {data['text']}\n"
        f"📎 Доказательства: {proof_text}\n"
        f"{_build_header(message)}"
    )
    refs = await _broadcast_to_moderators(caption, None, _build_complaint_keyboard(complaint_id))
    if refs:
        _finalize_complaint(complaint_id, message, data["text"], proof_text, refs)
        await message.answer("✅ Жалоба отправлена модератору(ам).", reply_markup=MAIN_KEYBOARD)
    else:
        await message.answer(
            "⚠️ Не удалось отправить жалобу. Попробуйте позже.", reply_markup=MAIN_KEYBOARD
        )
    await state.clear()


@dp.callback_query(F.data.startswith("banuser:"))
async def handle_ban_from_complaint(callback: CallbackQuery):
    if callback.from_user.id not in MODERATOR_IDS_SET:
        await callback.answer("У вас нет прав банить пользователей.", show_alert=True)
        return

    _, complaint_id = callback.data.split(":", 1)
    entry = HISTORY.get(complaint_id)

    if entry is None:
        await callback.answer("Жалоба не найдена в истории.", show_alert=True)
        return

    decider_name = callback.from_user.full_name or str(callback.from_user.id)
    target_id = entry["user_id"]

    _ban_user(target_id, username=entry.get("username", ""), banned_by=decider_name, reason="через жалобу")

    for ref in entry.get("moderator_messages", []):
        try:
            if callback.message.photo:
                await bot.edit_message_caption(
                    chat_id=ref["chat_id"],
                    message_id=ref["message_id"],
                    caption=f"{callback.message.caption or ''}\n\n— 🚫 Автор забанен ({decider_name})",
                    reply_markup=None,
                )
            else:
                await bot.edit_message_text(
                    chat_id=ref["chat_id"],
                    message_id=ref["message_id"],
                    text=f"{callback.message.text or ''}\n\n— 🚫 Автор забанен ({decider_name})",
                    reply_markup=None,
                )
        except Exception:
            log.debug("Не удалось обновить копию сообщения у chat_id=%s", ref["chat_id"])

    try:
        await bot.send_message(
            chat_id=target_id,
            text=f"🚫 Вы были забанены в боте жалоб клана {CLAN_NAME} и больше не можете отправлять жалобы.",
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
        await message.answer("История жалоб пока пуста.")
        return

    entries = sorted(HISTORY.values(), key=lambda e: e["submitted_at"], reverse=True)
    total = len(entries)
    shown = entries[:HISTORY_PAGE_SIZE]

    lines = [f"📜 История жалоб (показаны последние {len(shown)} из {total}):\n"]
    for e in shown:
        submitted = storage.format_ts(e["submitted_at"])
        text_preview = e["text"] if len(e["text"]) <= 120 else e["text"][:120] + "…"
        lines.append(
            f"⚠️ {submitted} — {e['username']}\n"
            f"   {text_preview}\n"
            f"   Доказательства: {e['proof']}"
        )

    text = "\n".join(lines)
    for chunk_start in range(0, len(text), 3500):
        await message.answer(text[chunk_start:chunk_start + 3500])


# Фолбэк на случай, если пользователь пишет что-то вне сценария (нет активного
# состояния и это не команда/кнопка).
@dp.message(StateFilter(None))
async def fallback(message: Message):
    if _is_banned(message.from_user.id):
        await message.answer("🚫 Вы забанены в этом боте и не можете оставлять жалобы.")
        return
    await message.answer(
        "Нажмите кнопку ниже, чтобы оставить жалобу, либо используйте /start.",
        reply_markup=MAIN_KEYBOARD,
    )


async def _set_commands():
    default_commands = [
        BotCommand(command="start", description="Начать / показать меню"),
        BotCommand(command="cancel", description="Отменить заполнение жалобы"),
    ]
    await bot.set_my_commands(default_commands, scope=BotCommandScopeDefault())

    moderator_commands = default_commands + [
        BotCommand(command="history", description="История жалоб (модератор)"),
        BotCommand(command="ban", description="Забанить пользователя (модератор)"),
        BotCommand(command="unban", description="Разбанить пользователя (модератор)"),
        BotCommand(command="banlist", description="Список забаненных (модератор)"),
    ]
    for mod_id in MODERATOR_IDS_COMPLAINTS:
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
    log.info("Complaint bot запущен (модераторов: %d)", len(MODERATOR_IDS_COMPLAINTS))
    await _set_commands()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
