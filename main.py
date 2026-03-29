import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import CommandStart
import yt_dlp

TOKEN = "8766647589:AAHmY6x59GgKA25K3e737-7jomufi9wRv2Y"

bot = Bot(token=TOKEN)
dp = Dispatcher()

# video info olish
def get_video_formats(url):
    ydl_opts = {
        'quiet': True,
        'no_warnings': True
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        formats = info.get("formats", [])
        
        results = []
        for f in formats:
            if f.get("height"):
                size = f.get("filesize") or 0
                if size:
                    size_mb = round(size / 1024 / 1024, 2)
                else:
                    size_mb = "?"
                
                results.append({
                    "format_id": f["format_id"],
                    "quality": f"{f['height']}p",
                    "size": size_mb
                })
        
        return results[:6]  # eng kerakli 6 ta format


# video yuklash
def download_video(url, format_id):
    ydl_opts = {
        'format': format_id,
        'outtmpl': 'video.%(ext)s'
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])


@dp.message(CommandStart())
async def start(message: Message):
    await message.answer("📥 Link yubor (Instagram / YouTube)")


@dp.message()
async def handle_link(message: Message):
    url = message.text

    await message.answer("⏳ Tekshirilmoqda...")

    try:
        formats = get_video_formats(url)

        buttons = []
        for f in formats:
            text = f"{f['quality']} - {f['size']} MB"
            buttons.append([
                InlineKeyboardButton(
                    text=text,
                    callback_data=f"{f['format_id']}|{url}"
                )
            ])

        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

        await message.answer("🎬 Formatni tanla:", reply_markup=keyboard)

    except Exception as e:
        await message.answer("❌ Xatolik yoki noto‘g‘ri link")


@dp.callback_query()
async def download_callback(callback: types.CallbackQuery):
    format_id, url = callback.data.split("|")

    await callback.message.answer("📥 Yuklanmoqda...")

    try:
        download_video(url, format_id)

        # topilgan faylni yuborish
        for file in os.listdir():
            if file.startswith("video."):
                await bot.send_video(callback.from_user.id, types.FSInputFile(file))
                os.remove(file)
                break

    except Exception as e:
        await callback.message.answer("❌ Yuklashda xato")


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
