import os
import asyncio
import subprocess
from pyrogram import Client, filters

# SIZNING API MA'LUMOTLARINGIZ
API_ID = 37366974
API_HASH = "08d09c7ed8b7cb414ed6a99c104f1bd6"
BOT_TOKEN = "8229730974:AAF-aDQkGu6wCO1uT2Rjbbr-6F_blnxc880"

app = Client("video_compressor", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

user_data = {}

def get_duration(file_path):
    try:
        cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", file_path]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        return float(res.stdout.strip())
    except Exception as e:
        print(f"Duration xatosi: {e}")
        return 0

async def compress_video(input_path, output_path, target_mb):
    duration = get_duration(input_path)
    if duration == 0: return False
    
    # Maqsadli bitreytni hisoblash
    target_size_bits = (target_mb * 1024 * 1024 * 8) * 0.95
    audio_bitrate = 64 * 1024
    video_bitrate = int((target_size_bits / duration) - audio_bitrate)
    if video_bitrate < 150000: video_bitrate = 150000
    video_bitrate_k = int(video_bitrate / 1000)

    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vf", "scale='min(iw,1280)':-2", 
        "-c:v", "libx264",
        "-b:v", f"{video_bitrate_k}k",
        "-preset", "medium", # 'slow' o'rniga 'medium' (server o'chib qolmasligi uchun)
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "64k",
        "-movflags", "+faststart",
        output_path
    ]
    
    process = await asyncio.create_subprocess_exec(*cmd)
    await process.wait()
    return True

@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text("Salom! Video yuboring, men uni sifatli qilib siqib beraman.")

@app.on_message(filters.video | filters.document)
async def handle_video(client, message):
    if message.document and not message.document.mime_type.startswith("video/"):
        return
    
    user_id = message.from_user.id
    msg = await message.reply_text("📥 Video qabul qilindi. Serverga yuklanmoqda...")
    
    file_size = message.video.file_size if message.video else message.document.file_size
    orig_size_mb = round(file_size / (1024 * 1024), 2)

    if not os.path.exists("downloads"): os.makedirs("downloads")
    file_path = f"downloads/{user_id}_{message.id}.mp4"
    
    await message.download(file_name=file_path)
    user_data[user_id] = {"path": file_path, "orig_size": orig_size_mb}
    
    await msg.edit_text(f"✅ Video yuklandi ({orig_size_mb} MB).\nNecha MB bo'lsin? (Faqat raqam yozing, masalan: 20)")

@app.on_message(filters.text & filters.private)
async def set_size(client, message):
    user_id = message.from_user.id
    if user_id not in user_data or not message.text.isdigit():
        return

    target_mb = int(message.text)
    input_path = user_data[user_id]["path"]
    orig_size = user_data[user_id]["orig_size"]
    output_path = f"downloads/out_{user_id}.mp4"
    
    status = await message.reply_text(f"⏳ {target_mb} MB ga siqilmoqda...")
    
    try:
        success = await compress_video(input_path, output_path, target_mb)
        
        if success and os.path.exists(output_path):
            real_size = round(os.path.getsize(output_path) / (1024 * 1024), 2)
            caption_text = (
                f"Siz yuborgan {orig_size} MB videoni {real_size} MB ga qisqartirdim! 😎\n\n"
                f"✨ Sifat: Maksimal\n✅ Tayyor!"
            )
            await client.send_video(chat_id=user_id, video=output_path, caption=caption_text, supports_streaming=True)
            await status.delete()
        else:
            await status.edit_text("❌ Siqishda xato bo'ldi.")
    except Exception as e:
        await status.edit_text(f"❌ Xato: {e}")
    
    if os.path.exists(input_path): os.remove(input_path)
    if os.path.exists(output_path): os.remove(output_path)
    del user_data[user_id]

if __name__ == "__main__":
    app.run()
