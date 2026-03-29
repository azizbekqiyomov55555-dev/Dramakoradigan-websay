import os
import logging
import asyncio
from aiogram import Bot, Dispatcher, executor, types
import yt_dlp

# BOT TOKEN
API_TOKEN = '8766647589:AAHmY6x59GgKA25K3e737-7jomufi9wRv2Y'

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

def download_video(url, chat_id):
    file_name = f"video_{chat_id}.mp4"
    cookie_path = 'cookies.txt' if os.path.exists('cookies.txt') else None
    
    # Yuklab olish sozlamalari: 20MB limit va eng yaxshi mp4
    ydl_opts = {
        'format': 'best[ext=mp4][filesize<20M]/best[ext=mp4]/best', # 20MB dan kichik eng yaxshisi
        'outtmpl': file_name,
        'cookiefile': cookie_path,
        'quiet': True,
        'no_warnings': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        # Avval ma'lumotni olamiz (Hajmni tekshirish uchun)
        info = ydl.extract_info(url, download=False)
        filesize = info.get('filesize') or info.get('filesize_approx') or 0
        size_mb = round(filesize / (1024 * 1024), 2)

        if size_mb > 20:
            return None, f"❌ Video juda katta ({size_mb} MB). Limit: 20 MB."

        # Yuklab olish
        ydl.download([url])
        return file_name, size_mb

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    await message.answer("Salom! 🎬 Link yuboring, men uni darhol (max 20MB) yuklab beraman.")

@dp.message_handler(regexp=r'(https?://.+)')
async def auto_download(message: types.Message):
    url = message.text
    status = await message.answer("⏳ Video tahlil qilinmoqda va yuklanmoqda...")
    
    try:
        # Videoni yuklash funksiyasini chaqiramiz
        loop = asyncio.get_event_loop()
        file_path, size = await loop.run_in_executor(None, download_video, url, message.chat.id)

        if file_path:
            await status.edit_text(f"📤 Telegramga yuborilmoqda... ({size} MB)")
            with open(file_path, 'rb') as video:
                # Siz so'ragandek sifatni har doim 240p deb ko'rsatish
                caption_text = f"🎬 Sifati: 240p\n📁 Hajmi: {size} MB\n✅ Tayyor!"
                await bot.send_video(message.chat.id, video, caption=caption_text)
            
            os.remove(file_path)
            await status.delete()
        else:
            await status.edit_text(size) # Bu yerda xatolik xabari (hajm katta bo'lsa)

    except Exception as e:
        logging.error(e)
        await status.edit_text("❌ Xatolik! Video topilmadi yoki Instagram botni blokladi.")
        if os.path.exists(f"video_{message.chat.id}.mp4"):
            os.remove(f"video_{message.chat.id}.mp4")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
