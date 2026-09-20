import asyncio
import logging
import sys
from os import getenv
from typing import Any

from aiogram import Bot, Dispatcher, F, Router, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)


TOKEN = getenv("BOT_TOKEN")

form_router = Router()

class Form(StatesGroup):
    name = State()
    birth_date = State()
    gender = State()
    email = State()
    
# Обработчик запросов
@form_router.message(CommandStart())
async def command_start_handler(message: Message, state: FSMContext) -> None:
    await state.set_state(Form.name)
    await message.answer(
        "Привет! Как тебя зовут?",
        reply_markup=ReplyKeyboardRemove(),
        )

@form_router.message(Form.name)
async def process_name(message: Message, state: FSMContext) -> None:
    await state.update_data(name=message.text)
    await message.answer(
        f"Приятно познакомиться, {html.quote(message.text)}!"
    )
    
async def main() -> None:
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(form_router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
