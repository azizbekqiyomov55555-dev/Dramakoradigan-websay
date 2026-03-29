import os
import asyncio
import subprocess
import math
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from static_ffmpeg import add_paths

add_paths()

API_ID = 37366974
API_HASH = "08d09c7ed8b7cb414ed6a99c104f1bd6"
BOT_TOKEN = "8487571646:AAFp8EE6lRHeLYhS0v50_her2q-QYBZ3rmI"

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
    
    total_bitrate = (target_mb * 8000) / duration
    audio_bitrate = 128
    video_bitrate = int(total_bitrate - audio_bitrate)
    if video_bitrate < 200: video_bitrate = 200

    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vf", "scale=-2:720",
        "-c:v", "libx264", "-b:v", f"{video_bitrate}k",
        "-preset", "fast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", f"{audio_bitrate}k",
        "-movflags", "+faststart", output_path
    ]
    process = await asyncio.create_subprocess_exec(*cmd)
    await process.wait()
    return True

async def split_video(input_path, part_num, total_parts, start_time, duration_part, output_path):
    # -ss (start) va -t (duration) orqali kesish
    cmd = [
        "ffmpeg", "-y", "-ss", str(start_time), "-t", str(duration_part),
        "-i", input_path,
        "-c", "copy", # "copy" ishlatilsa judayam tez bo'ladi (sifat buzilmaydi)
        "-map", "0", "-movflags", "+faststart", output_path
    ]
    process = await asyncio.create_subprocess_exec(*cmd)
    await process.wait()
    return os.path.exists(output_path)

@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text("Salom! Video yuboring, uni siqishim yoki qismlarga bo'lishim mumkin.")

@app.on_message(filters.video | filters.document)
async def handle_video(client, message):
    if message.document and not message.document.mime_type.startswith("video/"):
        return
    
    msg = await message.reply_text("📥 Video yuklanmoqda...")
    file_path = await message.download(file_name=f"downloads/{message.from_user.id}_{message.id}.mp4")
    
    orig_size_mb = round(os.path.getsize(file_path) / (1024 * 1024), 2)
    duration = get_duration(file_path)

    user_data[message.from_user.id] = {
        "path": file_path,
        "orig_size": orig_size_mb,
        "duration": duration,
        "action": None
    }
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("🗜 Siqish (Hajm bo'yicha)", callback_data="choice_compress")],
        [InlineKeyboardButton("✂️ Qismlarga bo'lish", callback_data="choice_split")]
    ])
    
    await msg.edit_text(f"✅ Video yuklandi ({orig_size_mb} MB).\nNima qilamiz?", reply_markup=buttons)

@app.on_callback_query(filters.regex("^choice_"))
async def callback_handler(client, callback_query):
    user_id = callback_query.from_user.id
    action = callback_query.data.split("_")[1]
    
    if user_id not in user_data:
        await callback_query.answer("Xatolik: Ma'lumot topilmadi.", show_alert=True)
        return

    user_data[user_id]["action"] = action
    
    if action == "compress":
        await callback_query.message.edit_text("Necha MB bo'lishini xohlaysiz? (Masalan: 50)")
    else:
        await callback_query.message.edit_text("Videoni nechta qismga bo'lmoqchisiz? (Masalan: 3)")

@app.on_message(filters.text & filters.private)
async def handle_input(client, message):
    user_id = message.from_user.id
    if user_id not in user_data or not user_data[user_id]["action"]: return

    if not message.text.isdigit():
        await message.reply_text("Iltimos, faqat raqam kiriting!")
        return

    val = int(message.text)
    data = user_data[user_id]
    action = data["action"]

    if action == "compress":
        # SIQISH LOGIKASI
        target_mb = val
        if target_mb >= data["orig_size"]:
            await message.reply_text("Kichikroq hajm kiriting!")
            return
        
        status = await message.reply_text(f"⏳ {target_mb}MB ga siqilmoqda...")
        out = f"downloads/compressed_{user_id}.mp4"
        if await compress_video(data["path"], out, target_mb):
            await client.send_video(user_id, out, caption=f"✅ Siqildi: {target_mb}MB")
            await status.delete()
        else:
            await status.edit_text("❌ Xatolik!")
        
        if os.path.exists(out): os.remove(out)

    elif action == "split":
        # QISMLARGA BO'LISH LOGIKASI
        num_parts = val
        if num_parts < 2:
            await message.reply_text("Kamida 2 ta qism bo'lishi kerak!")
            return
        
        status = await message.reply_text(f"⏳ Video {num_parts} qismga bo'linmoqda...")
        total_duration = data["duration"]
        part_duration = total_duration / num_parts
        
        for i in range(num_parts):
            start_time = i * part_duration
            part_path = f"downloads/part_{i+1}_{user_id}.mp4"
            await status.edit_text(f"⏳ {i+1}-qism tayyorlanmoqda...")
            
            success = await split_video(data["path"], i+1, num_parts, start_time, part_duration, part_path)
            if success:
                await client.send_video(
                    chat_id=user_id,
                    video=part_path,
                    caption=f"🎬 {i+1}-qism / {num_parts} jami"
                )
                os.remove(part_path)
            else:
                await message.reply_text(f"❌ {i+1}-qismda xatolik!")
        
        await status.edit_text("✅ Barcha qismlar yuborildi!")

    # Tozalash
    if os.path.exists(data["path"]): os.remove(data["path"])
    del user_data[user_id]

if __name__ == "__main__":
    if not os.path.exists("downloads"): os.makedirs("downloads")
    app.run()
