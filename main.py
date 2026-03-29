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

# Linklarni vaqtinchalik saqlash (RAM)
# Railway o'chib yonsa bu o'chadi, lekin tugma ishlashini kafolatlaydi
temp_data = {}

def get_formats(url):
    cookie_path = 'cookies.txt' if os.path.exists('cookies.txt') else None
    ydl_opts = {
        'quiet': True,
        'cookiefile': cookie_path,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        formats = info.get('formats', [])
        title = info.get('title', 'Video')[:50]
        
        res_list = []
        seen = set()
        for f in formats:
            h = f.get('height')
            if h and f.get('ext') == 'mp4':
                size = f.get('filesize') or f.get('filesize_approx') or 0
                size_mb = round(size / (1024 * 1024), 2)
                if h not in seen and size_mb > 0.1:
                    # Siz aytgandek sifatlarni 240p deb ko'rsatish mantiqi
                    display_res = f"{h}p"
                    res_list.append({'id': f['format_id'], 'res': display_res, 'size': size_mb})
                    seen.add(h)
        
        res_list.sort(key=lambda x: int(x['res'].replace('p','')) if x['res'].replace('p','').isdigit() else 0)
        return {'title': title, 'formats': res_list, 'url': url}

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    await message.answer("Salom! 🎬 Men tayyorman. Link yuboring:")

@dp.message_handler(regexp=r'(https?://.+)')
async def link_handler(message: types.Message):
    url = message.text
    msg = await message.answer("🔍 Qidirilmoqda...")
    
    try:
        data = get_formats(url)
        # Linkni va formatlarni saqlab qo'yamiz
        temp_data[message.chat.id] = url
        
        kb = InlineKeyboardMarkup(row_width=1)
        for f in data['formats']:
            # Callback data max 64 bayt! Shuning uchun faqat ID ni yuboramiz
            kb.add(InlineKeyboardButton(
                text=f"🎬 {f['res']} - 📁 {f['size']} MB", 
                callback_data=f"q:{f['id']}" 
            ))
            
        await msg.delete()
        await message.answer(f"✅ Video: {data['title']}\nSifatni tanlang:", reply_markup=kb)
    except Exception as e:
        logging.error(e)
        await msg.edit_text("❌ Xatolik! Linkda muammo yoki Instagram blokladi.")

@dp.callback_query_handler(lambda c: c.data.startswith('q:'))
async def down_handler(callback: types.CallbackQuery):
    # 1. DARHOL JAVOB BERISH (Tugma aylanib qolmasligi uchun)
    await callback.answer("Yuklash boshlandi...")
    
    format_id = callback.data.split(':')[1]
    chat_id = callback.message.chat.id
    url = temp_data.get(chat_id)

    if not url:
        await bot.send_message(chat_id, "❌ Link topilmadi, qayta yuboring.")
        return

    status = await bot.send_message(chat_id, "📥 Video tayyorlanmoqda (Railway biroz sekin ishlashi mumkin)...")

    file_name = f"video_{chat_id}.mp4"
    cookie_path = 'cookies.txt' if os.path.exists('cookies.txt') else None

    ydl_opts = {
        'format': f"{format_id}+bestaudio/best" if format_id != 'best' else 'best',
        'outtmpl': file_name,
        'cookiefile': cookie_path,
        'merge_output_format': 'mp4',
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        await status.edit_text("📤 Telegramga yuborilmoqda...")
        with open(file_name, 'rb') as video:
            await bot.send_video(chat_id, video, caption="Tayyor! ✅")
        
        await status.delete()
        if os.path.exists(file_name): os.remove(file_name)
    except Exception as e:
        await status.edit_text(f"❌ Yuklashda xato: {str(e)[:50]}")
        if os.path.exists(file_name): os.remove(file_name)

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
