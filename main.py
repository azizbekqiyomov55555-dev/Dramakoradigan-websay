import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import yt_dlp

# BOT TOKEN
API_TOKEN = '8766647589:AAHmY6x59GgKA25K3e737-7jomufi9wRv2Y'

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# Foydalanuvchi yuborgan linklarni saqlash uchun (Tugma ishlashi uchun)
url_storage = {}

def get_video_info(url):
    # Instagram va YouTube uchun maxsus sozlamalar
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'format': 'best',
        # Instagram blokidan o'tish uchun "odam" agenti
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'geo_bypass': True,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        formats = info.get('formats', [info])
        
        results = []
        seen_res = set()

        for f in formats:
            # Sifatni aniqlash
            res = f.get('height') or f.get('format_note')
            if res and str(res).isdigit():
                res = int(res)
                if res not in seen_res:
                    filesize = f.get('filesize') or f.get('filesize_approx') or 0
                    size_mb = round(filesize / (1024 * 1024), 2)
                    
                    # Faqat hajmi aniq bo'lganlarni olamiz (yoki taxminiy)
                    if size_mb > 0:
                        results.append({
                            'id': f['format_id'],
                            'res': res,
                            'size': size_mb
                        })
                        seen_res.add(res)

        # Agar formatlar topilmasa (Instagram ba'zan bitta format beradi)
        if not results:
            filesize = info.get('filesize') or info.get('filesize_approx') or 0
            results.append({
                'id': info.get('format_id', 'best'),
                'res': info.get('height', '720'),
                'size': round(filesize / (1024 * 1024), 2)
            })

        # Sifatni 240p dan boshlab o'sish tartibida saralash
        results.sort(key=lambda x: int(x['res']) if str(x['res']).isdigit() else 0)
        
        return {
            'title': info.get('title', 'Video'),
            'formats': results,
            'url': url
        }

@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    await message.answer("Salom! 🎬\nYouTube yoki Instagram linkini yuboring, men sizga yuklab beraman.")

@dp.message_handler(regexp=r'(https?://.+)')
async def handle_link(message: types.Message):
    url = message.text
    status_msg = await message.answer("⏳ Qidirilmoqda...")
    
    try:
        info = get_video_info(url)
        chat_id = message.chat.id
        url_storage[chat_id] = url # Linkni saqlab qo'yamiz

        keyboard = InlineKeyboardMarkup(row_width=1)
        for f in info['formats']:
            btn_text = f"🎬 {f['res']}p - 📁 {f['size']} MB"
            # Faqat format_id ni yuboramiz (64 bayt limitidan qochish uchun)
            keyboard.add(InlineKeyboardButton(text=btn_text, callback_data=f"down|{f['id']}"))
        
        await status_msg.delete()
        await message.answer(f"🎥 {info['title']}\n\nPastdan sifatni tanlang (240p dan boshlab):", reply_markup=keyboard)
    
    except Exception as e:
        logging.error(f"Xatolik: {e}")
        await status_msg.edit_text("❌ Xatolik yuz berdi!\nBu bo'lishi mumkin:\n1. Link noto'g'ri.\n2. Instagram botni blokladi.\n3. Video shaxsiy (Private).")

@dp.callback_query_handler(lambda c: c.data.startswith('down|'))
async def process_download(callback_query: types.CallbackQuery):
    format_id = callback_query.data.split('|')[1]
    chat_id = callback_query.message.chat.id
    
    if chat_id not in url_storage:
        await callback_query.answer("Xatolik: Link topilmadi, qaytadan yuboring.", show_alert=True)
        return

    url = url_storage[chat_id]
    await bot.answer_callback_query(callback_query.id, text="Yuklab olish boshlandi...")
    sent_msg = await bot.send_message(chat_id, "📥 Video serverga yuklanmoqda...")

    file_path = f"vid_{chat_id}.mp4"
    
    ydl_opts = {
        'format': f"{format_id}+bestaudio/best",
        'outtmpl': file_path,
        'merge_output_format': 'mp4',
        'quiet': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        await sent_msg.edit_text("📤 Telegramga yuborilmoqda...")
        with open(file_path, 'rb') as video:
            await bot.send_video(chat_id, video, caption="Tayyor! ✅")
        
        await sent_msg.delete()
        os.remove(file_path)
    except Exception as e:
        await sent_msg.edit_text(f"❌ Yuklab bo'lmadi. Xatolik: {e}")
        if os.path.exists(file_path):
            os.remove(file_path)

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
