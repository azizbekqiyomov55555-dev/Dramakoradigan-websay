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

add_paths()

# --- SOZLAMALAR ---
API_ID = 37366974
API_HASH = "08d09c7ed8b7cb414ed6a99c104f1bd6"
BOT_TOKEN = "8630024708:AAGRE2oY2c74wR4mP3U5C298d3k3a7SUEVU"

app = Client("video_processor", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

user_data = {}
MAX_MERGE_VIDEOS = 150

# ──────────────────────────────────────────────
#  YORDAMCHI
# ──────────────────────────────────────────────

def make_bar(pct, n=12):
    f = int(n * pct / 100)
    return "█" * f + "░" * (n - f)

def get_duration(path):
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )
        return float(r.stdout.strip())
    except:
        return 0

def parts_list_text(videos):
    lines = [f"  ✅ {i+1}-qism" for i in range(len(videos))]
    return "\n".join(lines) if lines else "  (hali yo'q)"

def merge_keyboard(count):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🎬 Birlashtir  ({count} ta qism)", callback_data="do_merge")],
        [InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel_merge")]
    ])

async def safe_edit(msg, text, kb=None, last_t=None, min_gap=2.5):
    now = time.time()
    if last_t is not None and now - last_t[0] < min_gap:
        return
    try:
        await msg.edit_text(text, parse_mode=ParseMode.MARKDOWN,
                            reply_markup=kb, disable_web_page_preview=True)
        if last_t is not None:
            last_t[0] = now
    except:
        pass

# ──────────────────────────────────────────────
#  DOWNLOAD PROGRESS
# ──────────────────────────────────────────────

_dl_last: dict = {}

async def dl_progress(current, total, msg, label):
    if not total:
        return
    uid = id(msg)
    now = time.time()
    if now - _dl_last.get(uid, 0) < 2.0:
        return
    _dl_last[uid] = now
    pct = int(current * 100 / total)
    try:
        await msg.edit_text(
            f"📥 *{label}*\n`{make_bar(pct)}` {pct}%",
            parse_mode=ParseMode.MARKDOWN
        )
    except:
        pass

# ──────────────────────────────────────────────
#  BIRLASHTIRISH (PROGRESS BILAN)
# ──────────────────────────────────────────────

async def merge_with_progress(video_paths: list, out_path: str, status_msg) -> bool:
    total = len(video_paths)
    tmp_dir = os.path.dirname(out_path)
    reenc = []
    t = [time.time()]

    # 1-bosqich: Har qismni re-encode
    for i, vpath in enumerate(video_paths):
        part_n = i + 1
        tmp_out = os.path.join(tmp_dir, f"_p{i}.mp4")
        dur = get_duration(vpath)

        cmd = [
            "ffmpeg", "-y", "-i", vpath,
            "-vf", "scale=-2:720",
            "-c:v", "libx264", "-preset", "fast",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            "-progress", "pipe:1", "-nostats",
            tmp_out
        ]
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
            if line.startswith("out_time_ms=") and dur > 0:
                try:
                    done_s = int(line.split("=")[1]) / 1_000_000
                    part_pct = min(int(done_s / dur * 100), 100)
                    overall = int((i / total) * 90 + (part_pct / total) * 0.9)
                    await safe_edit(
                        status_msg,
                        f"⚙️ *Tayyorlanmoqda...*\n\n"
                        f"🎞 Qism: *{part_n}/{total}*  —  {part_pct}%\n"
                        f"`{make_bar(part_pct)}`\n\n"
                        f"📊 Umumiy: `{make_bar(overall)}` {overall}%",
                        last_t=t
                    )
                except:
                    pass

        await proc.wait()
        if os.path.exists(tmp_out):
            reenc.append(tmp_out)

        done_overall = int(((i + 1) / total) * 90)
        await safe_edit(
            status_msg,
            f"⚙️ *Tayyorlanmoqda...*\n\n"
            f"✅ Tayyor: *{i+1}/{total}* qism\n\n"
            f"📊 Umumiy: `{make_bar(done_overall)}` {done_overall}%",
            last_t=t
        )

    if not reenc:
        return False

    # 2-bosqich: Concat
    list_file = os.path.join(tmp_dir, "_list.txt")
    with open(list_file, "w", encoding="utf-8") as f:
        for fp in reenc:
            f.write(f"file '{os.path.abspath(fp)}'\n")

    await safe_edit(
        status_msg,
        f"🔗 *Qismlar birlashtirilmoqda...*\n\n"
        f"📊 `{make_bar(90)}` 90%\n\n_Deyarli tayyor..._",
        last_t=t, min_gap=0
    )

    total_dur = sum(get_duration(fp) for fp in reenc)

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", list_file,
        "-c", "copy", "-movflags", "+faststart",
        "-progress", "pipe:1", "-nostats",
        out_path
    ]
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
        if line.startswith("out_time_ms=") and total_dur > 0:
            try:
                done_s = int(line.split("=")[1]) / 1_000_000
                extra = min(int(done_s / total_dur * 10), 10)
                pct = 90 + extra
                await safe_edit(
                    status_msg,
                    f"🔗 *Birlashtirilmoqda...*\n\n"
                    f"📊 `{make_bar(pct)}` {pct}%",
                    last_t=t
                )
            except:
                pass

    await proc.wait()

    for fp in reenc:
        try: os.remove(fp)
        except: pass
    try: os.remove(list_file)
    except: pass

    return os.path.exists(out_path)

# ──────────────────────────────────────────────
#  ASOSIY MENYU
# ──────────────────────────────────────────────

def main_kb():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🎬 Kino qismlarini birlashtirish")],
        [KeyboardButton("🎞 Video ishlash"), KeyboardButton("🖼 Rasm ishlash")],
        [KeyboardButton("📊 Statistika"), KeyboardButton("❓ Yordam")]
    ], resize_keyboard=True)

@app.on_message(filters.command("start"))
async def cmd_start(client, message):
    await message.reply_text(
        "👋 *Assalomu alaykum!*\n\n"
        "Kino qismlarini birlashtirish uchun:\n"
        "👉 *«🎬 Kino qismlarini birlashtirish»* tugmasini bosing,\n"
        "keyin kanaldan videolarni tartib bilan yuboring.",
        reply_markup=main_kb(),
        parse_mode=ParseMode.MARKDOWN
    )

# ──────────────────────────────────────────────
#  KINO BIRLASHTIRISH REJIMI
# ──────────────────────────────────────────────

@app.on_message(filters.regex("🎬 Kino qismlarini birlashtirish"))
async def start_merge(client, message):
    uid = message.from_user.id
    clean_user(uid)
    user_data[uid] = {"mode": "merge", "videos": []}
    await message.reply_text(
        "🎬 *Kino birlashtirish rejimi yoqildi!*\n\n"
        "📌 Kanaldan videolarni *tartib bilan* yuboring:\n"
        "1-qism → 2-qism → 3-qism → ...\n\n"
        f"📦 Maksimal *{MAX_MERGE_VIDEOS}* ta qism qabul qilinadi.\n\n"
        "Hammasi yuborilgach *«🎬 Birlashtir»* tugmasini bosing.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=merge_keyboard(0)
    )

# ──────────────────────────────────────────────
#  VIDEO KELGANDA
# ──────────────────────────────────────────────

@app.on_message(filters.video | filters.document)
async def handle_video(client, message):
    if message.document and not message.document.mime_type.startswith("video/"):
        return

    uid = message.from_user.id

    # ── BIRLASHTIRISH REJIMI ──
    if uid in user_data and user_data[uid].get("mode") == "merge":
        videos = user_data[uid]["videos"]
        count = len(videos)

        if count >= MAX_MERGE_VIDEOS:
            await message.reply_text(
                f"⚠️ Maksimal *{MAX_MERGE_VIDEOS}* ta qism!\n"
                "«🎬 Birlashtir» tugmasini bosing.",
                parse_mode=ParseMode.MARKDOWN
            )
            return

        part_n = count + 1

        # Yuklanmoqda xabari
        status = await message.reply_text(
            f"📥 *{part_n}-qism yuklanmoqda...*\n`{make_bar(0)}` 0%",
            parse_mode=ParseMode.MARKDOWN
        )

        file_path = await message.download(
            file_name=f"downloads/merge_{uid}_{count}.mp4",
            progress=dl_progress,
            progress_args=(status, f"{part_n}-qism yuklanmoqda")
        )

        videos.append(file_path)
        new_count = len(videos)

        if new_count < MAX_MERGE_VIDEOS:
            hint = f"📤 Keyingi: *{new_count+1}-qism*ni yuboring yoki birlashtiring."
        else:
            hint = f"⚠️ Maksimal {MAX_MERGE_VIDEOS} ta. Endi birlashtiring."

        parts_txt = parts_list_text(videos)

        await status.edit_text(
            f"✅ *{part_n}-qism qabul qilindi!*\n\n"
            f"📋 *Qabul qilingan qismlar:*\n{parts_txt}\n\n"
            f"{hint}",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=merge_keyboard(new_count)
        )
        return

    # ── ODDIY VIDEO REJIMI ──
    msg = await message.reply_text(
        "📥 *Video yuklanmoqda...*\n`░░░░░░░░░░░░` 0%",
        parse_mode=ParseMode.MARKDOWN
    )
    file_path = await message.download(
        file_name=f"downloads/vid_{uid}.mp4",
        progress=dl_progress,
        progress_args=(msg, "Video yuklanmoqda")
    )
    user_data[uid] = {
        "path": file_path,
        "type": "video",
        "orig_size": round(os.path.getsize(file_path) / (1024*1024), 2)
    }
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🗜 Siqish", callback_data="v_comp"),
         InlineKeyboardButton("✂️ Bo'lish", callback_data="v_split")]
    ])
    await msg.edit_text("✅ Video yuklandi. Tanlang:", reply_markup=kb)

# ──────────────────────────────────────────────
#  CALLBACK HANDLER
# ──────────────────────────────────────────────

@app.on_callback_query()
async def on_callback(client, q):
    uid = q.from_user.id
    data = q.data

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
            await q.answer("⚠️ Kamida 2 ta qism yuboring!", show_alert=True)
            return

        total = len(videos)
        parts_txt = parts_list_text(videos)

        status = await q.message.edit_text(
            f"🎬 *{total} ta qism birlashtirish boshlandi!*\n\n"
            f"📋 *Tartib:*\n{parts_txt}\n\n"
            f"📊 `{make_bar(0)}` 0%\n\n_Iltimos, kuting..._",
            parse_mode=ParseMode.MARKDOWN
        )

        out_path = f"downloads/merged_{uid}.mp4"
        ok = await merge_with_progress(videos, out_path, status)

        if ok:
            size_mb = round(os.path.getsize(out_path) / (1024*1024), 2)
            await status.edit_text(
                f"✅ *Birlashtirish tugadi!*\n\n"
                f"📹 Qismlar: *{total}* ta\n"
                f"📦 Hajmi: *{size_mb} MB*\n\n"
                f"📤 Yuborilmoqda...",
                parse_mode=ParseMode.MARKDOWN
            )
            await client.send_video(
                uid, out_path,
                caption=(
                    f"🎬 *Kino tayyor!*\n"
                    f"📹 {total} ta qism birlashtirildi\n"
                    f"📦 Hajmi: {size_mb} MB"
                ),
                supports_streaming=True,
                parse_mode=ParseMode.MARKDOWN
            )
            await status.delete()
            try: os.remove(out_path)
            except: pass
        else:
            await status.edit_text(
                "❌ Birlashtirish muvaffaqiyatsiz bo'ldi.\n"
                "Qaytadan urinib ko'ring."
            )

        for vp in videos:
            try: os.remove(vp)
            except: pass
        user_data.pop(uid, None)
        return

    if data == "v_comp":
        if uid not in user_data:
            await q.answer("Ma'lumot topilmadi.", show_alert=True)
            return
        await q.message.edit_text("🗜 *Necha MB bo'lsin?* (Faqat raqam yozing):",
                                   parse_mode=ParseMode.MARKDOWN)
        user_data[uid]["action"] = "wait_v_size"

    elif data == "v_split":
        if uid not in user_data:
            await q.answer("Ma'lumot topilmadi.", show_alert=True)
            return
        await q.message.edit_text("✂️ *Nechta qismga bo'linsin?* (Faqat raqam):",
                                   parse_mode=ParseMode.MARKDOWN)
        user_data[uid]["action"] = "wait_v_split"

# ──────────────────────────────────────────────
#  MATN INPUT
# ──────────────────────────────────────────────

@app.on_message(filters.text & filters.private & ~filters.regex(
    "^(🎬|🎞|🖼|📊|❓)"
))
async def text_input(client, message):
    uid = message.from_user.id
    if uid not in user_data or "action" not in user_data[uid]:
        return
    action = user_data[uid]["action"]
    path = user_data[uid].get("path", "")

    if action == "wait_v_size":
        try:
            target = int(message.text.strip())
            st = await message.reply_text(f"⏳ {target} MB ga siqilmoqda...")
            out = f"downloads/res_{uid}.mp4"
            dur = get_duration(path)
            if dur > 0:
                vb = max(int((target * 8000) / dur - 128), 200)
                cmd = [
                    "ffmpeg", "-y", "-i", path,
                    "-vf", "scale=-2:720",
                    "-c:v", "libx264", "-b:v", f"{vb}k",
                    "-preset", "fast", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "128k",
                    "-movflags", "+faststart", out
                ]
                proc = await asyncio.create_subprocess_exec(*cmd)
                await proc.wait()
            if os.path.exists(out):
                await message.reply_video(out, caption=f"✅ Tayyor! ~{target} MB")
                await st.delete()
                try: os.remove(out)
                except: pass
            else:
                await st.edit_text("❌ Siqib bo'lmadi.")
            clean_user(uid)
        except:
            await message.reply_text("❌ Faqat son kiriting!")

    elif action == "wait_v_split":
        try:
            parts = int(message.text.strip())
            if parts < 2 or parts > 20:
                await message.reply_text("❌ 2 dan 20 gacha son kiriting.")
                return
            st = await message.reply_text(f"⏳ {parts} qismga bo'linmoqda...")
            dur = get_duration(path)
            part_dur = dur / parts
            sent = 0
            for p in range(parts):
                start = p * part_dur
                out = f"downloads/split_{uid}_{p+1}.mp4"
                cmd = [
                    "ffmpeg", "-y",
                    "-ss", str(start), "-t", str(part_dur),
                    "-i", path, "-c", "copy", "-map", "0",
                    "-movflags", "+faststart", out
                ]
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL
                )
                await proc.wait()
                if os.path.exists(out):
                    await message.reply_video(out, caption=f"✂️ {p+1}-qism / {parts}")
                    try: os.remove(out)
                    except: pass
                    sent += 1
            await st.edit_text(f"✅ {sent} ta qism yuborildi.")
            clean_user(uid)
        except:
            await message.reply_text("❌ Xato!")

# ──────────────────────────────────────────────
#  STATISTIKA / YORDAM
# ──────────────────────────────────────────────

@app.on_message(filters.regex("📊 Statistika"))
async def stats(client, message):
    await message.reply_text(
        f"📊 *Statistika:*\n\n"
        f"👥 Faol seans: {len(user_data)} ta\n"
        f"🤖 Bot holati: Ishlamoqda ✅",
        parse_mode=ParseMode.MARKDOWN
    )

@app.on_message(filters.regex("❓ Yordam"))
async def help_msg(client, message):
    await message.reply_text(
        "❓ *Yordam:*\n\n"
        "🎬 *Kino qismlarini birlashtirish:*\n"
        "1. «🎬 Kino qismlarini birlashtirish» tugmasini bosing\n"
        "2. Kanaldan videolarni *tartib bilan* yuboring (1→2→3...)\n"
        "3. «🎬 Birlashtir» tugmasini bosing\n"
        "4. Bot ularni tartib bo'yicha birlashtiradi ✅\n\n"
        "🎞 *Video siqish/bo'lish:*\n"
        "Video yuboring → amallardan birini tanlang\n\n"
        f"📦 Maksimal: *{MAX_MERGE_VIDEOS}* ta qism",
        parse_mode=ParseMode.MARKDOWN
    )

@app.on_message(filters.regex("🎞 Video ishlash"))
async def video_mode_msg(client, message):
    await message.reply_text("🎞 *Video ishlash:*\n\nVideo yuboring.",
                              parse_mode=ParseMode.MARKDOWN)

@app.on_message(filters.regex("🖼 Rasm ishlash"))
async def image_mode_msg(client, message):
    await message.reply_text("🖼 *Rasm ishlash:*\n\nRasm yuboring.",
                              parse_mode=ParseMode.MARKDOWN)

# ──────────────────────────────────────────────
#  CLEAN
# ──────────────────────────────────────────────

def clean_user(uid):
    if uid not in user_data:
        return
    if "path" in user_data[uid]:
        try:
            p = user_data[uid]["path"]
            if os.path.exists(p):
                os.remove(p)
        except: pass
    for vp in user_data[uid].get("videos", []):
        try:
            if os.path.exists(vp):
                os.remove(vp)
        except: pass
    del user_data[uid]

# ──────────────────────────────────────────────
#  RUN
# ──────────────────────────────────────────────

if __name__ == "__main__":
    os.makedirs("downloads", exist_ok=True)
    print("🤖 Bot ishga tushdi!")
    app.run()
