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

add_paths()

# --- SOZLAMALAR ---
API_ID = 37366974
API_HASH = "08d09c7ed8b7cb414ed6a99c104f1bd6"
BOT_TOKEN = "8630024708:AAGRE2oY2c74wR4mP3U5C298d3k3a7SUEVU"

app = Client("bulk_merge_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Foydalanuvchi ma'lumotlarini saqlash: {user_id: {"videos": [yo'llar], "is_merging": bool}}
user_storage = {}

# --- FUNKSIYALAR ---

async def merge_videos_ffmpeg(video_list, output_path):
    """FFmpeg orqali videolarni bir xil formatga keltirib birlashtiradi"""
    temp_dir = "downloads/temp_parts"
    os.makedirs(temp_dir, exist_ok=True)
    
    reencoded_list = []
    
    # 1. Har bir videoni bir xil o'lcham va formatga keltirish (bir xil bo'lmasa xato beradi)
    for i, file_path in enumerate(video_list):
        out_part = os.path.join(temp_dir, f"part_{i}.mp4")
        # Formatni standartlashtirish: 720p, libx264, aac
        cmd = [
            "ffmpeg", "-y", "-i", file_path,
            "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
            "-c:a", "aac", "-ar", "44100",
            out_part
        ]
        process = await asyncio.create_subprocess_exec(*cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        await process.wait()
        if os.path.exists(out_part):
            reencoded_list.append(out_part)

    if not reencoded_list:
        return False

    # 2. Concat faylini yaratish
    list_file = "downloads/concat_list.txt"
    with open(list_file, "w") as f:
        for p in reencoded_list:
            f.write(f"file '{os.path.abspath(p)}'\n")

    # 3. Birlashtirish
    cmd_merge = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", list_file, "-c", "copy", output_path
    ]
    process_merge = await asyncio.create_subprocess_exec(*cmd_merge, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    await process_merge.wait()

    # 4. Vaqtinchalik fayllarni o'chirish
    for p in reencoded_list:
        try: os.remove(p)
        except: pass
    try: os.remove(list_file)
    except: pass
    
    return os.path.exists(output_path)

# --- BOT BUYRUQLARI ---

@app.on_message(filters.command("start"))
async def start(client, message):
    uid = message.from_user.id
    user_storage[uid] = {"videos": [], "status": "idle"}
    
    btn = ReplyKeyboardMarkup([
        [KeyboardButton("🔗 Birlashtirish rejimini yoqish")],
        [KeyboardButton("🗑 Tozalash / Bekor qilish")]
    ], resize_keyboard=True)
    
    await message.reply_text(
        "👋 **Assalomu alaykum!**\n\n100 tagacha videoni birlashtirish uchun pastdagi tugmani bosing va videolarni (forward qilib) yuboring.",
        reply_markup=btn
    )

@app.on_message(filters.regex("🔗 Birlashtirish rejimini yoqish"))
async def enable_merge(client, message):
    uid = message.from_user.id
    user_storage[uid] = {"videos": [], "status": "collecting"}
    await message.reply_text(
        "✅ **Rejim yoqildi.**\nEndi kanalingizdan videolarni (100 tagacha) uzatishingiz (forward) mumkin.\n\n"
        "Videolar kelib tushganda men ularni sanab boraman.",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("✅ Hammasini yubordim, Birlashtir!")]], resize_keyboard=True)
    )

@app.on_message(filters.video | filters.document)
async def collect_videos(client, message):
    uid = message.from_user.id
    
    if uid not in user_storage or user_storage[uid].get("status") != "collecting":
        return # Agar rejim yoqilmagan bo'lsa e'tiborsiz qoldiramiz

    if message.document and not message.document.mime_type.startswith("video/"):
        return

    # Video sonini cheklash
    if len(user_storage[uid]["videos"]) >= 100:
        return await message.reply_text("⚠️ Maksimal 100 ta video yuklash mumkin!")

    # Yuklab olish (Telegramdan kelayotgan har bir xabar uchun)
    count = len(user_storage[uid]["videos"]) + 1
    msg = await message.reply_text(f"📥 {count}-video qabul qilinmoqda...")
    
    file_path = await message.download(f"downloads/v_{uid}_{count}.mp4")
    user_storage[uid]["videos"].append(file_path)
    
    await msg.edit_text(f"✅ {count}-video yuklandi. Yana yuboring yoki birlashtirishni bosing.")

@app.on_message(filters.regex("✅ Hammasini yubordim, Birlashtir!"))
async def process_merge(client, message):
    uid = message.from_user.id
    
    if uid not in user_storage or not user_storage[uid]["videos"]:
        return await message.reply_text("❌ Hech qanday video yuborilmadi!")

    video_list = user_storage[uid]["videos"]
    await message.reply_text(f"⏳ **{len(video_list)} ta video birlashtirilmoqda...**\n"
                             f"Bu jarayon videolarning hajmi va soniga qarab bir necha daqiqa olishi mumkin. Iltimos kuting.",
                             reply_markup=ReplyKeyboardMarkup([[KeyboardButton("🔗 Birlashtirish rejimini yoqish")]], resize_keyboard=True))

    output_file = f"downloads/final_merge_{uid}.mp4"
    
    # Birlashtirish funksiyasini chaqiramiz
    success = await merge_videos_ffmpeg(video_list, output_file)
    
    if success:
        await message.reply_chat_action(enums.ChatAction.UPLOAD_VIDEO)
        await message.reply_video(
            video=output_file,
            caption=f"✅ Barcha {len(video_list)} ta video muvaffaqiyatli birlashtirildi!",
            supports_streaming=True
        )
    else:
        await message.reply_text("❌ Xatolik yuz berdi. Videolar formatida muammo bo'lishi mumkin.")

    # Fayllarni tozalash
    for path in video_list:
        try: os.remove(path)
        except: pass
    if os.path.exists(output_file):
        os.remove(output_file)
    
    user_storage[uid] = {"videos": [], "status": "idle"}

@app.on_message(filters.regex("Tozalash / Bekor qilish"))
async def clear_data(client, message):
    uid = message.from_user.id
    if uid in user_storage:
        for path in user_storage[uid].get("videos", []):
            try: os.remove(path)
            except: pass
        user_storage[uid] = {"videos": [], "status": "idle"}
    await message.reply_text("🗑 Barcha yuklangan videolar o'chirildi va bekor qilindi.", reply_markup=get_main_keyboard())

# --- QO'SHIMCHA ---
def get_main_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🔗 Birlashtirish rejimini yoqish")],
        [KeyboardButton("📊 Statistika")]
    ], resize_keyboard=True)

if __name__ == "__main__":
    if not os.path.exists("downloads"):
        os.makedirs("downloads")
    print("🤖 Bot ishga tushdi! Kanaldan 100 ta vdyoni uzatishingiz mumkin.")
    app.run()
