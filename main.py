import os
import math
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
from pyrogram.enums import ParseMode, ButtonStyle
from static_ffmpeg import add_paths

add_paths()

# ──────────────────────────────────────────────
#  SOZLAMALAR
# ──────────────────────────────────────────────

API_ID    = 37366974
API_HASH  = "08d09c7ed8b7cb414ed6a99c104f1bd6"
BOT_TOKEN = "8766213463:AAGtuC1RWpd-QCCb6oLMOjYDH553Pbam8V0"

RAPIDAPI_KEY     = "30f65179admsh07b2707861cb0f6p104a91jsn2bb1ee84511f"
SEGMENT_SEC      = 15
MAX_MERGE_VIDEOS = 500

app = Client("video_processor", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

user_data = {}

# ──────────────────────────────────────────────
#  YORDAMCHI FUNKSIYALAR
# ──────────────────────────────────────────────

def make_bar(pct, n=12):
    f      = int(n * pct / 100)
    filled = "🟩" * f
    empty  = "⬜" * (n - f)
    return filled + empty

def get_duration(path):
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=30
        )
        return float(r.stdout.strip())
    except:
        return 0

def get_video_info(path):
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error",
             "-select_streams", "v:0",
             "-show_entries", "stream=width,height",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=30
        )
        lines  = r.stdout.strip().split("\n")
        width  = int(lines[0]) if len(lines) > 0 and lines[0].isdigit() else 1920
        height = int(lines[1]) if len(lines) > 1 and lines[1].isdigit() else 1080
        return width, height
    except:
        return 1920, 1080

def merge_keyboard(count):
    rows = []
    if count >= 1:
        rows.append([InlineKeyboardButton(
            f"🎬 Birlashtir  ({count} ta qism)", callback_data="do_merge"
        )])
    rows.append([InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel_merge")])
    return InlineKeyboardMarkup(rows)

async def safe_edit(msg, text, kb=None, last_t=None, min_gap=0.8):
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

def clean_user(uid):
    if uid not in user_data:
        return
    if "path" in user_data[uid]:
        try:
            p = user_data[uid]["path"]
            if os.path.exists(p):
                os.remove(p)
        except:
            pass
    for vp in user_data[uid].get("videos", []):
        try:
            if os.path.exists(vp):
                os.remove(vp)
        except:
            pass
    del user_data[uid]

# ──────────────────────────────────────────────
#  DOWNLOAD PROGRESS
# ──────────────────────────────────────────────

_dl_last:      dict = {}
_dl_anim_task: dict = {}
ANIM_FRAMES         = ["⏳", "⌛"]

async def _dl_animate(msg, label):
    frame = 0
    while True:
        try:
            await asyncio.sleep(1.5)
            icon = ANIM_FRAMES[frame % len(ANIM_FRAMES)]
            await msg.edit_text(
                f"{icon} *{label}*\n{make_bar(0)}\n_Yuklanmoqda..._",
                parse_mode=ParseMode.MARKDOWN
            )
            frame += 1
        except (asyncio.CancelledError, Exception):
            break

async def dl_progress(current, total, msg, label):
    uid  = id(msg)
    task = _dl_anim_task.pop(uid, None)
    if task and not task.done():
        task.cancel()

    now = time.time()
    if now - _dl_last.get(uid, 0) < 0.8:
        return
    _dl_last[uid] = now

    if not total:
        return

    pct    = int(current * 100 / total)
    cur_mb = round(current / (1024 * 1024), 1)
    tot_mb = round(total   / (1024 * 1024), 1)
    try:
        await msg.edit_text(
            f"📥 *{label}*\n"
            f"{make_bar(pct)} *{pct}%*\n"
            f"`{cur_mb} MB / {tot_mb} MB`",
            parse_mode=ParseMode.MARKDOWN
        )
    except:
        pass

async def start_dl(msg, label, coro_fn, *args, **kwargs):
    uid  = id(msg)
    anim = asyncio.ensure_future(_dl_animate(msg, label))
    _dl_anim_task[uid] = anim
    try:
        result = await coro_fn(*args, **kwargs)
    finally:
        anim.cancel()
        _dl_anim_task.pop(uid, None)
    return result

# ──────────────────────────────────────────────
#  UPLOAD PROGRESS
# ──────────────────────────────────────────────

_up_last: dict = {}

async def up_progress(current, total, msg, label):
    uid = id(msg)
    now = time.time()
    if now - _up_last.get(uid, 0) < 1.0:
        return
    _up_last[uid] = now
    if not total:
        return
    pct    = int(current * 100 / total)
    cur_mb = round(current / (1024 * 1024), 1)
    tot_mb = round(total   / (1024 * 1024), 1)
    try:
        await msg.edit_text(
            f"📤 *{label}*\n"
            f"{make_bar(pct)} *{pct}%*\n"
            f"`{cur_mb} MB / {tot_mb} MB`",
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
    t       = [time.time()]

    os.makedirs(tmp_dir, exist_ok=True)

    total_duration = sum(get_duration(vp) for vp in video_paths)
    mins = int(total_duration // 60)
    secs = int(total_duration % 60)

    await safe_edit(
        status_msg,
        f"⚡ *Birlashtirish boshlandi!*\n\n"
        f"🎞 Qismlar: *{total} ta*\n"
        f"⏱ Jami: *{mins}:{secs:02d}*\n\n"
        f"{make_bar(5)} **5%**",
        last_t=t, min_gap=0
    )

    list_file = os.path.join(tmp_dir, "_list.txt")

    def write_list(paths):
        with open(list_file, "w", encoding="utf-8") as f:
            for p in paths:
                f.write(f"file '{os.path.abspath(p)}'\n")

    async def run_copy_concat(src_paths, dest, pct_start=5, pct_end=97):
        write_list(src_paths)
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", list_file,
            "-c", "copy", "-movflags", "+faststart",
            "-progress", "pipe:1", "-nostats",
            dest
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        async def _read():
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                line = line.decode("utf-8", errors="ignore").strip()
                if line.startswith("out_time_ms=") and total_duration > 0:
                    try:
                        done_s = int(line.split("=")[1]) / 1_000_000
                        pct    = pct_start + min(
                            int(done_s / total_duration * (pct_end - pct_start)),
                            pct_end - pct_start
                        )
                        await safe_edit(
                            status_msg,
                            f"⚡ *Birlashtirilmoqda...*\n\n"
                            f"📊 {make_bar(pct)} **{pct}%**",
                            last_t=t
                        )
                    except:
                        pass

        try:
            await asyncio.wait_for(_read(), timeout=7200)
        except asyncio.TimeoutError:
            proc.kill()

        _, stderr_data = await proc.communicate()
        ok = os.path.exists(dest) and os.path.getsize(dest) > 1024
        return ok, stderr_data

    ok, stderr_data = await run_copy_concat(video_paths, out_path, 5, 97)

    if ok:
        try:
            os.remove(list_file)
        except:
            pass
        return True

    await safe_edit(
        status_msg,
        f"🔄 *Qismlar moslashtirilmoqda...*\n\n"
        f"{make_bar(10)} **10%**\n\n_Bir oz kutish..._",
        last_t=t, min_gap=0
    )

    remuxed = []
    for i, vpath in enumerate(video_paths):
        tmp_out = os.path.join(tmp_dir, f"_remux_{i}.mp4")
        cmd_remux = [
            "ffmpeg", "-y", "-i", vpath,
            "-c", "copy", "-movflags", "+faststart", tmp_out
        ]
        proc_r = await asyncio.create_subprocess_exec(
            *cmd_remux,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL
        )
        await proc_r.wait()

        pct = 10 + int((i + 1) / total * 45)
        await safe_edit(
            status_msg,
            f"🔄 *Moslashtirilmoqda...*\n\n"
            f"🎞 *{i+1}/{total}* qism\n"
            f"{make_bar(pct)} **{pct}%**",
            last_t=t
        )

        if os.path.exists(tmp_out) and os.path.getsize(tmp_out) > 1024:
            remuxed.append(tmp_out)
        else:
            remuxed.append(vpath)

    ok2, _ = await run_copy_concat(remuxed, out_path, 55, 97)

    for fp in remuxed:
        if "_remux_" in fp:
            try:
                os.remove(fp)
            except:
                pass
    try:
        os.remove(list_file)
    except:
        pass

    return ok2

# ──────────────────────────────────────────────
#  CONTENTID BYPASS
# ──────────────────────────────────────────────

async def bypass_contentid(video_path: str, level: str, status_msg) -> str | None:
    t   = [time.time()]
    os.makedirs("downloads", exist_ok=True)
    out = f"downloads/_bypass_{os.path.basename(video_path)}"

    await safe_edit(
        status_msg,
        f"🔧 *Taqiq olib tashlanmoqda...*\n\n{make_bar(10)} **10%**\n\n_Audio qayta ishlanmoqda..._",
        last_t=t, min_gap=0
    )

    vf = (
        "hflip,"
        "crop=iw*0.97:ih*0.97:(iw-iw*0.97)/2:(ih-ih*0.97)/2,"
        "scale=iw/0.97:ih/0.97,"
        "eq=brightness=0.03:saturation=1.08:contrast=1.02,"
        "setpts=PTS/1.01"
    )
    af = "asetrate=44100*1.03,aresample=44100,atempo=1.01"
    total_dur = get_duration(video_path)

    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vf", vf, "-af", af,
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        "-progress", "pipe:1", "-nostats", out
    ]

    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )

    while True:
        line = await proc.stdout.readline()
        if not line:
            break
        line = line.decode("utf-8", errors="ignore").strip()
        if line.startswith("out_time_ms=") and total_dur > 0:
            try:
                done_s = int(line.split("=")[1]) / 1_000_000
                pct    = min(10 + int(done_s / total_dur * 88), 98)
                await safe_edit(
                    status_msg,
                    f"🔧 *Taqiq olib tashlanmoqda...*\n\n{make_bar(pct)} **{pct}%**",
                    last_t=t
                )
            except:
                pass

    _, stderr_data = await proc.communicate()

    if os.path.exists(out) and os.path.getsize(out) > 0:
        return out

    print(f"[BYPASS ERROR] {stderr_data.decode('utf-8', errors='ignore')[-500:]}")
    return None

# ──────────────────────────────────────────────
#  SHAZAM / COPYRIGHT
# ──────────────────────────────────────────────

def acr_check(audio_bytes: bytes) -> dict:
    try:
        resp = requests.post(
            "https://api.audd.io/",
            data={"api_token": "", "return": "apple_music,spotify"},
            files={"file": ("audio.mp3", audio_bytes, "audio/mpeg")},
            timeout=25
        )
        result = resp.json().get("result")
        if result:
            return {
                "found":  True,
                "title":  result.get("title", "Noma'lum"),
                "artist": result.get("artist", "?"),
            }
    except:
        pass
    return {"found": False}

async def remove_copyright(video_path: str, mode: str, status_msg) -> tuple:
    total_dur    = get_duration(video_path)
    num_seg      = math.ceil(total_dur / SEGMENT_SEC)
    found_ranges = []
    found_list   = []
    t            = [time.time()]
    os.makedirs("downloads", exist_ok=True)
    tmp_dir = "downloads"

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
            f"🔍 *Tekshirilmoqda...*\n\nSegment: *{i+1}/{num_seg}*\n{make_bar(pct)} **{pct}%**",
            last_t=t
        )

        with open(seg_path, "rb") as f:
            audio_bytes = f.read()
        try:
            os.remove(seg_path)
        except:
            pass

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
        f"⚙️ *Qayta ishlanmoqda...*\n\n{make_bar(70)} **70%**\n\n"
        f"_{len(found_ranges)} ta segment qayta ishlanmoqda..._",
        last_t=t, min_gap=0
    )

    out_path = os.path.join(tmp_dir, f"_cr_out_{os.path.basename(video_path)}")

    if mode == "mute":
        parts = [f"volume=enable='between(t,{s},{e})':volume=0" for s, e in found_ranges]
        af    = ",".join(parts)
        cmd   = [
            "ffmpeg", "-y", "-i", video_path,
            "-af", af,
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            "-progress", "pipe:1", "-nostats", out_path
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            line = line.decode("utf-8", errors="ignore").strip()
            if line.startswith("out_time_ms=") and total_dur > 0:
                try:
                    done_s = int(line.split("=")[1]) / 1_000_000
                    pct    = 70 + min(int(done_s / total_dur * 30), 30)
                    await safe_edit(
                        status_msg,
                        f"⚙️ *Ovoz o'chirilmoqda...*\n\n{make_bar(pct)} **{pct}%**",
                        last_t=t
                    )
                except:
                    pass
        await proc.wait()
    else:
        merged_ranges = []
        for s, e in sorted(found_ranges):
            s2 = max(0.0, s - 0.5)
            e2 = min(total_dur, e + 0.5)
            if merged_ranges and s2 <= merged_ranges[-1][1]:
                merged_ranges[-1] = (merged_ranges[-1][0], max(merged_ranges[-1][1], e2))
            else:
                merged_ranges.append((s2, e2))

        keep = []
        prev = 0.0
        for s, e in merged_ranges:
            if prev < s - 0.01:
                keep.append((prev, s))
            prev = e
        if prev < total_dur - 0.01:
            keep.append((prev, total_dur))

        if not keep:
            return None, found_list

        part_files = []
        for j, (s, e) in enumerate(keep):
            pf      = os.path.join(tmp_dir, f"_keep_{j}.mp4")
            dur_seg = e - s
            subprocess.run(
                ["ffmpeg", "-y", "-i", video_path,
                 "-ss", f"{s:.3f}", "-t", f"{dur_seg:.3f}",
                 "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
                 "-pix_fmt", "yuv420p",
                 "-c:a", "aac", "-b:a", "192k",
                 "-avoid_negative_ts", "make_zero",
                 "-movflags", "+faststart", pf],
                capture_output=True
            )
            if os.path.exists(pf) and os.path.getsize(pf) > 0:
                part_files.append(pf)

        if not part_files:
            return None, found_list

        if len(part_files) == 1:
            import shutil
            shutil.copy2(part_files[0], out_path)
            try:
                os.remove(part_files[0])
            except:
                pass
        else:
            list_file = os.path.join(tmp_dir, "_keep_list.txt")
            with open(list_file, "w", encoding="utf-8") as f:
                for pf in part_files:
                    f.write(f"file '{os.path.abspath(pf)}'\n")
            subprocess.run(
                ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
                 "-i", list_file,
                 "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
                 "-pix_fmt", "yuv420p",
                 "-c:a", "aac", "-b:a", "192k",
                 "-movflags", "+faststart", out_path],
                capture_output=True
            )
            for pf in part_files:
                try:
                    os.remove(pf)
                except:
                    pass
            try:
                os.remove(list_file)
            except:
                pass

    if os.path.exists(out_path):
        return out_path, found_list
    return None, found_list

# ──────────────────────────────────────────────
#  MENYU — RANGLI TUGMALAR
# ──────────────────────────────────────────────

def main_kb():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🎬 Kino qismlarini birlashtirish", style=ButtonStyle.SUCCESS)],
        [
            KeyboardButton("🎞 Video ishlash", style=ButtonStyle.PRIMARY),
            KeyboardButton("🖼 Rasm ishlash",  style=ButtonStyle.PRIMARY),
        ],
        [
            KeyboardButton("📊 Statistika", style=ButtonStyle.PRIMARY),
            KeyboardButton("❓ Yordam",      style=ButtonStyle.PRIMARY),
        ],
        [KeyboardButton("🚫 YT taqiqini olib tashlash", style=ButtonStyle.DANGER)],
    ], resize_keyboard=True, is_persistent=True)

# ──────────────────────────────────────────────
#  /start
# ──────────────────────────────────────────────

@app.on_message(filters.command("start"))
async def cmd_start(client, message):
    await message.reply_text(
        "👋 *Assalomu alaykum!*\n\n"
        "🎬 Kino birlashtirish, video siqish yoki bo'lish uchun tugmalardan foydalaning.",
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
        "📌 Videolarni *tartib bilan* yuboring.\n"
        f"📦 Maksimal *{MAX_MERGE_VIDEOS}* ta qism qo'llab-quvvatlanadi.",
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
        "🚫 *YT taqiqini olib tashlash*\n\n📌 Video yuboring.",
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

    # ── BIRLASHTIRISH REJIMI ──
    if uid in user_data and user_data[uid].get("mode") == "merge":
        videos = user_data[uid]["videos"]
        count  = len(videos)

        if count >= MAX_MERGE_VIDEOS:
            await message.reply_text(
                f"⚠️ Maksimal *{MAX_MERGE_VIDEOS}* ta qism!",
                parse_mode=ParseMode.MARKDOWN
            )
            return

        part_n = count + 1
        status = await message.reply_text(
            f"📥 *{part_n}-qism yuklanmoqda...*\n{make_bar(0)}\n_Kutish..._",
            parse_mode=ParseMode.MARKDOWN
        )

        file_path = await start_dl(
            status,
            f"{part_n}-qism yuklanmoqda",
            message.download,
            file_name=f"downloads/merge_{uid}_{count}.mp4",
            progress=dl_progress,
            progress_args=(status, f"{part_n}-qism yuklanmoqda")
        )

        videos.append(file_path)
        new_count = len(videos)

        hint = (
            f"📤 Keyingi: *{new_count+1}-qism*ni yuboring yoki birlashtiring."
            if new_count < MAX_MERGE_VIDEOS
            else f"⚠️ Maksimal {MAX_MERGE_VIDEOS} ta. Endi birlashtiring."
        )

        await status.edit_text(
            f"✅ *{part_n}-qism qabul qilindi!*\n\n"
            f"📋 Jami qabul qilingan: *{new_count} ta qism*\n\n"
            f"{hint}",
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
        file_path = await start_dl(
            status,
            "Video yuklanmoqda",
            message.download,
            file_name=f"downloads/cr_{uid}.mp4",
            progress=dl_progress,
            progress_args=(status, "Video yuklanmoqda")
        )
        user_data[uid]["path"] = file_path

        await status.edit_text(
            "✅ *Video yuklandi!*\n\n"
            "🔧 YouTube taqiqini chetlab o'tish:\n"
            "• Vizual o'zgartiriladi (mirror + crop + color)\n"
            "• Tezlik biroz oshiriladi (+1%)\n"
            "• Audio pitch o'zgartiriladi (+3%)\n\n"
            "_ContentID vizual va audio fingerprint tanimaydi_",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🚀 Taqiqni olib tashlash", callback_data="bp_medium")],
                [InlineKeyboardButton("❌ Bekor qilish",          callback_data="cr_cancel")]
            ])
        )
        return

    # ── ODDIY VIDEO REJIMI ──
    msg = await message.reply_text(
        f"📥 *Video yuklanmoqda...*\n{make_bar(0)}\n_Kutish..._",
        parse_mode=ParseMode.MARKDOWN
    )
    file_path = await start_dl(
        msg,
        "Video yuklanmoqda",
        message.download,
        file_name=f"downloads/vid_{uid}.mp4",
        progress=dl_progress,
        progress_args=(msg, "Video yuklanmoqda")
    )
    user_data[uid] = {
        "path":      file_path,
        "type":      "video",
        "orig_size": round(os.path.getsize(file_path) / (1024 * 1024), 2)
    }
    await msg.edit_text(
        "✅ Video yuklandi. Tanlang:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🗜 Siqish",  callback_data="v_comp"),
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
            await q.answer("⚠️ Kamida 2 ta qism kerak!", show_alert=True)
            return

        total  = len(videos)
        status = await q.message.edit_text(
            f"🎬 *{total} ta qism birlashtirish boshlandi!*\n\n"
            f"{make_bar(0)} **0%**",
            parse_mode=ParseMode.MARKDOWN
        )

        out_path = f"downloads/merged_{uid}.mp4"
        success  = await merge_with_progress(videos, out_path, status)

        if not success:
            await status.edit_text("❌ Birlashtirish bajarilmadi.")
            clean_user(uid)
            return

        size_mb      = round(os.path.getsize(out_path) / (1024 * 1024), 2)
        total_dur    = sum(get_duration(v) for v in videos)
        mins         = int(total_dur // 60)
        secs         = int(total_dur % 60)

        await status.edit_text(
            f"✅ *Tayyor!*\n\n"
            f"🎞 *{total} ta qism* birlashtirildi\n"
            f"⏱ Davomiyligi: *{mins}:{secs:02d}*\n"
            f"📦 Hajm: *{size_mb} MB*\n\n"
            f"📤 *Yuborilmoqda...*",
            parse_mode=ParseMode.MARKDOWN
        )

        await client.send_video(
            uid, out_path,
            caption=(
                f"🎬 *{total} ta qism birlashtirildi!*\n"
                f"⏱ {mins}:{secs:02d} | 📦 {size_mb} MB"
            ),
            supports_streaming=True,
            parse_mode=ParseMode.MARKDOWN,
            progress=up_progress,
            progress_args=(status, "Yuborilmoqda")
        )
        try:
            os.remove(out_path)
        except:
            pass
        try:
            await status.delete()
        except:
            pass
        clean_user(uid)
        return

    if data in ("bp_light", "bp_medium", "bp_heavy"):
        if uid not in user_data or "path" not in user_data.get(uid, {}):
            await q.answer("Fayl topilmadi.", show_alert=True)
            return

        level_map      = {"bp_light": "light", "bp_medium": "medium", "bp_heavy": "heavy"}
        level_text_map = {"bp_light": "Yengil", "bp_medium": "O'rta", "bp_heavy": "Kuchli"}
        level          = level_map[data]
        level_text     = level_text_map[data]
        video_path     = user_data[uid]["path"]

        status = await q.message.edit_text(
            f"🔧 *Bypass boshlandi...*\n\nDaraja: *{level_text}*\n{make_bar(0)} **0%**",
            parse_mode=ParseMode.MARKDOWN
        )

        out_path = await bypass_contentid(video_path, level, status)

        if not out_path:
            await status.edit_text("❌ Xato yuz berdi.")
            clean_user(uid)
            return

        size_mb = round(os.path.getsize(out_path) / (1024 * 1024), 2)
        await status.edit_text(
            f"✅ *Tayyor!*\n\n📦 *{size_mb} MB*\n📤 *Yuborilmoqda...*",
            parse_mode=ParseMode.MARKDOWN
        )
        await client.send_video(
            uid, out_path,
            caption=(
                f"🚫 *ContentID bypass qilindi!*\n"
                f"🔧 Daraja: {level_text}\n"
                f"📦 {size_mb} MB\n\n"
                f"✅ Endi YouTube'ga yuklay olasiz!"
            ),
            supports_streaming=True,
            parse_mode=ParseMode.MARKDOWN,
            progress=up_progress,
            progress_args=(status, "Yuborilmoqda")
        )
        try:
            os.remove(out_path)
        except:
            pass
        try:
            await status.delete()
        except:
            pass
        clean_user(uid)
        return

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
            f"🔍 *Tekshirilmoqda...*\n\nRejim: *{mode_text}*\n{make_bar(0)} **0%**",
            parse_mode=ParseMode.MARKDOWN
        )

        out_path, found_list = await remove_copyright(video_path, mode, status)

        if not found_list:
            await status.edit_text(
                "⚠️ *Shazam topolmadi.*\n\n«🔧 Bypass» usulini ishlatib ko'ring!",
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

        size_mb    = round(os.path.getsize(out_path) / (1024 * 1024), 2)
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
            supports_streaming=True,
            parse_mode=ParseMode.MARKDOWN,
            progress=up_progress,
            progress_args=(status, "Yuborilmoqda")
        )
        try:
            os.remove(out_path)
        except:
            pass
        try:
            await status.delete()
        except:
            pass
        clean_user(uid)
        return

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
                if vb >= 2500:   crf = 18
                elif vb >= 1500: crf = 21
                elif vb >= 900:  crf = 23
                elif vb >= 500:  crf = 26
                else:            crf = 28
                cmd = [
                    "ffmpeg", "-y", "-i", path,
                    "-vf", "scale=-2:1080",
                    "-c:v", "libx264", "-preset", "ultrafast", "-crf", str(crf),
                    "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "128k",
                    "-movflags", "+faststart", out
                ]
                proc = await asyncio.create_subprocess_exec(*cmd)
                await proc.wait()
            if os.path.exists(out):
                await message.reply_video(out, caption=f"✅ Tayyor! ~{target} MB")
                await st.delete()
                try:
                    os.remove(out)
                except:
                    pass
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
            st       = await message.reply_text(f"⏳ {parts} qismga bo'linmoqda...")
            dur      = get_duration(path)
            part_dur = dur / parts
            sent     = 0
            for p in range(parts):
                start = p * part_dur
                out   = f"downloads/split_{uid}_{p+1}.mp4"
                cmd   = [
                    "ffmpeg", "-y", "-ss", str(start), "-t", str(part_dur),
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
                    try:
                        os.remove(out)
                    except:
                        pass
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
        "🎬 *Kino birlashtirish:*\n"
        "Videolarni tartib bilan yuboring → Birlashtir tugmasini bosing\n\n"
        "🎞 *Video ishlash:*\n"
        "Video yuboring → Siqish yoki bo'lish tanlang\n\n"
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
#  RUN
# ──────────────────────────────────────────────

if __name__ == "__main__":
    os.makedirs("downloads", exist_ok=True)
    print("🤖 Bot ishga tushdi!")
    app.run()
