import os
import asyncio
import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, FSInputFile
from aiogram.filters import CommandStart

TOKEN = os.getenv("TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()

QUALITIES = [240, 480, 720]


@dp.message(CommandStart())
async def start(message: Message):
    await message.answer("📥 Link yubor (Instagram / YouTube)")


# INSTAGRAM VIDEO OLISH (API)
async def get_instagram_video(url):
    api = f"https://api.cobalt.tools/api/json"

    async with aiohttp.ClientSession() as session:
        async with session.post(api, json={"url": url}) as resp:
            data = await resp.json()

            if "url" in data:
                return data["url"]

    return None


# VIDEO DOWNLOAD
async def download_file(url, filename):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            with open(filename, "wb") as f:
                f.write(await resp.read())


# LINK HANDLER
@dp.message()
async def handle_link(message: Message):
    url = message.text

    await message.answer("⏳ Tekshirilmoqda...")

    try:
        if "instagram.com" in url:
            video_url = await get_instagram_video(url)

            if not video_url:
                await message.answer("❌ Video topilmadi")
                return

            buttons = []
            for q in QUALITIES:
                buttons.append([
                    InlineKeyboardButton(
                        text=f"{q}p",
                        callback_data=f"{q}|{video_url}"
                    )
                ])

            kb = InlineKeyboardMarkup(inline_keyboard=buttons)

            await message.answer("🎬 Sifatni tanla:", reply_markup=kb)

        else:
            await message.answer("❌ Faqat Instagram hozircha")

    except Exception as e:
        print(e)
        await message.answer("❌ Xatolik")


# CALLBACK
@dp.callback_query()
async def process(callback: types.CallbackQuery):
    quality, video_url = callback.data.split("|")
    quality = int(quality)

    await callback.message.answer("📥 Yuklanmoqda...")

    try:
        filename = "video.mp4"
        await download_file(video_url, filename)

        size = round(os.path.getsize(filename) / 1024 / 1024, 2)

        await bot.send_video(
            callback.from_user.id,
            FSInputFile(filename),
            caption=f"✅ {quality}p | {size} MB"
        )

        os.remove(filename)

    except Exception as e:
        print(e)
        await callback.message.answer("❌ Xatolik")


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
