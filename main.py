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

# FFmpeg yo'llarini sozlash
add_paths()

# --- SOZLAMALAR ---
API_ID = 37366974
API_HASH = "08d09c7ed8b7cb414ed6a99c104f1bd6"
BOT_TOKEN = "8630024708:AAGRE2oY2c74wR4mP3U5C298d3k3a7SUEVU"

app = Client("media_ultra_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Foydalanuvchi ma'lumotlari ombori
user_data = {}

# --- YORDAMCHI FUNKSIYALAR ---

def clean_user_files(uid):
    user_dir = f"downloads/{uid}"
    if os.path.exists(user_dir):
        shutil.rmtree(user_dir)
    if uid in user_data:
        user_data[uid]["videos"] = []
        user_data[uid]["status_msg_id"] = None
        user_data[uid]["is_processing"] = False

async def progress_bar(current, total, msg, type_msg):
    try:
        percent = current * 100 / total
        # Har 5 foizda yangilash (Telegram limitiga tushmaslik uchun)
        if int(percent) % 10 == 0:
            await msg.edit_text(f"{type_msg}\n📊 Jarayon: {percent:.1f}%")
    except: pass

# --- VIDEO ISHLOV BERISH ---

async def process_all_videos(uid, message):
    """Navbatdagi barcha videolarni yuklash va qayta ishlash"""
    data = user_data[uid]
    if not data["pending_messages"]:
        return

    data["is_processing"] = True
    total_to_process = len(data["pending_messages"])
    
    status_msg = await message.reply_text(f"🚀 **Jarayon boshlandi!**\nUmumiy: {total_to_process} ta video aniqlandi.\n\nTayyorlanmoqda...")
    data["status_msg_id"] = status_msg.id

    user_dir = f"downloads/{uid}"
    os.makedirs(user_dir, exist_ok=True)
    
    processed_paths = []
    
    # Navbatma-navbat yuklash va standartlashtirish
    for index, msg in enumerate(data["pending_messages"]):
        current_num = index + 1
        video_path = f"{user_dir}/raw_{current_num}.mp4"
        std_path = f"{user_dir}/std_{current_num}.mp4"

        # 1. Yuklab olish
        await status_msg.edit_text(f"📥 **Yuklanmoqda:** {current_num}/{total_to_process}-video...")
        try:
            await msg.download(
                file_name=video_path,
                progress=progress_bar,
                progress_args=(status_msg, f"📥 Yuklanmoqda: {current_num}/{total_to_process}")
            )
        except Exception as e:
            await message.reply_text(f"❌ {current_num}-videoni yuklashda xato: {e}")
            continue

        # 2. Standartlashtirish (Encoding)
        await status_msg.edit_text(f"🛠 **Ishlov berilmoqda:** {current_num}/{total_to_process}-video...\n(Format sozlanmoqda...)")
        
        cmd = [
            "ffmpeg", "-y", "-i", video_path,
            "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2",
            "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", std_path
        ]
        
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        await proc.wait()
        
        if os.path.exists(std_path):
            processed_paths.append(std_path)
            user_data[uid]["videos"].append(std_path)
            # Xom videoni o'chirish (joy tejash uchun)
            if os.path.exists(video_path): os.remove(video_path)

    await status_msg.edit_text(f"✅ Barcha {len(processed_paths)} ta video tayyorlandi.\nEndi birlashtirish tugmasini bosing.")
    data["pending_messages"] = [] # Navbatni bo'shatish
    data["is_processing"] = False

async def merge_final(uid, message):
    """Barcha tayyorlangan videolarni bitta faylga birlashtirish"""
    videos = user_data[uid].get("videos", [])
    if not videos:
        await message.reply_text("❌ Hech qanday video tayyor emas!")
        return

    status_msg = await message.reply_text("⚡️ **Yakuniy birlashtirish ketmoqda...**")
    
    user_dir = f"downloads/{uid}"
    list_file = f"{user_dir}/list.txt"
    
    with open(list_file, "w") as f:
        for fp in videos:
            f.write(f"file '{os.path.abspath(fp)}'\n")

    output_file = f"downloads/final_{uid}_{int(time.time())}.mp4"
    
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file, "-c", "copy", output_file]
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    await proc.wait()

    if os.path.exists(output_file):
        await status_msg.edit_text("✅ **Birlashtirildi! Telegramga yuklanmoqda...**")
        await message.reply_video(
            video=output_file,
            caption=f"🎬 **Tayyor!**\nBirlashtirilgan videolar soni: {len(videos)} ta",
            progress=progress_bar,
            progress_args=(status_msg, "📤 Telegramga yuborilmoqda...")
        )
    else:
        await message.reply_text("❌ Birlashtirishda xatolik yuz berdi.")
    
    clean_user_files(uid)

# --- KLAVIATURALAR ---
def main_kb():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🔗 Videolarni birlashtirish")],
        [KeyboardButton("🗑 Tozalash")]
    ], resize_keyboard=True)

def merge_control_kb():
    return ReplyKeyboardMarkup([
        [KeyboardButton("✅ Yakuniy Birlashtirish")],
        [KeyboardButton("🗑 Tozalash")]
    ], resize_keyboard=True)

# --- HANDLERLAR ---

@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text("👋 Media Ultra Botga xush kelibsiz!", reply_markup=main_kb())

@app.on_message(filters.regex("🔗 Videolarni birlashtirish"))
async def merge_mode_on(client, message):
    uid = message.from_user.id
    user_data[uid] = {
        "mode": "merge", 
        "videos": [], 
        "pending_messages": [], 
        "is_processing": False,
        "collecting": False
    }
    await message.reply_text(
        "🔗 **Birlashtirish rejimi yondi.**\n\nVideolarni botga yuboring (Forward qiling). Hamma yuborganingizdan so'ng men ularni navbatma-navbat yuklab olaman.",
        reply_markup=merge_control_kb()
    )

@app.on_message((filters.video | filters.document) & filters.private)
async def handle_videos(client, message):
    uid = message.from_user.id
    if uid not in user_data or user_data[uid].get("mode") != "merge":
        return

    # Hujjat bo'lsa video ekanligini tekshirish
    if message.document and not message.document.mime_type.startswith("video/"):
        return

    # Videoni navbatga qo'shish
    user_data[uid]["pending_messages"].append(message)

    # Agar hali yig'ish jarayoni boshlanmagan bo'lsa (Debounce timer)
    if not user_data[uid]["collecting"]:
        user_data[uid]["collecting"] = True
        wait_msg = await message.reply_text("⏳ Videolar qabul qilinmoqda, kuting...")
        
        # 3 soniya kutamiz (foydalanuvchi hamma videolarni yuborib bo'lishi uchun)
        await asyncio.sleep(4) 
        
        count = len(user_data[uid]["pending_messages"])
        await wait_msg.edit_text(f"✅ {count} ta video qabul qilindi.\nNavbat bilan yuklash boshlanmoqda...")
        
        user_data[uid]["collecting"] = False
        # Yuklash va ishlov berishni boshlash
        await process_all_videos(uid, message)

@app.on_message(filters.regex("✅ Yakuniy Birlashtirish"))
async def start_final_merge(client, message):
    uid = message.from_user.id
    if uid in user_data and user_data[uid]["videos"]:
        if user_data[uid]["is_processing"]:
            await message.reply_text("⚠️ Hali videolar yuklanib tugamadi, kuting...")
        else:
            await merge_final(uid, message)
    else:
        await message.reply_text("❌ Avval videolarni yuboring!")

@app.on_message(filters.regex("🗑 Tozalash"))
async def clear_all(client, message):
    uid = message.from_user.id
    clean_user_files(uid)
    await message.reply_text("🗑 Tozalandi.", reply_markup=main_kb())

if __name__ == "__main__":
    if not os.path.exists("downloads"): os.makedirs("downloads")
    print("🤖 Bot ishga tushdi...")
    app.run()
