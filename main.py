import os
import asyncio
import subprocess
from pyrogram import Client, filters
from pyrogram.types import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
from aiohttp import web
from static_ffmpeg import add_paths

# FFMPEG kutubxonasini ulash
add_paths()

# --- SOZLAMALAR ---
API_ID = 37366974
API_HASH = "08d09c7ed8b7cb414ed6a99c104f1bd6"
BOT_TOKEN = "8487571646:AAFp8EE6lRHeLYhS0v50_her2q-QYBZ3rmI"

# DIQQAT: Agar botingizni VPS serverga qo'ysangiz, IP manzilingizni yozing.
# Hozircha bu bot o'z ichida veb-menyuni hosil qiladi.
# Web App ishlashi uchun HTTPS havola shart. 
# Agar sizda HTTPS bo'lmasa, bot emojili chiroyli tugmalarni ishlatadi.
MY_URL = "https://t.me/your_bot_username/app" # Bu yerga Web App manzili qo'yiladi

app = Client("video_master_pro", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
user_data = {}

# --- HTML MENYU (RANGLI TUGMALAR UCHUN) ---
HTML_MENU = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        body { background: #f4f4f9; display: flex; flex-direction: column; gap: 15px; padding: 20px; font-family: sans-serif; }
        .btn {
            border: none; padding: 20px; color: white; font-weight: bold;
            border-radius: 15px; cursor: pointer; font-size: 16px; width: 100%;
            transition: 0.3s; box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        }
        .compress { background: linear-gradient(135deg, #28a745, #218838); } /* Yashil */
        .split { background: linear-gradient(135deg, #007bff, #0069d9); }    /* Ko'k */
        .close { background: linear-gradient(135deg, #dc3545, #c82333); }    /* Qizil */
        .btn:active { transform: scale(0.98); }
    </style>
</head>
<body>
    <button class="btn compress" onclick="send('siqish')">🟢 VIDEO HAJMINI QISQARTIRISH</button>
    <button class="btn split" onclick="send('bolish')">🔵 VIDEONI QISMLARGA BO'LISH</button>
    <button class="btn close" onclick="tg.close()">🔴 BEKOR QILISH</button>

    <script>
        let tg = window.Telegram.WebApp;
        tg.expand();
        function send(mode) {
            tg.sendData(mode); // Botga rejimni yuboradi
            tg.close();
        }
    </script>
</body>
</html>
"""

# --- VIDEO FUNKSIYALARI ---
def get_duration(file_path):
    try:
        cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", file_path]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, text=True)
        return float(res.stdout.strip())
    except: return 0

async def compress_video(input_path, output_path, target_mb, duration):
    bitrate = int((target_mb * 8000) / duration) if duration > 0 else 500
    cmd = ["ffmpeg", "-y", "-i", input_path, "-b:v", f"{bitrate}k", "-c:v", "libx264", "-preset", "fast", "-c:a", "aac", "-b:a", "128k", output_path]
    process = await asyncio.create_subprocess_exec(*cmd)
    await process.wait()
    return os.path.exists(output_path)

async def split_video(input_path, start_time, part_duration, output_path):
    cmd = ["ffmpeg", "-y", "-ss", str(start_time), "-t", str(part_duration), "-i", input_path, "-c", "copy", "-movflags", "+faststart", output_path]
    process = await asyncio.create_subprocess_exec(*cmd)
    await process.wait()
    return os.path.exists(output_path)

# --- BOT HANDLERLARI ---
@app.on_message(filters.command("start"))
async def start_cmd(client, message):
    # Asosiy menyu (Pastki tugmalar)
    # Eslatma: WebAppInfo ishlashi uchun MY_URL (HTTPS) bo'lishi kerak. 
    # Hozircha vizual ko'rinish uchun Emojili chiroyli menyuni ham qo'shaman.
    kb = ReplyKeyboardMarkup(
        [
            [KeyboardButton("🟢 Video Hajmini Qisqartirish")],
            [KeyboardButton("🔵 Videoni Qismlarga Bo'lish")]
        ],
        resize_keyboard=True
    )
    await message.reply_text(
        f"Assalomu alaykum **{message.from_user.first_name}**!\n\n"
        "Siz bu bot orqali videolarni sifatli siqishingiz yoki qismlarga bo'lishingiz mumkin.\n\n"
        "Xizmatlardan birini tanlang 👇",
        reply_markup=kb
    )

@app.on_message(filters.text)
async def handle_text(client, message):
    user_id = message.from_user.id
    if "Video Hajmini Qisqartirish" in message.text:
        user_data[user_id] = {"mode": "compress"}
        await message.reply_text("📥 **Siqish uchun videoni yuboring:**")
    elif "Videoni Qismlarga Bo'lish" in message.text:
        user_data[user_id] = {"mode": "split"}
        await message.reply_text("📥 **Bo'lish uchun videoni yuboring:**")

@app.on_message(filters.video | filters.document)
async def handle_media(client, message):
    user_id = message.from_user.id
    if user_id not in user_data:
        await message.reply_text("Iltimos, avval pastdagi menyudan xizmatni tanlang!")
        return

    msg = await message.reply_text("⏳ **Video serverga yuklanmoqda...**")
    path = await message.download(file_name=f"downloads/{user_id}_{message.id}.mp4")
    
    user_data[user_id]["path"] = path
    user_data[user_id]["duration"] = get_duration(path)

    if user_data[user_id]["mode"] == "compress":
        await msg.edit_text("✅ Video qabul qilindi.\n\nEndi videoni **necha MB** bo'lishini xohlaysiz? (Faqat raqam yozing, masalan: 50)")
    else:
        await msg.edit_text("✅ Video qabul qilindi.\n\nVideoni **nechta qismga** bo'lishni xohlaysiz? (Faqat raqam yozing, masalan: 3)")

@app.on_message(filters.text & filters.private)
async def process_input(client, message):
    user_id = message.from_user.id
    if user_id not in user_data or "path" not in user_data[user_id]: return
    if not message.text.isdigit(): return

    val = int(message.text)
    data = user_data[user_id]
    input_path = data["path"]

    if data["mode"] == "compress":
        status = await message.reply_text(f"⏳ **Video {val} MB ga moslab siqilmoqda...**\nBu biroz vaqt olishi mumkin.")
        out = f"downloads/compressed_{user_id}.mp4"
        if await compress_video(input_path, out, val, data["duration"]):
            await client.send_video(user_id, out, caption=f"✅ Siqildi: {val} MB")
            os.remove(out)
        await status.delete()

    elif data["mode"] == "split":
        status = await message.reply_text(f"⏳ **Video {val} qismga bo'linmoqda...**")
        part_dur = data["duration"] / val
        for i in range(val):
            out_p = f"downloads/part_{i+1}_{user_id}.mp4"
            if await split_video(input_path, i * part_dur, part_dur, out_p):
                await client.send_video(user_id, out_p, caption=f"🎬 {i+1}-qism")
                os.remove(out_p)
        await status.edit_text("✅ Barcha qismlar yuborildi!")

    if os.path.exists(input_path): os.remove(input_path)
    del user_data[user_id]

# --- ASOSIY ISHGA TUSHIRISH ---
if __name__ == "__main__":
    if not os.path.exists("downloads"): os.makedirs("downloads")
    print("🚀 Bot ishga tushdi!")
    app.run()
