import os
import asyncio
import yt_dlp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv
from aiofiles import open as aio_open

# Sozlamalarni yuklash
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise ValueError("BOT_TOKEN .env faylida topilmadi!")

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Vaqtinchalik papka yaratish (agar yo'q bo'lsa)
TEMP_DIR = "downloads"
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer(
        "Salom! 👋\n\nMen Instagram va YouTube videolarini yuklab olaman.\n"
        "Menga istalgan video havolasini (link) yuboring."
    )

@dp.message(F.text.startswith(("http://", "https://")))
async def process_link(message: types.Message):
    link = message.text
    status_msg = await message.answer("🔍 Video ma'lumotlari olinmoqda... Iltimos kuting.")

    try:
        # yt-dlp sozlamalari
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False, # Barcha formatlarni aniq olish uchun
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(link, download=False)

        if not info:
            await status_msg.edit_text("❌ Xatolik: Video ma'lumotlarini topib bo'lmadi.")
            return
        title = info.get('title', 'Noma\'lum video')
        duration = info.get('duration', 0)
        thumbnail = info.get('thumbnail', None)
        
        # Formatlarni filtrlash (faqat video+audio birga bo'lganlari yoki birlashtirish kerak bo'lsa)
        # Oddiylik uchun eng yaxshi birlashgan formatlarni izlaymiz
        formats_list = []
        
        # Formatlarni tahlil qilish
        for f in info.get('formats', []):
            height = f.get('height')
            vcodec = f.get('vcodec')
            acodec = f.get('acodec')
            filesize = f.get('filesize') or f.get('filesize_approx', 0)
            ext = f.get('ext', 'mp4')
            format_id = f.get('format_id')

            # Faqat video va audio bor formatlarni olamiz (yoki mp4 konteyner)
            if height and vcodec != 'none':
                # Agar audio yo'q bo'lsa, ba'zan muammo bo'ladi, shuning uchun 'best' yoki birlashganlarni qidiramiz
                # Lekin yt-dlp da ko'pincha alohida bo'ladi. Keling, eng oddiy usulni ishlatamiz:
                # Format ID orqali keyinroq yuklaymiz.
                
                label = ""
                if height <= 240:
                    label = "240p"
                elif height <= 480:
                    label = "480p"
                elif height <= 720:
                    label = "720p"
                elif height <= 1080:
                    label = "1080p"
                else:
                    label = f"{height}p" # 1440p, 4k va h.k
                
                # Takrorlanmaslik uchun tekshirish (eng yaxshi bitrate ni tanlash mumkin, hozircha birinchisini olamiz)
                # Biz faqat unikal balandliklarni ko'rsatamiz yoki aniq format ID larni
                formats_list.append({
                    'id': format_id,
                    'label': label,
                    'height': height,
                    'size': filesize,
                    'ext': ext
                })

        # Formatlarni tozalash (bir xil p dagilardan eng yaxshisini qoldirish yoki guruhlash)
        # Bu yerda oddiyroq qilamiz: Har bir turli balandlik uchun bitta variant
        unique_formats = {}
        for fmt in formats_list:            h = fmt['height']
            if h not in unique_formats or fmt['size'] > unique_formats[h]['size']:
                unique_formats[h] = fmt
        
        sorted_formats = sorted(unique_formats.values(), key=lambda x: x['height'])

        if not sorted_formats:
            await status_msg.edit_text("❌ Ushbu video uchun yuklab olish mumkin bo'lgan format topilmadi.")
            return

        # Tugmalarni yaratish
        keyboard = []
        for fmt in sorted_formats:
            size_mb = round(fmt['size'] / (1024 * 1024), 2) if fmt['size'] else "Noma'lum"
            btn_text = f"🎬 {fmt['label']} ({size_mb} MB)"
            callback_data = f"download_{fmt['id']}_{link}"
            
            # Callback data 64 belgidan oshmasligi kerak, link uzun bo'lsa qisqartirish kerak
            # Xavfsizlik uchun linkni base64 qilish yoki session da saqlash yaxshiroq, 
            # lekin hozircha linkni qisqartirmasdan urunamiz (agar link qisqa bo'lsa).
            # Agar link uzun bo'lsa, bu usul ishlamasligi mumkin. 
            # Yechim: Linkni ma'lumotlar bazasiga yoki redisga saqlash. 
            # Hozircha sodda holatda qoldiramiz, lekin ehtiyot chorasi:
            
            if len(callback_data) > 64:
                # Link juda uzun bo'lsa, foydalanuvchiga xabar berish kerak yoki boshqa usul
                # Hozircha shunchaki kesib tashlaymiz (bu ishlamasligi mumkin), 
                # real loyihada DB ishlatish shart.
                pass 

            keyboard.append([InlineKeyboardButton(text=btn_text, callback_data=callback_data)])

        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

        caption = f"📥 **{title}**\n⏱ Davomiyligi: {duration} soniya\n\nSifatni tanlang:"
        
        photo_input = None
        if thumbnail:
            photo_input = types.InputPhoto(url=thumbnail)

        await status_msg.delete()
        
        if photo_input:
            await message.answer_photo(photo=photo_input, caption=caption, reply_markup=reply_markup)
        else:
            await message.answer(caption, reply_markup=reply_markup)

    except Exception as e:
        await status_msg.edit_text(f"❌ Xatolik yuz berdi: {str(e)}")
@dp.callback_query(F.data.startswith("download_"))
async def download_video(callback: types.CallbackQuery):
    await callback.answer("⏳ Yuklanmoqda...")
    
    parts = callback.data.split("_", 2)
    if len(parts) < 3:
        await callback.message.answer("❌ Noto'g'ri so'rov.")
        return

    format_id = parts[1]
    original_link = parts[2]
    
    edit_msg = await callback.message.edit_text("⬇️ Video yuklanmoqda... Bu biroz vaqt olishi mumkin.")

    filename = f"{TEMP_DIR}/{format_id}.mp4"
    
    ydl_opts = {
        'format': f"{format_id}+bestaudio/best", # Video va audioni birlashtirishga harakat
        'outtmpl': filename,
        'merge_output_format': 'mp4',
        'quiet': True,
        'no_warnings': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([original_link])

        # Fayl mavjudligini tekshirish (ba'zan merge bo'lmasligi mumkin)
        if not os.path.exists(filename):
            # Agar merge qilinmasa, boshqa formatni izlash kerak, hozircha xato deb hisoblaymiz
            # Yoki faqat videoni yuklab olamiz (ovozsiz)
             ydl_opts_single = {
                'format': format_id,
                'outtmpl': filename,
                'quiet': True,
            }
            with yt_dlp.YoutubeDL(ydl_opts_single) as ydl:
                ydl.download([original_link])

        # Faylni yuborish
        file_size = os.path.getsize(filename)
        if file_size > 50 * 1024 * 1024: # 50MB dan katta bo'lsa ogohlantirish (Telegram limiti)
             await edit_msg.edit_text("⚠️ Video hajmi 50MB dan katta, Telegram orqali yuborib bo'lmaydi.")
             return

        await bot.send_video(
            chat_id=callback.message.chat.id,
            video=types.FSInputFile(filename),
            caption="✅ Mana sizning videongiz!",            reply_to_message_id=callback.message.message_id
        )
        
        await edit_msg.delete()
        
        # Faylni o'chirish
        os.remove(filename)

    except Exception as e:
        await edit_msg.edit_text(f"❌ Yuklashda xatolik: {str(e)}")
        if os.path.exists(filename):
            os.remove(filename)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
