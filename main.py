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
user_locks = {}  # Har bir user uchun alohida Lock

MAX_MERGE_VIDEOS = 150


def get_user_lock(uid):
    """Har bir foydalanuvchi uchun asyncio.Lock qaytaradi."""
    if uid not in user_locks:
        user_locks[uid] = asyncio.Lock()
    return user_locks[uid]


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


# --- VIDEO BIRLASHTIRISH ---

async def merge_videos(video_paths: list, output_path: str) -> bool:
    if not video_paths:
        return False

    temp_dir = os.path.dirname(output_path)
    reencoded_files = []

    # Parallel re-encode: barcha videolarni bir vaqtda qayta kodlash
    async def reencode(i, vpath):
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
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL
        )
        await proc.wait()
        return (i, temp_out) if os.path.exists(temp_out) else (i, None)

    # Bir vaqtda max 8 ta ffmpeg jarayoni (server resurs limiti)
    semaphore = asyncio.Semaphore(8)

    async def reencode_limited(i, vpath):
        async with semaphore:
            return await reencode(i, vpath)

    tasks = [reencode_limited(i, vpath) for i, vpath in enumerate(video_paths)]
    results = await asyncio.gather(*tasks)

    # Tartibni saqlagan holda fayllarni yig'ish
    results_sorted = sorted(results, key=lambda x: x[0])
    reencoded_files = [r[1] for r in results_sorted if r[1] is not None]

    if not reencoded_files:
        return False

    # Concat ro'yxat fayli
    list_file = os.path.join(temp_dir, "_merge_list.txt")
    with open(list_file, "w", encoding="utf-8") as f:
        for fp in reencoded_files:
            f.write(f"file '{os.path.abspath(fp)}'\n")

    # Birlashtirish
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", list_file,
        "-c", "copy",
        "-movflags", "+faststart",
        output_path
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL
    )
    await proc.wait()

    # Tozalash
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
        draw.text((w / 2, h - 50), text, fill="white", font=font, anchor="ms", stroke_width=2, stroke_fill="black")
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
        f"• Kanaldan 100-150 ta videoni tanlang va **forward** qiling (birdaniga).\n"
        "• Bot ularni parallel yuklab oladi.\n"
        f"• Yuklash tugagach «✅ Birlashtir» tugmasini bosing.\n"
        f"• Maksimal: {MAX_MERGE_VIDEOS} ta video."
    )


# --- BIRLASHTIRISH REJIMINI BOSHLASH ---

@app.on_message(filters.regex("🔗 Videolarni birlashtirish"))
async def start_merge_mode(client, message):
    uid = message.from_user.id
    async with get_user_lock(uid):
        clean_user(uid)
        user_data[uid] = {
            "mode": "merge",
            "videos": [],        # (index, path) juftliklari
            "recv_count": 0,     # Qabul qilingan video soni (tartib uchun)
            "type": "merge",
            "status_msg_id": None
        }

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Birlashtir (0 ta video)", callback_data="do_merge")],
        [InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel_merge")]
    ])
    sent = await message.reply_text(
        f"🔗 **Video birlashtirish rejimi yoqildi!**\n\n"
        f"Kanaldan {MAX_MERGE_VIDEOS} tagacha videoni tanlang va **forward** qiling.\n"
        f"Bot ularni bir vaqtda yuklab oladi ⚡\n\n"
        f"📥 Yuklangan: **0** ta",
        reply_markup=kb
    )
    # Status xabarini eslab qolish (keyinchalik yangilash uchun)
    async with get_user_lock(uid):
        if uid in user_data:
            user_data[uid]["status_msg_id"] = sent.id
            user_data[uid]["status_msg"] = sent


# --- VIDEO QABUL QILISH (PARALLEL) ---

@app.on_message(filters.video | filters.document)
async def handle_video(client, message):
    if message.document and not message.document.mime_type.startswith("video/"):
        return

    uid = message.from_user.id

    # ── BIRLASHTIRISH REJIMI ──────────────────────────────────────────────────
    if uid in user_data and user_data[uid].get("mode") == "merge":

        # Lock bilan video indeksini atomik olish
        async with get_user_lock(uid):
            if uid not in user_data or user_data[uid].get("mode") != "merge":
                return
            videos = user_data[uid]["videos"]
            if len(videos) >= MAX_MERGE_VIDEOS:
                await message.reply_text(
                    f"⚠️ Maksimal {MAX_MERGE_VIDEOS} ta to'ldi! «✅ Birlashtir» tugmasini bosing."
                )
                return
            # Ushbu video uchun joy ajratish (tartib saqlash uchun)
            idx = user_data[uid]["recv_count"]
            user_data[uid]["recv_count"] += 1
            user_data[uid]["videos"].append(None)  # placeholder

        # ── PARALLEL YUKLASH: Lock tashqarisida ──────────────────────────────
        file_path = await message.download(
            file_name=f"downloads/merge_{uid}_{idx}.mp4"
        )

        # Yuklash tugagach — natijani joyiga qo'yish
        async with get_user_lock(uid):
            if uid not in user_data or user_data[uid].get("mode") != "merge":
                # Rejim o'chirilgan — faylni o'chirish
                try:
                    if file_path and os.path.exists(file_path):
                        os.remove(file_path)
                except:
                    pass
                return

            user_data[uid]["videos"][idx] = file_path
            count = sum(1 for v in user_data[uid]["videos"] if v is not None)
            total_reserved = len(user_data[uid]["videos"])

            # Status xabarini yangilash
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    f"✅ Birlashtir ({count} ta tayyor / {total_reserved} ta yuklanyapti)",
                    callback_data="do_merge"
                )],
                [InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel_merge")]
            ])
            status_msg = user_data[uid].get("status_msg")
            if status_msg:
                try:
                    await status_msg.edit_text(
                        f"🔗 **Video birlashtirish rejimi**\n\n"
                        f"📥 Yuklangan: **{count}** ta ✅\n"
                        f"⏳ Yuklanmoqda: **{total_reserved - count}** ta\n"
                        f"📊 Jami: {total_reserved} / {MAX_MERGE_VIDEOS}",
                        reply_markup=kb
                    )
                except:
                    pass

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


# --- RASM QABUL QILISH ---

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


# --- CALLBACKS ---

@app.on_callback_query()
async def callback_handler(client, q):
    uid = q.from_user.id
    data = q.data

    # ── BIRLASHTIRISH BEKOR QILISH ───────────────────────────────────────────
    if data == "cancel_merge":
        async with get_user_lock(uid):
            clean_user(uid)
        await q.message.edit_text("❌ Birlashtirish bekor qilindi.")
        return

    # ── BIRLASHTIRISH BOSHLASH ───────────────────────────────────────────────
    if data == "do_merge":
        async with get_user_lock(uid):
            if uid not in user_data or user_data[uid].get("mode") != "merge":
                await q.answer("Ma'lumot topilmadi, qaytadan boshlang.", show_alert=True)
                return

            videos_raw = user_data[uid].get("videos", [])
            # Faqat yuklab bo'lingan (None bo'lmagan) fayllarni olish
            videos = [v for v in videos_raw if v is not None]

        if len(videos) < 2:
            await q.answer("⚠️ Kamida 2 ta video yuklanishi kerak! Kuting...", show_alert=True)
            return

        # Hali yuklanayotgan bor-yo'qligini tekshirish
        async with get_user_lock(uid):
            total_reserved = len(user_data[uid]["videos"]) if uid in user_data else 0
            still_loading = total_reserved - len(videos)

        if still_loading > 0:
            await q.answer(
                f"⏳ Hali {still_loading} ta video yuklanmoqda. Kuting yoki hozirgi {len(videos)} ta bilan davom eting.",
                show_alert=True
            )
            # Agar foydalanuvchi birlashtirish tugmasini bosgan bo'lsa,
            # faqat yuklab bo'linganlarni birlashtirish uchun davom etamiz

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
                caption=(
                    f"✅ **Birlashtirish tayyor!**\n"
                    f"📹 Video soni: {len(videos)} ta\n"
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
            await status.edit_text("❌ Birlashtirish muvaffaqiyatsiz bo'ldi. Qaytadan urinib ko'ring.")

        async with get_user_lock(uid):
            clean_user(uid)
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


# --- MATN KIRITISH ---

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


# --- TOZALASH ---

def clean_user(uid):
    if uid in user_data:
        if "path" in user_data[uid]:
            try:
                if os.path.exists(user_data[uid]["path"]):
                    os.remove(user_data[uid]["path"])
            except:
                pass
        for vp in user_data[uid].get("videos", []):
            if vp:
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
