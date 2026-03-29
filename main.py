import os
import asyncio
import aiohttp
import yt_dlp
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message, FSInputFile
from aiogram.filters import CommandStart

TOKEN = os.getenv("TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()


@dp.message(CommandStart())
async def start(message: Message):
    await message.answer("📥 Link yubor (Instagram / YouTube / TikTok)")


# 1️⃣ API (cobalt)
async def api1(url):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post("https://api.cobalt.tools/api/json", json={"url": url}) as r:
                data = await r.json()
                return data.get("url")
    except:
        return None


# 2️⃣ API (snapinsta-like fallback)
async def api2(url):
    try:
        api = f"https://api.vevioz.com/api/button/mp4/{url}"
        async with aiohttp.ClientSession() as session:
            async with session.get(api) as r:
                text = await r.text()
                if "mp4" in text:
                    return url  # fallback signal
    except:
        return None


# 3️⃣ yt-dlp (oxirgi variant)
def api3(url):
    try:
        ydl_opts = {
            "format": "best",
            "outtmpl": "video.%(ext)s",
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        for f in os.listdir():
            if f.startswith("video."):
                return f
    except:
        return None


# LINK HANDLER
@dp.message()
async def handle(message: Message):
    url = message.text
    await message.answer("⏳ Qidirilmoqda...")

    # 1 urinish
    video_url = await api1(url)

    # 2 urinish
    if not video_url:
        video_url = await api2(url)

    # 3 urinish (local download)
    if not video_url:
        file = api3(url)
        if file:
            size = round(os.path.getsize(file) / 1024 / 1024, 2)
            await bot.send_video(message.chat.id, FSInputFile(file), caption=f"{size} MB")
            os.remove(file)
            return

    # agar API orqali kelsa
    if video_url and video_url.startswith("http"):
        filename = "video.mp4"

        async with aiohttp.ClientSession() as session:
            async with session.get(video_url) as r:
                with open(filename, "wb") as f:
                    f.write(await r.read())

        size = round(os.path.getsize(filename) / 1024 / 1024, 2)

        await bot.send_video(
            message.chat.id,
            FSInputFile(filename),
            caption=f"✅ {size} MB"
        )

        os.remove(filename)
        return

    await message.answer("❌ Hech qaysi usul ishlamadi")


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
