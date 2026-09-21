import asyncio
import logging
import tempfile
from pathlib import Path
from os import getenv

from dotenv import load_dotenv

load_dotenv()  # Загружаем переменные окружения из .env файла

from aiogram import Bot, Dispatcher, F, Router, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    FSInputFile,
)

from db import (
    init_db,
    get_user_by_telegram_id,
    save_user_name,
    save_user_profile,
)

TOKEN = getenv("BOT_TOKEN")
REDIS_URL = getenv("REDIS_URL")

dialog_router = Router()


class Dialog(StatesGroup):
    ask_name = State()
    main_menu = State()

    reg_birth_date = State()
    reg_gender = State()
    reg_address = State()

    func_docx = State()


# Обработчик запросов
@dialog_router.message(CommandStart())
async def command_start_handler(message: Message, state: FSMContext) -> None:
    await state.clear()  # Очищаем состояние пользователя при старте

    if message.from_user is None:
        return

    user = await get_user_by_telegram_id(message.from_user.id)

    if user and user.name:
        await state.set_state(Dialog.main_menu)

        await message.answer(
            f"Здравствуйте, {html.quote(user.name)}! Выберите действие:",
            reply_markup=main_menu_keyboard(),
        )
    else:
        await state.set_state(Dialog.ask_name)
        await message.answer(
            "Приветствую! Как мне к вам обращаться?",
            reply_markup=ReplyKeyboardRemove(),
        )


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text="Регистрация")],
        [KeyboardButton(text="Конвертация .docx в .pdf")],
    ]
    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        one_time_keyboard=True,
    )


@dialog_router.message(Dialog.ask_name, F.text)
async def process_name(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return

    name = message.text.strip()

    if not name:
        await message.answer("Имя не может быть пустым. Попробуйте ещё раз.")
        return

    await save_user_name(message.from_user.id, name)

    await state.update_data(name=name)
    await state.set_state(Dialog.main_menu)

    await message.answer(
        f"Приятно познакомиться, {html.quote(message.text)}! Выберите действие:",
        reply_markup=main_menu_keyboard(),
    )


def convert_docx_to_pdf(docx_path: Path, pdf_path: Path) -> None:
    from docx2pdf import convert

    convert(str(docx_path), str(pdf_path))


@dialog_router.message(Dialog.main_menu, F.text == "Конвертация .docx в .pdf")
async def conversion_handler(message: Message, state: FSMContext) -> None:
    await state.set_state(Dialog.func_docx)
    await message.answer(
        "Отправьте файл .docx для конвертации в .pdf",
        reply_markup=ReplyKeyboardRemove(),
    )


@dialog_router.message(Dialog.func_docx, F.document)
async def convert_docx_handler(message: Message, state: FSMContext) -> None:
    document = message.document

    file_name = document.file_name or ""

    if not file_name.lower().endswith(".docx"):
        await message.answer("Пожалуйста, отправьте файл с расширением .docx")
        return

    # Telegram-боты обычно могут скачивать файлы до 20 МБ.
    # Проверяем размер, если он известен.
    if document.file_size and document.file_size > 20 * 1024 * 1024:
        await message.answer("Файл слишком большой. Максимальный размер — 20 МБ.")
        return

    status_message = await message.answer("Конвертация файла, пожалуйста, подождите...")

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            input_path = temp_path / "input.docx"
            output_path = temp_path / "output.pdf"

            # Скачтваем документ из Telegram
            bot = message.bot
            await bot.download(document, destination=input_path)

            # Запускаем блокирующую конвертацию в отдельном потоке.
            await asyncio.to_thread(convert_docx_to_pdf, input_path, output_path)

            await message.answer_document(
                FSInputFile(output_path, filename="converted.pdf"),
                caption="Готово! Ваш файл был успешно конвертирован в PDF.",
            )
    except ImportError:
        logging.exception("Conversion error")
        await status_message.edit_text(
            "Не установлена библиотека для конвертации.\n"
            "Выполните: pip install docx2pdf"
        )

    except Exception as error:
        logging.exception("Conversion error")
        await status_message.edit_text(
            "Ошибка при конвертации файла.\n"
            "Убедитесь, что файл не повреждён и конвертер установлен корректно."
        )

    finally:
        # В любом случае возвращаем пользователя в главное меню.
        await state.set_state(Dialog.main_menu)

        await message.answer(
            "Выберите действие:",
            reply_markup=main_menu_keyboard(),
        )


# Если пользователь прислал что-то не то, пока он находится в состоянии конвертации.
@dialog_router.message(Dialog.func_docx)
async def invalid_function_input(message: Message, state: FSMContext) -> None:
    await message.answer(
        "Пожалуйста, отправьте именно документ .docx, чтобы конвертировать его в PDF."
    )


@dialog_router.message(Dialog.main_menu, F.text == "Регистрация")
async def registration_handler(message: Message, state: FSMContext) -> None:
    await state.set_state(Dialog.reg_birth_date)
    await message.answer(
        "Введите вашу дату рождения в формате ДД.ММ.ГГГГ",
        reply_markup=ReplyKeyboardRemove(),
    )


@dialog_router.message(Dialog.reg_birth_date, F.text)
async def process_birth_date(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return

    birth_date = message.text.strip()

    if not birth_date:
        await message.answer("Дата рождения не может быть пустой.")
        return

    await state.update_data(birth_date=birth_date)

    await state.set_state(Dialog.reg_gender)
    await message.answer("Укажите ваш пол")


@dialog_router.message(Dialog.reg_gender, F.text)
async def process_gender(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return

    gender = message.text.strip()

    if not gender:
        await message.answer("Пол не может быть пустым.")
        return

    await state.update_data(gender=gender)

    await state.set_state(Dialog.reg_address)
    await message.answer("Укажите ваш адрес")


@dialog_router.message(Dialog.reg_address, F.text)
async def process_address(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return

    address = message.text.strip()

    if not address:
        await message.answer("Адрес не может быть пустым.")
        return

    await state.update_data(address=address)

    data = await state.get_data()

    await save_user_profile(
        telegram_id=message.from_user.id,
        birth_date=data.get("birth_date", ""),
        gender=data.get("gender", ""),
        address=address,
    )

    user = await get_user_by_telegram_id(message.from_user.id)

    name = ""
    if user and user.name:
        name = user.name
    else:
        name = data.get("name", "")

    await state.set_state(Dialog.main_menu)

    await message.answer(
        f"""
Ваш профиль сохранен.

Имя: {html.quote(name)}
Дата рождения: {html.quote(data.get("birth_date", ""))}
Пол: {html.quote(data.get("gender", ""))}
Адрес: {html.quote(address)}
        """,
        reply_markup=main_menu_keyboard(),
    )


async def main() -> None:
    logging.basicConfig(level=logging.INFO)

    await init_db()  # Инициализация базы данных

    bot = Bot(
        token=TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    storage = RedisStorage.from_url(
        REDIS_URL
    )  # Используем Redis для хранения состояния

    dp = Dispatcher(storage=storage)
    dp.include_router(dialog_router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
