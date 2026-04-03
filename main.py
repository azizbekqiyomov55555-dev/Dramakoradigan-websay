import os
import asyncio
import subprocess
from pyrogram import Client, filters, enums
from pyrogram.types import (
    InlineKeyboardMarkup, 
    InlineKeyboardButton, 
    ReplyKeyboardMarkup, 
    KeyboardButton
)
from static_ffmpeg import add_paths
from PIL import Image, ImageDraw, ImageFont

# FFmpeg yo'llarini sozlash
add_paths()

# --- SOZLAMALAR ---
API_ID = 37366974
API_HASH = "08d09c7ed8b7cb414ed6a99c104f1bd6"
BOT_TOKEN = "8630024708:AAGRE2oY2c74wR4mP3U5C298d3k3a7SUEVU"

app = Client("media_ultra_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Foydalanuvchi ma'lumotlari ombori
user_data = {}
MAX_MERGE_VIDEOS = 150 

# --- VIDEO FUNKSIYALARI ---

def get_duration(file_path):
    try:
        cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "default=noprint_wrappers=1:nokey=1", file_path]
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
    
    cmd = [
        "ffmpeg", "-y", "-i", input_path, "-vf", "scale=-2:720",
        "-c:v", "libx264", "-b:v", f"{video_bitrate}k", "-preset", "fast",
        "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", output_path
    ]
    process = await asyncio.create_subprocess_exec(*cmd)
    await process.wait()
    return os.path.exists(output_path)

async def split_video_part(input_path, start_time, duration_part, output_path):
    cmd = [
        "ffmpeg", "-y", "-ss", str(start_time), "-t", str(duration_part),
        "-i", input_path, "-c:v", "libx264", "-preset", "fast", 
        "-c:a", "aac", "-movflags", "+faststart", output_path
    ]
    process = await asyncio.create_subprocess_exec(*cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    await process.wait()
    return os.path.exists(output_path)

async def merge_videos_standardized(video_paths, output_path, status_msg):
    """100 tagacha videoni bir xil formatga keltirib birlashtiradi"""
    temp_dir = "downloads/temp_merge"
    os.makedirs(temp_dir, exist_ok=True)
    reencoded_files = []

    for i, vpath in enumerate(video_paths):
        await status_msg.edit_text(f"⏳ {len(video_paths)} tadan {i+1}-video tayyorlanmoqda...")
        temp_out = os.path.join(temp_dir, f"std_{i}.mp4")
        # Standartlashtirish: 720p, 16:9 formatga keltirish
        cmd = [
            "ffmpeg", "-y", "-i", vpath,
            "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2",
            "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", temp_out
        ]
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        await proc.wait()
        if os.path.exists(temp_out): reencoded_files.append(temp_out)

    if not reencoded_files: return False

    # Concat ro'yxati
    list_file = os.path.join(temp_dir, "list.txt")
    with open(list_file, "w") as f:
        for fp in reencoded_files: f.write(f"file '{os.path.abspath(fp)}'\n")

    await status_msg.edit_text("⚡️ Yakuniy birlashtirish ketmoqda...")
    cmd_merge = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file, "-c", "copy", output_path]
    proc_m = await asyncio.create_subprocess_exec(*cmd_merge, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    await proc_m.wait()

    # Tozalash
    for f in reencoded_files: 
        try: os.remove(f)
        except: pass
    return os.path.exists(output_path)

# --- RASM FUNKSIYALARI ---
def process_image(input_path, output_path, mode, extra=None):
    try:
        img = Image.open(input_path).convert("RGB")
        if mode == "fit":
            w, h = extra
            img.thumbnail((w, h), Image.Resampling.LANCZOS)
            new_img = Image.new("RGB", (w, h), (0, 0, 0))
            new_img.paste(img, ((w - img.size[0]) // 2, (h - img.size[1]) // 2))
            new_img.save(output_path, "JPEG", quality=95)
        elif mode == "text":
            draw = ImageDraw.Draw(img)
            font = ImageFont.load_default()
            draw.text((img.size[0]/2, img.size[1]-50), extra, fill="white", anchor="ms", stroke_width=2, stroke_fill="black")
            img.save(output_path, "JPEG", quality=95)
        return True
    except: return False

# --- KLAVIATURALAR ---
def main_kb():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🎬 Video yuborish"), KeyboardButton("🖼 Rasm yuborish")],
        [KeyboardButton("🔗 Videolarni birlashtirish")],
        [KeyboardButton("📊 Statistika"), KeyboardButton("🗑 Tozalash")]
    ], resize_keyboard=True)

# --- ASOSIY HANDLERLAR ---

@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text("🤖 **Media Pro Botga xush kelibsiz!**\n\nVideolarni birlashtirish, siqish va bo'lish uchun xizmat qilaman.", reply_markup=main_kb())

@app.on_message(filters.regex("🔗 Videolarni birlashtirish"))
async def merge_mode_on(client, message):
    uid = message.from_user.id
    clean_user_files(uid)
    user_data[uid] = {"mode": "merge", "videos": []}
    await message.reply_text(
        "🔗 **Birlashtirish rejimi yoqildi.**\n\nEndi kanalingizdan videolarni **uzatish (forward)** qiling.\n"
        "Hammasini yuborib bo'lgach, pastdagi **«✅ Birlashtir»** tugmasini bosing.",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("✅ Birlashtir"), KeyboardButton("🗑 Tozalash")]], resize_keyboard=True)
    )

@app.on_message(filters.video | filters.document)
async def handle_media(client, message):
    if message.document and not message.document.mime_type.startswith("video/"): return
    uid = message.from_user.id

    # 100 ta video yuborilganda:
    if uid in user_data and user_data[uid].get("mode") == "merge":
        videos = user_data[uid]["videos"]
        if len(videos) >= 100:
            return await message.reply_text("⚠️ Maksimal 100 ta video mumkin!")
        
        path = await message.download(f"downloads/m_{uid}_{len(videos)}.mp4")
        videos.append(path)
        await message.reply_text(f"📥 {len(videos)}-video qabul qilindi.")
        return

    # Oddiy rejim:
    msg = await message.reply_text("📥 Yuklanmoqda...")
    path = await message.download(f"downloads/v_{uid}.mp4")
    user_data[uid] = {"path": path}
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🗜 Siqish", callback_data="v_comp"), InlineKeyboardButton("✂️ Bo'lish", callback_data="v_split")]
    ])
    await msg.edit_text("✅ Video yuklandi. Nima qilamiz?", reply_markup=kb)

@app.on_message(filters.photo)
async def handle_photo(client, message):
    uid = message.from_user.id
    path = await message.download(f"downloads/p_{uid}.jpg")
    user_data[uid] = {"path": path}
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📐 O'lcham", callback_data="p_fit"), InlineKeyboardButton("✍️ Matn", callback_data="p_text")]
    ])
    await message.reply_text("🖼 Rasm qabul qilindi:", reply_markup=kb)

@app.on_callback_query()
async def cb_handler(client, q):
    uid = q.from_user.id
    data = q.data
    if data == "v_comp":
        user_data[uid]["action"] = "wait_v_size"
        await q.message.edit_text("🗜 Necha MB bo'lsin? (Faqat son)")
    elif data == "v_split":
        user_data[uid]["action"] = "wait_v_split"
        await q.message.edit_text("✂️ Nechta qismga bo'lamiz? (Masalan: 2)")
    elif data == "p_fit":
        user_data[uid]["action"] = "wait_p_size"
        await q.message.edit_text("📐 O'lcham kiriting: (Masalan: 1280x720)")
    elif data == "p_text":
        user_data[uid]["action"] = "wait_p_text"
        await q.message.edit_text("✍️ Rasmga nima deb yozamiz?")

@app.on_message(filters.text & filters.private)
async def text_handler(client, message):
    uid = message.from_user.id
    text = message.text

    if text == "✅ Birlashtir":
        if uid not in user_data or not user_data[uid].get("videos"): return
        v_list = user_data[uid]["videos"]
        st = await message.reply_text("🚀 Jarayon boshlandi...")
        out = f"downloads/merged_{uid}.mp4"
        if await merge_videos_standardized(v_list, out, st):
            await message.reply_chat_action(enums.ChatAction.UPLOAD_VIDEO)
            await message.reply_video(out, caption=f"✅ {len(v_list)} ta video birlashtirildi.")
        else:
            await message.reply_text("❌ Birlashtirishda xatolik.")
        clean_user_files(uid)
        return

    if text == "🗑 Tozalash":
        clean_user_files(uid)
        await message.reply_text("🗑 Tozalandi.", reply_markup=main_kb())
        return

    if uid not in user_data or "action" not in user_data[uid]: return
    action = user_data[uid]["action"]
    path = user_data[uid].get("path")

    if action == "wait_v_split":
        try:
            num = int(text)
            dur = get_duration(path)
            part_dur = dur / num
            st = await message.reply_text(f"⏳ {num} qismga bo'linmoqda...")
            for i in range(num):
                out_p = f"downloads/p_{i}_{uid}.mp4"
                if await split_video_part(path, i*part_dur, part_dur, out_p):
                    await client.send_video(uid, out_p, caption=f"📹 {i+1}-qism")
                    os.remove(out_p)
            await st.delete()
        except: await message.reply_text("Xato!")
        clean_user_files(uid)

    elif action == "wait_v_size":
        try:
            st = await message.reply_text("⏳ Siqilmoqda...")
            out = f"downloads/c_{uid}.mp4"
            if await compress_video(path, out, int(text)):
                await client.send_video(uid, out, caption=f"✅ {text}MB bo'ldi.")
            await st.delete()
        except: pass
        clean_user_files(uid)

    elif action == "wait_p_size":
        try:
            w, h = map(int, text.lower().split('x'))
            out = f"downloads/f_{uid}.jpg"
            if process_image(path, out, "fit", (w, h)):
                await client.send_document(uid, out)
        except: pass
        clean_user_files(uid)

def clean_user_files(uid):
    if uid in user_data:
        if "path" in user_data[uid] and os.path.exists(user_data[uid]["path"]):
            try: os.remove(user_data[uid]["path"])
            except: pass
        for v in user_data[uid].get("videos", []):
            try: os.remove(v)
            except: pass
        user_data[uid] = {}

if __name__ == "__main__":
    if not os.path.exists("downloads"): os.makedirs("downloads")
    print("🤖 Bot ishlamoqda...")
    app.run()
