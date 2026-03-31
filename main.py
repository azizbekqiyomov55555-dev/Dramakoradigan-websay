import os
import asyncio
import subprocess
from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardMarkup, 
    InlineKeyboardButton, 
    ReplyKeyboardMarkup, 
    KeyboardButton,
    KeyboardButtonRequestUsers,
    ReplyKeyboardRemove
)
from pyrogram.enums import ParseMode
from static_ffmpeg import add_paths
from PIL import Image

add_paths()

API_ID = 37366974
API_HASH = "08d09c7ed8b7cb414ed6a99c104f1bd6"
BOT_TOKEN = "8630024708:AAGRE2oY2c74wR4mP3U5C298d3k3a7SUEVU"

app = Client("video_processor", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

user_data = {}

def get_duration(file_path):
    try:
        cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", file_path]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        return float(res.stdout.strip())
    except:
        return 0

async def compress_video(input_path, output_path, target_mb):
    duration = get_duration(input_path)
    if duration == 0: return False
    
    total_bitrate = (target_mb * 8000) / duration
    audio_bitrate = 128
    video_bitrate = int(total_bitrate - audio_bitrate)
    if video_bitrate < 200: video_bitrate = 200

    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vf", "scale=-2:720",
        "-c:v", "libx264", "-b:v", f"{video_bitrate}k",
        "-preset", "fast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", f"{audio_bitrate}k",
        "-movflags", "+faststart", output_path
    ]
    process = await asyncio.create_subprocess_exec(*cmd)
    await process.wait()
    return os.path.exists(output_path)

async def split_video(input_path, start_time, duration_part, output_path):
    cmd = [
        "ffmpeg", "-y", "-ss", str(start_time), "-t", str(duration_part),
        "-i", input_path,
        "-c", "copy", "-map", "0", "-movflags", "+faststart", output_path
    ]
    process = await asyncio.create_subprocess_exec(*cmd)
    await process.wait()
    return os.path.exists(output_path)

def compress_image(input_path, output_path, quality=85, max_size_mb=5):
    """Rasmni siqish"""
    try:
        img = Image.open(input_path)
        
        # EXIF ma'lumotlarini saqlash
        exif = img.info.get('exif', b'')
        
        # RGB formatga o'tkazish
        if img.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Siqish
        img.save(output_path, 'JPEG', quality=quality, optimize=True, exif=exif if exif else b'')
        
        # Fayl hajmini tekshirish
        file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
        
        # Agar hajm katta bo'lsa, sifatni pasaytirish
        while file_size_mb > max_size_mb and quality > 20:
            quality -= 10
            img.save(output_path, 'JPEG', quality=quality, optimize=True, exif=exif if exif else b'')
            file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
        
        return True
    except Exception as e:
        print(f"Rasm siqishda xatolik: {e}")
        return False

def crop_image_square(input_path, output_path):
    """Rasmni to'rtburchak (kvadrat) qilib qirqish"""
    try:
        img = Image.open(input_path)
        width, height = img.size
        
        # Eng kichik o'lchamni aniqlash
        min_side = min(width, height)
        
        # Markazdan qirqish
        left = (width - min_side) // 2
        top = (height - min_side) // 2
        right = left + min_side
        bottom = top + min_side
        
        cropped = img.crop((left, top, right, bottom))
        
        # Sifatli saqlash
        if cropped.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', cropped.size, (255, 255, 255))
            if cropped.mode == 'P':
                cropped = cropped.convert('RGBA')
            background.paste(cropped, mask=cropped.split()[-1] if cropped.mode == 'RGBA' else None)
            cropped = background
        
        cropped.save(output_path, 'JPEG', quality=95, optimize=True)
        return True
    except Exception as e:
        print(f"Rasm qirqishda xatolik: {e}")
        return False

def get_main_keyboard():
    """Rangli pastki menyu tugmalari"""
    keyboard = ReplyKeyboardMarkup(
        [
            [
                KeyboardButton("🎬 Video yuborish", button_color="#3390ec"),
                KeyboardButton("🖼 Rasm yuborish", button_color="#e8733a")
            ],
            [
                KeyboardButton("📊 Statistika", button_color="#2ea02e"),
                KeyboardButton("❓ Yordam", button_color="#a23de8")
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    return keyboard

@app.on_message(filters.command("start"))
async def start(client, message):
    keyboard = get_main_keyboard()
    await message.reply_text(
        "👋 <b>Assalomu alaykum!</b>\n\n"
        "🤖 <b>Men video va rasmlar bilan ishlaydigan botman:</b>\n\n"
        "📹 <b>Video:</b>\n"
        "  • Siqish (compress)\n"
        "  • Qismlarga bo'lish (split)\n"
        "  • Siqish + Bo'lish\n\n"
        "🖼 <b>Rasm:</b>\n"
        "  • Siqish\n"
        "  • Kvadrat qilib qirqish\n"
        "  • Siqish + Qirqish\n\n"
        "👇 <b>Pastdagi tugmalardan foydalaning!</b>",
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML
    )

@app.on_message(filters.regex("🎬 Video yuborish"))
async def video_button(client, message):
    await message.reply_text(
        "📹 <b>Video yuboring!</b>\n\n"
        "Video yuborilgandan keyin amallarni tanlaysiz.",
        parse_mode=ParseMode.HTML
    )

@app.on_message(filters.regex("🖼 Rasm yuborish"))
async def photo_button(client, message):
    await message.reply_text(
        "🖼 <b>Rasm yuboring!</b>\n\n"
        "Rasm yuborilgandan keyin amallarni tanlaysiz.",
        parse_mode=ParseMode.HTML
    )

@app.on_message(filters.regex("📊 Statistika"))
async def stats_button(client, message):
    total_users = len(user_data)
    await message.reply_text(
        f"📊 <b>Statistika:</b>\n\n"
        f"👥 Faol foydalanuvchilar: {total_users}\n"
        f"🤖 Bot holati: Ishlamoqda ✅",
        parse_mode=ParseMode.HTML
    )

@app.on_message(filters.regex("❓ Yordam"))
async def help_button(client, message):
    await message.reply_text(
        "❓ <b>Yordam:</b>\n\n"
        "🎬 <b>Video yuborish:</b>\n"
        "Video yuboring va kerakli amalni tanlang.\n\n"
        "🖼 <b>Rasm yuborish:</b>\n"
        "Rasm yuboring va kerakli amalni tanlang.\n\n"
        "💡 <b>Maslahat:</b> Eng yaxshi natija uchun yuqori sifatli fayllar yuboring!",
        parse_mode=ParseMode.HTML
    )

@app.on_message(filters.photo)
async def handle_photo(client, message):
    """Rasm yuborilganda"""
    msg = await message.reply_text("📥 Rasm yuklanmoqda...")
    
    # Rasmni yuklash
    file_path = await message.download(file_name=f"downloads/{message.from_user.id}_{message.id}.jpg")
    
    orig_size_mb = round(os.path.getsize(file_path) / (1024 * 1024), 2)
    
    # Rasm o'lchamlarini olish
    try:
        img = Image.open(file_path)
        width, height = img.size
        size_info = f"{width}x{height}"
    except:
        size_info = "Noma'lum"
    
    user_data[message.from_user.id] = {
        "path": file_path,
        "type": "photo",
        "orig_size": orig_size_mb,
        "action": None,
        "quality": None
    }
    
    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🗜 Faqat siqish", callback_data="photo_compress"),
            InlineKeyboardButton("✂️ Kvadrat qirqish", callback_data="photo_crop")
        ],
        [
            InlineKeyboardButton("⚡️ Siqish + Qirqish", callback_data="photo_both")
        ]
    ])
    
    await msg.edit_text(
        f"✅ <b>Rasm yuklandi!</b>\n\n"
        f"📏 O'lcham: {size_info}\n"
        f"💾 Hajm: {orig_size_mb} MB\n\n"
        f"👇 <b>Nima qilmoqchisiz?</b>",
        reply_markup=buttons,
        parse_mode=ParseMode.HTML
    )

@app.on_message(filters.video | filters.document)
async def handle_video(client, message):
    if message.document and not message.document.mime_type.startswith("video/"):
        return
    
    msg = await message.reply_text("📥 Video yuklanmoqda (Bu biroz vaqt olishi mumkin)...")
    file_path = await message.download(file_name=f"downloads/{message.from_user.id}_{message.id}.mp4")
    
    orig_size_mb = round(os.path.getsize(file_path) / (1024 * 1024), 2)
    duration = get_duration(file_path)

    user_data[message.from_user.id] = {
        "path": file_path,
        "type": "video",
        "orig_size": orig_size_mb,
        "duration": duration,
        "action": None,
        "target_mb": None,
        "parts": None
    }
    
    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🗜 Faqat siqish", callback_data="choice_compress"),
            InlineKeyboardButton("✂️ Faqat bo'lish", callback_data="choice_split")
        ],
        [
            InlineKeyboardButton("⚡️ Siqish + Bo'lish", callback_data="choice_both")
        ]
    ])
    
    duration_text = f"{int(duration // 60)}:{int(duration % 60):02d}"
    await msg.edit_text(
        f"✅ <b>Video yuklandi!</b>\n\n"
        f"⏱ Davomiyligi: {duration_text}\n"
        f"💾 Hajm: {orig_size_mb} MB\n\n"
        f"👇 <b>Nima qilmoqchisiz?</b>",
        reply_markup=buttons,
        parse_mode=ParseMode.HTML
    )

@app.on_callback_query(filters.regex("^photo_"))
async def photo_callback_handler(client, callback_query):
    user_id = callback_query.from_user.id
    action = callback_query.data.split("_")[1]
    
    if user_id not in user_data:
        await callback_query.answer("Xatolik: Ma'lumot topilmadi.", show_alert=True)
        return

    user_data[user_id]["action"] = action
    
    if action == "compress":
        await callback_query.message.edit_text(
            "🗜 <b>Siqish sifatini tanlang:</b>\n\n"
            "Raqam kiriting (1-100):\n"
            "• 90-100: Yuqori sifat\n"
            "• 70-90: O'rta sifat\n"
            "• 50-70: Past sifat\n\n"
            "Tavsiya: 85",
            parse_mode=ParseMode.HTML
        )
    elif action == "crop":
        await process_crop(client, user_id)
    elif action == "both":
        await callback_query.message.edit_text(
            "⚡️ <b>Siqish sifatini tanlang:</b>\n\n"
            "Raqam kiriting (1-100):\n"
            "• 90-100: Yuqori sifat\n"
            "• 70-90: O'rta sifat\n"
            "• 50-70: Past sifat\n\n"
            "Tavsiya: 85\n\n"
            "(Keyin avtomatik kvadrat qirqiladi)",
            parse_mode=ParseMode.HTML
        )

@app.on_callback_query(filters.regex("^choice_"))
async def callback_handler(client, callback_query):
    user_id = callback_query.from_user.id
    action = callback_query.data.split("_")[1]
    
    if user_id not in user_data:
        await callback_query.answer("Xatolik: Ma'lumot topilmadi.", show_alert=True)
        return

    user_data[user_id]["action"] = action
    
    if action == "compress":
        await callback_query.message.edit_text(
            "🗜 <b>Necha MB gacha siqmoqchisiz?</b>\n\n"
            "Masalan: 500",
            parse_mode=ParseMode.HTML
        )
    elif action == "split":
        await callback_query.message.edit_text(
            "✂️ <b>Nechta qismga bo'lmoqchisiz?</b>\n\n"
            "Masalan: 3",
            parse_mode=ParseMode.HTML
        )
    elif action == "both":
        await callback_query.message.edit_text(
            "⚡️ <b>1-QADAM: Jami video hajmi necha MB bo'lsin?</b>\n\n"
            "Masalan: 1200",
            parse_mode=ParseMode.HTML
        )

@app.on_message(filters.text & filters.private & ~filters.regex("^(🎬|🖼|📊|❓)"))
async def handle_text_input(client, message):
    user_id = message.from_user.id
    if user_id not in user_data or not user_data[user_id]["action"]: 
        return

    if not message.text.isdigit():
        await message.reply_text("❌ Iltimos, faqat raqam kiriting!")
        return

    val = int(message.text)
    data = user_data[user_id]
    
    # RASM uchun
    if data.get("type") == "photo":
        if data["action"] == "compress":
            if val < 1 or val > 100:
                await message.reply_text("❌ Sifat 1-100 oralig'ida bo'lishi kerak!")
                return
            await process_photo_compress(client, user_id, val)
        elif data["action"] == "both":
            if val < 1 or val > 100:
                await message.reply_text("❌ Sifat 1-100 oralig'ida bo'lishi kerak!")
                return
            user_data[user_id]["quality"] = val
            await process_photo_both(client, user_id)
        return
    
    # VIDEO uchun
    action = data["action"]

    if action == "compress":
        await process_compress(client, user_id, val)
    elif action == "split":
        await process_split(client, user_id, val, data["path"])
    elif action == "both":
        if data["target_mb"] is None:
            user_data[user_id]["target_mb"] = val
            await message.reply_text(
                f"✅ Hajm {val} MB etib belgilandi.\n\n"
                f"⚡️ <b>2-QADAM: Endi ushbu hajmdagi videoni nechta qismga bo'lish kerak?</b>\n\n"
                f"Masalan: 4",
                parse_mode=ParseMode.HTML
            )
        else:
            user_data[user_id]["parts"] = val
            await process_both(client, user_id)

async def process_photo_compress(client, user_id, quality):
    """Rasmni siqish"""
    data = user_data[user_id]
    status = await client.send_message(user_id, f"⏳ Rasm siqilmoqda (Sifat: {quality})...")
    out = f"downloads/compressed_{user_id}.jpg"
    
    if compress_image(data["path"], out, quality):
        new_size_mb = round(os.path.getsize(out) / (1024 * 1024), 2)
        await client.send_photo(
            user_id, 
            out, 
            caption=f"✅ <b>Tayyor!</b>\n\n"
                    f"📥 Eski hajm: {data['orig_size']} MB\n"
                    f"📤 Yangi hajm: {new_size_mb} MB\n"
                    f"🎯 Sifat: {quality}",
            parse_mode=ParseMode.HTML
        )
        await status.delete()
    else:
        await status.edit_text("❌ Siqishda xatolik!")
    
    if os.path.exists(out): os.remove(out)
    clean_user(user_id)

async def process_crop(client, user_id):
    """Rasmni kvadrat qirqish"""
    data = user_data[user_id]
    status = await client.send_message(user_id, "⏳ Rasm kvadrat qilib qirqilmoqda...")
    out = f"downloads/cropped_{user_id}.jpg"
    
    if crop_image_square(data["path"], out):
        await client.send_photo(
            user_id, 
            out, 
            caption="✅ <b>Tayyor!</b> Rasm kvadrat qilib qirqildi 🔲",
            parse_mode=ParseMode.HTML
        )
        await status.delete()
    else:
        await status.edit_text("❌ Qirqishda xatolik!")
    
    if os.path.exists(out): os.remove(out)
    clean_user(user_id)

async def process_photo_both(client, user_id):
    """Rasmni siqish + kvadrat qirqish"""
    data = user_data[user_id]
    quality = data["quality"]
    
    status = await client.send_message(user_id, f"⏳ 1/2: Rasm siqilmoqda (Sifat: {quality})...")
    temp_compressed = f"downloads/temp_comp_{user_id}.jpg"
    
    if compress_image(data["path"], temp_compressed, quality):
        await status.edit_text("⏳ 2/2: Siqilgan rasm kvadrat qilib qirqilmoqda...")
        
        out = f"downloads/final_{user_id}.jpg"
        if crop_image_square(temp_compressed, out):
            new_size_mb = round(os.path.getsize(out) / (1024 * 1024), 2)
            await client.send_photo(
                user_id, 
                out, 
                caption=f"✅ <b>Tayyor!</b>\n\n"
                        f"📥 Eski hajm: {data['orig_size']} MB\n"
                        f"📤 Yangi hajm: {new_size_mb} MB\n"
                        f"🎯 Sifat: {quality}\n"
                        f"🔲 Kvadrat qilib qirqildi",
                parse_mode=ParseMode.HTML
            )
            await status.delete()
        else:
            await status.edit_text("❌ Qirqishda xatolik!")
        
        if os.path.exists(out): os.remove(out)
    else:
        await status.edit_text("❌ Siqishda xatolik!")
    
    if os.path.exists(temp_compressed): os.remove(temp_compressed)
    clean_user(user_id)

async def process_compress(client, user_id, target_mb):
    data = user_data[user_id]
    status = await client.send_message(user_id, f"⏳ {target_mb}MB ga siqilmoqda...")
    out = f"downloads/comp_{user_id}.mp4"
    
    if await compress_video(data["path"], out, target_mb):
        actual_size = round(os.path.getsize(out) / (1024 * 1024), 2)
        await client.send_video(
            user_id, 
            out, 
            caption=f"✅ <b>Tayyor!</b>\n\n"
                    f"📥 Eski hajm: {data['orig_size']} MB\n"
                    f"📤 Yangi hajm: {actual_size} MB",
            parse_mode=ParseMode.HTML
        )
        await status.delete()
    else:
        await status.edit_text("❌ Siqishda xatolik!")
    
    if os.path.exists(out): os.remove(out)
    clean_user(user_id)

async def process_split(client, user_id, num_parts, file_path):
    data = user_data[user_id]
    duration = get_duration(file_path)
    part_duration = duration / num_parts
    status = await client.send_message(user_id, f"⏳ Video {num_parts} qismga bo'linmoqda...")

    for i in range(num_parts):
        out_part = f"downloads/part_{i+1}_{user_id}.mp4"
        if await split_video(file_path, i * part_duration, part_duration, out_part):
            await client.send_video(
                user_id, 
                out_part, 
                caption=f"🎬 <b>{i+1}/{num_parts}-qism</b>",
                parse_mode=ParseMode.HTML
            )
            if os.path.exists(out_part): os.remove(out_part)
    
    await status.edit_text("✅ Barcha qismlar yuborildi!")
    clean_user(user_id)

async def process_both(client, user_id):
    data = user_data[user_id]
    target_mb = data["target_mb"]
    num_parts = data["parts"]
    
    status = await client.send_message(user_id, f"⏳ 1/2-bosqich: Video {target_mb}MB ga siqilmoqda...")
    compressed_file = f"downloads/temp_comp_{user_id}.mp4"
    
    if await compress_video(data["path"], compressed_file, target_mb):
        await status.edit_text(f"⏳ 2/2-bosqich: Siqilgan video {num_parts} qismga bo'linmoqda...")
        
        duration = get_duration(compressed_file)
        part_dur = duration / num_parts
        
        for i in range(num_parts):
            out_part = f"downloads/p_{i+1}_{user_id}.mp4"
            if await split_video(compressed_file, i * part_dur, part_dur, out_part):
                await client.send_video(
                    user_id, 
                    out_part, 
                    caption=f"🎬 <b>{i+1}/{num_parts}-qism (Siqilgan)</b>",
                    parse_mode=ParseMode.HTML
                )
                if os.path.exists(out_part): os.remove(out_part)
        
        await status.edit_text("✅ Hammasi muvaffaqiyatli yakunlandi!")
    else:
        await status.edit_text("❌ Siqish jarayonida xatolik!")

    if os.path.exists(compressed_file): os.remove(compressed_file)
    clean_user(user_id)

def clean_user(user_id):
    if user_id in user_data:
        p = user_data[user_id]["path"]
        if os.path.exists(p): os.remove(p)
        del user_data[user_id]

if __name__ == "__main__":
    if not os.path.exists("downloads"): os.makedirs("downloads")
    print("🤖 Bot ishga tushdi!")
    app.run()
