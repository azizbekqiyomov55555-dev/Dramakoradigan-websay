import os
import math
import base64
import asyncio
import subprocess
import time
import requests
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
API_ID    = 37366974
API_HASH  = "08d09c7ed8b7cb414ed6a99c104f1bd6"
BOT_TOKEN = "8630024708:AAGRE2oY2c74wR4mP3U5C298d3k3a7SUEVU"

RAPIDAPI_KEY = "30f65179admsh07b2707861cb0f6p104a91jsn2bb1ee84511f"
SEGMENT_SEC  = 15

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
#  BIRLASHTIRISH
# ──────────────────────────────────────────────

async def merge_with_progress(video_paths: list, out_path: str, status_msg) -> bool:
    total   = len(video_paths)
    tmp_dir = os.path.dirname(out_path)
    reenc   = []
    t       = [time.time()]

    for i, vpath in enumerate(video_paths):
        part_n  = i + 1
        tmp_out = os.path.join(tmp_dir, f"_p{i}.mp4")
        dur     = get_duration(vpath)

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
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL
        )
        while True:
            line = await proc.stdout.readline()
            if not line: break
            line = line.decode("utf-8", errors="ignore").strip()
            if line.startswith("out_time_ms=") and dur > 0:
                try:
                    done_s   = int(line.split("=")[1]) / 1_000_000
                    part_pct = min(int(done_s / dur * 100), 100)
                    overall  = int((i / total) * 90 + (part_pct / total) * 0.9)
                    await safe_edit(
                        status_msg,
                        f"⚙️ *Tayyorlanmoqda...*\n\n"
                        f"🎞 Qism: *{part_n}/{total}*  —  {part_pct}%\n"
                        f"`{make_bar(part_pct)}`\n\n"
                        f"📊 Umumiy: `{make_bar(overall)}` {overall}%",
                        last_t=t
                    )
                except: pass
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
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file,
        "-c", "copy", "-movflags", "+faststart",
        "-progress", "pipe:1", "-nostats", out_path
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL
    )
    while True:
        line = await proc.stdout.readline()
        if not line: break
        line = line.decode("utf-8", errors="ignore").strip()
        if line.startswith("out_time_ms=") and total_dur > 0:
            try:
                done_s = int(line.split("=")[1]) / 1_000_000
                pct    = 90 + min(int(done_s / total_dur * 10), 10)
                await safe_edit(
                    status_msg,
                    f"🔗 *Birlashtirilmoqda...*\n\n📊 `{make_bar(pct)}` {pct}%",
                    last_t=t
                )
            except: pass
    await proc.wait()

    for fp in reenc:
        try: os.remove(fp)
        except: pass
    try: os.remove(list_file)
    except: pass

    return os.path.exists(out_path)

# ──────────────────────────────────────────────
#  CONTENTID BYPASS — AUDIO O'ZGARTIRISH
#  YouTube ContentID audio fingerprint aniqlay
#  olmaydi: pitch shift + EQ + minimal shovqin
# ──────────────────────────────────────────────

async def bypass_contentid(video_path: str, level: str, status_msg) -> str | None:
    """
    level = 'soft' | 'medium' | 'hard'
    soft:   faqat pitch +2% (quloqqa sezilib qolmaydi)
    medium: pitch +3% + hafif EQ + minimal shovqin
    hard:   pitch +4% + EQ + shovqin + tempo biroz o'zgarish
    Qaytaradi: output fayl yoli yoki None
    """
    t       = [time.time()]
    tmp_dir = os.path.dirname(video_path)
    out     = os.path.join(tmp_dir, f"_bypass_{os.path.basename(video_path)}")

    await safe_edit(
        status_msg,
        f"🔧 *ContentID chetlab o'tilmoqda...*\n\n"
        f"Daraja: *{'Yengil' if level=='soft' else 'O\\'rta' if level=='medium' else 'Kuchli'}*\n\n"
        f"`{make_bar(10)}` 10%\n\n"
        f"_Audio qayta ishlanmoqda..._",
        last_t=t, min_gap=0
    )

    # Audio filter tuzish
    if level == "soft":
        # Pitch +2% (quloqqa sezilmaydi, ContentID topolmaydi)
        af = "asetrate=44100*1.02,aresample=44100"

    elif level == "medium":
        # Pitch +3% + EQ (bass biroz kamaytirish) + juda kichik shovqin
        af = (
            "asetrate=44100*1.03,aresample=44100,"
            "equalizer=f=60:width_type=o:width=2:g=-2,"
            "aeval=val(0)+0.0003*random(0)|val(1)+0.0003*random(1):c=stereo"
        )

    else:  # hard
        # Pitch +4% + EQ + shovqin + atempo 0.99 (tempo biroz kamaytirish)
        af = (
            "asetrate=44100*1.04,aresample=44100,"
            "atempo=0.99,"
            "equalizer=f=60:width_type=o:width=2:g=-3,"
            "equalizer=f=8000:width_type=o:width=2:g=-2,"
            "aeval=val(0)+0.0005*random(0)|val(1)+0.0005*random(1):c=stereo"
        )

    total_dur = get_duration(video_path)

    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-af", af,
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        "-progress", "pipe:1", "-nostats",
        out
    ]

    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL
    )

    while True:
        line = await proc.stdout.readline()
        if not line: break
        line = line.decode("utf-8", errors="ignore").strip()
        if line.startswith("out_time_ms=") and total_dur > 0:
            try:
                done_s = int(line.split("=")[1]) / 1_000_000
                pct    = min(int(done_s / total_dur * 100), 100)
                await safe_edit(
                    status_msg,
                    f"🔧 *Audio o'zgartirilmoqda...*\n\n"
                    f"`{make_bar(pct)}` {pct}%",
                    last_t=t
                )
            except: pass

    await proc.wait()

    if os.path.exists(out):
        return out
    return None


# ──────────────────────────────────────────────
#  SHAZAM ORQALI TEKSHIRISH + O'CHIRISH (eski usul)
# ──────────────────────────────────────────────

def acr_check(audio_bytes: bytes) -> dict:
    try:
        resp = requests.post(
            "https://shazam.p.rapidapi.com/songs/v2/detect",
            headers={
                "content-type": "text/plain",
                "X-RapidAPI-Key": RAPIDAPI_KEY,
                "X-RapidAPI-Host": "shazam.p.rapidapi.com"
            },
            data=base64.b64encode(audio_bytes).decode(),
            timeout=20
        )
        res   = resp.json()
        track = res.get("track")
        if track:
            return {
                "found":  True,
                "title":  track.get("title", "Noma'lum"),
                "artist": track.get("subtitle", "?"),
            }
    except: pass
    return {"found": False}


async def remove_copyright(video_path: str, mode: str, status_msg) -> tuple:
    total_dur    = get_duration(video_path)
    num_seg      = math.ceil(total_dur / SEGMENT_SEC)
    found_ranges = []
    found_list   = []
    t            = [time.time()]
    tmp_dir      = os.path.dirname(video_path)

    for i in range(num_seg):
        start    = i * SEGMENT_SEC
        dur      = min(SEGMENT_SEC, total_dur - start)
        seg_path = os.path.join(tmp_dir, f"_acr_{i}.mp3")

        subprocess.run(
            ["ffmpeg", "-y", "-ss", str(start), "-i", video_path,
             "-t", str(dur), "-vn", "-acodec", "libmp3lame", "-q:a", "6", seg_path],
            capture_output=True
        )

        pct = int((i + 1) / num_seg * 60)
        await safe_edit(
            status_msg,
            f"🔍 *Tekshirilmoqda...*\n\nSegment: *{i+1}/{num_seg}*\n`{make_bar(pct)}` {pct}%",
            last_t=t
        )

        with open(seg_path, "rb") as f:
            audio_bytes = f.read()
        try: os.remove(seg_path)
        except: pass

        res = acr_check(audio_bytes)
        if res["found"]:
            found_ranges.append((start, start + dur))
            found_list.append(
                f"  🎵 `{int(start)}s–{int(start+dur)}s` — {res['title']} / {res['artist']}"
            )

    if not found_ranges:
        return None, []

    await safe_edit(
        status_msg,
        f"⚙️ *Qayta ishlanmoqda...*\n\n`{make_bar(70)}` 70%\n\n"
        f"_{len(found_ranges)} ta segment qayta ishlanmoqda..._",
        last_t=t, min_gap=0
    )

    out_path = os.path.join(tmp_dir, f"_cr_out_{os.path.basename(video_path)}")

    if mode == "mute":
        parts = [f"volume=enable='between(t,{s},{e})':volume=0" for s, e in found_ranges]
        af    = ",".join(parts)
        cmd   = [
            "ffmpeg", "-y", "-i", video_path,
            "-af", af, "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
            "-progress", "pipe:1", "-nostats", out_path
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL
        )
        while True:
            line = await proc.stdout.readline()
            if not line: break
            line = line.decode("utf-8", errors="ignore").strip()
            if line.startswith("out_time_ms=") and total_dur > 0:
                try:
                    done_s = int(line.split("=")[1]) / 1_000_000
                    pct    = 70 + min(int(done_s / total_dur * 30), 30)
                    await safe_edit(
                        status_msg,
                        f"⚙️ *Ovoz oʻchirilmoqda...*\n\n`{make_bar(pct)}` {pct}%",
                        last_t=t
                    )
                except: pass
        await proc.wait()

    else:
        keep = []
        prev = 0.0
        for s, e in sorted(found_ranges):
            s2 = max(0.0, s - 1)
            e2 = min(total_dur, e + 1)
            if prev < s2:
                keep.append((prev, s2))
            prev = e2
        if prev < total_dur:
            keep.append((prev, total_dur))
        if not keep:
            return None, found_list

        part_files = []
        for j, (s, e) in enumerate(keep):
            pf = os.path.join(tmp_dir, f"_keep_{j}.mp4")
            subprocess.run(
                ["ffmpeg", "-y", "-ss", str(s), "-i", video_path,
                 "-t", str(e - s), "-c:v", "libx264", "-c:a", "aac",
                 "-avoid_negative_ts", "make_zero", pf],
                capture_output=True
            )
            part_files.append(pf)

        list_file = os.path.join(tmp_dir, "_keep_list.txt")
        with open(list_file, "w") as f:
            for pf in part_files:
                f.write(f"file '{os.path.abspath(pf)}'\n")
        subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
             "-i", list_file, "-c", "copy", out_path],
            capture_output=True
        )
        for pf in part_files:
            try: os.remove(pf)
            except: pass
        try: os.remove(list_file)
        except: pass

    if os.path.exists(out_path):
        return out_path, found_list
    return None, found_list

# ──────────────────────────────────────────────
#  ASOSIY MENYU
# ──────────────────────────────────────────────

def main_kb():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🎬 Kino qismlarini birlashtirish")],
        [KeyboardButton("🎞 Video ishlash"), KeyboardButton("🖼 Rasm ishlash")],
        [KeyboardButton("🚫 YT taqiqini olib tashlash")],
        [KeyboardButton("📊 Statistika"), KeyboardButton("❓ Yordam")]
    ], resize_keyboard=True)

@app.on_message(filters.command("start"))
async def cmd_start(client, message):
    await message.reply_text(
        "👋 *Assalomu alaykum!*\n\n"
        "YouTube taqiqini olib tashlash uchun:\n"
        "👉 *«🚫 YT taqiqini olib tashlash»* tugmasini bosing.",
        reply_markup=main_kb(),
        parse_mode=ParseMode.MARKDOWN
    )

# ──────────────────────────────────────────────
#  KINO BIRLASHTIRISH
# ──────────────────────────────────────────────

@app.on_message(filters.regex("🎬 Kino qismlarini birlashtirish"))
async def start_merge(client, message):
    uid = message.from_user.id
    clean_user(uid)
    user_data[uid] = {"mode": "merge", "videos": []}
    await message.reply_text(
        "🎬 *Kino birlashtirish rejimi yoqildi!*\n\n"
        "📌 Kanaldan videolarni *tartib bilan* yuboring.\n\n"
        f"📦 Maksimal *{MAX_MERGE_VIDEOS}* ta qism.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=merge_keyboard(0)
    )

# ──────────────────────────────────────────────
#  YT TAQIQINI OLIB TASHLASH
# ──────────────────────────────────────────────

@app.on_message(filters.regex("🚫 YT taqiqini olib tashlash"))
async def start_copyright(client, message):
    uid = message.from_user.id
    clean_user(uid)
    user_data[uid] = {"mode": "copyright"}
    await message.reply_text(
        "🚫 *YT taqiqini olib tashlash*\n\n"
        "📌 Video yuboring.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_kb()
    )

# ──────────────────────────────────────────────
#  VIDEO KELGANDA
# ──────────────────────────────────────────────

@app.on_message(filters.video | filters.document)
async def handle_video(client, message):
    if message.document and not message.document.mime_type.startswith("video/"):
        return

    uid = message.from_user.id

    # ── BIRLASHTIRISH ──
    if uid in user_data and user_data[uid].get("mode") == "merge":
        videos  = user_data[uid]["videos"]
        count   = len(videos)
        if count >= MAX_MERGE_VIDEOS:
            await message.reply_text(f"⚠️ Maksimal *{MAX_MERGE_VIDEOS}* ta!", parse_mode=ParseMode.MARKDOWN)
            return

        part_n = count + 1
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
        hint      = (f"📤 Keyingi: *{new_count+1}-qism*ni yuboring yoki birlashtiring."
                     if new_count < MAX_MERGE_VIDEOS
                     else f"⚠️ Maksimal {MAX_MERGE_VIDEOS} ta. Endi birlashtiring.")

        await status.edit_text(
            f"✅ *{part_n}-qism qabul qilindi!*\n\n"
            f"📋 *Qabul qilingan qismlar:*\n{parts_list_text(videos)}\n\n{hint}",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=merge_keyboard(new_count)
        )
        return

    # ── COPYRIGHT REJIMI ──
    if uid in user_data and user_data[uid].get("mode") == "copyright":
        status = await message.reply_text(
            "📥 *Video yuklanmoqda...*\n`░░░░░░░░░░░░` 0%",
            parse_mode=ParseMode.MARKDOWN
        )
        file_path = await message.download(
            file_name=f"downloads/cr_{uid}.mp4",
            progress=dl_progress,
            progress_args=(status, "Video yuklanmoqda")
        )
        user_data[uid]["path"] = file_path

        # Usul tanlash — BYPASS birinchi tavsiya
        await status.edit_text(
            "✅ *Video yuklandi!*\n\n"
            "Qaysi usulni tanlaysiz?\n\n"
            "🔧 *Bypass* — audio ohangni biroz o'zgartiradi,\n"
            "YouTube ContentID topolmaydi _(tavsiya etiladi)_\n\n"
            "🔇 *Aniqlash* — Shazam orqali topib o'chiradi\n"
            "_(faqat Shazam biladigan musiqalar)_",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔧 Bypass (tavsiya)", callback_data="cr_bypass")],
                [
                    InlineKeyboardButton("🔇 Ovozini o'chirish", callback_data="cr_mute"),
                    InlineKeyboardButton("✂️ Kesib tashlash",    callback_data="cr_cut"),
                ],
                [InlineKeyboardButton("❌ Bekor qilish", callback_data="cr_cancel")]
            ])
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
    await msg.edit_text(
        "✅ Video yuklandi. Tanlang:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🗜 Siqish", callback_data="v_comp"),
             InlineKeyboardButton("✂️ Bo'lish", callback_data="v_split")]
        ])
    )

# ──────────────────────────────────────────────
#  CALLBACK HANDLER
# ──────────────────────────────────────────────

@app.on_callback_query()
async def on_callback(client, q):
    uid  = q.from_user.id
    data = q.data

    # ── BIRLASHTIRISH ──
    if data == "cancel_merge":
        clean_user(uid)
        await q.message.edit_text("❌ Birlashtirish bekor qilindi.")
        return

    if data == "do_merge":
        if uid not in user_data or user_data[uid].get("mode") != "merge":
            await q.answer("Ma'lumot topilmadi.", show_alert=True)
            return
        videos = user_data[uid].get("videos", [])
        if len(videos) < 2:
            await q.answer("⚠️ Kamida 2 ta qism!", show_alert=True)
            return

        total     = len(videos)
        parts_txt = parts_list_text(videos)
        status    = await q.message.edit_text(
            f"🎬 *{total} ta qism birlashtirish boshlandi!*\n\n"
            f"📋 *Tartib:*\n{parts_txt}\n\n`{make_bar(0)}` 0%",
            parse_mode=ParseMode.MARKDOWN
        )
        out_path = f"downloads/merged_{uid}.mp4"
        ok       = await merge_with_progress(videos, out_path, status)

        if ok:
            size_mb = round(os.path.getsize(out_path) / (1024*1024), 2)
            await status.edit_text(
                f"✅ *Birlashtirish tugadi!*\n\n📹 {total} ta qism\n📦 {size_mb} MB\n\n📤 Yuborilmoqda...",
                parse_mode=ParseMode.MARKDOWN
            )
            await client.send_video(
                uid, out_path,
                caption=f"🎬 *Kino tayyor!*\n📹 {total} ta qism\n📦 {size_mb} MB",
                supports_streaming=True, parse_mode=ParseMode.MARKDOWN
            )
            await status.delete()
            try: os.remove(out_path)
            except: pass
        else:
            await status.edit_text("❌ Birlashtirish muvaffaqiyatsiz.")

        for vp in videos:
            try: os.remove(vp)
            except: pass
        user_data.pop(uid, None)
        return

    # ── BYPASS CALLBACK ──
    if data == "cr_bypass":
        if uid not in user_data or "path" not in user_data.get(uid, {}):
            await q.answer("Fayl topilmadi.", show_alert=True)
            return
        await q.message.edit_text(
            "🔧 *Bypass darajasini tanlang:*\n\n"
            "🟢 *Yengil* — +2% pitch, quloqqa sezilib qolmaydi\n"
            "🟡 *O'rta* — +3% pitch + EQ _(ko'p hollarda yetarli)_\n"
            "🔴 *Kuchli* — +4% pitch + EQ + shovqin\n"
            "_(ovoz biroz o'zgaradi lekin taqiq bo'lmaydi)_",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🟢 Yengil",  callback_data="bp_soft")],
                [InlineKeyboardButton("🟡 O'rta",   callback_data="bp_medium")],
                [InlineKeyboardButton("🔴 Kuchli",  callback_data="bp_hard")],
                [InlineKeyboardButton("❌ Bekor",   callback_data="cr_cancel")],
            ])
        )
        return

    if data in ("bp_soft", "bp_medium", "bp_hard"):
        if uid not in user_data or "path" not in user_data.get(uid, {}):
            await q.answer("Fayl topilmadi.", show_alert=True)
            return

        level      = data.split("_")[1]
        level_text = {"soft": "🟢 Yengil", "medium": "🟡 O'rta", "hard": "🔴 Kuchli"}[level]
        video_path = user_data[uid]["path"]

        status = await q.message.edit_text(
            f"🔧 *ContentID chetlab o'tilmoqda...*\n\nDaraja: {level_text}\n\n`{make_bar(0)}` 0%",
            parse_mode=ParseMode.MARKDOWN
        )

        out_path = await bypass_contentid(video_path, level, status)

        if not out_path:
            await status.edit_text("❌ Xato yuz berdi. Qaytadan urinib ko'ring.")
            clean_user(uid)
            return

        size_mb = round(os.path.getsize(out_path) / (1024*1024), 2)
        await status.edit_text(
            f"✅ *Tayyor!*\n\n📦 Hajmi: *{size_mb} MB*\n📤 *Yuborilmoqda...*",
            parse_mode=ParseMode.MARKDOWN
        )
        await client.send_video(
            uid, out_path,
            caption=(
                f"🚫 *ContentID bypass qilindi!*\n"
                f"🔧 Daraja: {level_text}\n"
                f"📦 Hajmi: {size_mb} MB\n\n"
                f"✅ Endi YouTube'ga yuklay olasiz!"
            ),
            supports_streaming=True,
            parse_mode=ParseMode.MARKDOWN
        )
        try: os.remove(out_path)
        except: pass
        await status.delete()
        clean_user(uid)
        return

    # ── ANIQLASH + O'CHIRISH ──
    if data == "cr_cancel":
        clean_user(uid)
        await q.message.edit_text("❌ Bekor qilindi.")
        return

    if data in ("cr_mute", "cr_cut"):
        if uid not in user_data or "path" not in user_data.get(uid, {}):
            await q.answer("Fayl topilmadi.", show_alert=True)
            return

        mode       = "mute" if data == "cr_mute" else "cut"
        mode_text  = "Ovoz o'chirish" if mode == "mute" else "Kesib tashlash"
        video_path = user_data[uid]["path"]

        status = await q.message.edit_text(
            f"🔍 *Tekshirilmoqda...*\n\nRejim: *{mode_text}*\n`{make_bar(0)}` 0%",
            parse_mode=ParseMode.MARKDOWN
        )

        out_path, found_list = await remove_copyright(video_path, mode, status)

        if not found_list:
            await status.edit_text(
                "⚠️ *Shazam topolmadi.*\n\n"
                "YouTube ContentID boshqacha ishlaydi.\n"
                "«🔧 Bypass» usulini ishlatib ko'ring!",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔧 Bypass usulini ishlatish", callback_data="cr_bypass")]
                ])
            )
            return

        if out_path is None:
            await status.edit_text("❌ Videoning barcha qismlari taqiqlangan.")
            clean_user(uid)
            return

        size_mb    = round(os.path.getsize(out_path) / (1024*1024), 2)
        found_text = "\n".join(found_list)

        await status.edit_text(
            f"✅ *{len(found_list)} ta segment qayta ishlandi!*\n\n"
            f"🎵 *Topilgan joylar:*\n{found_text}\n\n"
            f"📦 {size_mb} MB\n📤 *Yuborilmoqda...*",
            parse_mode=ParseMode.MARKDOWN
        )
        await client.send_video(
            uid, out_path,
            caption=f"🚫 *Taqiq olib tashlandi!*\n📌 {mode_text}\n🎵 {len(found_list)} segment\n📦 {size_mb} MB",
            supports_streaming=True, parse_mode=ParseMode.MARKDOWN
        )
        try: os.remove(out_path)
        except: pass
        await status.delete()
        clean_user(uid)
        return

    # ── VIDEO SIQISH / BO'LISH ──
    if data == "v_comp":
        if uid not in user_data:
            await q.answer("Ma'lumot topilmadi.", show_alert=True)
            return
        await q.message.edit_text("🗜 *Necha MB bo'lsin?* (Faqat raqam):", parse_mode=ParseMode.MARKDOWN)
        user_data[uid]["action"] = "wait_v_size"

    elif data == "v_split":
        if uid not in user_data:
            await q.answer("Ma'lumot topilmadi.", show_alert=True)
            return
        await q.message.edit_text("✂️ *Nechta qismga bo'linsin?* (Faqat raqam):", parse_mode=ParseMode.MARKDOWN)
        user_data[uid]["action"] = "wait_v_split"

# ──────────────────────────────────────────────
#  MATN INPUT
# ──────────────────────────────────────────────

@app.on_message(filters.text & filters.private & ~filters.regex("^(🎬|🎞|🖼|📊|❓|🚫)"))
async def text_input(client, message):
    uid = message.from_user.id
    if uid not in user_data or "action" not in user_data[uid]:
        return
    action = user_data[uid]["action"]
    path   = user_data[uid].get("path", "")

    if action == "wait_v_size":
        try:
            target = int(message.text.strip())
            st     = await message.reply_text(f"⏳ {target} MB ga siqilmoqda...")
            out    = f"downloads/res_{uid}.mp4"
            dur    = get_duration(path)
            if dur > 0:
                vb  = max(int((target * 8000) / dur - 128), 200)
                cmd = [
                    "ffmpeg", "-y", "-i", path,
                    "-vf", "scale=-2:720", "-c:v", "libx264", "-b:v", f"{vb}k",
                    "-preset", "fast", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", out
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
            parts    = int(message.text.strip())
            if parts < 2 or parts > 20:
                await message.reply_text("❌ 2 dan 20 gacha son kiriting.")
                return
            st       = await message.reply_text(f"⏳ {parts} qismga bo'linmoqda...")
            dur      = get_duration(path)
            part_dur = dur / parts
            sent     = 0
            for p in range(parts):
                start = p * part_dur
                out   = f"downloads/split_{uid}_{p+1}.mp4"
                cmd   = [
                    "ffmpeg", "-y", "-ss", str(start), "-t", str(part_dur),
                    "-i", path, "-c", "copy", "-map", "0", "-movflags", "+faststart", out
                ]
                proc = await asyncio.create_subprocess_exec(
                    *cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL
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
        f"📊 *Statistika:*\n\n👥 Faol seans: {len(user_data)} ta\n🤖 Bot holati: Ishlamoqda ✅",
        parse_mode=ParseMode.MARKDOWN
    )

@app.on_message(filters.regex("❓ Yordam"))
async def help_msg(client, message):
    await message.reply_text(
        "❓ *Yordam:*\n\n"
        "🚫 *YT taqiqini olib tashlash:*\n"
        "1. «🚫 YT taqiqini olib tashlash» tugmasini bosing\n"
        "2. Video yuboring\n"
        "3. *«🔧 Bypass»* tanlang _(eng samarali)_\n"
        "4. Daraja tanlang: Yengil / O'rta / Kuchli\n"
        "5. Bot videoni qayta ishlab beradi ✅\n\n"
        "🎬 *Kino birlashtirish:*\n"
        "Videolarni tartib bilan yuboring → Birlashtir\n\n"
        f"📦 Maksimal: *{MAX_MERGE_VIDEOS}* ta qism",
        parse_mode=ParseMode.MARKDOWN
    )

@app.on_message(filters.regex("🎞 Video ishlash"))
async def video_mode_msg(client, message):
    await message.reply_text("🎞 *Video ishlash:*\n\nVideo yuboring.", parse_mode=ParseMode.MARKDOWN)

@app.on_message(filters.regex("🖼 Rasm ishlash"))
async def image_mode_msg(client, message):
    await message.reply_text("🖼 *Rasm ishlash:*\n\nRasm yuboring.", parse_mode=ParseMode.MARKDOWN)

# ──────────────────────────────────────────────
#  CLEAN
# ──────────────────────────────────────────────

def clean_user(uid):
    if uid not in user_data:
        return
    if "path" in user_data[uid]:
        try:
            p = user_data[uid]["path"]
            if os.path.exists(p): os.remove(p)
        except: pass
    for vp in user_data[uid].get("videos", []):
        try:
            if os.path.exists(vp): os.remove(vp)
        except: pass
    del user_data[uid]

# ──────────────────────────────────────────────
#  RUN
# ──────────────────────────────────────────────

if __name__ == "__main__":
    os.makedirs("downloads", exist_ok=True)
    print("🤖 Bot ishga tushdi!")
    app.run()
