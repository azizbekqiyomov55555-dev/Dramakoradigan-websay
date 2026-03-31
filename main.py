import os
import asyncio
import subprocess
from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardMarkup, 
    InlineKeyboardButton, 
    ReplyKeyboardMarkup, 
    KeyboardButton
)
from pyrogram.enums import ParseMode
from static_ffmpeg import add_paths
from PIL import Image, ImageDraw, ImageFont

add_paths()

# --- SOZLAMALAR ---
API_ID = 37366974
API_HASH = "08d09c7ed8b7cb414ed6a99c104f1bd6"
BOT_TOKEN = "8630024708:AAGRE2oY2c74wR4mP3U5C298d3k3a7SUEVU"

app = Client("video_processor", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

user_data = {}

# --- YORDAMCHI FUNKSIYALAR ---

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

# --- RASM FUNKSIYALARI ---

def compress_image(input_path, output_path, quality=85):
    try:
        img = Image.open(input_path).convert("RGB")
        img.save(output_path, 'JPEG', quality=quality, optimize=True)
        return True
    except: return False

def crop_image_square(input_path, output_path):
    try:
        img = Image.open(input_path).convert("RGB")
        width, height = img.size
        min_side = min(width, height)
        left = (width - min_side) // 2
        top = (height - min_side) // 2
        img.crop((left, top, left + min_side, top + min_side)).save(output_path, 'JPEG', quality=95)
        return True
    except: return False

def resize_image_fit(input_path, output_path, width, height):
    """Rasmni kesmasdan, hamma joyini ko'rsatib fonga joylash (Fit-mode)"""
    try:
        img = Image.open(input_path).convert("RGB")
        img.thumbnail((width, height), Image.Resampling.LANCZOS)
        new_img = Image.new("RGB", (width, height), (0, 0, 0)) # Qora fon
        offset = ((width - img.size[0]) // 2, (height - img.size[1]) // 2)
        new_img.paste(img, offset)
        new_img.save(output_path, "JPEG", quality=95)
        return True
    except: return False

def add_text_to_image(input_path, output_path, text):
    """Rasmga matn yozish (Montaj)"""
    try:
        img = Image.open(input_path).convert("RGB")
        draw = ImageDraw.Draw(img)
        font = ImageFont.load_default() # Railway uchun standart
        w, h = img.size
        draw.text((w/2, h-50), text, fill="white", font=font, anchor="ms", stroke_width=2, stroke_fill="black")
        img.save(output_path, "JPEG", quality=95)
        return True
    except: return False

# --- ASOSIY MENYU ---

def get_main_keyboard():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("🎬 Video yuborish"), KeyboardButton("🖼 Rasm yuborish")],
         [KeyboardButton("📊 Statistika"), KeyboardButton("❓ Yordam")]],
        resize_keyboard=True
    )

@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text("👋 **Assalomu alaykum!**\nMedia fayllarni qayta ishlash botiga xush kelibsiz!", reply_markup=get_main_keyboard())

# --- STATISTIKA VA YORDAM ---

@app.on_message(filters.regex("📊 Statistika"))
async def stats_button(client, message):
    total_users = len(user_data)
    await message.reply_text(f"📊 **Statistika:**\n\n👥 Faol foydalanuvchilar (seansda): {total_users}\n🤖 Bot holati: Ishlamoqda ✅")

@app.on_message(filters.regex("❓ Yordam"))
async def help_button(client, message):
    await message.reply_text("❓ **Yordam:**\n\n1. Video yoki rasm yuboring.\n2. Tugmalardan birini tanlang.\n3. Kerakli o'lcham yoki hajmni yozing.")

# --- RASM ISHLASH ---

@app.on_message(filters.photo)
async def handle_photo(client, message):
    msg = await message.reply_text("📥 Rasm yuklanmoqda...")
    file_path = await message.download(file_name=f"downloads/img_{message.from_user.id}.jpg")
    user_data[message.from_user.id] = {"path": file_path, "type": "photo", "orig_size": round(os.path.getsize(file_path)/(1024*1024),2)}
    
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📐 O'lcham (Kesmasdan Fit)", callback_data="p_fit"), InlineKeyboardButton("✂️ Kvadrat qirqish", callback_data="p_crop")],
        [InlineKeyboardButton("✍️ Matn yozish (Montaj)", callback_data="p_text"), InlineKeyboardButton("🗜 Siqish", callback_data="p_comp")]
    ])
    await msg.edit_text("✅ Rasm yuklandi. Amallardan birini tanlang:", reply_markup=kb)

# --- VIDEO ISHLASH ---

@app.on_message(filters.video | filters.document)
async def handle_video(client, message):
    if message.document and not message.document.mime_type.startswith("video/"): return
    msg = await message.reply_text("📥 Video yuklanmoqda...")
    file_path = await message.download(file_name=f"downloads/vid_{message.from_user.id}.mp4")
    user_data[message.from_user.id] = {"path": file_path, "type": "video", "orig_size": round(os.path.getsize(file_path)/(1024*1024),2)}
    
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🗜 Siqish", callback_data="v_comp"), InlineKeyboardButton("✂️ Bo'lish", callback_data="v_split")],
        [InlineKeyboardButton("⚡️ Siqish + Bo'lish", callback_data="v_both")]
    ])
    await msg.edit_text("✅ Video yuklandi. Tanlang:", reply_markup=kb)

# --- CALLBACKS ---

@app.on_callback_query()
async def callback_handler(client, q):
    uid = q.from_user.id
    if uid not in user_data:
        await q.answer("Ma'lumot topilmadi, qaytadan yuboring.", show_alert=True)
        return

    data = q.data
    if data == "p_fit":
        await q.message.edit_text("📐 **O'lchamni kiriting** (masalan: `1280x720` yoki `1080x1080`):")
        user_data[uid]["action"] = "wait_size"
    elif data == "p_text":
        await q.message.edit_text("✍️ **Rasmga yoziladigan matnni kiriting:**")
        user_data[uid]["action"] = "wait_text"
    elif data == "p_crop":
        status = await q.message.edit_text("⏳ Qirqilmoqda...")
        out = f"downloads/crop_{uid}.jpg"
        if crop_image_square(user_data[uid]["path"], out):
            await client.send_photo(uid, out, caption="✅ Kvadrat qilib qirqildi!")
            await status.delete()
        clean_user(uid)
    elif data == "v_comp":
        await q.message.edit_text("🗜 **Necha MB bo'lsin?** (Faqat raqam yozing):")
        user_data[uid]["action"] = "wait_v_size"
    elif data == "v_split":
        await q.message.edit_text("✂️ **Nechta qismga bo'linsin?** (Faqat raqam):")
        user_data[uid]["action"] = "wait_v_split"

# --- MATN KIRITISHNI BOSHQARISH ---

@app.on_message(filters.text & filters.private & ~filters.regex("^(🎬|🖼|📊|❓)"))
async def text_input(client, message):
    uid = message.from_user.id
    if uid not in user_data or "action" not in user_data[uid]: return
    
    action = user_data[uid]["action"]
    path = user_data[uid]["path"]

    if action == "wait_size":
        try:
            w, h = map(int, message.text.lower().split('x'))
            st = await message.reply_text("⏳ Ishlanmoqda...")
            out = f"downloads/fit_{uid}.jpg"
            if resize_image_fit(path, out, w, h):
                await message.reply_document(out, caption=f"✅ O'lcham: {w}x{h} (Hamma joyi ko'rinadi)")
                await st.delete()
            clean_user(uid)
        except: await message.reply_text("❌ Xato! Format: `1280x720` deb yozing.")

    elif action == "wait_text":
        st = await message.reply_text("⏳ Montaj qilinmoqda...")
        out = f"downloads/montaj_{uid}.jpg"
        if add_text_to_image(path, out, message.text):
            await message.reply_photo(out, caption=f"✅ Matn qo'shildi: {message.text}")
            await st.delete()
        clean_user(uid)

    elif action == "wait_v_size":
        try:
            target = int(message.text)
            st = await message.reply_text(f"⏳ {target}MB ga siqilmoqda...")
            out = f"downloads/res_{uid}.mp4"
            if await compress_video(path, out, target):
                await message.reply_video(out, caption=f"✅ Tayyor! Hajmi: {target}MB")
                await st.delete()
            clean_user(uid)
        except: await message.reply_text("❌ Faqat son kiriting!")

def clean_user(uid):
    if uid in user_data:
        if os.path.exists(user_data[uid]["path"]): os.remove(user_data[uid]["path"])
        del user_data[uid]

if __name__ == "__main__":
    if not os.path.exists("downloads"): os.makedirs("downloads")
    print("🤖 Bot ishga tushdi!")
    app.run()
