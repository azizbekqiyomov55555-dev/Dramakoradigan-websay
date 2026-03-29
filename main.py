import os
import asyncio
import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message, FSInputFile
from aiogram.filters import CommandStart

TOKEN = os.getenv("TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()


@dp.message(CommandStart())
async def start(message: Message):
    await message.answer("📥 Instagram link yubor")


# INSTAGRAM VIDEO OLISH (REAL)
async def get_instagram_video(url):
    try:
        if "reel" in url:
            shortcode = url.split("/reel/")[1].split("/")[0]
        elif "p/" in url:
            shortcode = url.split("/p/")[1].split("/")[0]
        else:
            return None

        api_url = f"https://www.instagram.com/api/v1/media/{shortcode}/info/"

        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "*/*",
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, headers=headers) as resp:
                data = await resp.json()

                items = data.get("items", [])
                if not items:
                    return None

                video = items[0]
                return video["video_versions"][0]["url"]

    except Exception as e:
        print(e)
        return None


# VIDEO DOWNLOAD
async def download(url, filename):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            with open(filename, "wb") as f:
                f.write(await resp.read())


# HANDLER
@dp.message()
async def handle(message: Message):
    url = message.text

    await message.answer("⏳ Qidirilmoqda...")

    video_url = await get_instagram_video(url)

    if not video_url:
        await message.answer("❌ Video topilmadi (private yoki blok)")
        return

    filename = "video.mp4"
    await download(video_url, filename)

    size = round(os.path.getsize(filename) / 1024 / 1024, 2)

    await bot.send_video(
        message.chat.id,
        FSInputFile(filename),
        caption=f"✅ {size} MB"
    )

    os.remove(filename)


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
