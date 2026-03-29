import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import yt_dlp

# BOT TOKENNI KIRITING
API_TOKEN = '8766647589:AAHmY6x59GgKA25K3e737-7jomufi9wRv2Y'

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# Video sifatlarini belgilash
target_resolutions = ['240', '360', '480', '720', '1080']

def get_video_info(url):
    ydl_opts = {'quiet': True, 'noplaylist': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        title = info.get('title', 'Video')
        formats = info.get('formats', [])
        
        available_formats = []
        seen_res = set()

        for f in formats:
            res = f.get('height')
            if res and res not in seen_res:
                filesize = f.get('filesize') or f.get('filesize_approx') or 0
                size_mb = round(filesize / (1024 * 1024), 2)
                
                # Agar o'lcham juda kichik bo'lsa (0.0 MB), uni ko'rsatmaymiz
                if size_mb > 0.1:
                    available_formats.append({
                        'id': f['format_id'],
                        'res': res,
                        'size': size_mb
                    })
                    seen_res.add(res)

        # Sifatlarni kichigidan kattasiga saralash
        available_formats.sort(key=lambda x: x['res'])
        return {'title': title, 'formats': available_formats, 'url': url}

@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    await message.reply("Salom! Video linkini yuboring (YouTube yoki Instagram).")

@dp.message_handler(regexp=r'(https?://.+)')
async def handle_link(message: types.Message):
    url = message.text
    status_msg = await message.answer("🔍 Qidirilmoqda...")
    
    try:
        info = get_video_info(url)
        if not info['formats']:
            await status_msg.edit_text("❌ Video formatlari topilmadi.")
            return

        keyboard = InlineKeyboardMarkup(row_width=1)
        for f in info['formats']:
            # Tugma ma'lumotiga URL va Format ID ni sig'dirish uchun qisqartiramiz
            # Callback data hajmi cheklangan (64 bayt), shuning uchun faqat keraklisini yozamiz
            btn_text = f"🎬 {f['res']}p - 📁 {f['size']} MB"
            callback_data = f"dl|{f['id']}|{url}"
            
            # Agar callback_data juda uzun bo'lsa, qisqartiramiz (YouTube uchun muhim)
            if len(callback_data) > 64:
                # Muqobil: URL o'rniga faqat format yuboramiz (oddiyroq usul)
                callback_data = f"dx|{f['id']}" 
                # Diqqat: Bu holatda URLni xotirada saqlash kerak bo'ladi (pastda ko'ring)

            keyboard.add(InlineKeyboardButton(text=btn_text, callback_data=callback_data))
        
        await status_msg.delete()
        await message.answer("✅ Video topildi!\n240p dan boshlab yuqori formatgacha tanlang:", reply_markup=keyboard)
        
        # URLni global yoki vaqtinchalik saqlash (Callback ishlashi uchun)
        global last_url
        last_url = url

    except Exception as e:
        logging.error(e)
        await status_msg.edit_text(f"❌ Xatolik: Link noto'g'ri yoki bot bloklangan.")

@dp.callback_query_handler(lambda c: c.data.startswith('dl|') or c.data.startswith('dx|'))
async def process_download(callback_query: types.CallbackQuery):
    data = callback_query.data.split('|')
    format_id = data[1]
    
    # URLni olish
    url = data[2] if len(data) > 2 else last_url
    
    await bot.answer_callback_query(callback_query.id, text="Yuklash boshlandi, kuting...")
    await bot.send_message(callback_query.from_user.id, "📥 Video tayyorlanmoqda (bir necha soniya vaqt olishi mumkin)...")

    file_path = f"video_{callback_query.from_user.id}.mp4"
    
    ydl_opts = {
        'format': f"{format_id}+bestaudio/best",
        'outtmpl': file_path,
        'merge_output_format': 'mp4',
        'quiet': True
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        with open(file_path, 'rb') as video:
            await bot.send_video(callback_query.from_user.id, video, caption="Tayyor! ✅ @sizning_botingiz")
        
        os.remove(file_path)
    except Exception as e:
        await bot.send_message(callback_query.from_user.id, "❌ Yuklashda xatolik yuz berdi. Bu sifat bot uchun mavjud emas bo'lishi mumkin.")
        if os.path.exists(file_path):
            os.remove(file_path)

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
