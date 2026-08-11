"""
SILENT REQUIEM — бот приёма жалоб.

Сценарий:
1. Пользователь описывает суть жалобы текстом.
2. Опционально прикладывает доказательство (фото/скриншот).
3. Жалоба уходит модератору (MODERATOR_ID_COMPLAINTS).

UX:
- Внизу экрана постоянная reply-клавиатура с кнопкой «⚠️ Оставить жалобу».
- Команда /cancel отменяет заполнение жалобы на любом шаге.
- Если нажать кнопку «Оставить жалобу» посреди заполнения — жалоба
  начнётся заново (старый прогресс сбрасывается).
"""

import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    BotCommand,
)

from config import BOT_TOKEN_COMPLAINTS, MODERATOR_ID_COMPLAINTS, CLAN_NAME

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("complaint_bot")

bot = Bot(token=BOT_TOKEN_COMPLAINTS)
dp = Dispatcher(storage=MemoryStorage())

BTN_START_COMPLAINT = "⚠️ Оставить жалобу"

MAIN_KEYBOARD = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text=BTN_START_COMPLAINT)]],
    resize_keyboard=True,
)


class Complaint(StatesGroup):
    text = State()
    proof = State()


async def _start_complaint(message: Message, state: FSMContext):
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


@dp.message(Complaint.proof, F.photo)
async def get_proof_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    caption = (
        f"⚠️ Новая жалоба ({CLAN_NAME})\n\n"
        f"📝 Текст: {data['text']}\n"
        f"{_build_header(message)}"
    )
    try:
        await bot.send_photo(
            chat_id=MODERATOR_ID_COMPLAINTS,
            photo=message.photo[-1].file_id,
            caption=caption,
        )
        await message.answer("✅ Жалоба отправлена модератору.", reply_markup=MAIN_KEYBOARD)
    except Exception:
        log.exception("Не удалось отправить жалобу модератору")
        await message.answer(
            "⚠️ Не удалось отправить жалобу. Попробуйте позже.", reply_markup=MAIN_KEYBOARD
        )
    finally:
        await state.clear()


@dp.message(Complaint.proof, F.document)
async def get_proof_document(message: Message, state: FSMContext):
    mime = (message.document.mime_type or "")
    data = await state.get_data()

    if mime.startswith("image/"):
        caption = (
            f"⚠️ Новая жалоба ({CLAN_NAME})\n\n"
            f"📝 Текст: {data['text']}\n"
            f"{_build_header(message)}"
        )
        try:
            await bot.send_photo(
                chat_id=MODERATOR_ID_COMPLAINTS,
                photo=message.document.file_id,
                caption=caption,
            )
            await message.answer("✅ Жалоба отправлена модератору.", reply_markup=MAIN_KEYBOARD)
        except Exception:
            log.exception("Не удалось отправить жалобу модератору")
            await message.answer(
                "⚠️ Не удалось отправить жалобу. Попробуйте позже.", reply_markup=MAIN_KEYBOARD
            )
        finally:
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

    caption = (
        f"⚠️ Новая жалоба ({CLAN_NAME})\n\n"
        f"📝 Текст: {data['text']}\n"
        f"📎 Доказательства: {proof_text}\n"
        f"{_build_header(message)}"
    )
    try:
        await bot.send_message(chat_id=MODERATOR_ID_COMPLAINTS, text=caption)
        await message.answer("✅ Жалоба отправлена модератору.", reply_markup=MAIN_KEYBOARD)
    except Exception:
        log.exception("Не удалось отправить жалобу модератору")
        await message.answer(
            "⚠️ Не удалось отправить жалобу. Попробуйте позже.", reply_markup=MAIN_KEYBOARD
        )
    finally:
        await state.clear()


# Фолбэк на случай, если пользователь пишет что-то вне сценария (нет активного
# состояния и это не команда/кнопка).
@dp.message(StateFilter(None))
async def fallback(message: Message):
    await message.answer(
        "Нажмите кнопку ниже, чтобы оставить жалобу, либо используйте /start.",
        reply_markup=MAIN_KEYBOARD,
    )


async def _set_commands():
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Начать / показать меню"),
            BotCommand(command="cancel", description="Отменить заполнение жалобы"),
        ]
    )


async def main():
    log.info("Complaint bot запущен")
    await _set_commands()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
