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

# Linklarni vaqtinchalik saqlash
url_data = {}

def get_video_info(url):
    # Agar papkada cookies.txt bo'lsa, undan foydalanadi
    cookie_path = 'cookies.txt' if os.path.exists('cookies.txt') else None
    
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'cookiefile': cookie_path, # Instagram blokidan o'tish kaliti
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        formats = info.get('formats', [])
        
        valid_formats = []
        seen_res = set()

        for f in formats:
            # Faqat video va audio birga bo'lgan yoki sifatli formatlarni ajratish
            res = f.get('height')
            if res and res not in seen_res:
                # Hajmini hisoblash
                filesize = f.get('filesize') or f.get('filesize_approx') or 0
                size_mb = round(filesize / (1024 * 1024), 2)
                
                if size_mb > 0.1: # Juda kichik fayllarni tashlab ketamiz
                    valid_formats.append({
                        'id': f['format_id'],
                        'res': res,
                        'size': size_mb
                    })
                    seen_res.add(res)

        # Agar maxsus formatlar topilmasa, borini olamiz
        if not valid_formats:
            valid_formats.append({
                'id': 'best',
                'res': info.get('height', 'Sifatli'),
                'size': round((info.get('filesize_approx') or 0) / (1024*1024), 2)
            })

        # Saralash: 240p, 360p, 480p...
        valid_formats.sort(key=lambda x: int(x['res']) if str(x['res']).isdigit() else 0)
        
        return {'title': info.get('title', 'Video'), 'formats': valid_formats, 'url': url}

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    await message.answer("Salom! 🎬 Men Instagram va YouTube'dan video yuklayman.\nLink yuboring:")

@dp.message_handler(regexp=r'(https?://.+)')
async def handle_link(message: types.Message):
    msg = await message.answer("🔍 Video tahlil qilinmoqda...")
    url = message.text
    
    try:
        info = get_video_info(url)
        url_data[message.chat.id] = url
        
        kb = InlineKeyboardMarkup(row_width=1)
        for f in info['formats']:
            text = f"🎬 {f['res']}p — 📁 {f['size']} MB"
            kb.add(InlineKeyboardButton(text=text, callback_data=f"dl:{f['id']}"))
            
        await msg.delete()
        await message.answer(f"✅ Topildi: {info['title']}\n\nPastdan sifatni tanlang:", reply_markup=kb)
        
    except Exception as e:
        logging.error(e)
        await msg.edit_text("❌ Xatolik! Video topilmadi yoki bot bloklandi.\n\nMaslahat: Cookies.txt faylini yangilang.")

@dp.callback_query_handler(lambda c: c.data.startswith('dl:'))
async def download_video(callback: types.CallbackQuery):
    format_id = callback.data.split(':')[1]
    chat_id = callback.message.chat.id
    url = url_data.get(chat_id)
    
    if not url:
        await callback.answer("Xatolik: Link eskirgan.", show_alert=True)
        return

    await bot.answer_callback_query(callback.id, text="Yuklanmoqda...")
    wait_msg = await bot.send_message(chat_id, "🚀 Video yuklanmoqda, kuting...")

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
        
        await wait_msg.edit_text("📤 Telegramga yuborilmoqda...")
        with open(file_name, 'rb') as video:
            await bot.send_video(chat_id, video, caption="Tayyor! ✅")
        
        os.remove(file_name)
        await wait_msg.delete()
    except Exception as e:
        await wait_msg.edit_text(f"❌ Xato: {str(e)}")
        if os.path.exists(file_name): os.remove(file_name)

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
