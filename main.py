import os
import logging
import asyncio
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import yt_dlp

# BOT TOKENINGIZ
API_TOKEN = '8766647589:AAHmY6x59GgKA25K3e737-7jomufi9wRv2Y'

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# Linklarni saqlash
user_links = {}

def get_video_data(url):
    cookie_file = 'cookies.txt' if os.path.exists('cookies.txt') else None
    
    ydl_opts = {
        'quiet': True,
        'cookiefile': cookie_file,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        formats = info.get('formats', [])
        
        results = []
        seen_res = set()

        for f in formats:
            res = f.get('height')
            # Faqat mp4 va aniq sifatlarni ajratamiz
            if res and f.get('ext') == 'mp4':
                filesize = f.get('filesize') or f.get('filesize_approx') or 0
                size_mb = round(filesize / (1024 * 1024), 2)
                
                if res not in seen_res and size_mb > 0.1:
                    results.append({'id': f['format_id'], 'res': res, 'size': size_mb})
                    seen_res.add(res)

        # Sifatni kichigidan (240p) kattasiga tartiblash
        results.sort(key=lambda x: x['res'])
        return {'title': info.get('title', 'Video'), 'formats': results}

@dp.message_handler(commands=['start'])
async def welcome(message: types.Message):
    await message.answer("Salom! 🎬 Instagram yoki YouTube linkini yuboring.")

@dp.message_handler(regexp=r'(https?://.+)')
async def process_link(message: types.Message):
    url = message.text
    msg = await message.answer("⏳ Video tahlil qilinmoqda...")
    
    try:
        data = get_video_data(url)
        user_links[message.chat.id] = url
        
        kb = InlineKeyboardMarkup(row_width=1)
        for f in data['formats']:
            # Tugma matni: 240p - 5.5 MB ko'rinishida
            btn_text = f"🎬 {f['res']}p — 📁 {f['size']} MB"
            kb.add(InlineKeyboardButton(text=btn_text, callback_data=f"dl:{f['id']}"))
        
        await msg.delete()
        await message.answer(f"✅ Topildi: {data['title']}\n240p dan boshlab yuqori formatgacha tanlang:", reply_markup=kb)
    except Exception as e:
        logging.error(e)
        await msg.edit_text("❌ Xatolik! Link noto'g'ri yoki Instagram botni blokladi.")

@dp.callback_query_handler(lambda c: c.data.startswith('dl:'))
async def download(callback: types.CallbackQuery):
    format_id = callback.data.split(':')[1]
    chat_id = callback.message.chat.id
    url = user_links.get(chat_id)

    if not url:
        await callback.answer("Xatolik: Link topilmadi.", show_alert=True)
        return

    await bot.answer_callback_query(callback.id, text="Yuklanmoqda...")
    status = await bot.send_message(chat_id, "📥 Video serverga yuklanmoqda...")

    file_name = f"vid_{chat_id}.mp4"
    cookie_file = 'cookies.txt' if os.path.exists('cookies.txt') else None

    ydl_opts = {
        'format': f"{format_id}+bestaudio/best",
        'outtmpl': file_name,
        'cookiefile': cookie_file,
        'merge_output_format': 'mp4',
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        await status.edit_text("📤 Telegramga yuborilmoqda...")
        with open(file_name, 'rb') as video:
            await bot.send_video(chat_id, video, caption="Tayyor! ✅")
        
        os.remove(file_name)
        await status.delete()
    except Exception as e:
        await status.edit_text(f"❌ Xato: {str(e)}")
        if os.path.exists(file_name): os.remove(file_name)

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
