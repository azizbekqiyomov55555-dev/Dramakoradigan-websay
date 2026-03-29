import os
import asyncio
import subprocess
from pyrogram import Client, filters
from static_ffmpeg import add_paths

add_paths()

API_ID = 37366974
API_HASH = "08d09c7ed8b7cb414ed6a99c104f1bd6"
BOT_TOKEN = "8766647589:AAHmY6x59GgKA25K3e737-7jomufi9wRv2Y"

app = Client("video_compressor", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Foydalanuvchi ma'lumotlarini saqlash uchun lug'at
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
    
    total_bitrate = (target_mb * 8192) / duration
    audio_bitrate = 64
    video_bitrate = int(total_bitrate - audio_bitrate)
    if video_bitrate < 150: video_bitrate = 150

    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vf", "scale=-2:480",
        "-c:v", "libx264",
        "-b:v", f"{video_bitrate}k",
        "-preset", "slow", 
        "-crf", "22",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", f"{audio_bitrate}k",
        "-movflags", "+faststart",
        output_path
    ]
    
    process = await asyncio.create_subprocess_exec(*cmd)
    await process.wait()
    return True

@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text("Salom! Video yuboring, uni sifatli qilib siqib beraman.")

@app.on_message(filters.video | filters.document)
async def handle_video(client, message):
    if message.document and not message.document.mime_type.startswith("video/"):
        return
    
    user_id = message.from_user.id
    msg = await message.reply_text("📥 Video yuklanmoqda...")
    
    # Asl hajmni aniqlash (MB da)
    if message.video:
        orig_size_bytes = message.video.file_size
    else:
        orig_size_bytes = message.document.file_size
    
    orig_size_mb = round(orig_size_bytes / (1024 * 1024), 2)

    if not os.path.exists("downloads"): os.makedirs("downloads")
    file_path = f"downloads/{user_id}_{message.id}.mp4"
    await message.download(file_name=file_path)
    
    # Ma'lumotlarni saqlaymiz
    user_data[user_id] = {
        "path": file_path,
        "orig_size": orig_size_mb
    }
    
    await msg.edit_text(f"✅ Video qabul qilindi (Asl hajm: {orig_size_mb} MB).\nNecha MB bo'lsin? (Faqat raqam yozing)")

@app.on_message(filters.text & filters.private)
async def set_size(client, message):
    user_id = message.from_user.id
    if user_id not in user_data: return

    if not message.text.isdigit():
        await message.reply_text("Iltimos, faqat raqam yozing!")
        return

    target_mb = int(message.text)
    input_path = user_data[user_id]["path"]
    orig_size = user_data[user_id]["orig_size"]
    output_path = f"downloads/out_{user_id}.mp4"
    
    status = await message.reply_text(f"⏳ Video {target_mb}MB ga moslab siqilmoqda...")
    
    try:
        success = await compress_video(input_path, output_path, target_mb)
        
        if success and os.path.exists(output_path):
            real_size = round(os.path.getsize(output_path) / (1024 * 1024), 2)
            
            # SIZ XOHLAGAN MATN:
            caption_text = (
                f"Siz yuborgan {orig_size} MB videoni {real_size} MB ga qisqartirdim! 😎\n\n"
                f"✨ Sifat: 480p (Tiniq)\n"
                f"✅ Tayyor!"
            )
            
            await client.send_video(
                chat_id=user_id,
                video=output_path,
                caption=caption_text,
                supports_streaming=True
            )
            await status.delete()
        else:
            await status.edit_text("❌ Xatolik yuz berdi.")
    except Exception as e:
        await status.edit_text(f"❌ Xato: {e}")
    
    # Fayllarni o'chirish
    if os.path.exists(input_path): os.remove(input_path)
    if os.path.exists(output_path): os.remove(output_path)
    del user_data[user_id]

if __name__ == "__main__":
    app.run()
