"""
ryu-vision — Telegram Mini App Bot

Bot Telegram untuk melayani Mini App (WebApp).
Menggunakan aiogram 3.x
"""

import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import WebAppInfo, MenuButtonWebApp
from aiogram.utils.keyboard import InlineKeyboardBuilder

import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN)
dp = Dispatcher()

WEBAPP_URL = os.getenv("WEBAPP_URL", "https://your-app.vercel.app")


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Welcome + tombol buka Mini App"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🚀 Buka Mini App", web_app=WebAppInfo(url=WEBAPP_URL))
    await message.answer(
        "👁️ Selamat datang di **ryu-vision**!\n\n"
        "Klik tombol di bawah untuk membuka Mini App:",
        reply_markup=builder.as_markup()
    )


@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "**Perintah yang tersedia:**\n"
        "/start — Buka Mini App\n"
        "/help — Bantuan ini"
    )


async def main():
    await bot.set_chat_menu_button(
        menu_button=MenuButtonWebApp(text="🚀 ryu-vision", web_app=WebAppInfo(url=WEBAPP_URL))
    )
    await dp.start_polling(bot)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
