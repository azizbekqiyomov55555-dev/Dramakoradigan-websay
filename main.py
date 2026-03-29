import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, FSInputFile
from aiogram.filters import CommandStart
import yt_dlp
import subprocess

TOKEN = os.getenv("TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()

# FAKE FORMATLAR (doim chiqadi)
QUALITIES = [240, 480, 720]

@dp.message(CommandStart())
async def start(message: Message):
    await message.answer("📥 Link yubor (Instagram / YouTube)")


# VIDEO DOWNLOAD (best)
def download_best(url):
    ydl_opts = {
        "format": "best",
        "outtmpl": "video.%(ext)s",
        "cookiefile": "cookies.txt"
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])


# CONVERT VIDEO
def convert_video(input_file, quality):
    output = f"video_{quality}p.mp4"

    subprocess.run([
        "ffmpeg",
        "-i", input_file,
        "-vf", f"scale=-2:{quality}",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "28",
        "-c:a", "aac",
        output
    ])

    size = round(os.path.getsize(output) / 1024 / 1024, 2)
    return output, size


# LINK HANDLER
@dp.message()
async def link_handler(message: Message):
    url = message.text

    await message.answer("⏳ Tekshirilmoqda...")

    try:
        buttons = []
        for q in QUALITIES:
            buttons.append([
                InlineKeyboardButton(
                    text=f"{q}p",
                    callback_data=f"{q}|{url}"
                )
            ])

        kb = InlineKeyboardMarkup(inline_keyboard=buttons)

        await message.answer("🎬 Sifatni tanla:", reply_markup=kb)

    except:
        await message.answer("❌ Xatolik")


# DOWNLOAD + CONVERT
@dp.callback_query()
async def process(callback: types.CallbackQuery):
    quality, url = callback.data.split("|")
    quality = int(quality)

    await callback.message.answer("📥 Yuklanmoqda...")

    try:
        download_best(url)

        # original topish
        input_file = None
        for f in os.listdir():
            if f.startswith("video."):
                input_file = f
                break

        await callback.message.answer("⚙️ Convert qilinmoqda...")

        output, size = convert_video(input_file, quality)

        await bot.send_video(
            callback.from_user.id,
            FSInputFile(output),
            caption=f"✅ {quality}p | {size} MB"
        )

        os.remove(input_file)
        os.remove(output)

    except Exception as e:
        print(e)
        await callback.message.answer("❌ Xatolik")


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
