import os
import json
import math
import asyncio
import subprocess
import time
import requests as req_lib
from pyrogram import Client, filters
from pyrogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from pyrogram.enums import ParseMode
from static_ffmpeg import add_paths

add_paths()

# ──────────────────────────────────────────────
#  SOZLAMALAR
# ──────────────────────────────────────────────

API_ID    = 37366974
API_HASH  = "08d09c7ed8b7cb414ed6a99c104f1bd6"
BOT_TOKEN = "8626867961:AAGhbJzxdBBLM-SOLVvX57q1m8-_FP36xuM"

SEGMENT_SEC      = 15
MAX_MERGE_VIDEOS = 500
STATS_FILE       = "stats.json"

TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

app = Client("video_processor", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

user_data: dict = {}

# ──────────────────────────────────────────────
#  RAW API — RANGLI TUGMALAR
#  style: yo'q=ko'k | "destructive"=qizil | "secondary"=kulrang
#  Rasmda yashil ham bor — "success" sinab ko'ramiz
# ──────────────────────────────────────────────

def _btn(text: str, cb: str, style: str = None) -> dict:
    """Bitta inline tugma dict"""
    b = {"text": text, "callback_data": cb}
    if style:
        b["style"] = style
    return b

def raw_send(chat_id: int, text: str, keyboard: list = None, parse_mode="Markdown") -> dict:
    """
    Bot API ga to'g'ridan-to'g'ri sendMessage
    keyboard = [[btn, btn], [btn]] — _btn() list
    """
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }
    if keyboard:
        payload["reply_markup"] = json.dumps({"inline_keyboard": keyboard})
    r = req_lib.post(f"{TG_API}/sendMessage", data=payload)
    return r.json()

def raw_edit(chat_id: int, msg_id: int, text: str,
             keyboard: list = None, parse_mode="Markdown") -> dict:
    """Bot API ga to'g'ridan-to'g'ri editMessageText"""
    payload = {
        "chat_id": chat_id,
        "message_id": msg_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }
    if keyboard:
        payload["reply_markup"] = json.dumps({"inline_keyboard": keyboard})
    elif keyboard is not None:
        payload["reply_markup"] = json.dumps({"inline_keyboard": []})
    r = req_lib.post(f"{TG_API}/editMessageText", data=payload)
    return r.json()

async def async_raw_send(chat_id, text, keyboard=None, parse_mode="Markdown"):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: raw_send(chat_id, text, keyboard, parse_mode))

async def async_raw_edit(chat_id, msg_id, text, keyboard=None, parse_mode="Markdown"):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: raw_edit(chat_id, msg_id, text, keyboard, parse_mode))

# ──────────────────────────────────────────────
#  TUGMA SHABLONLARI
#  KO'K  = style yo'q (default)
#  QIZIL = style "destructive"
#  YASHIL= style "success"  (Bot API 9.4 rasmida ko'rindi)
# ──────────────────────────────────────────────

def merge_keyboard(count: int) -> list:
    rows = []
    if count >= 1:
        rows.append([_btn(
            f"🎬 Kino qismlarini birlashtirish ({count} ta qism)",
            "do_merge",
            style="success"        # 🟢 YASHIL
        )])
    rows.append([_btn("❌ Bekor qilish", "cancel_merge", style="destructive")])  # 🔴 QIZIL
    return rows

def video_action_keyboard() -> list:
    return [[
        _btn("🗜 Siqish",  "v_comp"),          # 🔵 KO'K
        _btn("✂️ Bo'lish", "v_split"),         # 🔵 KO'K
    ]]

def copyright_keyboard() -> list:
    return [
        [_btn("🚀 Taqiqni olib tashlash", "bp_medium", style="success")],    # 🟢 YASHIL
        [_btn("❌ Bekor qilish",          "cr_cancel",  style="destructive")], # 🔴 QIZIL
    ]

def bypass_keyboard() -> list:
    return [
        [_btn("🟢 Yengil", "bp_soft")],                                       # 🔵 KO'K
        [_btn("🟡 O'rta",  "bp_medium", style="success")],                    # 🟢 YASHIL
        [_btn("🔴 Kuchli", "bp_hard",   style="destructive")],                # 🔴 QIZIL
        [_btn("❌ Bekor",  "cr_cancel", style="destructive")],                # 🔴 QIZIL
    ]

def bypass_fallback_keyboard() -> list:
    return [[_btn("🔧 Bypass usulini ishlatish", "cr_bypass", style="success")]]

# ──────────────────────────────────────────────
#  STATISTIKA
# ──────────────────────────────────────────────

def load_stats() -> dict:
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {"users": {}, "total_merges": 0}

def save_stats(data: dict):
    try:
        with open(STATS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except:
        pass

def register_user(uid: int, name: str):
    s = load_stats()
    k = str(uid)
    if k not in s["users"]:
        s["users"][k] = {"name": name, "merges": 0, "total_parts": 0, "total_size_mb": 0}
    else:
        s["users"][k]["name"] = name
    save_stats(s)

def record_merge(uid: int, parts: int, size_mb: float):
    s = load_stats()
    k = str(uid)
    if k not in s["users"]:
        s["users"][k] = {"name": "?", "merges": 0, "total_parts": 0, "total_size_mb": 0}
    s["users"][k]["merges"]       += 1
    s["users"][k]["total_parts"]  += parts
    s["users"][k]["total_size_mb"] = round(s["users"][k]["total_size_mb"] + size_mb, 2)
    s["total_merges"] += 1
    save_stats(s)

# ──────────────────────────────────────────────
#  YORDAMCHI
# ──────────────────────────────────────────────

def make_bar(pct, n=12):
    f = int(n * pct / 100)
    return "🟩" * f + "⬜" * (n - f)

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
            icon = ANIM_FRAMES[frame % 2]
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
    if task and not task.done(): task.cancel()
    now = time.time()
    if now - _dl_last.get(uid, 0) < 0.8: return
    _dl_last[uid] = now
    if not total: return
    pct    = int(current * 100 / total)
    cur_mb = round(current / (1024*1024), 1)
    tot_mb = round(total   / (1024*1024), 1)
    try:
        await msg.edit_text(
            f"📥 *{label}*\n{make_bar(pct)} *{pct}%*\n`{cur_mb} MB / {tot_mb} MB`",
            parse_mode=ParseMode.MARKDOWN
        )
    except: pass

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

_up_last: dict = {}

async def up_progress(current, total, msg, label):
    uid = id(msg)
    now = time.time()
    if now - _up_last.get(uid, 0) < 1.0: return
    _up_last[uid] = now
    if not total: return
    pct    = int(current * 100 / total)
    cur_mb = round(current / (1024*1024), 1)
    tot_mb = round(total   / (1024*1024), 1)
    try:
        await msg.edit_text(
            f"📤 *{label}*\n{make_bar(pct)} *{pct}%*\n`{cur_mb} MB / {tot_mb} MB`",
            parse_mode=ParseMode.MARKDOWN
        )
    except: pass

# ──────────────────────────────────────────────
#  SAFE EDIT (progress uchun)
# ──────────────────────────────────────────────

_se_last: dict = {}

async def safe_edit(msg, text, kb_raw: list = None, last_t=None, min_gap=0.8):
    now = time.time()
    if last_t is not None and now - last_t[0] < min_gap: return
    chat_id = msg.chat.id
    msg_id  = msg.id
    try:
        if kb_raw is not None:
            await async_raw_edit(chat_id, msg_id, text, kb_raw)
        else:
            await msg.edit_text(text, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
        if last_t is not None:
            last_t[0] = now
    except: pass

# ──────────────────────────────────────────────
#  BIRLASHTIRISH
# ──────────────────────────────────────────────

async def merge_with_progress(video_paths: list, out_path: str, status_msg) -> bool:
    total          = len(video_paths)
    tmp_dir        = os.path.dirname(out_path)
    t              = [time.time()]
    total_duration = sum(get_duration(vp) for vp in video_paths)
    mins = int(total_duration // 60)
    secs = int(total_duration % 60)

    os.makedirs(tmp_dir, exist_ok=True)

    await safe_edit(
        status_msg,
        f"⚡ *Birlashtirish boshlandi!*\n\n"
        f"🎞 Qismlar: *{total} ta*\n⏱ Jami: *{mins}:{secs:02d}*\n\n{make_bar(5)} **5%**",
        last_t=t, min_gap=0
    )

    list_file = os.path.join(tmp_dir, "_list.txt")

    def write_list(paths):
        with open(list_file, "w", encoding="utf-8") as f:
            for p in paths:
                f.write(f"file '{os.path.abspath(p)}'\n")

    async def run_copy_concat(src_paths, dest, pct_start=5, pct_end=97):
        write_list(src_paths)
        cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file,
               "-c", "copy", "-movflags", "+faststart", "-progress", "pipe:1", "-nostats", dest]
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        async def _read():
            while True:
                line = await proc.stdout.readline()
                if not line: break
                line = line.decode("utf-8", errors="ignore").strip()
                if line.startswith("out_time_ms=") and total_duration > 0:
                    try:
                        done_s = int(line.split("=")[1]) / 1_000_000
                        pct    = pct_start + min(int(done_s/total_duration*(pct_end-pct_start)), pct_end-pct_start)
                        await safe_edit(status_msg, f"⚡ *Birlashtirilmoqda...*\n\n{make_bar(pct)} **{pct}%**", last_t=t)
                    except: pass
        try:
            await asyncio.wait_for(_read(), timeout=7200)
        except asyncio.TimeoutError:
            proc.kill()
        _, stderr_data = await proc.communicate()
        ok = os.path.exists(dest) and os.path.getsize(dest) > 1024
        return ok, stderr_data

    ok, stderr_data = await run_copy_concat(video_paths, out_path, 5, 97)
    if ok:
        try: os.remove(list_file)
        except: pass
        return True

    await safe_edit(status_msg, f"🔄 *Moslashtirilmoqda...*\n\n{make_bar(10)} **10%**", last_t=t, min_gap=0)

    remuxed = []
    for i, vpath in enumerate(video_paths):
        tmp_out = os.path.join(tmp_dir, f"_remux_{i}.mp4")
        proc_r  = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y", "-i", vpath, "-c", "copy", "-movflags", "+faststart", tmp_out,
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL
        )
        await proc_r.wait()
        pct = 10 + int((i+1)/total*45)
        await safe_edit(status_msg, f"🔄 *Moslashtirilmoqda...*\n\n🎞 *{i+1}/{total}*\n{make_bar(pct)} **{pct}%**", last_t=t)
        remuxed.append(tmp_out if (os.path.exists(tmp_out) and os.path.getsize(tmp_out)>1024) else vpath)

    ok2, _ = await run_copy_concat(remuxed, out_path, 55, 97)
    for fp in remuxed:
        if "_remux_" in fp:
            try: os.remove(fp)
            except: pass
    try: os.remove(list_file)
    except: pass
    return ok2

# ──────────────────────────────────────────────
#  BYPASS CONTENTID
# ──────────────────────────────────────────────

async def bypass_contentid(video_path: str, status_msg) -> str | None:
    t   = [time.time()]
    out = f"downloads/_bypass_{os.path.basename(video_path)}"
    vf  = ("hflip,crop=iw*0.97:ih*0.97:(iw-iw*0.97)/2:(ih-ih*0.97)/2,"
           "scale=iw/0.97:ih/0.97,eq=brightness=0.03:saturation=1.08:contrast=1.02,setpts=PTS/1.01")
    af  = "asetrate=44100*1.03,aresample=44100,atempo=1.01"
    total_dur = get_duration(video_path)
    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vf", vf, "-af", af,
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart", "-progress", "pipe:1", "-nostats", out
    ]
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    while True:
        line = await proc.stdout.readline()
        if not line: break
        line = line.decode("utf-8", errors="ignore").strip()
        if line.startswith("out_time_ms=") and total_dur > 0:
            try:
                done_s = int(line.split("=")[1]) / 1_000_000
                pct    = min(10 + int(done_s/total_dur*88), 98)
                await safe_edit(status_msg, f"🔧 *Taqiq olib tashlanmoqda...*\n\n{make_bar(pct)} **{pct}%**", last_t=t)
            except: pass
    await proc.communicate()
    return out if (os.path.exists(out) and os.path.getsize(out) > 0) else None

# ──────────────────────────────────────────────
#  SHAZAM / COPYRIGHT
# ──────────────────────────────────────────────

def acr_check(audio_bytes: bytes) -> dict:
    try:
        resp = req_lib.post(
            "https://api.audd.io/",
            data={"api_token": "", "return": "apple_music,spotify"},
            files={"file": ("audio.mp3", audio_bytes, "audio/mpeg")},
            timeout=25
        )
        result = resp.json().get("result")
        if result:
            return {"found": True, "title": result.get("title","?"), "artist": result.get("artist","?")}
    except: pass
    return {"found": False}

async def remove_copyright(video_path: str, mode: str, status_msg) -> tuple:
    total_dur = get_duration(video_path)
    num_seg   = math.ceil(total_dur / SEGMENT_SEC)
    found_ranges, found_list = [], []
    t       = [time.time()]
    tmp_dir = "downloads"
    os.makedirs(tmp_dir, exist_ok=True)

    for i in range(num_seg):
        start    = i * SEGMENT_SEC
        dur      = min(SEGMENT_SEC, total_dur - start)
        seg_path = os.path.join(tmp_dir, f"_acr_{i}.mp3")
        subprocess.run(
            ["ffmpeg", "-y", "-ss", str(start), "-i", video_path,
             "-t", str(dur), "-vn", "-acodec", "libmp3lame", "-q:a", "6", seg_path],
            capture_output=True
        )
        pct = int((i+1)/num_seg*60)
        await safe_edit(status_msg, f"🔍 *Tekshirilmoqda...*\n\nSegment: *{i+1}/{num_seg}*\n{make_bar(pct)} **{pct}%**", last_t=t)
        with open(seg_path, "rb") as f: audio_bytes = f.read()
        try: os.remove(seg_path)
        except: pass
        res = acr_check(audio_bytes)
        if res["found"]:
            found_ranges.append((start, start+dur))
            found_list.append(f"  🎵 `{int(start)}s–{int(start+dur)}s` — {res['title']} / {res['artist']}")

    if not found_ranges:
        return None, []

    await safe_edit(status_msg, f"⚙️ *Qayta ishlanmoqda...*\n\n{make_bar(70)} **70%**", last_t=t, min_gap=0)
    out_path = os.path.join(tmp_dir, f"_cr_out_{os.path.basename(video_path)}")

    if mode == "mute":
        parts = [f"volume=enable='between(t,{s},{e})':volume=0" for s,e in found_ranges]
        af    = ",".join(parts)
        cmd   = ["ffmpeg", "-y", "-i", video_path, "-af", af,
                 "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
                 "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                 "-movflags", "+faststart", "-progress", "pipe:1", "-nostats", out_path]
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        while True:
            line = await proc.stdout.readline()
            if not line: break
            line = line.decode("utf-8", errors="ignore").strip()
            if line.startswith("out_time_ms=") and total_dur > 0:
                try:
                    done_s = int(line.split("=")[1])/1_000_000
                    pct    = 70 + min(int(done_s/total_dur*30), 30)
                    await safe_edit(status_msg, f"⚙️ *Ovoz o'chirilmoqda...*\n\n{make_bar(pct)} **{pct}%**", last_t=t)
                except: pass
        await proc.wait()
    else:
        merged_ranges = []
        for s,e in sorted(found_ranges):
            s2,e2 = max(0.0,s-0.5), min(total_dur,e+0.5)
            if merged_ranges and s2<=merged_ranges[-1][1]:
                merged_ranges[-1] = (merged_ranges[-1][0], max(merged_ranges[-1][1],e2))
            else:
                merged_ranges.append((s2,e2))
        keep, prev = [], 0.0
        for s,e in merged_ranges:
            if prev < s-0.01: keep.append((prev,s))
            prev = e
        if prev < total_dur-0.01: keep.append((prev,total_dur))
        if not keep: return None, found_list

        part_files = []
        for j,(s,e) in enumerate(keep):
            pf = os.path.join(tmp_dir, f"_keep_{j}.mp4")
            subprocess.run(
                ["ffmpeg", "-y", "-i", video_path,
                 "-ss", f"{s:.3f}", "-t", f"{e-s:.3f}",
                 "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
                 "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                 "-avoid_negative_ts", "make_zero", "-movflags", "+faststart", pf],
                capture_output=True
            )
            if os.path.exists(pf) and os.path.getsize(pf)>0: part_files.append(pf)
        if not part_files: return None, found_list
        if len(part_files)==1:
            import shutil; shutil.copy2(part_files[0], out_path)
            try: os.remove(part_files[0])
            except: pass
        else:
            lf = os.path.join(tmp_dir,"_keep_list.txt")
            with open(lf,"w") as f:
                for pf in part_files: f.write(f"file '{os.path.abspath(pf)}'\n")
            subprocess.run(
                ["ffmpeg","-y","-f","concat","-safe","0","-i",lf,
                 "-c:v","libx264","-preset","ultrafast","-crf","18",
                 "-pix_fmt","yuv420p","-c:a","aac","-b:a","192k",
                 "-movflags","+faststart",out_path], capture_output=True
            )
            for pf in part_files:
                try: os.remove(pf)
                except: pass
            try: os.remove(lf)
            except: pass

    return (out_path, found_list) if os.path.exists(out_path) else (None, found_list)

# ──────────────────────────────────────────────
#  REPLY KEYBOARD (oddiy tugmalar)
# ──────────────────────────────────────────────

def main_kb():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🎬 Kino qismlarini birlashtirish")],
        [KeyboardButton("🎞 Video ishlash"), KeyboardButton("🖼 Rasm ishlash")],
        [KeyboardButton("📊 Statistika"),    KeyboardButton("❓ Yordam")]
    ], resize_keyboard=True)

# ──────────────────────────────────────────────
#  /start
# ──────────────────────────────────────────────

@app.on_message(filters.command("start"))
async def cmd_start(client, message):
    uid  = message.from_user.id
    name = message.from_user.first_name or "Foydalanuvchi"
    register_user(uid, name)
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
    uid  = message.from_user.id
    name = message.from_user.first_name or "?"
    register_user(uid, name)
    clean_user(uid)
    user_data[uid] = {"mode": "merge", "videos": []}
    # Rangli tugma bilan yuborish
    await async_raw_send(
        uid,
        "🎬 *Kino birlashtirish rejimi yoqildi!*\n\n"
        "📌 Videolarni *tartib bilan* yuboring.\n"
        f"📦 Maksimal *{MAX_MERGE_VIDEOS}* ta qism.",
        keyboard=merge_keyboard(0)
    )

# ──────────────────────────────────────────────
#  YT TAQIQINI OLIB TASHLASH
# ──────────────────────────────────────────────

@app.on_message(filters.regex("🚫 YT taqiqini olib tashlash"))
async def start_copyright(client, message):
    uid  = message.from_user.id
    name = message.from_user.first_name or "?"
    register_user(uid, name)
    clean_user(uid)
    user_data[uid] = {"mode": "copyright"}
    await message.reply_text("🚫 *YT taqiqini olib tashlash*\n\n📌 Video yuboring.",
                             reply_markup=main_kb(), parse_mode=ParseMode.MARKDOWN)

# ──────────────────────────────────────────────
#  STATISTIKA
# ──────────────────────────────────────────────

@app.on_message(filters.regex("📊 Statistika"))
async def stats_handler(client, message):
    data         = load_stats()
    users        = data.get("users", {})
    total_merges = data.get("total_merges", 0)
    sorted_users = sorted(users.items(), key=lambda x: x[1].get("merges",0), reverse=True)[:5]
    top_text     = ""
    for i, (uid_s, info) in enumerate(sorted_users, 1):
        nm      = info.get("name","?")
        merges  = info.get("merges",0)
        parts   = info.get("total_parts",0)
        size_mb = info.get("total_size_mb",0)
        top_text += f"  {i}. *{nm}* — 🎬{merges} ta | 🎞{parts} qism | 📦{size_mb}MB\n"
    if not top_text:
        top_text = "  _Hali ma'lumot yo'q_\n"
    await message.reply_text(
        f"📊 *Bot Statistikasi*\n{'─'*28}\n\n"
        f"👥 Jami foydalanuvchi: *{len(users)}* ta\n"
        f"🎬 Jami birlashtirish: *{total_merges}* ta\n"
        f"⚙️ Faol seans: *{len(user_data)}* ta\n\n"
        f"🏆 *Top foydalanuvchilar:*\n{top_text}",
        parse_mode=ParseMode.MARKDOWN
    )

# ──────────────────────────────────────────────
#  YORDAM
# ──────────────────────────────────────────────

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
#  VIDEO KELGANDA
# ──────────────────────────────────────────────

@app.on_message(filters.video | filters.document)
async def handle_video(client, message):
    if message.document and not message.document.mime_type.startswith("video/"): return

    uid  = message.from_user.id
    name = message.from_user.first_name or "?"
    register_user(uid, name)

    # ── BIRLASHTIRISH REJIMI ──
    if uid in user_data and user_data[uid].get("mode") == "merge":
        videos = user_data[uid]["videos"]
        count  = len(videos)
        if count >= MAX_MERGE_VIDEOS:
            await message.reply_text(f"⚠️ Maksimal *{MAX_MERGE_VIDEOS}* ta qism!", parse_mode=ParseMode.MARKDOWN)
            return

        part_n = count + 1
        status = await message.reply_text(
            f"📥 *{part_n}-qism yuklanmoqda...*\n{make_bar(0)}\n_Kutish..._",
            parse_mode=ParseMode.MARKDOWN
        )
        file_path = await start_dl(
            status, f"{part_n}-qism yuklanmoqda",
            message.download,
            file_name=f"downloads/merge_{uid}_{count}.mp4",
            progress=dl_progress,
            progress_args=(status, f"{part_n}-qism yuklanmoqda")
        )
        videos.append(file_path)
        new_count = len(videos)
        hint = (f"📤 Keyingi: *{new_count+1}-qism*ni yuboring yoki birlashtiring."
                if new_count < MAX_MERGE_VIDEOS else f"⚠️ Maksimal {MAX_MERGE_VIDEOS} ta. Birlashtiring.")

        # Rangli tugma bilan edit
        await async_raw_edit(
            uid, status.id,
            f"✅ *{part_n}-qism qabul qilindi!*\n\n📋 Jami: *{new_count} ta qism*\n\n{hint}",
            keyboard=merge_keyboard(new_count)
        )
        return

    # ── COPYRIGHT REJIMI ──
    if uid in user_data and user_data[uid].get("mode") == "copyright":
        status = await message.reply_text("📥 *Video yuklanmoqda...*", parse_mode=ParseMode.MARKDOWN)
        file_path = await start_dl(
            status, "Video yuklanmoqda",
            message.download,
            file_name=f"downloads/cr_{uid}.mp4",
            progress=dl_progress,
            progress_args=(status, "Video yuklanmoqda")
        )
        user_data[uid]["path"] = file_path
        await async_raw_edit(
            uid, status.id,
            "✅ *Video yuklandi!*\n\n"
            "🔧 YouTube taqiqini chetlab o'tish:\n"
            "• Vizual o'zgartiriladi (mirror + crop + color)\n"
            "• Tezlik biroz oshiriladi (+1%)\n"
            "• Audio pitch o'zgartiriladi (+3%)",
            keyboard=copyright_keyboard()
        )
        return

    # ── ODDIY VIDEO REJIMI ──
    msg = await message.reply_text(f"📥 *Video yuklanmoqda...*\n{make_bar(0)}\n_Kutish..._", parse_mode=ParseMode.MARKDOWN)
    file_path = await start_dl(
        msg, "Video yuklanmoqda",
        message.download,
        file_name=f"downloads/vid_{uid}.mp4",
        progress=dl_progress,
        progress_args=(msg, "Video yuklanmoqda")
    )
    user_data[uid] = {"path": file_path, "type": "video", "orig_size": round(os.path.getsize(file_path)/(1024*1024),2)}
    await async_raw_edit(
        uid, msg.id,
        "✅ *Video yuklandi. Tanlang:*",
        keyboard=video_action_keyboard()
    )

# ──────────────────────────────────────────────
#  CALLBACK HANDLER
# ──────────────────────────────────────────────

@app.on_callback_query()
async def on_callback(client, q):
    uid  = q.from_user.id
    data = q.data
    msg  = q.message

    await q.answer()

    # ── BIRLASHTIRISH BEKOR ──
    if data == "cancel_merge":
        clean_user(uid)
        await async_raw_edit(uid, msg.id, "❌ Birlashtirish bekor qilindi.", keyboard=[])
        return

    # ── BIRLASHTIR ──
    if data == "do_merge":
        if uid not in user_data or user_data[uid].get("mode") != "merge":
            await q.answer("Ma'lumot topilmadi.", show_alert=True); return
        videos = user_data[uid].get("videos", [])
        if len(videos) < 2:
            await q.answer("⚠️ Kamida 2 ta qism kerak!", show_alert=True); return

        total  = len(videos)
        await async_raw_edit(uid, msg.id, f"🎬 *{total} ta qism birlashtirilmoqda...*\n\n{make_bar(0)} **0%**", keyboard=[])
        status   = msg
        out_path = f"downloads/merged_{uid}.mp4"
        ok       = await merge_with_progress(videos, out_path, status)

        if ok:
            size_mb = round(os.path.getsize(out_path)/(1024*1024), 2)
            record_merge(uid, total, size_mb)
            await async_raw_edit(uid, msg.id,
                f"✅ *Birlashtirish tugadi!*\n\n📹 {total} ta qism\n📦 *{size_mb} MB*\n\n📤 *Yuborilmoqda...*",
                keyboard=[]
            )
            await client.send_video(uid, out_path,
                caption=f"🎬 *Kino tayyor!*\n📹 {total} ta qism\n📦 {size_mb} MB",
                supports_streaming=True, parse_mode=ParseMode.MARKDOWN,
                progress=up_progress, progress_args=(status,"Yuborilmoqda")
            )
            try: await status.delete()
            except: pass
            try: os.remove(out_path)
            except: pass
        else:
            await async_raw_edit(uid, msg.id,
                "❌ *Birlashtirish muvaffaqiyatsiz.*\n\nVideolar formati har xil bo'lishi mumkin.", keyboard=[])

        for vp in videos:
            try: os.remove(vp)
            except: pass
        user_data.pop(uid, None)
        return

    # ── TO'LIQ OVOZ O'CHIRISH ──
    if data == "cr_mute_full":
        if uid not in user_data or "path" not in user_data.get(uid, {}):
            await q.answer("Fayl topilmadi.", show_alert=True); return
        video_path = user_data[uid]["path"]
        await async_raw_edit(uid, msg.id, "🔇 *Ovoz o'chirilmoqda...*\n\n`░░░░░░░░░░░░` 0%", keyboard=[])
        status    = msg
        out_path  = f"downloads/_muted_{uid}.mp4"
        total_dur = get_duration(video_path)
        t         = [time.time()]
        cmd = ["ffmpeg","-y","-i",video_path,"-an","-c:v","copy","-movflags","+faststart",
               "-progress","pipe:1","-nostats",out_path]
        proc = await asyncio.create_subprocess_exec(*cmd,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
        while True:
            line = await proc.stdout.readline()
            if not line: break
            line = line.decode("utf-8",errors="ignore").strip()
            if line.startswith("out_time_ms=") and total_dur>0:
                try:
                    done_s = int(line.split("=")[1])/1_000_000
                    pct    = min(int(done_s/total_dur*100),100)
                    await safe_edit(status, f"🔇 *Ovoz o'chirilmoqda...*\n\n{make_bar(pct)} **{pct}%**", last_t=t)
                except: pass
        await proc.wait()
        if not os.path.exists(out_path) or os.path.getsize(out_path)==0:
            await async_raw_edit(uid,msg.id,"❌ Xato yuz berdi.",keyboard=[]); clean_user(uid); return
        size_mb = round(os.path.getsize(out_path)/(1024*1024),2)
        await async_raw_edit(uid,msg.id,f"✅ *Tayyor!*\n\n🔇 Ovoz o'chirildi\n📦 *{size_mb} MB*\n📤 *Yuborilmoqda...*",keyboard=[])
        await client.send_video(uid,out_path,caption=f"🔇 *Ovoz o'chirilgan video*\n📦 {size_mb} MB",
                                supports_streaming=True,parse_mode=ParseMode.MARKDOWN,
                                progress=up_progress,progress_args=(status,"Yuborilmoqda"))
        try: os.remove(out_path)
        except: pass
        try: await status.delete()
        except: pass
        clean_user(uid)
        return

    # ── BYPASS TANLASH ──
    if data == "cr_bypass":
        if uid not in user_data or "path" not in user_data.get(uid,{}):
            await q.answer("Fayl topilmadi.",show_alert=True); return
        await async_raw_edit(uid,msg.id,
            "🔧 *Bypass darajasini tanlang:*\n\n"
            "🟢 *Yengil* — +2% pitch\n"
            "🟡 *O'rta* — +3% pitch + EQ\n"
            "🔴 *Kuchli* — +4% pitch + shovqin",
            keyboard=bypass_keyboard()
        )
        return

    if data in ("bp_soft","bp_medium","bp_hard"):
        if uid not in user_data or "path" not in user_data.get(uid,{}):
            await q.answer("Fayl topilmadi.",show_alert=True); return
        level_text = {"soft":"🟢 Yengil","medium":"🟡 O'rta","hard":"🔴 Kuchli"}[data.split("_")[1]]
        video_path = user_data[uid]["path"]
        await async_raw_edit(uid,msg.id,
            f"🔧 *ContentID chetlab o'tilmoqda...*\n\nDaraja: {level_text}\n\n{make_bar(0)} **0%**",keyboard=[])
        status   = msg
        out_path = await bypass_contentid(video_path, status)
        if not out_path:
            await async_raw_edit(uid,msg.id,"❌ Xato yuz berdi. Qaytadan urinib ko'ring.",keyboard=[])
            clean_user(uid); return
        size_mb = round(os.path.getsize(out_path)/(1024*1024),2)
        await async_raw_edit(uid,msg.id,f"✅ *Tayyor!*\n\n📦 *{size_mb} MB*\n📤 *Yuborilmoqda...*",keyboard=[])
        await client.send_video(uid,out_path,
            caption=f"🚫 *ContentID bypass qilindi!*\n🔧 {level_text}\n📦 {size_mb} MB\n\n✅ Endi YouTube'ga yuklay olasiz!",
            supports_streaming=True,parse_mode=ParseMode.MARKDOWN,
            progress=up_progress,progress_args=(status,"Yuborilmoqda"))
        try: os.remove(out_path)
        except: pass
        try: await status.delete()
        except: pass
        clean_user(uid)
        return

    if data == "cr_cancel":
        clean_user(uid)
        await async_raw_edit(uid,msg.id,"❌ Bekor qilindi.",keyboard=[])
        return

    if data in ("cr_mute","cr_cut"):
        if uid not in user_data or "path" not in user_data.get(uid,{}):
            await q.answer("Fayl topilmadi.",show_alert=True); return
        mode      = "mute" if data=="cr_mute" else "cut"
        mode_text = "Ovoz o'chirish" if mode=="mute" else "Kesib tashlash"
        video_path= user_data[uid]["path"]
        await async_raw_edit(uid,msg.id,
            f"🔍 *Tekshirilmoqda...*\n\nRejim: *{mode_text}*\n{make_bar(0)} **0%**",keyboard=[])
        status = msg
        out_path, found_list = await remove_copyright(video_path, mode, status)
        if not found_list:
            await async_raw_edit(uid,msg.id,
                "⚠️ *Shazam topolmadi.*\n\n«🔧 Bypass» usulini ishlatib ko'ring!",
                keyboard=bypass_fallback_keyboard())
            return
        if out_path is None:
            await async_raw_edit(uid,msg.id,"❌ Videoning barcha qismlari taqiqlangan.",keyboard=[])
            clean_user(uid); return
        size_mb    = round(os.path.getsize(out_path)/(1024*1024),2)
        found_text = "\n".join(found_list)
        await async_raw_edit(uid,msg.id,
            f"✅ *{len(found_list)} ta segment qayta ishlandi!*\n\n🎵 *Topilgan:*\n{found_text}\n\n📦 {size_mb} MB\n📤 *Yuborilmoqda...*",
            keyboard=[])
        await client.send_video(uid,out_path,
            caption=f"🚫 *Taqiq olib tashlandi!*\n📌 {mode_text}\n🎵 {len(found_list)} segment\n📦 {size_mb} MB",
            supports_streaming=True,parse_mode=ParseMode.MARKDOWN,
            progress=up_progress,progress_args=(status,"Yuborilmoqda"))
        try: os.remove(out_path)
        except: pass
        try: await status.delete()
        except: pass
        clean_user(uid); return

    # ── VIDEO SIQISH / BO'LISH ──
    if data == "v_comp":
        if uid not in user_data: await q.answer("Ma'lumot topilmadi.",show_alert=True); return
        await async_raw_edit(uid,msg.id,"🗜 *Necha MB bo'lsin?* (Faqat raqam):",keyboard=[])
        user_data[uid]["action"] = "wait_v_size"
    elif data == "v_split":
        if uid not in user_data: await q.answer("Ma'lumot topilmadi.",show_alert=True); return
        await async_raw_edit(uid,msg.id,"✂️ *Nechta qismga bo'linsin?* (Faqat raqam):",keyboard=[])
        user_data[uid]["action"] = "wait_v_split"

# ──────────────────────────────────────────────
#  MATN INPUT
# ──────────────────────────────────────────────

@app.on_message(filters.text & filters.private & ~filters.regex("^(🎬|🎞|🖼|📊|❓|🚫)"))
async def text_input(client, message):
    uid = message.from_user.id
    if uid not in user_data or "action" not in user_data[uid]: return
    action = user_data[uid]["action"]
    path   = user_data[uid].get("path","")

    if action == "wait_v_size":
        try:
            target = int(message.text.strip())
            st     = await message.reply_text(f"⏳ *{target} MB* ga siqilmoqda...", parse_mode=ParseMode.MARKDOWN)
            out    = f"downloads/res_{uid}.mp4"
            dur    = get_duration(path)
            if dur > 0:
                vb  = max(int((target*8000)/dur-128),200)
                crf = 18 if vb>=2500 else 21 if vb>=1500 else 23 if vb>=900 else 26 if vb>=500 else 28
                cmd = ["ffmpeg","-y","-i",path,"-vf","scale=-2:1080",
                       "-c:v","libx264","-preset","ultrafast","-crf",str(crf),
                       "-pix_fmt","yuv420p","-c:a","aac","-b:a","128k","-movflags","+faststart",out]
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
                await message.reply_text("❌ 2 dan 20 gacha son kiriting."); return
            st       = await message.reply_text(f"⏳ *{parts}* qismga bo'linmoqda...", parse_mode=ParseMode.MARKDOWN)
            dur      = get_duration(path)
            part_dur = dur / parts
            sent     = 0
            for p in range(parts):
                start = p * part_dur
                out   = f"downloads/split_{uid}_{p+1}.mp4"
                cmd   = ["ffmpeg","-y","-ss",str(start),"-t",str(part_dur),
                         "-i",path,"-c","copy","-map","0","-movflags","+faststart",out]
                proc = await asyncio.create_subprocess_exec(*cmd,
                    stdout=asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.DEVNULL)
                await proc.wait()
                if os.path.exists(out):
                    await message.reply_video(out, caption=f"✂️ {p+1}-qism / {parts}")
                    try: os.remove(out)
                    except: pass
                    sent += 1
            await st.edit_text(f"✅ *{sent}* ta qism yuborildi.", parse_mode=ParseMode.MARKDOWN)
            clean_user(uid)
        except:
            await message.reply_text("❌ Xato!")

# ──────────────────────────────────────────────
#  RUN
# ──────────────────────────────────────────────

if __name__ == "__main__":
    os.makedirs("downloads", exist_ok=True)
    print("🤖 Bot ishga tushdi! (Rangli tugmalar — Raw API)")
    app.run()
