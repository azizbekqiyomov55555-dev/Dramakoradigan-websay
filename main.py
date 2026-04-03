import os
import asyncio
import subprocess
import shutil
import time
from pyrogram import Client, filters, enums
from pyrogram.types import (
    InlineKeyboardMarkup, 
    InlineKeyboardButton, 
    ReplyKeyboardMarkup, 
    KeyboardButton
)
from static_ffmpeg import add_paths
from PIL import Image

# FFmpeg sozlash
add_paths()

# --- SOZLAMALAR ---
API_ID = 37366974
API_HASH = "08d09c7ed8b7cb414ed6a99c104f1bd6"
BOT_TOKEN = "8630024708:AAGRE2oY2c74wR4mP3U5C298d3k3a7SUEVU"

app = Client("media_ultra_pro", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

user_data = {}

# --- YORDAMCHI FUNKSIYALAR ---

def get_video_info(file_path):
    """Videoning eni, bo'yi va davomiyligini aniqlash"""
    try:
        cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", 
               "stream=width,height,duration", "-of", "default=noprint_wrappers=1:nokey=1", file_path]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, text=True).stdout.splitlines()
        return int(res[0]), int(res[1]), float(res[2])
    except: return 1280, 720, 0

async def progress_bar(current, total, msg, type_msg):
    try:
        percent = current * 100 / total
        if int(percent) % 15 == 0: # Telegram limitidan qochish
            await msg.edit_text(f"{type_msg}\n📊 Jarayon: {percent:.1f}%")
    except: pass

def clean_user_files(uid):
    user_dir = f"downloads/{uid}"
    if os.path.exists(user_dir): shutil.rmtree(user_dir)
    user_data[uid] = {"mode": "none", "videos": [], "pending_messages": [], "is_processing": False}

# --- ASOSIY FUNKSIYALAR ---

async def merge_videos_as_is(uid, message):
    """Videolarni o'z o'lchamida birlashtirish"""
    data = user_data[uid]
    videos = data["videos"]
    if not videos: return

    status = await message.reply_text("⚡️ **Birlashtirish boshlandi...**")
    
    # Birinchi videoning o'lchamini asos qilib olamiz (FFmpeg talabi)
    width, height, _ = get_video_info(videos[0])
    
    user_dir = f"downloads/{uid}"
    processed_list = []
    
    for i, v in enumerate(videos):
        out = f"{user_dir}/ready_{i}.mp4"
        await status.edit_text(f"🛠 {i+1}-videoga ishlov berilmoqda...")
        # Har xil o'lchamdagi videolarni birinchi video o'lchamiga moslash (buzilmasdan)
        cmd = [
            "ffmpeg", "-y", "-i", v,
            "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2",
            "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", out
        ]
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        await proc.wait()
        processed_list.append(out)

    # Concat
    list_path = f"{user_dir}/list.txt"
    with open(list_path, "w") as f:
        for p in processed_list: f.write(f"file '{os.path.abspath(p)}'\n")
    
    final_out = f"downloads/final_{uid}.mp4"
    cmd_merge = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_path, "-c", "copy", final_out]
    proc = await asyncio.create_subprocess_exec(*cmd_merge, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    await proc.wait()

    if os.path.exists(final_out):
        await status.edit_text("✅ Tayyor! Yuklanmoqda...")
        await message.reply_video(final_out, caption="✅ Videolar birlashtirildi.")
    else:
        await message.reply_text("❌ Xatolik yuz berdi.")
    clean_user_files(uid)

# --- KLAVIATURALAR ---
def main_kb():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🔗 Videolarni birlashtirish")],
        [KeyboardButton("📊 Statistika"), KeyboardButton("🗑 Tozalash")]
    ], resize_keyboard=True)

# --- HANDLERLAR ---

@app.on_message(filters.command("start"))
async def start(client, message):
    clean_user_files(message.from_user.id)
    await message.reply_text("🤖 **Media Pro Bot ishga tushdi!**\n\n- Videolarni birlashtirish uchun pastdagi tugmani bosing.\n- Video yuborsangiz uni bo'lish yoki siqish mumkin.", reply_markup=main_kb())

@app.on_message(filters.regex("🔗 Videolarni birlashtirish"))
async def merge_mode(client, message):
    uid = message.from_user.id
    user_data[uid] = {"mode": "merge", "videos": [], "pending_messages": [], "collecting": False}
    await message.reply_text("📥 **Videolarni yuboring (Forward qiling).**\n\nHamma yuborganingizdan so'ng men ularni sanab yuklashni boshlayman.", 
                             reply_markup=ReplyKeyboardMarkup([[KeyboardButton("✅ Birlashtirish"), KeyboardButton("🗑 Tozalash")]], resize_keyboard=True))

@app.on_message((filters.video | filters.document) & filters.private)
async def handle_media(client, message):
    uid = message.from_user.id
    if message.document and not message.document.mime_type.startswith("video/"): return

    # --- Birlashtirish Rejimi ---
    if uid in user_data and user_data[uid].get("mode") == "merge":
        user_data[uid]["pending_messages"].append(message)
        
        if not user_data[uid]["collecting"]:
            user_data[uid]["collecting"] = True
            await asyncio.sleep(5) # 5 soniya kutish (hamma videolar kelishi uchun)
            
            total = len(user_data[uid]["pending_messages"])
            st_msg = await message.reply_text(f"✅ **{total} ta video qabul qilindi.**\nNavbat bilan yuklash boshlanmoqda...")
            
            user_dir = f"downloads/{uid}"
            os.makedirs(user_dir, exist_ok=True)
            
            for i, msg in enumerate(user_data[uid]["pending_messages"]):
                v_path = f"{user_dir}/v_{i}.mp4"
                await st_msg.edit_text(f"📥 **Yuklanmoqda:** {i+1}/{total}-video...")
                path = await msg.download(file_name=v_path)
                user_data[uid]["videos"].append(path)
            
            await st_msg.edit_text(f"✅ Barcha {total} ta video yuklandi.\nBirlashtirish uchun tugmani bosing.")
            user_data[uid]["collecting"] = False
        return

    # --- Oddiy Rejim (Siqish/Bo'lish) ---
    path = await message.download(f"downloads/v_{uid}.mp4")
    user_data[uid] = {"path": path}
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🗜 Siqish", callback_data="v_comp"), InlineKeyboardButton("✂️ Bo'lish", callback_data="v_split")]
    ])
    await message.reply_text("🎬 Video yuklandi. Nima qilamiz?", reply_markup=kb)

@app.on_message(filters.photo & filters.private)
async def handle_photo(client, message):
    uid = message.from_user.id
    path = await message.download(f"downloads/p_{uid}.jpg")
    user_data[uid] = {"path": path, "action": "wait_p_size"}
    await message.reply_text("📐 **Rasm o'lchamini kiriting.**\nMasalan: `1280x720` (Eni x Bo'yi)")

@app.on_callback_query()
async def callbacks(client, q):
    uid = q.from_user.id
    if q.data == "v_comp":
        user_data[uid]["action"] = "wait_v_size"
        await q.message.edit_text("🗜 Necha MB bo'lsin? (Faqat son yuboring)")
    elif q.data == "v_split":
        user_data[uid]["action"] = "wait_v_split"
        await q.message.edit_text("✂️ Nechta qismga bo'lamiz? (Masalan: 3)")

@app.on_message(filters.text & filters.private)
async def text_logic(client, message):
    uid = message.from_user.id
    text = message.text

    if text == "✅ Birlashtirish":
        if uid in user_data and user_data[uid].get("videos"):
            await merge_videos_as_is(uid, message)
        return

    if text == "🗑 Tozalash":
        clean_user_files(uid)
        await message.reply_text("🗑 Tozalandi.", reply_markup=main_kb())
        return

    if uid not in user_data or "action" not in user_data[uid]: return
    action = user_data[uid]["action"]
    path = user_data[uid].get("path")

    # ✂️ VIDEO BO'LISH
    if action == "wait_v_split":
        try:
            num = int(text)
            _, _, duration = get_video_info(path)
            part_dur = duration / num
            st = await message.reply_text(f"⏳ {num} qismga bo'linmoqda...")
            for i in range(num):
                out = f"downloads/part_{i}_{uid}.mp4"
                cmd = ["ffmpeg", "-y", "-ss", str(i*part_dur), "-t", str(part_dur), "-i", path, "-c", "copy", out]
                await (await asyncio.create_subprocess_exec(*cmd)).wait()
                await message.reply_video(out, caption=f"📹 {i+1}-qism")
                os.remove(out)
            await st.delete()
        except: await message.reply_text("Xato!")
        clean_user_files(uid)

    # 🗜 VIDEO SIQISH
    elif action == "wait_v_size":
        try:
            target_mb = int(text)
            st = await message.reply_text("⏳ Siqilmoqda (bu vaqt oladi)...")
            out = f"downloads/comp_{uid}.mp4"
            _, _, dur = get_video_info(path)
            bitrate = (target_mb * 8192) / dur
            cmd = ["ffmpeg", "-y", "-i", path, "-b:v", f"{bitrate}k", "-c:a", "aac", "-b:a", "128k", out]
            await (await asyncio.create_subprocess_exec(*cmd)).wait()
            await message.reply_video(out, caption=f"✅ {target_mb}MB qilib siqildi.")
            await st.delete()
        except: await message.reply_text("Xato!")
        clean_user_files(uid)

    # 📐 RASM O'LCHAM
    elif action == "wait_p_size":
        try:
            w, h = map(int, text.lower().split('x'))
            img = Image.open(path)
            img = img.resize((w, h), Image.Resampling.LANCZOS)
            out = f"downloads/res_{uid}.jpg"
            img.save(out)
            await message.reply_document(out, caption=f"📐 {w}x{h} o'lchamida.")
        except: await message.reply_text("Xato! Format: 1280x720")
        clean_user_files(uid)

if __name__ == "__main__":
    if not os.path.exists("downloads"): os.makedirs("downloads")
    print("🤖 Bot ishlamoqda...")
    app.run()
