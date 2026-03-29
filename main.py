import os
import asyncio
import yt_dlp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()

TEMP_DIR = "downloads"
os.makedirs(TEMP_DIR, exist_ok=True)

user_links = {}


@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer(
        "Salom! 👋\n\nMen Instagram va YouTube videolarini yuklab olaman.\n"
        "Menga link yuboring."
    )


@dp.message(F.text.startswith(("http://", "https://")))
async def process_link(message: types.Message):
    link = message.text
    user_id = message.from_user.id
    user_links[user_id] = link
    
    status_msg = await message.answer("🔍 Qidirilmoqda...")

    try:
        ydl_opts = {'quiet': True, 'no_warnings': True}
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(link, download=False)

        title = info.get('title', 'Video')
        duration = info.get('duration', 0)
        thumbnail = info.get('thumbnail')
        
        formats_list = []
        seen_heights = set()
        
        for f in info.get('formats', []):            height = f.get('height')
            vcodec = f.get('vcodec')
            filesize = f.get('filesize') or f.get('filesize_approx', 0)
            format_id = f.get('format_id')
            
            if height and vcodec != 'none' and height not in seen_heights:
                seen_heights.add(height)
                
                if height <= 240:
                    label = "240p"
                elif height <= 480:
                    label = "480p"
                elif height <= 720:
                    label = "720p"
                elif height <= 1080:
                    label = "1080p"
                else:
                    label = f"{height}p"
                
                formats_list.append({
                    'id': format_id,
                    'label': label,
                    'height': height,
                    'size': filesize,
                })

        formats_list.sort(key=lambda x: x['height'])
        
        if not formats_list:
            await status_msg.edit_text("❌ Format topilmadi.")
            return

        keyboard = []
        for i, fmt in enumerate(formats_list[:6]):
            size_mb = round(fmt['size'] / (1024 * 1024), 1) if fmt['size'] else "?"
            btn_text = f"🎬 {fmt['label']} ({size_mb} MB)"
            callback_data = f"dl_{user_id}_{i}_{fmt['id']}"
            keyboard.append([InlineKeyboardButton(text=btn_text, callback_data=callback_data)])

        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        caption = f"📥 {title}\n⏱ {duration} soniya\n\nSifatni tanlang:"
        
        await status_msg.delete()
        
        if thumbnail:
            await message.answer_photo(
                photo=thumbnail,
                caption=caption,
                reply_markup=reply_markup
            )        else:
            await message.answer(caption, reply_markup=reply_markup)
    except Exception as e:
        await status_msg.edit_text(f"❌ Xatolik: {str(e)[:100]}")


@dp.callback_query(F.data.startswith("dl_"))
async def download_video(callback: types.CallbackQuery):
    await callback.answer("⏳ Yuklanmoqda...")
    
    try:
        parts = callback.data.split("_")
        user_id = int(parts[1])
        index = int(parts[2])
        format_id = parts[3]
        
        link = user_links.get(user_id)
        if not link:
            await callback.message.answer("❌ Link topilmadi. Qaytadan yuboring.")
            return

        edit_msg = await callback.message.edit_text("⬇️ Yuklanmoqda...")
        
        filename = f"{TEMP_DIR}/{format_id}.mp4"
        
        ydl_opts = {
            'format': f"{format_id}+bestaudio/best",
            'outtmpl': filename,
            'merge_output_format': 'mp4',
            'quiet': True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([link])
        except:
            ydl_opts_single = {
                'format': format_id,
                'outtmpl': filename,
                'quiet': True,
            }
            with yt_dlp.YoutubeDL(ydl_opts_single) as ydl:
                ydl.download([link])

        if os.path.exists(filename):
            file_size = os.path.getsize(filename)
            
            if file_size > 50 * 1024 * 1024:
                await edit_msg.edit_text("⚠️ Video 50MB dan katta.")
                os.remove(filename)                return
                
            await bot.send_video(
                chat_id=callback.message.chat.id,
                video=types.FSInputFile(filename),
                caption="✅ Tayyor!"
            )
            
            os.remove(filename)
            await edit_msg.delete()
        else:
            await edit_msg.edit_text("❌ Yuklash xatosi.")
            
    except Exception as e:
        await callback.message.answer(f"❌ Xatolik: {str(e)[:100]}")


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
