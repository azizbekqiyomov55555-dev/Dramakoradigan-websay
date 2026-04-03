import os
import asyncio
import subprocess
import time
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

# --- PROGRESS BAR HELPER ---

def make_progress_bar(percent, length=10):
    filled = int(length * percent / 100)
    bar = "█" * filled + "░" * (length - filled)
    return bar

# --- VIDEO BIRLASHTIRISH (PROGRESS BILAN) ---

async def merge_videos_with_progress(video_paths: list, output_path: str, status_msg) -> bool:
    """
    Videolarni birlashtiradi va har qadam uchun status xabarini yangilaydi.
    """
    if not video_paths:
        return False

    total = len(video_paths)
    temp_dir = os.path.dirname(output_path)
    reencoded_files = []
    last_edit_time = [0.0]  # throttle uchun

    async def safe_edit(text):
        now = time.time()
        if now - last_edit_time[0] >= 2.5:
            try:
                await status_msg.edit_text(text, parse_mode=ParseMode.MARKDOWN)
                last_edit_time[0] = now
            except:
                pass

    # 1-qadam: Har bir videoni re-encode qilish + ffmpeg progress o'qish
    for i, vpath in enumerate(video_paths):
        temp_out = os.path.join(temp_dir, f"_merge_temp_{i}.mp4")
        video_num = i + 1
        overall_pct = int((i / total) * 90)  # 90% gacha re-encode, 10% concat uchun

        # Videoning davomiyligini olish
        vid_duration = get_duration(vpath)

        cmd = [
            "ffmpeg", "-y", "-i", vpath,
            "-vf", "scale=-2:720",
            "-c:v", "libx264", "-preset", "fast",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            "-progress", "pipe:1",  # progress stdout ga
            "-nostats",
            temp_out
        ]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL
        )

        # ffmpeg progress o'qish
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            line = line.decode("utf-8", errors="ignore").strip()

            if line.startswith("out_time_ms=") and vid_duration > 0:
                try:
                    out_time_s = int(line.split("=")[1]) / 1_000_000
                    vid_pct = min(int((out_time_s / vid_duration) * 100), 100)

                    # Umumiy foiz: i-video uchun hissa + joriy video foizi
                    current_overall = int(overall_pct + (vid_pct / total))
                    bar = make_progress_bar(current_overall)

                    await safe_edit(
                        f"🔄 **Birlashtirmoqda...**\n\n"
                        f"📹 Video: {video_num}/{total} ({vid_pct}%)\n"
                        f"📊 Umumiy: `{bar}` {current_overall}%\n\n"
                        f"_Iltimos, kuting..._"
                    )
                except:
                    pass

        await proc.wait()

        if os.path.exists(temp_out):
            reencoded_files.append(temp_out)

        # Har video tugaganda aniq yangilanish
        done_pct = int(((i + 1) / total) * 90)
        bar = make_progress_bar(done_pct)
        await safe_edit(
            f"🔄 **Birlashtirmoqda...**\n\n"
            f"✅ Tayyor: {i + 1}/{total}\n"
            f"📊 Umumiy: `{bar}` {done_pct}%\n\n"
            f"_Iltimos, kuting..._"
        )

    if not reencoded_files:
        return False

    # 2-qadam: concat ro'yxat fayli
    list_file = os.path.join(temp_dir, "_merge_list.txt")
    with open(list_file, "w", encoding="utf-8") as f:
        for fp in reencoded_files:
            f.write(f"file '{os.path.abspath(fp)}'\n")

    await safe_edit(
        f"⚡️ **Yakuniy birlashtirish boshlandi...**\n\n"
        f"📊 `{'█' * 9 + '░'}` 90%\n\n"
        f"_Deyarli tayyor..._"
    )

    # 3-qadam: FFmpeg concat demuxer
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", list_file,
        "-c", "copy",
        "-movflags", "+faststart",
        "-progress", "pipe:1",
        "-nostats",
        output_path
    ]

    # Concat uchun umumiy davomiylikni hisoblash
    total_duration = sum(get_duration(fp) for fp in reencoded_files)

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL
    )

    while True:
        line = await proc.stdout.readline()
        if not line:
            break
        line = line.decode("utf-8", errors="ignore").strip()

        if line.startswith("out_time_ms=") and total_duration > 0:
            try:
                out_time_s = int(line.split("=")[1]) / 1_000_000
                concat_pct = min(int((out_time_s / total_duration) * 10), 10)
                final_pct = 90 + concat_pct
                bar = make_progress_bar(final_pct)
                await safe_edit(
                    f"⚡️ **Yakuniy birlashtirish...**\n\n"
                    f"📊 `{bar}` {final_pct}%\n\n"
                    f"_Deyarli tayyor..._"
                )
            except:
                pass

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
    clean_user(uid)
    user_data[uid] = {
        "mode": "merge",
        "videos": [],
        "type": "merge"
    }
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"✅ Birlashtir (0 ta video)", callback_data="do_merge")],
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

# Download progress callback
async def download_progress(current, total, msg, label):
    if total == 0:
        return
    pct = int(current * 100 / total)
    bar = make_progress_bar(pct)
    # Har 10% da yangilansin (throttle)
    if pct % 10 == 0 or pct >= 99:
        try:
            await msg.edit_text(
                f"📥 **{label} yuklanmoqda...**\n\n"
                f"`{bar}` {pct}%",
                parse_mode=ParseMode.MARKDOWN
            )
        except:
            pass

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
        video_num = idx + 1

        # ── Yuklanmoqda xabari ──
        status_msg = await message.reply_text(
            f"📥 **{video_num}-video qabul qilindi!**\n\n"
            f"`{'░' * 10}` 0%",
            parse_mode=ParseMode.MARKDOWN
        )

        file_path = await message.download(
            file_name=f"downloads/merge_{uid}_{idx}.mp4",
            progress=download_progress,
            progress_args=(status_msg, f"{video_num}-video")
        )

        videos.append(file_path)
        count = len(videos)

        # ── Qabul qilindi xabari ──
        if count < MAX_MERGE_VIDEOS:
            next_msg = f"📤 **{count + 1}-videoni yuboring** yoki birlashtiring."
        else:
            next_msg = f"⚠️ Maksimal {MAX_MERGE_VIDEOS} ta. Endi birlashtiring."

        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                f"✅ Birlashtir ({count} ta video)",
                callback_data="do_merge"
            )],
            [InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel_merge")]
        ])

        await status_msg.edit_text(
            f"✅ **{video_num}-video yuklandi!** ({count} ta jami)\n\n"
            f"`{'█' * 10}` 100%\n\n"
            f"{next_msg}",
            reply_markup=kb,
            parse_mode=ParseMode.MARKDOWN
        )
        return

    # ── ODDIY VIDEO ISHLASH REJIMI ────────────────────────────────────────────
    msg = await message.reply_text(
        "📥 **Video yuklanmoqda...**\n\n`░░░░░░░░░░` 0%",
        parse_mode=ParseMode.MARKDOWN
    )
    file_path = await message.download(
        file_name=f"downloads/vid_{uid}.mp4",
        progress=download_progress,
        progress_args=(msg, "Video")
    )
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

        total = len(videos)
        status = await q.message.edit_text(
            f"⏳ **{total} ta video birlashtirish boshlandi...**\n\n"
            f"📊 `{'░' * 10}` 0%\n\n"
            f"_Iltimos, kuting..._",
            parse_mode=ParseMode.MARKDOWN
        )

        out_path = f"downloads/merged_{uid}.mp4"
        success = await merge_videos_with_progress(videos, out_path, status)

        if success:
            size_mb = round(os.path.getsize(out_path) / (1024 * 1024), 2)
            await status.edit_text(
                f"✅ **Birlashtirish tugadi!**\n\n"
                f"📊 `{'█' * 10}` 100%\n\n"
                f"📤 Video yuborilmoqda...",
                parse_mode=ParseMode.MARKDOWN
            )
            await client.send_video(
                uid,
                out_path,
                caption=(
                    f"✅ **Birlashtirish tayyor!**\n"
                    f"📹 Video soni: {total} ta\n"
                    f"📦 Hajmi: {size_mb} MB"
                ),
                supports_streaming=True
            )
            await status.delete()
            try:
                os.remove(out_path)
            except:
                pass
        else:
            await status.edit_text(
                "❌ Birlashtirish muvaffaqiyatsiz bo'ldi. Qaytadan urinib ko'ring."
            )

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
        if "path" in user_data[uid]:
            try:
                if os.path.exists(user_data[uid]["path"]):
                    os.remove(user_data[uid]["path"])
            except:
                pass
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
