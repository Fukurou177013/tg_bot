import asyncio
from os import getenv

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message

TOKEN = getenv("8679179719:AAG1ZGKS7OpaKutaao9iS6HdFkTFaRXERPE")

dp = Dispatcher()

# Обработчик запросов
@dp.message(Command("start"))
async def command_start_handler(message: Message) -> None:
    await message.answer("ПРИВЕТ!")

async def main() -> None:
    bot = Bot(token=TOKEN)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
    