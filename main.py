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
    
    # Aniqroq hisob-kitob (Maqsadli hajmdan 2% zaxira olamiz xatolik uchun)
    target_size_bits = (target_mb * 1024 * 1024 * 8) * 0.98 
    audio_bitrate = 64 * 1024 # 64kbps
    video_bitrate = int((target_size_bits / duration) - audio_bitrate)
    
    if video_bitrate < 150000: video_bitrate = 150000

    video_bitrate_k = int(video_bitrate / 1000)

    # FFmpeg buyrug'i: Sifatni saqlash va hajmga tushirish uchun
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vf", "scale='min(iw,1280)':-2", # Agar video katta bo'lsa 720p ga tushiradi (sifat uchun yaxshi)
        "-c:v", "libx264",
        "-b:v", f"{video_bitrate_k}k",
        "-minrate", f"{video_bitrate_k}k", # Minimal bitreytni qotiramiz
        "-maxrate", f"{video_bitrate_k}k", # Maksimalni ham (hajm aniq chiqishi uchun)
        "-bufsize", f"{video_bitrate_k * 2}k",
        "-preset", "slow",               # Sekin lekin sifatli siqish
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "64k",
        "-movflags", "+faststart",
        output_path
    ]
    
    process = await asyncio.create_subprocess_exec(*cmd)
    await process.wait()
    return True

@app.on_message(filters.video | filters.document)
async def handle_video(client, message):
    if message.document and not message.document.mime_type.startswith("video/"):
        return
    
    user_id = message.from_user.id
    msg = await message.reply_text("📥 Video yuklanmoqda...")
    
    if message.video:
        orig_size_mb = round(message.video.file_size / (1024 * 1024), 2)
    else:
        orig_size_mb = round(message.document.file_size / (1024 * 1024), 2)

    file_path = f"downloads/{user_id}_{message.id}.mp4"
    if not os.path.exists("downloads"): os.makedirs("downloads")
    await message.download(file_name=file_path)
    
    user_data[user_id] = {"path": file_path, "orig_size": orig_size_mb}
    await msg.edit_text(f"✅ Video qabul qilindi ({orig_size_mb} MB).\nNecha MB bo'lsin? (Masalan: 20)")

@app.on_message(filters.text & filters.private)
async def set_size(client, message):
    user_id = message.from_user.id
    if user_id not in user_data: return
    if not message.text.isdigit(): return

    target_mb = int(message.text)
    input_path = user_data[user_id]["path"]
    orig_size = user_data[user_id]["orig_size"]
    output_path = f"downloads/out_{user_id}.mp4"
    
    status = await message.reply_text(f"⏳ {target_mb} MB ga tayyorlanmoqda (Sifat maksimal darajada bo'ladi)...")
    
    try:
        success = await compress_video(input_path, output_path, target_mb)
        
        if success and os.path.exists(output_path):
            real_size = round(os.path.getsize(output_path) / (1024 * 1024), 2)
            
            caption_text = (
                f"Siz yuborgan {orig_size} MB videoni {real_size} MB ga qisqartirdim! 😎\n\n"
                f"✨ Sifat: Maksimal (Optimallashgan)\n"
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
            await status.edit_text("❌ Xato yuz berdi.")
    except Exception as e:
        await status.edit_text(f"❌ Xato: {e}")
    
    if os.path.exists(input_path): os.remove(input_path)
    if os.path.exists(output_path): os.remove(output_path)
    del user_data[user_id]

if __name__ == "__main__":
    app.run()
