import os
import asyncio
import yt_dlp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise ValueError("BOT_TOKEN .env faylida topilmadi!")

bot = Bot(token=TOKEN)
dp = Dispatcher()

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
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(link, download=False)

        if not info:
            await status_msg.edit_text("❌ Xatolik: Video ma'lumotlarini topib bo'lmadi.")
            return

        title = info.get('title', 'Noma\'lum video')        duration = info.get('duration', 0)
        thumbnail = info.get('thumbnail', None)

        formats_list = []

        for f in info.get('formats', []):
            height = f.get('height')
            vcodec = f.get('vcodec')
            filesize = f.get('filesize') or f.get('filesize_approx', 0)
            format_id = f.get('format_id')

            if height and vcodec != 'none':
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

        unique_formats = {}
        for fmt in formats_list:
            h = fmt['height']
            if h not in unique_formats or fmt['size'] > unique_formats[h]['size']:
                unique_formats[h] = fmt

        sorted_formats = sorted(unique_formats.values(), key=lambda x: x['height'])

        if not sorted_formats:
            await status_msg.edit_text("❌ Format topilmadi.")
            return

        keyboard = []
        for fmt in sorted_formats:
            size_mb = round(fmt['size'] / (1024 * 1024), 2) if fmt['size'] else "Noma'lum"
            btn_text = f"🎬 {fmt['label']} ({size_mb} MB)"
            callback_data = f"dl_{fmt['id']}_{fmt['height']}"

            keyboard.append([InlineKeyboardButton(text=btn_text, callback_data=callback_data)])
        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

        caption = f"📥 **{title}**\n⏱ Davomiyligi: {duration} soniya\n\nSifatni tanlang:"

        await status_msg.delete()

        if thumbnail:
            await message.answer_photo(
                photo=types.InputPhoto(url=thumbnail),
                caption=caption,
                reply_markup=reply_markup
            )
        else:
            await message.answer(caption, reply_markup=reply_markup)

        await message.answer(
            f"LINK:{link}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🔄 Yangilash", callback_data=f"refresh_{link}")
            ]])
        )

    except Exception as e:
        await status_msg.edit_text(f"❌ Xatolik: {str(e)}")


@dp.callback_query(F.data.startswith("dl_"))
async def download_video(callback: types.CallbackQuery):
    await callback.answer("⏳ Yuklanmoqda...")

    parts = callback.data.split("_")
    if len(parts) < 3:
        await callback.message.answer("❌ Noto'g'ri so'rov.")
        return

    format_id = parts[1]
    height = parts[2]

    edit_msg = await callback.message.edit_text("⬇️ Video yuklanmoqda...")

    try:
        links_msg = None
        async for msg in callback.message.bot.get_messages(
            callback.message.chat.id,
            message_ids=range(callback.message.message_id, callback.message.message_id + 5)
        ):
            if msg.text and msg.text.startswith("LINK:"):
                links_msg = msg
                break
        if not links_msg:
            await edit_msg.edit_text("❌ Link topilmadi. Qaytadan link yuboring.")
            return

        original_link = links_msg.text.replace("LINK:", "")

        filename = f"{TEMP_DIR}/{format_id}_{height}.mp4"

        ydl_opts = {
            'format': f"{format_id}+bestaudio/best",
            'outtmpl': filename,
            'merge_output_format': 'mp4',
            'quiet': True,
            'no_warnings': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([original_link])

        if not os.path.exists(filename):
            ydl_opts_single = {
                'format': format_id,
                'outtmpl': filename,
                'quiet': True,
            }
            with yt_dlp.YoutubeDL(ydl_opts_single) as ydl:
                ydl.download([original_link])

        file_size = os.path.getsize(filename)
        if file_size > 50 * 1024 * 1024:
            await edit_msg.edit_text("⚠️ Video 50MB dan katta.")
            if os.path.exists(filename):
                os.remove(filename)
            return

        await bot.send_video(
            chat_id=callback.message.chat.id,
            video=types.FSInputFile(filename),
            caption="✅ Tayyor!",
            reply_to_message_id=callback.message.message_id
        )

        await edit_msg.delete()

        if os.path.exists(filename):
            os.remove(filename)

    except Exception as e:
        await edit_msg.edit_text(f"❌ Xatolik: {str(e)}")

@dp.callback_query(F.data.startswith("refresh_"))
async def refresh_link(callback: types.CallbackQuery):
    link = callback.data.replace("refresh_", "")
    await callback.message.delete()
    await process_link(types.Message(message_id=0, chat=callback.message.chat, text=link))


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
