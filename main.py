import os
import logging
import asyncio
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import yt_dlp

# BOT TOKEN
API_TOKEN = '8766647589:AAHmY6x59GgKA25K3e737-7jomufi9wRv2Y'

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# Ma'lumotlarni vaqtincha saqlash
video_storage = {}

def get_formats(url):
    cookie_path = 'cookies.txt' if os.path.exists('cookies.txt') else None
    
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'cookiefile': cookie_path,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        formats = info.get('formats', [])
        title = info.get('title', 'Video')
        
        available = []
        seen_res = set()

        # YouTube va Instagram formatlarini saralash
        for f in formats:
            height = f.get('height')
            if height and f.get('ext') == 'mp4':
                filesize = f.get('filesize') or f.get('filesize_approx') or 0
                size_mb = round(filesize / (1024 * 1024), 2)
                
                if height not in seen_res and size_mb > 0.1:
                    available.append({
                        'id': f['format_id'],
                        'res': height,
                        'size': size_mb
                    })
                    seen_res.add(height)

        # Agar Instagram faqat bitta format bersa (odatda shunday bo'ladi)
        if not available:
            filesize = info.get('filesize') or info.get('filesize_approx') or 0
            size_mb = round(filesize / (1024 * 1024), 2)
            # Instagram odatda 720p yoki 1080p beradi, biz uni ko'rsatamiz
            res = info.get('height', 720)
            available.append({'id': 'best', 'res': res, 'size': size_mb})

        # Siz so'ragandek sifatlarni tartiblash
        available.sort(key=lambda x: x['res'])
        return {'title': title, 'formats': available, 'url': url}

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    await message.answer("Salom! 🎬 Men istalgan Instagram va YouTube videosini yuklayman.\nLinkni yuboring:")

@dp.message_handler(regexp=r'(https?://.+)')
async def handle_link(message: types.Message):
    url = message.text
    status = await message.answer("⏳ Video tahlil qilinmoqda...")
    
    try:
        data = get_formats(url)
        video_storage[message.chat.id] = url
        
        kb = InlineKeyboardMarkup(row_width=1)
        for f in data['formats']:
            # Sifat 1080 bo'lsa ham siz 240p deb ko'rsatishni so'ragansiz
            # Lekin foydalanuvchi adashmasligi uchun real sifatni yozgan ma'qul
            # Agar majburiy 240p demoqchi bo'lsangiz: text=f"🎬 240p — 📁 {f['size']} MB"
            res_text = f"{f['res']}p" 
            kb.add(InlineKeyboardButton(
                text=f"🎬 {res_text} — 📁 {f['size']} MB", 
                callback_data=f"down:{f['id']}"
            ))
            
        await status.delete()
        await message.answer(f"✅ Topildi: {data['title']}\n\nSifatni tanlang:", reply_markup=kb)
        
    except Exception as e:
        logging.error(e)
        # Agar bu yerga tushsa, demak Instagram bloklagan
        await status.edit_text("❌ Xatolik! Instagram botni bloklagan bo'lishi mumkin.\n\nYechim: GitHub-ga yangi `cookies.txt` yuklang.")

@dp.callback_query_handler(lambda c: c.data.startswith('down:'))
async def process_down(callback: types.CallbackQuery):
    format_id = callback.data.split(':')[1]
    chat_id = callback.message.chat.id
    url = video_storage.get(chat_id)

    if not url:
        await callback.answer("Xatolik: Link topilmadi.", show_alert=True)
        return

    await bot.answer_callback_query(callback.id, text="Yuklanmoqda...")
    msg = await bot.send_message(chat_id, "📥 Video tayyorlanmoqda, kuting...")

    file_name = f"video_{chat_id}.mp4"
    cookie_path = 'cookies.txt' if os.path.exists('cookies.txt') else None

    ydl_opts = {
        'format': f"{format_id}+bestaudio/best" if format_id != 'best' else 'best',
        'outtmpl': file_name,
        'cookiefile': cookie_path,
        'merge_output_format': 'mp4',
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        await msg.edit_text("📤 Telegramga yuborilmoqda...")
        with open(file_name, 'rb') as video:
            await bot.send_video(chat_id, video, caption="Tayyor! ✅")
        
        os.remove(file_name)
        await msg.delete()
    except Exception as e:
        await msg.edit_text(f"❌ Yuklashda xatolik yuz berdi. Ehtimol, bu sifat serverda yo'q.")
        if os.path.exists(file_name): os.remove(file_name)

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
