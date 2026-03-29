import os
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message, FSInputFile
from aiogram.filters import CommandStart

TOKEN = os.getenv("TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()


@dp.message(CommandStart())
async def start(message: Message):
    await message.answer("📥 Instagram link yubor")


# SNAPSAVE SCRAPER (ISHLAYDI)
async def get_video(url):
    try:
        api = "https://snapsave.app/action.php"

        data = {
            "url": url
        }

        headers = {
            "User-Agent": "Mozilla/5.0"
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(api, data=data, headers=headers) as r:
                html = await r.text()

                soup = BeautifulSoup(html, "html.parser")
                links = soup.find_all("a")

                for a in links:
                    href = a.get("href")
                    if href and ".mp4" in href:
                        return href

    except Exception as e:
        print(e)

    return None


# DOWNLOAD
async def download(url, filename):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as r:
            with open(filename, "wb") as f:
                f.write(await r.read())


@dp.message()
async def handle(message: Message):
    url = message.text

    await message.answer("⏳ Qidirilmoqda...")

    video_url = await get_video(url)

    if not video_url:
        await message.answer("❌ Baribir topilmadi (Instagram blok)")
        return

    file = "video.mp4"
    await download(video_url, file)

    size = round(os.path.getsize(file) / 1024 / 1024, 2)

    await bot.send_video(
        message.chat.id,
        FSInputFile(file),
        caption=f"✅ {size} MB"
    )

    os.remove(file)


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
