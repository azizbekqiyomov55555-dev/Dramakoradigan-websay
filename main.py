import os
import asyncio
import subprocess
from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardMarkup, 
    InlineKeyboardButton, 
    ReplyKeyboardMarkup, 
    KeyboardButton,
    ReplyKeyboardRemove
)
from pyrogram.enums import ParseMode
from static_ffmpeg import add_paths
from PIL import Image, ImageOps, ImageDraw, ImageFont

add_paths()

# --- SOZLAMALAR ---
API_ID = 37366974
API_HASH = "08d09c7ed8b7cb414ed6a99c104f1bd6"
BOT_TOKEN = "8630024708:AAGRE2oY2c74wR4mP3U5C298d3k3a7SUEVU"

app = Client("video_processor", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
user_data = {}

# --- VIDEO FUNKSIYALARI ---
def get_duration(file_path):
    try:
        cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", file_path]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        return float(res.stdout.strip())
    except: return 0

async def compress_video(input_path, output_path, target_mb):
    duration = get_duration(input_path)
    if duration == 0: return False
    total_bitrate = (target_mb * 8000) / duration
    audio_bitrate = 128
    video_bitrate = int(total_bitrate - audio_bitrate)
    if video_bitrate < 200: video_bitrate = 200
    cmd = ["ffmpeg", "-y", "-i", input_path, "-vf", "scale=-2:720", "-c:v", "libx264", "-b:v", f"{video_bitrate}k", "-preset", "fast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", f"{audio_bitrate}k", "-movflags", "+faststart", output_path]
    process = await asyncio.create_subprocess_exec(*cmd)
    await process.wait()
    return os.path.exists(output_path)

async def split_video(input_path, start_time, duration_part, output_path):
    cmd = ["ffmpeg", "-y", "-ss", str(start_time), "-t", str(duration_part), "-i", input_path, "-c", "copy", "-map", "0", "-movflags", "+faststart", output_path]
    process = await asyncio.create_subprocess_exec(*cmd)
    await process.wait()
    return os.path.exists(output_path)

# --- RASM FUNKSIYALARI (MONTAJ VA O'LCHAM) ---

def resize_to_fit(input_path, output_path, target_size=(1080, 1080)):
    """Rasmni kesmasdan, hamma joyini ko'rsatib fonga joylashtirish"""
    try:
        img = Image.open(input_path).convert("RGB")
        img.thumbnail(target_size, Image.Resampling.LANCZOS)
        
        # Yangi fon yaratish (qora)
        new_img = Image.new("RGB", target_size, (0, 0, 0))
        # Markazga qo'yish
        offset = ((target_size[0] - img.size[0]) // 2, (target_size[1] - img.size[1]) // 2)
        new_img.paste(img, offset)
        new_img.save(output_path, "JPEG", quality=95)
        return True
    except Exception as e:
        print(f"Xatolik: {e}")
        return False

def add_text_to_image(input_path, output_path, text):
    """Rasmga matn yozish (Montaj)"""
    try:
        img = Image.open(input_path).convert("RGB")
        draw = ImageDraw.Draw(img)
        # Standart shrift (agar o'zingizda .ttf fayl bo'lsa yo'lini ko'rsatishingiz mumkin)
        try:
            font = ImageFont.truetype("arial.ttf", 40)
        except:
            font = ImageFont.load_default()
            
        w, h = img.size
        draw.text((w/2, h-50), text, fill="white", font=font, anchor="ms", stroke_width=2, stroke_fill="black")
        img.save(output_path, "JPEG", quality=95)
        return True
    except: return False

# --- KLAVIATURALAR ---
def get_main_keyboard():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("🎬 Video yuborish"), KeyboardButton("🖼 Rasm yuborish")],
         [KeyboardButton("📊 Statistika"), KeyboardButton("❓ Yordam")]],
        resize_keyboard=True
    )

# --- HANDLERLAR ---

@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text("👋 **Assalomu alaykum!**\nRasm va videolarni professional qayta ishlash botiga xush kelibsiz!", reply_markup=get_main_keyboard())

@app.on_message(filters.photo)
async def handle_photo(client, message):
    msg = await message.reply_text("📥 Rasm yuklanmoqda...")
    file_path = await message.download(file_name=f"downloads/{message.from_user.id}_{message.id}.jpg")
    
    user_data[message.from_user.id] = {"path": file_path, "type": "photo"}
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("📐 O'lchamni tanlash (Fit)", callback_data="photo_fit_size")],
        [InlineKeyboardButton("✍️ Matn yozish (Montaj)", callback_data="photo_add_text")],
        [InlineKeyboardButton("🗜 Siqish", callback_data="photo_compress")]
    ])
    
    await msg.edit_text("✅ Rasm yuklandi. Tanlang:", reply_markup=buttons)

@app.on_callback_query(filters.regex("^photo_"))
async def photo_callback(client, callback_query):
    user_id = callback_query.from_user.id
    action = callback_query.data.split("_")[1]
    
    if action == "fit_size":
        await callback_query.message.edit_text(
            "📐 **O'lchamni kiriting:**\n\nMasalan:\n`1080x1080` (Kvadrat)\n`1280x720` (YouTube)\n`1920x1080` (Full HD)\n\n"
            "Rasm kesilmaydi, hamma joyi ko'rinadi!", parse_mode=ParseMode.MARKDOWN)
        user_data[user_id]["action"] = "waiting_size"
    
    elif action == "add_text":
        await callback_query.message.edit_text("✍️ **Rasmga yoziladigan matnni kiriting:**")
        user_data[user_id]["action"] = "waiting_text"

@app.on_message(filters.text & filters.private)
async def handle_text_input(client, message):
    user_id = message.from_user.id
    if user_id not in user_data: return

    data = user_data[user_id]
    
    # O'lcham kiritilganda (masalan 1280x720)
    if data.get("action") == "waiting_size":
        try:
            w, h = map(int, message.text.lower().split('x'))
            status = await message.reply_text("⏳ Ishlanmoqda...")
            out = f"downloads/fit_{user_id}.jpg"
            
            if resize_to_fit(data["path"], out, (w, h)):
                await message.reply_document(out, caption=f"✅ O'lcham: {w}x{h} (Hamma joyi ko'rinadi)")
                await status.delete()
            else:
                await message.reply_text("❌ Xatolik yuz berdi.")
        except:
            await message.reply_text("❌ Noto'g'ri format. Masalan: `1280x720` deb yozing.")
        clean_user(user_id)

    # Matn kiritilganda
    elif data.get("action") == "waiting_text":
        status = await message.reply_text("⏳ Matn yozilmoqda...")
        out = f"downloads/text_{user_id}.jpg"
        if add_text_to_image(data["path"], out, message.text):
            await message.reply_photo(out, caption="✅ Matn qo'shildi!")
            await status.delete()
        else:
            await message.reply_text("❌ Xatolik.")
        clean_user(user_id)

# --- VIDEO HANDLERLAR (AVVALGI KODINGIZDAN) ---
@app.on_message(filters.video | filters.document)
async def handle_video(client, message):
    if message.document and not message.document.mime_type.startswith("video/"): return
    msg = await message.reply_text("📥 Video yuklanmoqda...")
    file_path = await message.download(file_name=f"downloads/{message.from_user.id}_{message.id}.mp4")
    user_data[message.from_user.id] = {"path": file_path, "type": "video", "orig_size": round(os.path.getsize(file_path)/(1024*1024),2)}
    
    buttons = InlineKeyboardMarkup([[InlineKeyboardButton("🗜 Siqish", callback_data="v_compress"), InlineKeyboardButton("✂️ Bo'lish", callback_data="v_split")]])
    await msg.edit_text("📹 Video yuklandi. Nima qilamiz?", reply_markup=buttons)

@app.on_callback_query(filters.regex("^v_"))
async def video_callback(client, callback_query):
    user_id = callback_query.from_user.id
    action = callback_query.data.split("_")[1]
    user_data[user_id]["action"] = action
    await callback_query.message.edit_text("Raqam kiriting (Masalan: 50 MB gacha siqish uchun 50 yoki 3 qismga bo'lish uchun 3)")

def clean_user(user_id):
    if user_id in user_data:
        if os.path.exists(user_data[user_id]["path"]): os.remove(user_data[user_id]["path"])
        del user_data[user_id]

if __name__ == "__main__":
    if not os.path.exists("downloads"): os.makedirs("downloads")
    print("🤖 Bot ishga tushdi!")
    app.run()
