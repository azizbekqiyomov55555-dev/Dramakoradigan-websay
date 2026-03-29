import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, FSInputFile
from aiogram.filters import CommandStart
import yt_dlp

TOKEN = os.getenv("TOKEN")  # Railway uchun

bot = Bot(token=TOKEN)
dp = Dispatcher()

# VIDEO FORMATLARNI OLISH
def get_formats(url):
    ydl_opts = {
        "quiet": True,
        "noplaylist": True,
        "cookiefile": "cookies.txt",  # Instagram fix
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

        formats = []
        for f in info.get("formats", []):
            if f.get("height") and f.get("filesize"):
                size = round(f["filesize"] / 1024 / 1024, 2)
                formats.append({
                    "id": f["format_id"],
                    "quality": f"{f['height']}p",
                    "size": size
                })

        # faqat eng yaxshilarini olish
        return sorted(formats, key=lambda x: int(x["quality"][:-1]))[-5:]


# VIDEO YUKLASH
def download(url, format_id):
    ydl_opts = {
        "format": format_id,
        "outtmpl": "video.%(ext)s",
        "cookiefile": "cookies.txt"
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])


# START
@dp.message(CommandStart())
async def start(message: Message):
    await message.answer("📥 Link yubor (Instagram / YouTube)")


# LINK QABUL QILISH
@dp.message()
async def link_handler(message: Message):
    url = message.text

    await message.answer("⏳ Tekshirilmoqda...")

    try:
        formats = get_formats(url)

        if not formats:
            await message.answer("❌ Format topilmadi")
            return

        buttons = []
        for f in formats:
            text = f"{f['quality']} - {f['size']} MB"
            data = f"{f['id']}|{url}"
            buttons.append([InlineKeyboardButton(text=text, callback_data=data)])

        kb = InlineKeyboardMarkup(inline_keyboard=buttons)

        await message.answer("🎬 Formatni tanla:", reply_markup=kb)

    except Exception as e:
        print(e)
        await message.answer("❌ Xatolik yoki noto‘g‘ri link")


# BOSILGANDA VIDEO YUBORISH
@dp.callback_query()
async def send_video(callback: types.CallbackQuery):
    format_id, url = callback.data.split("|")

    await callback.message.answer("📥 Yuklanmoqda...")

    try:
        download(url, format_id)

        for file in os.listdir():
            if file.startswith("video."):
                await bot.send_video(callback.from_user.id, FSInputFile(file))
                os.remove(file)
                break

    except Exception as e:
        print(e)
        await callback.message.answer("❌ Yuklashda xato")


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
