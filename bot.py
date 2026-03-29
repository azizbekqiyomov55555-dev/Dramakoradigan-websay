import os
import logging
import asyncio
from tempfile import NamedTemporaryFile
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, filters, ContextTypes
)
import yt_dlp

# Log sozlamalari
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Holatlar
WAITING_LINK, SELECTING_QUALITY = range(2)

# Yt-dlp sozlamalari (instagram va youtube uchun)
YDL_OPTS = {
    'quiet': True,
    'no_warnings': True,
    'extract_flat': False,
    'ignoreerrors': True,
    'no_color': True,
}

# Qabul qilinadigan platformalar
ALLOWED_DOMAINS = ['youtube.com', 'youtu.be', 'instagram.com', 'www.instagram.com']

def is_valid_link(text: str) -> bool:
    """Linkni tekshirish - YouTube yoki Instagram"""
    return any(domain in text for domain in ALLOWED_DOMAINS)

def extract_video_info(url: str):
    """Video ma'lumotlarini olish (formatlar, o'lchamlar)"""
    with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
            if info is None:
                return None, None
            formats = []
            # video+audio birgalikda bo'lgan formatlarni filtrlash
            for f in info.get('formats', []):
                vcodec = f.get('vcodec', 'none')
                acodec = f.get('acodec', 'none')
                height = f.get('height')
                filesize = f.get('filesize') or f.get('filesize_approx')
                if vcodec != 'none' and acodec != 'none' and height:
                    # Sifat nomi (240p, 480p, 1080p va h.k.)
                    if height <= 240:
                        quality = "240p"
                    elif height <= 480:
                        quality = "480p"
                    elif height <= 720:
                        quality = "720p"
                    elif height <= 1080:
                        quality = "1080p"
                    else:
                        quality = f"{height}p"  # 1440p, 2160p va h.k.
                    formats.append({
                        'format_id': f['format_id'],
                        'quality': quality,
                        'height': height,
                        'filesize': filesize,
                        'ext': f.get('ext', 'mp4')
                    })
            # Eng yaxshi sifatni alohida qo'shamiz (eng baland height)
            if formats:
                best = max(formats, key=lambda x: x['height'])
                best_copy = best.copy()
                best_copy['quality'] = f"Eng yuqori ({best_copy['quality']})"
                formats.append(best_copy)
            # Takrorlanuvchi sifatlarni olib tashlash (faqat bitta 240p, 480p...)
            unique = {}
            for f in formats:
                q = f['quality']
                if q not in unique or f['height'] > unique[q]['height']:
                    unique[q] = f
            formats = list(unique.values())
            # Sifat bo'yicha tartiblash
            def quality_key(q):
                if '240p' in q: return 1
                if '480p' in q: return 2
                if '720p' in q: return 3
                if '1080p' in q: return 4
                if 'Eng yuqori' in q: return 10
                return 5
            formats.sort(key=lambda x: quality_key(x['quality']))
            return formats, info.get('title', 'Video')
        except Exception as e:
            logger.error(f"Extract error: {e}")
            return None, None

def format_size(size_bytes):
    """Baytni MB ga o'tkazish"""
    if size_bytes is None:
        return "noma'lum"
    return f"{size_bytes / (1024*1024):.2f} MB"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Salom! Menga Instagram yoki YouTube video linkini yuboring.\n"
        "Men sizga kerakli sifat va fayl hajmini ko'rsatib, videoni yuklab beraman."
    )

async def link_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Foydalanuvchi link yuborganda"""
    text = update.message.text.strip()
    if not is_valid_link(text):
        await update.message.reply_text(
            "❌ Iltimos, faqat YouTube yoki Instagram video linkini yuboring."
        )
        return WAITING_LINK

    await update.message.reply_text("⏳ Videoni tahlil qilmoqda, biroz kuting...")
    formats, title = await asyncio.to_thread(extract_video_info, text)

    if not formats:
        await update.message.reply_text(
            "❌ Video ma'lumotlarini olishning iloji bo'lmadi.\n"
            "Link to'g'riligini tekshiring yoki video omma uchun ochiqmi?"
        )
        return WAITING_LINK

    # Ma'lumotlarni saqlash
    context.user_data['link'] = text
    context.user_data['formats'] = formats
    context.user_data['title'] = title[:50]  # uzun nomni qisqartirish

    # Tugmalar yaratish (sifat + fayl hajmi)
    keyboard = []
    for fmt in formats:
        size_str = format_size(fmt['filesize'])
        label = f"{fmt['quality']} ({size_str})"
        callback_data = f"quality_{fmt['format_id']}"
        keyboard.append([InlineKeyboardButton(label, callback_data=callback_data)])
    keyboard.append([InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"🎬 Video: {title}\n\nKerakli sifatni tanlang (fayl hajmi MB da):",
        reply_markup=reply_markup
    )
    return SELECTING_QUALITY

async def quality_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Foydalanuvchi sifat tugmasini bosganda"""
    query = update.callback_query
    await query.answer()

    if query.data == "cancel":
        await query.edit_message_text("❌ Bekor qilindi.")
        return ConversationHandler.END

    format_id = query.data.replace("quality_", "")
    formats = context.user_data.get('formats', [])
    selected = next((f for f in formats if f['format_id'] == format_id), None)
    if not selected:
        await query.edit_message_text("❌ Xatolik: format topilmadi.")
        return ConversationHandler.END

    link = context.user_data['link']
    title = context.user_data['title']

    # Tanlangan format ma'lumoti
    quality_label = selected['quality']
    size_mb = format_size(selected['filesize'])
    await query.edit_message_text(
        f"✅ Tanlangan: {quality_label}\n"
        f"📦 Hajmi: {size_mb}\n"
        f"⏳ Yuklab olinmoqda, iltimos kuting..."
    )

    # Video yuklab olish
    temp_file = NamedTemporaryFile(delete=False, suffix=f".{selected['ext']}")
    temp_path = temp_file.name
    temp_file.close()

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'outtmpl': temp_path,
        'format': format_id,
    }
    try:
        # Yuklab olish (blokirovka qilmaydigan thread)
        def download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([link])
        await asyncio.to_thread(download)

        # Fayl hajmini tekshirish (Telegram video limiti 50MB)
        file_size = os.path.getsize(temp_path)
        if file_size > 50 * 1024 * 1024:
            await query.message.reply_text(
                f"⚠️ Video hajmi {file_size/(1024*1024):.1f} MB (50MB dan katta).\n"
                "Telegram bot orqali 50MB dan katta videolarni galereyaga yuborib bo'lmaydi."
            )
            os.unlink(temp_path)
            return ConversationHandler.END

        # Videoni yuborish
        with open(temp_path, 'rb') as video_file:
            await query.message.reply_video(
                video=video_file,
                caption=f"🎥 {title}\n📌 Sifat: {quality_label}\n💾 Hajmi: {size_mb}",
                supports_streaming=True,
                write_timeout=60
            )
        await query.message.reply_text("✅ Video yuborildi! Galereyangizda saqlangan.")
    except Exception as e:
        logger.error(f"Download/send error: {e}")
        await query.message.reply_text(f"❌ Xatolik yuz berdi: {str(e)[:100]}")
    finally:
        # Tozalash
        if os.path.exists(temp_path):
            os.unlink(temp_path)

    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Suhbatni bekor qilish"""
    await update.message.reply_text("❌ Bekor qilindi. Yangi link yuborishingiz mumkin.")
    return ConversationHandler.END

def main():
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise ValueError("BOT_TOKEN muhit o'zgaruvchisi topilmadi")

    app = Application.builder().token(token).build()

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT & ~filters.COMMAND, link_received)],
        states={
            WAITING_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, link_received)],
            SELECTING_QUALITY: [CallbackQueryHandler(quality_selected, pattern="^(quality_|cancel)")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)

    # Railway'da webhook emas, polling ishlatamiz
    app.run_polling()

if __name__ == "__main__":
    main()
