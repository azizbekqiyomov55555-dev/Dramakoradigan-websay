import os
import asyncio
import subprocess
from pyrogram import Client, filters
from pyrogram.types import Message

# SIZNING API MA'LUMOTLARINGIZ
API_ID = 37366974
API_HASH = "08d09c7ed8b7cb414ed6a99c104f1bd6"
BOT_TOKEN = "8766647589:AAHmY6x59GgKA25K3e737-7jomufi9wRv2Y" # BotFather'dan olgan token

app = Client("video_compressor_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Foydalanuvchi yuklagan fayl yo'lini vaqtincha saqlash
user_files = {}

# Video davomiyligini aniqlash (Bitreyt hisoblash uchun)
def get_duration(file_path):
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", file_path]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        return float(result.stdout.strip())
    except:
        return 0

# Videoni siqish (FFmpeg orqali)
async def compress_video(input_path, output_path, target_mb):
    duration = get_duration(input_path)
    if duration == 0:
        return False
    
    # Maqsadli bitreytni hisoblash (MB dan kbps ga o'tkazish)
    # Formula: (Maqsadli_MB * 8192 / Davomiylik) - 128 (audio uchun)
    total_bitrate = (target_mb * 8192) / duration
    video_bitrate = int(total_bitrate - 128)
    
    if video_bitrate < 50: video_bitrate = 50 # Sifat juda yomon bo'lib ketmasligi uchun

    # FFmpeg buyrug'i: 240p ga o'tkazish va siqish
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vf", "scale=-2:240", # Haqiqiy 240p sifatga tushirish
        "-b:v", f"{video_bitrate}k",
        "-vcodec", "libx264",
        "-preset", "ultrafast", # Railway tezroq ishlashi uchun
        "-acodec", "aac",
        "-b:a", "128k",
        output_path
    ]
    
    process = await asyncio.create_subprocess_exec(*cmd)
    await process.wait()
    return True

@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text(
        "Salom! 🎬 Men katta hajmli videolarni (50MB, 100MB+) siquvchi botman.\n\n"
        "Menga video yuboring, men uni siz xohlagan hajmgacha kichraytirib beraman."
    )

@app.on_message(filters.video | filters.document)
async def handle_video(client, message):
    # Agar document bo'lsa, u video ekanligini tekshirish
    if message.document and not message.document.mime_type.startswith("video/"):
        return

    user_id = message.from_user.id
    msg = await message.reply_text("📥 Video qabul qilindi. Serverga yuklanmoqda... (Katta fayllar biroz vaqt oladi)")
    
    if not os.path.exists("downloads"):
        os.makedirs("downloads")

    file_path = f"downloads/{user_id}_{message.id}.mp4"
    
    # Pyrogram orqali cheklovsiz yuklab olish
    await message.download(file_name=file_path)
    
    user_files[user_id] = file_path
    await msg.edit_text(
        "✅ Video yuklandi!\n\nEndi bu video necha MB bo'lishini xohlaysiz? "
        "Faqat raqam yozing (masalan: 10 yoki 20)."
    )

@app.on_message(filters.text & filters.private)
async def set_size(client, message):
    user_id = message.from_user.id
    
    if user_id not in user_files:
        return

    if not message.text.isdigit():
        await message.reply_text("Iltimos, faqat raqam kiriting!")
        return

    target_mb = int(message.text)
    input_path = user_files[user_id]
    output_path = f"downloads/ready_{user_id}.mp4"
    
    status = await message.reply_text(f"⏳ Video {target_mb} MB formatga keltirilmoqda (240p)...")
    
    try:
        success = await compress_video(input_path, output_path, target_mb)
        
        if success and os.path.exists(output_path):
            await status.edit_text("📤 Tayyor! Telegramga yuborilmoqda...")
            
            # Sifatni va hajmni ko'rsatish
            real_size = round(os.path.getsize(output_path) / (1024 * 1024), 2)
            
            await client.send_video(
                chat_id=user_id,
                video=output_path,
                caption=f"🎬 Sifati: 240p\n📁 Hajmi: {real_size} MB\n✅ Siqish muvaffaqiyatli yakunlandi!"
            )
            await status.delete()
        else:
            await status.edit_text("❌ Xatolik: Videoni qayta ishlab bo'lmadi.")
            
    except Exception as e:
        await status.edit_text(f"❌ Xato yuz berdi: {e}")
    
    # Fayllarni o'chirish
    if os.path.exists(input_path): os.remove(input_path)
    if os.path.exists(output_path): os.remove(output_path)
    del user_files[user_id]

if __name__ == "__main__":
    app.run()
