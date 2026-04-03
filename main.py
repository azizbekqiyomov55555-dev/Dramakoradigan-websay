import os
import asyncio
import subprocess
from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardMarkup, 
    InlineKeyboardButton, 
    ReplyKeyboardMarkup, 
    KeyboardButton
)
from pyrogram.enums import ParseMode
from static_ffmpeg import add_paths
from PIL import Image, ImageDraw, ImageFont

add_paths()

# --- SOZLAMALAR ---
API_ID = 37366974
API_HASH = "08d09c7ed8b7cb414ed6a99c104f1bd6"
BOT_TOKEN = "8630024708:AAGRE2oY2c74wR4mP3U5C298d3k3a7SUEVU"

app = Client("video_processor", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

user_data = {}

MAX_MERGE_VIDEOS = 150  # Maksimal birlashtiriladigan video soni

# --- YORDAMCHI FUNKSIYALAR ---

def get_duration(file_path):
    try:
        cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "default=noprint_wrappers=1:nokey=1", file_path]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        return float(res.stdout.strip())
    except:
        return 0

async def compress_video(input_path, output_path, target_mb):
    duration = get_duration(input_path)
    if duration == 0:
        return False
    total_bitrate = (target_mb * 8000) / duration
    audio_bitrate = 128
    video_bitrate = int(total_bitrate - audio_bitrate)
    if video_bitrate < 200:
        video_bitrate = 200
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
        "-i", input_path, "-c", "copy", "-map", "0",
        "-movflags", "+faststart", output_path
    ]
    process = await asyncio.create_subprocess_exec(*cmd)
    await process.wait()
    return os.path.exists(output_path)

# --- VIDEO BIRLASHTIRISH FUNKSIYASI ---

async def merge_videos(video_paths: list, output_path: str) -> bool:
    """
    100 tagacha (max 150) videoni birlashtirib, bitta MP4 faylga chiqaradi.
    Barcha videolar avval qayta kodlanadi (re-encode) — format farqlari muammo bo'lmaydi.
    """
    if not video_paths:
        return False

    temp_dir = os.path.dirname(output_path)
    reencoded_files = []

    # 1-qadam: Har bir videoni bir xil formatga keltirish (720p, libx264)
    for i, vpath in enumerate(video_paths):
        temp_out = os.path.join(temp_dir, f"_merge_temp_{i}.mp4")
        cmd = [
            "ffmpeg", "-y", "-i", vpath,
            "-vf", "scale=-2:720",
            "-c:v", "libx264", "-preset", "fast",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            temp_out
        ]
        proc = await asyncio.create_subprocess_exec(*cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL)
        await proc.wait()
        if os.path.exists(temp_out):
            reencoded_files.append(temp_out)

    if not reencoded_files:
        return False

    # 2-qadam: concat ro'yxat faylini yaratish
    list_file = os.path.join(temp_dir, "_merge_list.txt")
    with open(list_file, "w", encoding="utf-8") as f:
        for fp in reencoded_files:
            f.write(f"file '{os.path.abspath(fp)}'\n")

    # 3-qadam: FFmpeg concat demuxer bilan birlashtirish
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", list_file,
        "-c", "copy",
        "-movflags", "+faststart",
        output_path
    ]
    proc = await asyncio.create_subprocess_exec(*cmd,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL)
    await proc.wait()

    # 4-qadam: Vaqtinchalik fayllarni tozalash
    for fp in reencoded_files:
        try:
            os.remove(fp)
        except:
            pass
    try:
        os.remove(list_file)
    except:
        pass

    return os.path.exists(output_path)

# --- RASM FUNKSIYALARI ---

def compress_image(input_path, output_path, quality=85):
    try:
        img = Image.open(input_path).convert("RGB")
        img.save(output_path, 'JPEG', quality=quality, optimize=True)
        return True
    except:
        return False

def crop_image_square(input_path, output_path):
    try:
        img = Image.open(input_path).convert("RGB")
        width, height = img.size
        min_side = min(width, height)
        left = (width - min_side) // 2
        top = (height - min_side) // 2
        img.crop((left, top, left + min_side, top + min_side)).save(output_path, 'JPEG', quality=95)
        return True
    except:
        return False

def resize_image_fit(input_path, output_path, width, height):
    try:
        img = Image.open(input_path).convert("RGB")
        img.thumbnail((width, height), Image.Resampling.LANCZOS)
        new_img = Image.new("RGB", (width, height), (0, 0, 0))
        offset = ((width - img.size[0]) // 2, (height - img.size[1]) // 2)
        new_img.paste(img, offset)
        new_img.save(output_path, "JPEG", quality=95)
        return True
    except:
        return False

def add_text_to_image(input_path, output_path, text):
    try:
        img = Image.open(input_path).convert("RGB")
        draw = ImageDraw.Draw(img)
        font = ImageFont.load_default()
        w, h = img.size
        draw.text((w/2, h-50), text, fill="white", font=font, anchor="ms", stroke_width=2, stroke_fill="black")
        img.save(output_path, "JPEG", quality=95)
        return True
    except:
        return False

# --- ASOSIY MENYU ---

def get_main_keyboard():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("🎬 Video yuborish"), KeyboardButton("🖼 Rasm yuborish")],
            [KeyboardButton("🔗 Videolarni birlashtirish"), KeyboardButton("📊 Statistika")],
            [KeyboardButton("❓ Yordam")]
        ],
        resize_keyboard=True
    )

@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text(
        "👋 **Assalomu alaykum!**\nMedia fayllarni qayta ishlash botiga xush kelibsiz!",
        reply_markup=get_main_keyboard()
    )

# --- STATISTIKA VA YORDAM ---

@app.on_message(filters.regex("📊 Statistika"))
async def stats_button(client, message):
    total_users = len(user_data)
    await message.reply_text(
        f"📊 **Statistika:**\n\n👥 Faol foydalanuvchilar (seansda): {total_users}\n🤖 Bot holati: Ishlamoqda ✅"
    )

@app.on_message(filters.regex("❓ Yordam"))
async def help_button(client, message):
    await message.reply_text(
        "❓ **Yordam:**\n\n"
        "1. Video yoki rasm yuboring.\n"
        "2. Tugmalardan birini tanlang.\n"
        "3. Kerakli o'lcham yoki hajmni yozing.\n\n"
        "🔗 **Videolarni birlashtirish:**\n"
        "• «🔗 Videolarni birlashtirish» tugmasini bosing.\n"
        f"• Birma-bir video yuboring (max {MAX_MERGE_VIDEOS} ta).\n"
        "• Tayyor bo'lgach «✅ Birlashtir» tugmasini bosing."
    )

# --- VIDEOLARNI BIRLASHTIRISH REJIMI ---

@app.on_message(filters.regex("🔗 Videolarni birlashtirish"))
async def start_merge_mode(client, message):
    uid = message.from_user.id
    # Avvalgi ma'lumotlarni tozalash
    clean_user(uid)
    user_data[uid] = {
        "mode": "merge",
        "videos": [],
        "type": "merge"
    }
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"✅ Birlashtir ({0} ta video)", callback_data="do_merge")],
        [InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel_merge")]
    ])
    await message.reply_text(
        f"🔗 **Video birlashtirish rejimi yoqildi!**\n\n"
        f"Endi videolarni yuboravering (max {MAX_MERGE_VIDEOS} ta).\n"
        f"Hammasi yuborilgach **«✅ Birlashtir»** tugmasini bosing.",
        reply_markup=kb
    )

# --- RASM ISHLASH ---

@app.on_message(filters.photo)
async def handle_photo(client, message):
    uid = message.from_user.id
    msg = await message.reply_text("📥 Rasm yuklanmoqda...")
    file_path = await message.download(file_name=f"downloads/img_{uid}.jpg")
    user_data[uid] = {
        "path": file_path,
        "type": "photo",
        "orig_size": round(os.path.getsize(file_path) / (1024 * 1024), 2)
    }
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📐 O'lcham (Kesmasdan Fit)", callback_data="p_fit"),
         InlineKeyboardButton("✂️ Kvadrat qirqish", callback_data="p_crop")],
        [InlineKeyboardButton("✍️ Matn yozish (Montaj)", callback_data="p_text"),
         InlineKeyboardButton("🗜 Siqish", callback_data="p_comp")]
    ])
    await msg.edit_text("✅ Rasm yuklandi. Amallardan birini tanlang:", reply_markup=kb)

# --- VIDEO ISHLASH ---

@app.on_message(filters.video | filters.document)
async def handle_video(client, message):
    if message.document and not message.document.mime_type.startswith("video/"):
        return

    uid = message.from_user.id

    # ── BIRLASHTIRISH REJIMI ──────────────────────────────────────────────────
    if uid in user_data and user_data[uid].get("mode") == "merge":
        videos = user_data[uid]["videos"]
        if len(videos) >= MAX_MERGE_VIDEOS:
            await message.reply_text(
                f"⚠️ Maksimal {MAX_MERGE_VIDEOS} ta video yuborishingiz mumkin!\n"
                f"«✅ Birlashtir» tugmasini bosing."
            )
            return

        idx = len(videos)
        file_path = await message.download(
            file_name=f"downloads/merge_{uid}_{idx}.mp4"
        )
        videos.append(file_path)
        count = len(videos)

        # Keyingi qism haqida xabar
        if count < MAX_MERGE_VIDEOS:
            next_msg = f"📤 **{count + 1}-qismni yuboring** yoki birlashtiring."
        else:
            next_msg = f"⚠️ Maksimal {MAX_MERGE_VIDEOS} ta. Endi birlashtiring."

        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                f"✅ Birlashtir ({count} ta video)",
                callback_data="do_merge"
            )],
            [InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel_merge")]
        ])
        await message.reply_text(
            f"✅ **{count}-qism qabul qilindi.**\n{next_msg}",
            reply_markup=kb
        )
        return

    # ── ODDIY VIDEO ISHLASH REJIMI ────────────────────────────────────────────
    msg = await message.reply_text("📥 Video yuklanmoqda...")
    file_path = await message.download(file_name=f"downloads/vid_{uid}.mp4")
    user_data[uid] = {
        "path": file_path,
        "type": "video",
        "orig_size": round(os.path.getsize(file_path) / (1024 * 1024), 2)
    }
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🗜 Siqish", callback_data="v_comp"),
         InlineKeyboardButton("✂️ Bo'lish", callback_data="v_split")],
        [InlineKeyboardButton("⚡️ Siqish + Bo'lish", callback_data="v_both")]
    ])
    await msg.edit_text("✅ Video yuklandi. Tanlang:", reply_markup=kb)

# --- CALLBACKS ---

@app.on_callback_query()
async def callback_handler(client, q):
    uid = q.from_user.id
    data = q.data

    # ── BIRLASHTIRISH CALLBACK'LARI ──────────────────────────────────────────
    if data == "cancel_merge":
        clean_user(uid)
        await q.message.edit_text("❌ Birlashtirish bekor qilindi.")
        return

    if data == "do_merge":
        if uid not in user_data or user_data[uid].get("mode") != "merge":
            await q.answer("Ma'lumot topilmadi, qaytadan boshlang.", show_alert=True)
            return
        videos = user_data[uid].get("videos", [])
        if len(videos) < 2:
            await q.answer("⚠️ Kamida 2 ta video yuboring!", show_alert=True)
            return

        status = await q.message.edit_text(
            f"⏳ **{len(videos)} ta video birlashtirilmoqda...**\n"
            f"Bu biroz vaqt olishi mumkin, kuting..."
        )
        out_path = f"downloads/merged_{uid}.mp4"
        success = await merge_videos(videos, out_path)

        if success:
            size_mb = round(os.path.getsize(out_path) / (1024 * 1024), 2)
            await client.send_video(
                uid,
                out_path,
                caption=f"✅ **Birlashtirish tayyor!**\n"
                        f"📹 Video soni: {len(videos)} ta\n"
                        f"📦 Hajmi: {size_mb} MB",
                supports_streaming=True
            )
            await status.delete()
            try:
                os.remove(out_path)
            except:
                pass
        else:
            await status.edit_text("❌ Birlashtirish muvaffaqiyatsiz bo'ldi. Qaytadan urinib ko'ring.")

        # Fayllarni tozalash
        for vp in videos:
            try:
                os.remove(vp)
            except:
                pass
        if uid in user_data:
            del user_data[uid]
        return

    # ── ODDIY CALLBACK'LAR ───────────────────────────────────────────────────
    if uid not in user_data:
        await q.answer("Ma'lumot topilmadi, qaytadan yuboring.", show_alert=True)
        return

    if data == "p_fit":
        await q.message.edit_text("📐 **O'lchamni kiriting** (masalan: `1280x720` yoki `1080x1080`):")
        user_data[uid]["action"] = "wait_size"
    elif data == "p_text":
        await q.message.edit_text("✍️ **Rasmga yoziladigan matnni kiriting:**")
        user_data[uid]["action"] = "wait_text"
    elif data == "p_crop":
        status = await q.message.edit_text("⏳ Qirqilmoqda...")
        out = f"downloads/crop_{uid}.jpg"
        if crop_image_square(user_data[uid]["path"], out):
            await client.send_photo(uid, out, caption="✅ Kvadrat qilib qirqildi!")
            await status.delete()
        clean_user(uid)
    elif data == "v_comp":
        await q.message.edit_text("🗜 **Necha MB bo'lsin?** (Faqat raqam yozing):")
        user_data[uid]["action"] = "wait_v_size"
    elif data == "v_split":
        await q.message.edit_text("✂️ **Nechta qismga bo'linsin?** (Faqat raqam):")
        user_data[uid]["action"] = "wait_v_split"

# --- MATN KIRITISHNI BOSHQARISH ---

@app.on_message(filters.text & filters.private & ~filters.regex("^(🎬|🖼|📊|❓|🔗)"))
async def text_input(client, message):
    uid = message.from_user.id
    if uid not in user_data or "action" not in user_data[uid]:
        return

    action = user_data[uid]["action"]
    path = user_data[uid]["path"]

    if action == "wait_size":
        try:
            w, h = map(int, message.text.lower().split('x'))
            st = await message.reply_text("⏳ Ishlanmoqda...")
            out = f"downloads/fit_{uid}.jpg"
            if resize_image_fit(path, out, w, h):
                await message.reply_document(out, caption=f"✅ O'lcham: {w}x{h} (Hamma joyi ko'rinadi)")
                await st.delete()
            clean_user(uid)
        except:
            await message.reply_text("❌ Xato! Format: `1280x720` deb yozing.")

    elif action == "wait_text":
        st = await message.reply_text("⏳ Montaj qilinmoqda...")
        out = f"downloads/montaj_{uid}.jpg"
        if add_text_to_image(path, out, message.text):
            await message.reply_photo(out, caption=f"✅ Matn qo'shildi: {message.text}")
            await st.delete()
        clean_user(uid)

    elif action == "wait_v_size":
        try:
            target = int(message.text)
            st = await message.reply_text(f"⏳ {target}MB ga siqilmoqda...")
            out = f"downloads/res_{uid}.mp4"
            if await compress_video(path, out, target):
                await message.reply_video(out, caption=f"✅ Tayyor! Hajmi: {target}MB")
                await st.delete()
            clean_user(uid)
        except:
            await message.reply_text("❌ Faqat son kiriting!")

def clean_user(uid):
    if uid in user_data:
        # Oddiy fayl
        if "path" in user_data[uid]:
            try:
                if os.path.exists(user_data[uid]["path"]):
                    os.remove(user_data[uid]["path"])
            except:
                pass
        # Merge videolar ro'yxati
        for vp in user_data[uid].get("videos", []):
            try:
                if os.path.exists(vp):
                    os.remove(vp)
            except:
                pass
        del user_data[uid]

if __name__ == "__main__":
    if not os.path.exists("downloads"):
        os.makedirs("downloads")
    print("🤖 Bot ishga tushdi!")
    app.run()
