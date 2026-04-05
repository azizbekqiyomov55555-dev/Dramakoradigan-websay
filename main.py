import os
import json
import math
import asyncio
import subprocess
import time
import requests
import logging

from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import (
    Message,
    CallbackQuery,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

from static_ffmpeg import add_paths

add_paths()
logging.basicConfig(level=logging.INFO)

# ──────────────────────────────────────────────
#  SOZLAMALAR
# ──────────────────────────────────────────────

BOT_TOKEN        = "8626867961:AAGhbJzxdBBLM-SOLVvX57q1m8-_FP36xuM"
SEGMENT_SEC      = 15
MAX_MERGE_VIDEOS = 500
STATS_FILE       = "stats.json"

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode="Markdown")
)
dp  = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

user_data: dict = {}

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
    uid_s = str(uid)
    if uid_s not in s["users"]:
        s["users"][uid_s] = {"name": name, "merges": 0, "total_parts": 0, "total_size_mb": 0}
    else:
        s["users"][uid_s]["name"] = name
    save_stats(s)

def record_merge(uid: int, parts: int, size_mb: float):
    s = load_stats()
    uid_s = str(uid)
    if uid_s not in s["users"]:
        s["users"][uid_s] = {"name": "?", "merges": 0, "total_parts": 0, "total_size_mb": 0}
    s["users"][uid_s]["merges"]       += 1
    s["users"][uid_s]["total_parts"]  += parts
    s["users"][uid_s]["total_size_mb"] = round(s["users"][uid_s]["total_size_mb"] + size_mb, 2)
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
#  RANGLI TUGMALAR  (Bot API 9.4)
#  style: None=ko'k | "destructive"=qizil | "secondary"=kulrang
# ──────────────────────────────────────────────

def _ibtn(text, cb, style=None):
    """InlineKeyboardButton — style bilan"""
    btn = InlineKeyboardButton(text=text, callback_data=cb)
    if style:
        btn.model_extra["style"] = style   # aiogram extra field
        # aiogram 3.7+ dan boshlab: btn.style = style  ham ishlaydi
        try:
            object.__setattr__(btn, "style", style)
        except:
            pass
    return btn

def main_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎬 Kino qismlarini birlashtirish")],
            [KeyboardButton(text="🎞 Video ishlash"), KeyboardButton(text="🖼 Rasm ishlash")],
            [KeyboardButton(text="📊 Statistika"),    KeyboardButton(text="❓ Yordam")],
        ],
        resize_keyboard=True
    )

def merge_kb(count: int) -> InlineKeyboardMarkup:
    rows = []
    if count >= 1:
        rows.append([
            InlineKeyboardButton(
                text=f"🎬 Kino qismlarini birlashtirish ({count} ta qism)",
                callback_data="do_merge",
                **{"style": "destructive"}   # ← QIZIL
            )
        ])
    rows.append([
        InlineKeyboardButton(
            text="❌ Bekor qilish",
            callback_data="cancel_merge",
            **{"style": "secondary"}   # ← KULRANG
        )
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def video_action_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🗜 Siqish",  callback_data="v_comp",  **{"style": "secondary"}),
        InlineKeyboardButton(text="✂️ Bo'lish", callback_data="v_split", **{"style": "secondary"}),
    ]])

def copyright_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Taqiqni olib tashlash", callback_data="bp_medium", **{"style": "destructive"})],
        [InlineKeyboardButton(text="❌ Bekor qilish",          callback_data="cr_cancel",  **{"style": "secondary"})],
    ])

def bypass_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🟢 Yengil", callback_data="bp_soft")],
        [InlineKeyboardButton(text="🟡 O'rta",  callback_data="bp_medium")],
        [InlineKeyboardButton(text="🔴 Kuchli", callback_data="bp_hard",   **{"style": "destructive"})],
        [InlineKeyboardButton(text="❌ Bekor",  callback_data="cr_cancel", **{"style": "secondary"})],
    ])

def bypass_fallback_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🔧 Bypass usulini ishlatish", callback_data="cr_bypass", **{"style": "destructive"})
    ]])

# ──────────────────────────────────────────────
#  PROGRESS YORDAMCHI
# ──────────────────────────────────────────────

_last_edit: dict = {}

async def safe_edit(msg: Message, text: str, kb=None, min_gap=0.8):
    uid = msg.message_id
    now = time.time()
    if now - _last_edit.get(uid, 0) < min_gap:
        return
    _last_edit[uid] = now
    try:
        await msg.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
    except:
        pass

# ──────────────────────────────────────────────
#  DOWNLOAD PROGRESS
# ──────────────────────────────────────────────

async def download_with_progress(message: Message, status_msg: Message,
                                  label: str, dest: str) -> str:
    file_id = None
    if message.video:
        file_id = message.video.file_id
    elif message.document:
        file_id = message.document.file_id

    if not file_id:
        return ""

    file = await bot.get_file(file_id)
    file_size = file.file_size or 0

    await safe_edit(status_msg, f"📥 *{label}*\n{make_bar(0)} *0%*", min_gap=0)

    downloaded = 0
    chunk_size = 512 * 1024  # 512KB

    os.makedirs(os.path.dirname(dest) if os.path.dirname(dest) else "downloads", exist_ok=True)

    url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file.file_path}"

    loop = asyncio.get_event_loop()

    def _download():
        nonlocal downloaded
        import urllib.request
        with urllib.request.urlopen(url) as resp, open(dest, "wb") as f:
            while True:
                chunk = resp.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)

    await loop.run_in_executor(None, _download)

    pct = 100
    await safe_edit(
        status_msg,
        f"📥 *{label}*\n{make_bar(pct)} *{pct}%*",
        min_gap=0
    )
    return dest

# ──────────────────────────────────────────────
#  UPLOAD PROGRESS
# ──────────────────────────────────────────────

async def send_video_progress(uid: int, path: str, caption: str, status_msg: Message):
    await safe_edit(status_msg, f"📤 *Yuborilmoqda...*\n{make_bar(0)} *0%*", min_gap=0)
    try:
        with open(path, "rb") as f:
            await bot.send_video(
                chat_id=uid,
                video=f,
                caption=caption,
                supports_streaming=True,
            )
        await safe_edit(status_msg, f"📤 *Yuborilmoqda...*\n{make_bar(100)} *100%*", min_gap=0)
    except Exception as e:
        await safe_edit(status_msg, f"❌ Yuborishda xato: {e}", min_gap=0)

# ──────────────────────────────────────────────
#  BIRLASHTIRISH
# ──────────────────────────────────────────────

async def merge_with_progress(video_paths: list, out_path: str, status_msg: Message) -> bool:
    total          = len(video_paths)
    tmp_dir        = os.path.dirname(out_path) or "downloads"
    t              = [time.time()]
    total_duration = sum(get_duration(vp) for vp in video_paths)
    mins = int(total_duration // 60)
    secs = int(total_duration % 60)

    await safe_edit(
        status_msg,
        f"⚡ *Birlashtirish boshlandi!*\n\n"
        f"🎞 Qismlar: *{total} ta*\n"
        f"⏱ Jami: *{mins}:{secs:02d}*\n\n"
        f"{make_bar(5)} **5%**",
        min_gap=0
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
            "-progress", "pipe:1", "-nostats", dest
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
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
                        pct = pct_start + min(
                            int(done_s / total_duration * (pct_end - pct_start)),
                            pct_end - pct_start
                        )
                        now = time.time()
                        if now - t[0] >= 0.8:
                            t[0] = now
                            await safe_edit(
                                status_msg,
                                f"⚡ *Birlashtirilmoqda...*\n\n{make_bar(pct)} **{pct}%**"
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
        f"🔄 *Qismlar moslashtirilmoqda...*\n\n{make_bar(10)} **10%**",
        min_gap=0
    )

    remuxed = []
    for i, vpath in enumerate(video_paths):
        tmp_out = os.path.join(tmp_dir, f"_remux_{i}.mp4")
        proc_r  = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y", "-i", vpath, "-c", "copy", "-movflags", "+faststart", tmp_out,
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL
        )
        await proc_r.wait()
        pct = 10 + int((i + 1) / total * 45)
        now = time.time()
        if now - t[0] >= 0.8:
            t[0] = now
            await safe_edit(status_msg, f"🔄 *Moslashtirilmoqda...*\n\n🎞 *{i+1}/{total}*\n{make_bar(pct)} **{pct}%**")
        remuxed.append(tmp_out if (os.path.exists(tmp_out) and os.path.getsize(tmp_out) > 1024) else vpath)

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
#  BYPASS CONTENTID
# ──────────────────────────────────────────────

async def bypass_contentid(video_path: str, status_msg: Message) -> str | None:
    t   = [time.time()]
    out = f"downloads/_bypass_{os.path.basename(video_path)}"

    vf = ("hflip,crop=iw*0.97:ih*0.97:(iw-iw*0.97)/2:(ih-ih*0.97)/2,"
          "scale=iw/0.97:ih/0.97,eq=brightness=0.03:saturation=1.08:contrast=1.02,setpts=PTS/1.01")
    af = "asetrate=44100*1.03,aresample=44100,atempo=1.01"
    total_dur = get_duration(video_path)

    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vf", vf, "-af", af,
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart", "-progress", "pipe:1", "-nostats", out
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
                now    = time.time()
                if now - t[0] >= 0.8:
                    t[0] = now
                    await safe_edit(status_msg, f"🔧 *Taqiq olib tashlanmoqda...*\n\n{make_bar(pct)} **{pct}%**")
            except:
                pass
    await proc.communicate()
    return out if (os.path.exists(out) and os.path.getsize(out) > 0) else None

# ──────────────────────────────────────────────
#  /start
# ──────────────────────────────────────────────

@router.message(Command("start"))
async def cmd_start(message: Message):
    uid  = message.from_user.id
    name = message.from_user.first_name or "Foydalanuvchi"
    register_user(uid, name)
    await message.answer(
        "👋 *Assalomu alaykum!*\n\n"
        "🎬 Kino birlashtirish, video siqish yoki bo'lish uchun "
        "quyidagi tugmalardan foydalaning.",
        reply_markup=main_kb()
    )

# ──────────────────────────────────────────────
#  KINO BIRLASHTIRISH
# ──────────────────────────────────────────────

@router.message(F.text == "🎬 Kino qismlarini birlashtirish")
async def start_merge(message: Message):
    uid  = message.from_user.id
    name = message.from_user.first_name or "?"
    register_user(uid, name)
    clean_user(uid)
    user_data[uid] = {"mode": "merge", "videos": []}
    await message.answer(
        "🎬 *Kino birlashtirish rejimi yoqildi!*\n\n"
        "📌 Videolarni *tartib bilan* yuboring.\n"
        f"📦 Maksimal *{MAX_MERGE_VIDEOS}* ta qism.",
        reply_markup=merge_kb(0)
    )

# ──────────────────────────────────────────────
#  STATISTIKA
# ──────────────────────────────────────────────

@router.message(F.text == "📊 Statistika")
async def stats_handler(message: Message):
    data         = load_stats()
    users        = data.get("users", {})
    total_merges = data.get("total_merges", 0)
    total_users  = len(users)

    sorted_users = sorted(users.items(), key=lambda x: x[1].get("merges", 0), reverse=True)[:5]

    top_text = ""
    for i, (uid_s, info) in enumerate(sorted_users, 1):
        nm      = info.get("name", "?")
        merges  = info.get("merges", 0)
        parts   = info.get("total_parts", 0)
        size_mb = info.get("total_size_mb", 0)
        top_text += f"  {i}\\. *{nm}* — 🎬{merges} ta | 🎞{parts} qism | 📦{size_mb}MB\n"

    if not top_text:
        top_text = "  _Hali ma'lumot yo'q_\n"

    await message.answer(
        f"📊 *Bot Statistikasi*\n{'─'*28}\n\n"
        f"👥 Jami foydalanuvchi: *{total_users}* ta\n"
        f"🎬 Jami birlashtirish: *{total_merges}* ta\n"
        f"⚙️ Faol seans: *{len(user_data)}* ta\n\n"
        f"🏆 *Top foydalanuvchilar:*\n{top_text}"
    )

# ──────────────────────────────────────────────
#  YORDAM
# ──────────────────────────────────────────────

@router.message(F.text == "❓ Yordam")
async def help_handler(message: Message):
    await message.answer(
        "❓ *Yordam:*\n\n"
        "🎬 *Kino birlashtirish:*\n"
        "Videolarni tartib bilan yuboring → Birlashtir tugmasini bosing\n\n"
        "🎞 *Video ishlash:*\n"
        "Video yuboring → Siqish yoki bo'lish tanlang\n\n"
        f"📦 Maksimal: *{MAX_MERGE_VIDEOS}* ta qism"
    )

@router.message(F.text == "🎞 Video ishlash")
async def video_mode_handler(message: Message):
    await message.answer("🎞 *Video ishlash:*\n\nVideo yuboring.")

@router.message(F.text == "🖼 Rasm ishlash")
async def image_mode_handler(message: Message):
    await message.answer("🖼 *Rasm ishlash:*\n\nRasm yuboring.")

# ──────────────────────────────────────────────
#  VIDEO KELGANDA
# ──────────────────────────────────────────────

@router.message(F.video | F.document)
async def handle_video(message: Message):
    if message.document and not message.document.mime_type.startswith("video/"):
        return

    uid  = message.from_user.id
    name = message.from_user.first_name or "?"
    register_user(uid, name)

    # ── BIRLASHTIRISH REJIMI ──
    if uid in user_data and user_data[uid].get("mode") == "merge":
        videos = user_data[uid]["videos"]
        count  = len(videos)

        if count >= MAX_MERGE_VIDEOS:
            await message.reply(f"⚠️ Maksimal *{MAX_MERGE_VIDEOS}* ta qism!")
            return

        part_n    = count + 1
        status    = await message.reply(f"📥 *{part_n}-qism yuklanmoqda...*\n{make_bar(0)}")
        dest_path = f"downloads/merge_{uid}_{count}.mp4"

        file_path = await download_with_progress(message, status, f"{part_n}-qism yuklanmoqda", dest_path)
        if not file_path:
            await safe_edit(status, "❌ Yuklab bo'lmadi.", min_gap=0)
            return

        videos.append(file_path)
        new_count = len(videos)
        hint = (f"📤 Keyingi: *{new_count+1}-qism*ni yuboring yoki birlashtiring."
                if new_count < MAX_MERGE_VIDEOS else f"⚠️ Maksimal {MAX_MERGE_VIDEOS} ta. Birlashtiring.")

        await safe_edit(
            status,
            f"✅ *{part_n}-qism qabul qilindi!*\n\n"
            f"📋 Jami: *{new_count} ta qism*\n\n{hint}",
            kb=merge_kb(new_count),
            min_gap=0
        )
        return

    # ── ODDIY VIDEO REJIMI ──
    status    = await message.reply(f"📥 *Video yuklanmoqda...*\n{make_bar(0)}")
    dest_path = f"downloads/vid_{uid}.mp4"
    file_path = await download_with_progress(message, status, "Video yuklanmoqda", dest_path)

    if not file_path:
        await safe_edit(status, "❌ Yuklab bo'lmadi.", min_gap=0)
        return

    user_data[uid] = {"path": file_path, "type": "video"}
    await safe_edit(status, "✅ Video yuklandi\\. Tanlang:", kb=video_action_kb(), min_gap=0)

# ──────────────────────────────────────────────
#  CALLBACK HANDLER
# ──────────────────────────────────────────────

@router.callback_query()
async def on_callback(query: CallbackQuery):
    uid  = query.from_user.id
    data = query.data
    msg  = query.message

    await query.answer()

    # ── BIRLASHTIRISH BEKOR ──
    if data == "cancel_merge":
        clean_user(uid)
        await msg.edit_text("❌ Birlashtirish bekor qilindi.")
        return

    # ── BIRLASHTIR ──
    if data == "do_merge":
        if uid not in user_data or user_data[uid].get("mode") != "merge":
            await query.answer("Ma'lumot topilmadi.", show_alert=True)
            return
        videos = user_data[uid].get("videos", [])
        if len(videos) < 2:
            await query.answer("⚠️ Kamida 2 ta qism kerak!", show_alert=True)
            return

        total    = len(videos)
        status   = await msg.edit_text(f"🎬 *{total} ta qism birlashtirilmoqda...*\n\n{make_bar(0)} **0%**")
        out_path = f"downloads/merged_{uid}.mp4"
        ok       = await merge_with_progress(videos, out_path, status)

        if ok:
            size_mb = round(os.path.getsize(out_path) / (1024 * 1024), 2)
            record_merge(uid, total, size_mb)
            await safe_edit(
                status,
                f"✅ *Birlashtirish tugadi!*\n\n📹 {total} ta qism\n📦 *{size_mb} MB*\n\n📤 *Yuborilmoqda...*",
                min_gap=0
            )
            await send_video_progress(uid, out_path, f"🎬 *Kino tayyor!*\n📹 {total} ta qism\n📦 {size_mb} MB", status)
            try:
                await status.delete()
            except:
                pass
            try:
                os.remove(out_path)
            except:
                pass
        else:
            await safe_edit(status, "❌ *Birlashtirish muvaffaqiyatsiz.*\n\nVideolar formati har xil bo'lishi mumkin.", min_gap=0)

        for vp in videos:
            try:
                os.remove(vp)
            except:
                pass
        user_data.pop(uid, None)
        return

    # ── BYPASS ──
    if data == "cr_bypass":
        if uid not in user_data or "path" not in user_data.get(uid, {}):
            await query.answer("Fayl topilmadi.", show_alert=True)
            return
        await msg.edit_text(
            "🔧 *Bypass darajasini tanlang:*\n\n"
            "🟢 *Yengil* — +2% pitch\n"
            "🟡 *O'rta* — +3% pitch + EQ\n"
            "🔴 *Kuchli* — +4% pitch + EQ + shovqin",
            reply_markup=bypass_kb()
        )
        return

    if data in ("bp_soft", "bp_medium", "bp_hard"):
        if uid not in user_data or "path" not in user_data.get(uid, {}):
            await query.answer("Fayl topilmadi.", show_alert=True)
            return

        level_text = {"soft": "🟢 Yengil", "medium": "🟡 O'rta", "hard": "🔴 Kuchli"}[data.split("_")[1]]
        video_path = user_data[uid]["path"]

        status   = await msg.edit_text(f"🔧 *ContentID chetlab o'tilmoqda...*\n\nDaraja: {level_text}\n\n{make_bar(0)} **0%**")
        out_path = await bypass_contentid(video_path, status)

        if not out_path:
            await safe_edit(status, "❌ Xato yuz berdi. Qaytadan urinib ko'ring.", min_gap=0)
            clean_user(uid)
            return

        size_mb = round(os.path.getsize(out_path) / (1024 * 1024), 2)
        await safe_edit(status, f"✅ *Tayyor!*\n\n📦 *{size_mb} MB*\n📤 *Yuborilmoqda...*", min_gap=0)
        await send_video_progress(
            uid, out_path,
            f"🚫 *ContentID bypass qilindi!*\n🔧 {level_text}\n📦 {size_mb} MB\n\n✅ Endi YouTube'ga yuklay olasiz!",
            status
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
        await msg.edit_text("❌ Bekor qilindi.")
        return

    # ── VIDEO SIQISH / BO'LISH ──
    if data == "v_comp":
        if uid not in user_data:
            await query.answer("Ma'lumot topilmadi.", show_alert=True)
            return
        await msg.edit_text("🗜 *Necha MB bo'lsin?*\n\nFaqat raqam yuboring:")
        user_data[uid]["action"] = "wait_v_size"

    elif data == "v_split":
        if uid not in user_data:
            await query.answer("Ma'lumot topilmadi.", show_alert=True)
            return
        await msg.edit_text("✂️ *Nechta qismga bo'linsin?* (2–20):\n\nFaqat raqam yuboring:")
        user_data[uid]["action"] = "wait_v_split"

# ──────────────────────────────────────────────
#  MATN INPUT (siqish/bo'lish)
# ──────────────────────────────────────────────

@router.message(F.text & ~F.text.startswith("/") & ~F.text.regexp(r"^(🎬|🎞|🖼|📊|❓|🚫)"))
async def text_input(message: Message):
    uid = message.from_user.id
    if uid not in user_data or "action" not in user_data[uid]:
        return
    action = user_data[uid]["action"]
    path   = user_data[uid].get("path", "")

    if action == "wait_v_size":
        try:
            target = int(message.text.strip())
            st     = await message.reply(f"⏳ *{target} MB* ga siqilmoqda...")
            out    = f"downloads/res_{uid}.mp4"
            dur    = get_duration(path)
            if dur > 0:
                vb  = max(int((target * 8000) / dur - 128), 200)
                crf = 18 if vb >= 2500 else 21 if vb >= 1500 else 23 if vb >= 900 else 26 if vb >= 500 else 28
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
                await message.reply_video(out, caption=f"✅ Tayyor\\! ~{target} MB")
                try:
                    await st.delete()
                    os.remove(out)
                except:
                    pass
            else:
                await st.edit_text("❌ Siqib bo'lmadi.")
            clean_user(uid)
        except:
            await message.reply("❌ Faqat son kiriting\\!")

    elif action == "wait_v_split":
        try:
            parts = int(message.text.strip())
            if parts < 2 or parts > 20:
                await message.reply("❌ 2 dan 20 gacha son kiriting.")
                return
            st       = await message.reply(f"⏳ *{parts}* qismga bo'linmoqda...")
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
                    await message.reply_video(out, caption=f"✂️ {p+1}\\-qism / {parts}")
                    try:
                        os.remove(out)
                    except:
                        pass
                    sent += 1
            await st.edit_text(f"✅ *{sent}* ta qism yuborildi.")
            clean_user(uid)
        except:
            await message.reply("❌ Xato\\!")

# ──────────────────────────────────────────────
#  RUN
# ──────────────────────────────────────────────

async def main():
    os.makedirs("downloads", exist_ok=True)
    print("🤖 Bot ishga tushdi! (aiogram 3.x)")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
