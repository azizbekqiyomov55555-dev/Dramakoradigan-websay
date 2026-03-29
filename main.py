import os
import asyncio
import subprocess
from pyrogram import Client, filters
from static_ffmpeg import add_paths

# FFmpeg va ffprobe yo'llarini avtomatik qo'shish
add_paths()

# SIZNING API MA'LUMOTLARINGIZ
API_ID = 37366974
API_HASH = "08d09c7ed8b7cb414ed6a99c104f1bd6"
BOT_TOKEN = "8766647589:AAHmY6x59GgKA25K3e737-7jomufi9wRv2Y"

app = Client("video_compressor", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

user_files = {}

def get_duration(file_path):
    """Video davomiyligini aniqlash"""
    try:
        cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", file_path]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        return float(res.stdout.strip())
    except Exception as e:
        print(f"Duration xatosi: {e}")
        return 0

async def compress_video(input_path, output_path, target_mb):
    """Videoni sifatli siqish mantiqi"""
    duration = get_duration(input_path)
    if duration == 0:
        return False
    
    # Maqsadli bitreytni hisoblash (Bitrate = Size / Duration)
    # target_mb * 8192 (kilobits) / duration
    total_bitrate = (target_mb * 8192) / duration
    video_bitrate = int(total_bitrate * 0.9) # 90% video uchun
    audio_bitrate = int(total_bitrate * 0.1) # 10% audio uchun
    
    if audio_bitrate > 128: audio_bitrate = 128
    if audio_bitrate < 32: audio_bitrate = 32
    if video_bitrate < 100: video_bitrate = 100

    # FFmpeg buyrug'i (Yaxshilangan sifat sozlamalari)
    # scale='min(iw,1280)':-2 -> Videoni 720p dan oshirmaydi, lekin aslini saqlaydi
    # -preset veryfast -> Tezlik va sifat balansi (yaxshiroq sifat uchun 'medium' qiling)
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vf", "scale='min(iw,854)':-2", # Maksimal 480p (sifat va hajm uchun eng yaxshi balans)
        "-c:v", "libx264",
        "-b:v", f"{video_bitrate}k",
        "-maxrate", f"{video_bitrate*2}k",
        "-bufsize", f"{video_bitrate*4}k",
        "-preset", "veryfast", # Sifat yaxshi bo'lishi uchun 'ultrafast'dan voz kechildi
        "-profile:v", "high",
        "-level", "4.1",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", f"{audio_bitrate}k",
        "-movflags", "+faststart", # Telegramda yuklanmasdan ko'rish imkoniyati
        output_path
    ]
    
    process = await asyncio.create_subprocess_exec(*cmd)
    await process.wait()
    return True

@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text("Salom! 🎬 Men sifatli video siquvchi botman.\n\nVideo yuboring va kutilayotgan hajmni yozing.")

@app.on_message(filters.video | filters.document)
async def handle_video(client, message):
    if message.document and not message.document.mime_type.startswith("video/"):
        return

    user_id = message.from_user.id
    msg = await message.reply_text("📥 Video qabul qilindi. Serverga yuklanmoqda...")
    
    if not os.path.exists("downloads"):
        os.makedirs("downloads")

    file_path = f"downloads/{user_id}_{message.id}.mp4"
    await message.download(file_name=file_path)
    
    user_files[user_id] = file_path
    await msg.edit_text("✅ Yuklandi! Maqsadli hajmni yozing (MB):\n(Masalan: 10 yoki 25)")

@app.on_message(filters.text & filters.private)
async def set_size(client, message):
    user_id = message.from_user.id
    if user_id not in user_files:
        return

    if not message.text.isdigit():
        await message.reply_text("Iltimos, faqat raqam yozing!")
        return

    target_mb = int(message.text)
    input_path = user_files[user_id]
    output_path = f"downloads/out_{user_id}.mp4"
    
    status = await message.reply_text(f"⏳ Video {target_mb} MB ga moslab siqilmoqda...\n(Sifatni saqlashga harakat qilaman)")
    
    try:
        success = await compress_video(input_path, output_path, target_mb)
        
        if success and os.path.exists(output_path):
            await status.edit_text("📤 Telegramga yuborilmoqda...")
            real_size = round(os.path.getsize(output_path) / (1024 * 1024), 2)
            
            await client.send_video(
                chat_id=user_id,
                video=output_path,
                caption=f"🎬 Maqsad: {target_mb} MB\n📁 Haqiqiy hajm: {real_size} MB\n✨ Sifat: Optimallashgan",
                supports_streaming=True
            )
            await status.delete()
        else:
            await status.edit_text("❌ Xatolik: Videoni siqishda muammo bo'ldi.")
    except Exception as e:
        await status.edit_text(f"❌ Xato: {e}")
    
    if os.path.exists(input_path): os.remove(input_path)
    if os.path.exists(output_path): os.remove(output_path)
    del user_files[user_id]

if __name__ == "__main__":
    app.run()
