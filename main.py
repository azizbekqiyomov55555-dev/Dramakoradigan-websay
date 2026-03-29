import os
import logging
import sqlite3
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import yt_dlp

# BOT TOKEN
API_TOKEN = '8766647589:AAHmY6x59GgKA25K3e737-7jomufi9wRv2Y'

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# Ma'lumotlar bazasini sozlash (Tugmalar o'lib qolmasligi uchun)
conn = sqlite3.connect('bot_data.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS links (chat_id INTEGER, url TEXT)''')
conn.commit()

def save_url(chat_id, url):
    cursor.execute("DELETE FROM links WHERE chat_id=?", (chat_id,))
    cursor.execute("INSERT INTO links VALUES (?, ?)", (chat_id, url))
    conn.commit()

def get_url(chat_id):
    cursor.execute("SELECT url FROM links WHERE chat_id=?", (chat_id,))
    res = cursor.fetchone()
    return res[0] if res else None

def get_video_info(url):
    cookie_path = 'cookies.txt' if os.path.exists('cookies.txt') else None
    ydl_opts = {
        'quiet': True,
        'cookiefile': cookie_path,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        formats = info.get('formats', [])
        
        # Sifatlarni saralash (Faqat eng kerakli va ishlaydiganlarini olamiz)
        results = []
        seen = set()
        for f in formats:
            h = f.get('height')
            if h and f.get('ext') == 'mp4':
                filesize = f.get('filesize') or f.get('filesize_approx') or 0
                size_mb = round(filesize / (1024 * 1024), 2)
                if h not in seen and size_mb > 0.1:
                    results.append({'id': f['format_id'], 'res': h, 'size': size_mb})
                    seen.add(h)
        
        results.sort(key=lambda x: x['res'])
        return {'title': info.get('title', 'Video'), 'formats': results}

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    await message.answer("Salom! 🎬 Men Instagram va YouTube yuklovchisiman.\nLinkni yuboring:")

@dp.message_handler(regexp=r'(https?://.+)')
async def handle_link(message: types.Message):
    status = await message.answer("⏳ Video tahlil qilinmoqda...")
    url = message.text
    
    try:
        data = get_video_info(url)
        save_url(message.chat.id, url) # Linkni bazaga saqlaymiz

        kb = InlineKeyboardMarkup(row_width=1)
        for f in data['formats']:
            kb.add(InlineKeyboardButton(
                text=f"🎬 {f['res']}p — 📁 {f['size']} MB", 
                callback_data=f"down:{f['id']}"
            ))
            
        await status.delete()
        await message.answer(f"✅ Topildi: {data['title']}\nSifatni tanlang:", reply_markup=kb)
    except Exception as e:
        await status.edit_text("❌ Xatolik! Instagram botni blokladi yoki link noto'g'ri.")

@dp.callback_query_handler(lambda c: c.data.startswith('down:'))
async def process_download(callback: types.CallbackQuery):
    format_id = callback.data.split(':')[1]
    url = get_url(callback.message.chat.id) # Bazadan linkni olamiz

    if not url:
        await callback.answer("❌ Link muddati o'tgan, qayta yuboring.", show_alert=True)
        return

    await bot.answer_callback_query(callback.id, text="Yuklanmoqda...")
    msg = await bot.send_message(callback.message.chat.id, "📥 Video tayyorlanmoqda, kuting...")

    file_name = f"video_{callback.message.chat.id}.mp4"
    cookie_path = 'cookies.txt' if os.path.exists('cookies.txt') else None

    # Railway xotirasi (RAM) kamligi uchun eng xavfsiz yuklash usuli
    ydl_opts = {
        'format': f"{format_id}+bestaudio/best" if format_id != 'best' else 'best',
        'outtmpl': file_name,
        'cookiefile': cookie_path,
        'merge_output_format': 'mp4',
        'quiet': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        await msg.edit_text("📤 Telegramga yuborilmoqda...")
        with open(file_name, 'rb') as video:
            await bot.send_video(callback.message.chat.id, video, caption="Tayyor! ✅")
        
        os.remove(file_name)
        await msg.delete()
    except Exception as e:
        await msg.edit_text(f"❌ Xatolik: Serverda joy yetmadi yoki video juda katta.")
        if os.path.exists(file_name): os.remove(file_name)

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
