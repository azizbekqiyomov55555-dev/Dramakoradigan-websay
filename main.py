import os
import logging
import asyncio
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import yt_dlp

# BOT TOKENINGIZNI BU YERGA YOZING
API_TOKEN = '8766647589:AAHmY6x59GgKA25K3e737-7jomufi9wRv2Y'

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# Linklarni vaqtinchalik saqlash (Oddiy lug'at)
video_links = {}

def get_formats(url):
    cookie_path = 'cookies.txt' if os.path.exists('cookies.txt') else None
    ydl_opts = {
        'quiet': True,
        'cookiefile': cookie_path,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        formats = info.get('formats', [])
        
        res_dict = {}
        for f in formats:
            # Faqat mp4 va video+audio formatlarni qidiramiz
            height = f.get('height')
            if height and f.get('ext') == 'mp4':
                filesize = f.get('filesize') or f.get('filesize_approx') or 0
                size_mb = round(filesize / (1024 * 1024), 2)
                if size_mb > 0.1:
                    res_dict[height] = {'id': f['format_id'], 'size': size_mb}
        
        # Sifatlarni tartiblash
        sorted_res = sorted(res_dict.keys())
        final_formats = []
        for r in sorted_res:
            final_formats.append({
                'res': r,
                'id': res_dict[r]['id'],
                'size': res_dict[r]['size']
            })
        
        # Agar hech narsa topilmasa, eng yaxshisini olamiz
        if not final_formats:
            final_formats.append({'res': 'Best', 'id': 'best', 'size': 'Unknown'})
            
        return {'title': info.get('title', 'Video'), 'formats': final_formats}

@dp.message_handler(commands=['start'])
async def start_cmd(message: types.Message):
    await message.answer("Salom! 🎬 Link yuboring, men videoni yuklab beraman.")

@dp.message_handler(regexp=r'(https?://.+)')
async def link_handler(message: types.Message):
    url = message.text
    msg = await message.answer("⏳ Video tahlil qilinmoqda...")
    
    try:
        data = get_formats(url)
        video_links[message.chat.id] = url # Linkni saqlab qolamiz
        
        kb = InlineKeyboardMarkup(row_width=1)
        for f in data['formats']:
            # Callback data juda qisqa bo'lishi kerak (max 64 belgidan kam)
            kb.add(InlineKeyboardButton(
                text=f"🎬 {f['res']}p — 📁 {f['size']} MB", 
                callback_data=f"v:{f['id']}"
            ))
            
        await msg.delete()
        await message.answer(f"✅ Topildi: {data['title']}\nSifatni tanlang:", reply_markup=kb)
    except Exception as e:
        logging.error(e)
        await msg.edit_text("❌ Xatolik! Link noto'g'ri yoki Instagram botni blokladi.")

@dp.callback_query_handler(lambda c: c.data.startswith('v:'))
async def download_handler(callback: types.CallbackQuery):
    format_id = callback.data.split(':')[1]
    chat_id = callback.message.chat.id
    url = video_links.get(chat_id)

    if not url:
        await callback.answer("❌ Link topilmadi, iltimos linkni qayta yuboring!", show_alert=True)
        return

    # Tugmani bosganda yuklash holatini ko'rsatish
    await bot.answer_callback_query(callback.id, text="Yuklanmoqda...")
    status_msg = await bot.send_message(chat_id, "📥 Video serverga yuklanmoqda, kuting...")

    file_name = f"vid_{chat_id}.mp4"
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
        
        await status_msg.edit_text("📤 Telegramga yuborilmoqda...")
        with open(file_name, 'rb') as video:
            await bot.send_video(chat_id, video, caption="Tayyor! ✅")
        
        await status_msg.delete()
        os.remove(file_name)
    except Exception as e:
        await status_msg.edit_text(f"❌ Yuklashda xatolik: {e}")
        if os.path.exists(file_name): os.remove(file_name)

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
