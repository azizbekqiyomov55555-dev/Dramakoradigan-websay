import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import yt_dlp

# Bot tokeningizni bura yozing yoki Railway Env orqali bering
API_TOKEN = '8766647589:AAHmY6x59GgKA25K3e737-7jomufi9wRv2Y'

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# Video ma'lumotlarini vaqtinchalik saqlash uchun
video_data = {}

def get_video_info(url):
    ydl_opts = {'quiet': True, 'noplaylist': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        formats = []
        
        # Sifatlarni saralash (240p, 480p, 720p, 1080p)
        res_list = [240, 480, 720, 1080]
        for res in res_list:
            # Har bir sifat uchun eng mos formatni topish
            best_f = None
            for f in info['formats']:
                if f.get('vcodec') != 'none' and f.get('height') == res:
                    best_f = f
                    break
            
            if best_f:
                filesize = best_f.get('filesize') or best_f.get('filesize_approx') or 0
                filesize_mb = round(filesize / (1024 * 1024), 2)
                formats.append({
                    'format_id': best_f['format_id'],
                    'res': res,
                    'size': filesize_mb
                })
        
        # Agar aniq res topilmasa, borini olish
        if not formats:
            f = info['formats'][-1]
            filesize = f.get('filesize') or f.get('filesize_approx') or 0
            formats.append({
                'format_id': f['format_id'],
                'res': f.get('height', 'Unknown'),
                'size': round(filesize / (1024 * 1024), 2)
            })
            
        return {'title': info.get('title', 'video'), 'formats': formats, 'url': url}

@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    await message.reply("Salom! Instagram yoki YouTube linkini yuboring.")

@dp.message_handler(regexp=r'(https?://(www\.)?(youtube\.com|youtu\.be|instagram\.com).+)')
async def handle_link(message: types.Message):
    url = message.text
    msg = await message.answer("Ma'lumotlar olinmoqda, kuting...")
    
    try:
        info = get_video_info(url)
        video_data[message.chat.id] = info
        
        keyboard = InlineKeyboardMarkup(row_width=1)
        for f in info['formats']:
            btn_text = f"🎬 {f['res']}p - 📁 {f['size']} MB"
            callback_data = f"dl_{f['format_id']}"
            keyboard.add(InlineKeyboardButton(text=btn_text, callback_data=callback_data))
        
        await msg.delete()
        await message.answer(f"Sarlavha: {info['title']}\nSifatni tanlang:", reply_markup=keyboard)
    except Exception as e:
        await msg.edit_text(f"Xatolik yuz berdi: {str(e)}")

@dp.callback_query_handler(lambda c: c.data.startswith('dl_'))
async def process_download(callback_query: types.CallbackQuery):
    format_id = callback_query.data.split('_')[1]
    chat_id = callback_query.message.chat.id
    
    if chat_id not in video_data:
        await callback_query.answer("Ma'lumot eskirgan, linkni qayta yuboring.")
        return

    url = video_data[chat_id]['url']
    await bot.answer_callback_query(callback_query.id, text="Yuklab olish boshlandi...")
    await bot.send_message(chat_id, "Video yuklanmoqda va Telegramga yuborilmoqda...")

    file_path = f"{chat_id}_{format_id}.mp4"
    
    ydl_opts = {
        'format': f"{format_id}+bestaudio/best",
        'outtmpl': file_path,
        'merge_output_format': 'mp4',
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        with open(file_path, 'rb') as video:
            await bot.send_video(chat_id, video, caption="Tayyor! ✅")
        
        os.remove(file_path) # Faylni o'chirish
    except Exception as e:
        await bot.send_message(chat_id, f"Yuklashda xatolik: {str(e)}")
        if os.path.exists(file_path):
            os.remove(file_path)

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
