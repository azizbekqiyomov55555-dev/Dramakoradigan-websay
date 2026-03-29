import os
import asyncio
import subprocess
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from static_ffmpeg import add_paths

add_paths()

API_ID = 37366974
API_HASH = "08d09c7ed8b7cb414ed6a99c104f1bd6"
BOT_TOKEN = "8487571646:AAFp8EE6lRHeLYhS0v50_her2q-QYBZ3rmI"

app = Client("video_processor", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

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
    return os.path.exists(output_path)

async def split_video(input_path, start_time, duration_part, output_path):
    cmd = [
        "ffmpeg", "-y", "-ss", str(start_time), "-t", str(duration_part),
        "-i", input_path,
        "-c", "copy", "-map", "0", "-movflags", "+faststart", output_path
    ]
    process = await asyncio.create_subprocess_exec(*cmd)
    await process.wait()
    return os.path.exists(output_path)

@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text("Salom! Video yuboring, uni siqishim va qismlarga bo'lishim mumkin.")

@app.on_message(filters.video | filters.document)
async def handle_video(client, message):
    if message.document and not message.document.mime_type.startswith("video/"):
        return
    
    msg = await message.reply_text("📥 Video yuklanmoqda (Bu biroz vaqt olishi mumkin)...")
    file_path = await message.download(file_name=f"downloads/{message.from_user.id}_{message.id}.mp4")
    
    orig_size_mb = round(os.path.getsize(file_path) / (1024 * 1024), 2)
    duration = get_duration(file_path)

    user_data[message.from_user.id] = {
        "path": file_path,
        "orig_size": orig_size_mb,
        "duration": duration,
        "action": None,
        "target_mb": None,
        "parts": None
    }
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("🗜 Faqat siqish", callback_data="choice_compress")],
        [InlineKeyboardButton("✂️ Faqat bo'lish", callback_data="choice_split")],
        [InlineKeyboardButton("⚡️ Siqish + Bo'lish", callback_data="choice_both")]
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
        await callback_query.message.edit_text("Necha MB gacha siqmoqchisiz? (Masalan: 500)")
    elif action == "split":
        await callback_query.message.edit_text("Nechta qismga bo'lmoqchisiz? (Masalan: 3)")
    elif action == "both":
        await callback_query.message.edit_text("1-QADAM: Jami video hajmi necha MB bo'lsin? (Masalan: 1200)")

@app.on_message(filters.text & filters.private)
async def handle_text_input(client, message):
    user_id = message.from_user.id
    if user_id not in user_data or not user_data[user_id]["action"]: return

    if not message.text.isdigit():
        await message.reply_text("Iltimos, faqat raqam kiriting!")
        return

    val = int(message.text)
    data = user_data[user_id]
    action = data["action"]

    # 1. FAQAT SIQISH
    if action == "compress":
        await process_compress(client, user_id, val)

    # 2. FAQAT BO'LISH
    elif action == "split":
        await process_split(client, user_id, val, data["path"])

    # 3. SIQISH + BO'LISH (IKKALA BOSQICH)
    elif action == "both":
        if data["target_mb"] is None:
            user_data[user_id]["target_mb"] = val
            await message.reply_text(f"✅ Hajm {val} MB etib belgilandi.\n\n2-QADAM: Endi ushbu hajmdagi videoni nechta qismga bo'lish kerak? (Masalan: 4)")
        else:
            user_data[user_id]["parts"] = val
            await process_both(client, user_id)

async def process_compress(client, user_id, target_mb):
    data = user_data[user_id]
    status = await client.send_message(user_id, f"⏳ {target_mb}MB ga siqilmoqda...")
    out = f"downloads/comp_{user_id}.mp4"
    
    if await compress_video(data["path"], out, target_mb):
        await client.send_video(user_id, out, caption=f"✅ Tayyor! ({target_mb} MB)")
    else:
        await client.send_message(user_id, "❌ Siqishda xatolik!")
    
    if os.path.exists(out): os.remove(out)
    clean_user(user_id)

async def process_split(client, user_id, num_parts, file_path):
    data = user_data[user_id]
    duration = get_duration(file_path)
    part_duration = duration / num_parts
    status = await client.send_message(user_id, f"⏳ Video {num_parts} qismga bo'linmoqda...")

    for i in range(num_parts):
        out_part = f"downloads/part_{i+1}_{user_id}.mp4"
        if await split_video(file_path, i * part_duration, part_duration, out_part):
            await client.send_video(user_id, out_part, caption=f"🎬 {i+1}-qism")
            if os.path.exists(out_part): os.remove(out_part)
    
    await status.edit_text("✅ Barcha qismlar yuborildi!")
    clean_user(user_id)

async def process_both(client, user_id):
    data = user_data[user_id]
    target_mb = data["target_mb"]
    num_parts = data["parts"]
    
    status = await client.send_message(user_id, f"⏳ 1/2-bosqich: Video {target_mb}MB ga siqilmoqda...")
    compressed_file = f"downloads/temp_comp_{user_id}.mp4"
    
    if await compress_video(data["path"], compressed_file, target_mb):
        await status.edit_text(f"⏳ 2/2-bosqich: Siqilgan video {num_parts} qismga bo'linmoqda...")
        
        duration = get_duration(compressed_file)
        part_dur = duration / num_parts
        
        for i in range(num_parts):
            out_part = f"downloads/p_{i+1}_{user_id}.mp4"
            if await split_video(compressed_file, i * part_dur, part_dur, out_part):
                await client.send_video(user_id, out_part, caption=f"🎬 {i+1}-qism (Siqilgan)")
                if os.path.exists(out_part): os.remove(out_part)
        
        await status.edit_text("✅ Hammasi muvaffaqiyatli yakunlandi!")
    else:
        await status.edit_text("❌ Siqish jarayonida xatolik!")

    if os.path.exists(compressed_file): os.remove(compressed_file)
    clean_user(user_id)

def clean_user(user_id):
    if user_id in user_data:
        p = user_data[user_id]["path"]
        if os.path.exists(p): os.remove(p)
        del user_data[user_id]

if __name__ == "__main__":
    if not os.path.exists("downloads"): os.makedirs("downloads")
    app.run()
