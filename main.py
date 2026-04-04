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
from pyrogram.enums import ParseMode
from static_ffmpeg import add_paths

add_paths()

# --- SOZLAMALAR ---
API_ID    = 37366974
API_HASH  = "08d09c7ed8b7cb414ed6a99c104f1bd6"
BOT_TOKEN = "8713773581:AAEu0fZmpEMyg0aNqrbVOtnbNaXhXbqONGM"

RAPIDAPI_KEY = "30f65179admsh07b2707861cb0f6p104a91jsn2bb1ee84511f"
SEGMENT_SEC  = 15

app = Client("video_processor", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

user_data = {}
MAX_MERGE_VIDEOS = 150

# ──────────────────────────────────────────────
#  YORDAMCHI
# ──────────────────────────────────────────────

def make_bar(pct, n=15):
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

def parts_list_text(videos):
    lines = [f"  ✅ {i+1}-qism" for i in range(len(videos))]
    return "\n".join(lines) if lines else "  (hali yo'q)"

def merge_keyboard(count):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🎬 Birlashtir  ({count} ta qism)", callback_data="do_merge")],
        [InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel_merge")]
    ])

async def safe_edit(msg, text, kb=None, last_t=None, min_gap=0.5):
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

_dl_last: dict      = {}
_dl_anim_task: dict = {}
ANIM_FRAMES         = ["⏳", "⌛"]

async def _dl_animate(msg, label):
    frame = 0
    while True:
        try:
            await asyncio.sleep(1.2)
            icon = ANIM_FRAMES[frame % len(ANIM_FRAMES)]
            await msg.edit_text(
                f"{icon} *{label}*\n{make_bar(0)}\n_Yuklanmoqda..._",
                parse_mode=ParseMode.MARKDOWN
            )
            frame += 1
        except asyncio.CancelledError:
            break
        except:
            break

async def dl_progress(current, total, msg, label):
    uid  = id(msg)
    task = _dl_anim_task.pop(uid, None)
    if task and not task.done():
        task.cancel()

    now = time.time()
    if now - _dl_last.get(uid, 0) < 0.5:
        return
    _dl_last[uid] = now

    if not total or total == 0:
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
#  UPLOAD PROGRESS (send_video uchun)
# ──────────────────────────────────────────────

_up_last: dict = {}

async def up_progress(current, total, msg, label):
    """send_video() uchun upload progress"""
    uid = id(msg)
    now = time.time()
    if now - _up_last.get(uid, 0) < 1.0:   # 1 soniyada bir marta yangilanadi
        return
    _up_last[uid] = now

    if not total or total == 0:
        return

    pct    = int(current * 100 / total)
    cur_mb = round(current / (1024 * 1024), 1)
    tot_mb = round(total   / (1024 * 1024), 1)

    bar = make_bar(pct)
    try:
        await msg.edit_text(
            f"📤 *{label}*\n"
            f"{bar} *{pct}%*\n"
            f"`{cur_mb} MB / {tot_mb} MB`",
            parse_mode=ParseMode.MARKDOWN
        )
    except:
        pass

# ──────────────────────────────────────────────
#  BIRLASHTIRISH — TUZATILGAN
# ──────────────────────────────────────────────

def calc_crf_for_size(total_duration_sec: float, max_size_mb: float = 1900.0) -> int:
    """Jami vaqtdan kelib chiqib optimal CRF hisoblash. max_size_mb=1900 (Telegram 2GB limit)"""
    if total_duration_sec <= 0:
        return 18
    audio_kbps  = 192
    total_kbits = max_size_mb * 1024 * 8
    audio_kbits = audio_kbps * total_duration_sec
    video_kbits = total_kbits - audio_kbits
    needed_vbr  = int(video_kbits / total_duration_sec)

    # Sifatli CRF jadvali (past = yaxshi sifat)
    if needed_vbr >= 4000:   return 14
    elif needed_vbr >= 3000: return 15
    elif needed_vbr >= 2500: return 16
    elif needed_vbr >= 2000: return 17
    elif needed_vbr >= 1500: return 18
    elif needed_vbr >= 1000: return 19
    elif needed_vbr >= 700:  return 20
    elif needed_vbr >= 500:  return 21
    else:                    return 22


async def merge_with_progress(video_paths: list, out_path: str, status_msg) -> bool:
    """
    TUZATILGAN merge funksiyasi:
      1. Avval -c copy bilan tezkor birlashtirish (encode yo'q)
      2. Agar copy ishlamasa → ultrafast encode (slow o'rniga 50x tez)
      3. Har jarayonga timeout — bot qotib qolmaydi
      4. Xatolar logga tushadi
    """
    total   = len(video_paths)
    tmp_dir = os.path.dirname(out_path)
    t       = [time.time()]

    os.makedirs(tmp_dir, exist_ok=True)

    # 1-QADAM: Jami davomiylik va CRF
    await safe_edit(status_msg, f"📐 *Hajm hisoblanmoqda...*\n\n{make_bar(0)} **0%**",
                    last_t=t, min_gap=0)

    total_duration = sum(get_duration(vp) for vp in video_paths)
    target_crf     = calc_crf_for_size(total_duration, max_size_mb=1900)

    await safe_edit(
        status_msg,
        f"📐 *Maqsad sifat:* CRF `{target_crf}` (2GB chegarasi)\n"
        f"⏱ Jami: `{int(total_duration//60)}:{int(total_duration%60):02d}`\n\n"
        f"{make_bar(3)} **3%**",
        last_t=t, min_gap=0
    )

    list_file = os.path.join(tmp_dir, "_list.txt")
    with open(list_file, "w", encoding="utf-8") as f:
        for vp in video_paths:
            f.write(f"file '{os.path.abspath(vp)}'\n")

    # ══════════════════════════════════════════
    # USUL 1: -c copy (encode yo'q — eng tez)
    # ══════════════════════════════════════════
    await safe_edit(status_msg,
                    f"⚡ *Tezkor birlashtirish (copy)...*\n\n{make_bar(10)} **10%**",
                    last_t=t, min_gap=0)

    copy_out = out_path.replace(".mp4", "_copy.mp4")
    copy_cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", list_file,
        "-c", "copy",
        "-movflags", "+faststart",
        "-progress", "pipe:1", "-nostats",
        copy_out
    ]

    copy_ok = False
    try:
        proc = await asyncio.create_subprocess_exec(
            *copy_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        async def _read_copy():
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                line = line.decode("utf-8", errors="ignore").strip()
                if line.startswith("out_time_ms=") and total_duration > 0:
                    try:
                        done_s = int(line.split("=")[1]) / 1_000_000
                        pct    = 10 + min(int(done_s / total_duration * 85), 85)
                        await safe_edit(
                            status_msg,
                            f"⚡ *Birlashtirilmoqda (copy)...*\n\n📊 {make_bar(pct)} **{pct}%**",
                            last_t=t
                        )
                    except:
                        pass

        try:
            await asyncio.wait_for(_read_copy(), timeout=1800)  # 30 daqiqa
        except asyncio.TimeoutError:
            proc.kill()

        await proc.wait()

        if os.path.exists(copy_out) and os.path.getsize(copy_out) > 1024:
            os.rename(copy_out, out_path)
            copy_ok = True
            print("[MERGE] ✅ copy mode muvaffaqiyatli!")
        else:
            print("[MERGE] ⚠️ copy mode bajarilmadi → encode rejimiga o'tilmoqda")

    except Exception as e:
        print(f"[MERGE copy ERROR] {e}")

    # ══════════════════════════════════════════
    # USUL 2: ultrafast encode (copy ishlamasa)
    # ══════════════════════════════════════════
    if not copy_ok:
        reenc = []

        await safe_edit(status_msg,
                        f"⚙️ *Encode rejimi (ultrafast)...*\n\n{make_bar(5)} **5%**",
                        last_t=t, min_gap=0)

        for i, vpath in enumerate(video_paths):
            part_n  = i + 1
            tmp_out = os.path.join(tmp_dir, f"_p{i}.mp4")
            dur     = get_duration(vpath)
            _, h    = get_video_info(vpath)

            scale = "scale=-2:min(ih\\,1080)" if h > 1080 else "scale=-2:trunc(ih/2)*2"

            cmd = [
                "ffmpeg", "-y", "-i", vpath,
                "-vf", scale,
                "-c:v", "libx264",
                "-preset", "fast",        # ← yaxshi sifat/tezlik balansi
                "-crf", str(target_crf),
                "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k",
                "-movflags", "+faststart",
                "-progress", "pipe:1", "-nostats",
                tmp_out
            ]

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            async def _read_encode(proc=proc, dur=dur, i=i, part_n=part_n):
                while True:
                    line = await proc.stdout.readline()
                    if not line:
                        break
                    line = line.decode("utf-8", errors="ignore").strip()
                    if line.startswith("out_time_ms=") and dur > 0:
                        try:
                            done_s   = int(line.split("=")[1]) / 1_000_000
                            part_pct = min(int(done_s / dur * 100), 100)
                            overall  = int(((i * 100 + part_pct) / (total * 100)) * 85)
                            await safe_edit(
                                status_msg,
                                f"⚙️ *Tayyorlanmoqda...*\n\n"
                                f"🎞 Qism: *{part_n}/{total}*  —  {part_pct}%\n"
                                f"{make_bar(part_pct)}\n\n"
                                f"📊 Umumiy: {make_bar(overall)} **{overall}%**\n"
                                f"🎯 CRF: `{target_crf}`",
                                last_t=t
                            )
                        except:
                            pass

            try:
                await asyncio.wait_for(_read_encode(), timeout=1200)  # 20 daqiqa/qism
            except asyncio.TimeoutError:
                proc.kill()
                print(f"[MERGE] {part_n}-qism timeout!")

            _, stderr_data = await proc.communicate()

            if not os.path.exists(tmp_out) or os.path.getsize(tmp_out) == 0:
                err = stderr_data.decode("utf-8", errors="ignore")[-300:]
                print(f"[MERGE encode ERROR qism {part_n}]: {err}")
            else:
                reenc.append(tmp_out)

            done_overall = int(((i + 1) / total) * 85)
            await safe_edit(
                status_msg,
                f"⚙️ *Tayyorlanmoqda...*\n\n"
                f"✅ Tayyor: *{i+1}/{total}* qism\n\n"
                f"📊 Umumiy: {make_bar(done_overall)} **{done_overall}%**",
                last_t=t
            )

        if not reenc:
            try:
                os.remove(list_file)
            except:
                pass
            return False

        # Concat (encode qilingan qismlarni birlashtirish)
        with open(list_file, "w", encoding="utf-8") as f:
            for fp in reenc:
                f.write(f"file '{os.path.abspath(fp)}'\n")

        await safe_edit(
            status_msg,
            f"🔗 *Qismlar birlashtirilmoqda...*\n\n📊 {make_bar(90)} **90%**\n\n_Deyarli tayyor..._",
            last_t=t, min_gap=0
        )

        total_enc_dur = sum(get_duration(fp) for fp in reenc)
        concat_cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", list_file,
            "-c", "copy",
            "-movflags", "+faststart",
            "-progress", "pipe:1", "-nostats",
            out_path
        ]
        proc2 = await asyncio.create_subprocess_exec(
            *concat_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL
        )
        while True:
            line = await proc2.stdout.readline()
            if not line:
                break
            line = line.decode("utf-8", errors="ignore").strip()
            if line.startswith("out_time_ms=") and total_enc_dur > 0:
                try:
                    done_s = int(line.split("=")[1]) / 1_000_000
                    pct    = 90 + min(int(done_s / total_enc_dur * 10), 10)
                    await safe_edit(
                        status_msg,
                        f"🔗 *Birlashtirilmoqda...*\n\n📊 {make_bar(pct)} **{pct}%**",
                        last_t=t
                    )
                except:
                    pass
        await proc2.wait()

        for fp in reenc:
            try:
                os.remove(fp)
            except:
                pass

    # Cleanup list file
    try:
        os.remove(list_file)
    except:
        pass

    # ── Hajm tekshirish (>1900MB bo'lsa qayta siqish) ──
    if os.path.exists(out_path):
        final_mb = os.path.getsize(out_path) / (1024 * 1024)
        if final_mb > 1900:
            await safe_edit(
                status_msg,
                f"⚠️ *Hajm {final_mb:.0f} MB — 2GB dan oshdi!*\n\n"
                f"🗜 Qayta siqilmoqda...\n{make_bar(0)} **0%**",
                last_t=t, min_gap=0
            )
            compressed = out_path.replace(".mp4", "_c.mp4")
            new_crf    = min(target_crf + 2, 24)
            re_dur     = get_duration(out_path)

            compress_cmd = [
                "ffmpeg", "-y", "-i", out_path,
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-crf", str(new_crf),
                "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "128k",
                "-movflags", "+faststart",
                "-progress", "pipe:1", "-nostats",
                compressed
            ]
            proc3 = await asyncio.create_subprocess_exec(
                *compress_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL
            )
            while True:
                line = await proc3.stdout.readline()
                if not line:
                    break
                line = line.decode("utf-8", errors="ignore").strip()
                if line.startswith("out_time_ms=") and re_dur > 0:
                    try:
                        done_s = int(line.split("=")[1]) / 1_000_000
                        pct    = min(int(done_s / re_dur * 100), 100)
                        await safe_edit(
                            status_msg,
                            f"🗜 *Qayta siqilmoqda...*\n\n{make_bar(pct)} **{pct}%**",
                            last_t=t
                        )
                    except:
                        pass
            await proc3.wait()
            try:
                os.remove(out_path)
            except:
                pass
            if os.path.exists(compressed):
                os.rename(compressed, out_path)

    return os.path.exists(out_path)


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
        "-vf", vf,
        "-af", af,
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        "-progress", "pipe:1", "-nostats",
        out
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

    err_text = stderr_data.decode("utf-8", errors="ignore")[-500:]
    print(f"[BYPASS ERROR] {err_text}")
    return None


# ──────────────────────────────────────────────
#  SHAZAM ORQALI TEKSHIRISH + O'CHIRISH
# ──────────────────────────────────────────────

def acr_check(audio_bytes: bytes) -> dict:
    try:
        resp = requests.post(
            "https://api.audd.io/",
            data={"api_token": "", "return": "apple_music,spotify"},
            files={"file": ("audio.mp3", audio_bytes, "audio/mpeg")},
            timeout=25
        )
        res    = resp.json()
        result = res.get("result")
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
    tmp_dir      = "downloads"

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
                [
                    "ffmpeg", "-y",
                    "-i", video_path,
                    "-ss", f"{s:.3f}",
                    "-t",  f"{dur_seg:.3f}",
                    "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
                    "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "192k",
                    "-avoid_negative_ts", "make_zero",
                    "-movflags", "+faststart",
                    pf
                ],
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
                [
                    "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                    "-i", list_file,
                    "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
                    "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "192k",
                    "-movflags", "+faststart",
                    out_path
                ],
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

    # ── BIRLASHTIRISH ──
    if uid in user_data and user_data[uid].get("mode") == "merge":
        videos  = user_data[uid]["videos"]
        count   = len(videos)
        if count >= MAX_MERGE_VIDEOS:
            await message.reply_text(f"⚠️ Maksimal *{MAX_MERGE_VIDEOS}* ta!", parse_mode=ParseMode.MARKDOWN)
            return

        part_n    = count + 1
        status    = await message.reply_text(
            f"⏳ *{part_n}-qism yuklanmoqda...*\n{make_bar(0)}\n_Yuklanmoqda..._",
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
        f"⏳ *Video yuklanmoqda...*\n{make_bar(0)}\n_Yuklanmoqda..._",
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
        "orig_size": round(os.path.getsize(file_path) / (1024*1024), 2)
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
            f"📋 *Tartib:*\n{parts_txt}\n\n{make_bar(0)} **0%**",
            parse_mode=ParseMode.MARKDOWN
        )
        out_path = f"downloads/merged_{uid}.mp4"
        ok       = await merge_with_progress(videos, out_path, status)

        if ok:
            size_mb = round(os.path.getsize(out_path) / (1024*1024), 2)
            size_ok = "✅" if size_mb < 1900 else "⚠️"
            await status.edit_text(
                f"✅ *Birlashtirish tugadi!*\n\n"
                f"📹 {total} ta qism\n"
                f"📦 Hajmi: {size_ok} *{size_mb} MB*\n\n"
                f"📤 *Yuborilmoqda...*",
                parse_mode=ParseMode.MARKDOWN
            )
            await client.send_video(
                uid, out_path,
                caption=(
                    f"🎬 *Kino tayyor!*\n"
                    f"📹 {total} ta qism\n"
                    f"📦 {size_mb} MB"
                ),
                supports_streaming=True,
                parse_mode=ParseMode.MARKDOWN,
                progress=up_progress,
                progress_args=(status, "Yuborilmoqda")
            )
            try:
                await status.delete()
            except:
                pass
            try:
                os.remove(out_path)
            except:
                pass
        else:
            await status.edit_text("❌ Birlashtirish muvaffaqiyatsiz.")

        for vp in videos:
            try:
                os.remove(vp)
            except:
                pass
        user_data.pop(uid, None)
        return

    # ── TO'LIQ OVOZ O'CHIRISH ──
    if data == "cr_mute_full":
        if uid not in user_data or "path" not in user_data.get(uid, {}):
            await q.answer("Fayl topilmadi.", show_alert=True)
            return

        video_path = user_data[uid]["path"]
        status     = await q.message.edit_text(
            "🔇 *Ovoz o'chirilmoqda...*\n\n`░░░░░░░░░░░░` 0%",
            parse_mode=ParseMode.MARKDOWN
        )

        out_path  = f"downloads/_muted_{uid}.mp4"
        total_dur = get_duration(video_path)
        t         = [time.time()]

        cmd = [
            "ffmpeg", "-y", "-i", video_path,
            "-an", "-c:v", "copy",
            "-movflags", "+faststart",
            "-progress", "pipe:1", "-nostats",
            out_path
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
                    pct    = min(int(done_s / total_dur * 100), 100)
                    await safe_edit(
                        status,
                        f"🔇 *Ovoz o'chirilmoqda...*\n\n{make_bar(pct)} **{pct}%**",
                        last_t=t
                    )
                except:
                    pass
        await proc.wait()

        if not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
            await status.edit_text("❌ Xato yuz berdi. Qaytadan urinib ko'ring.")
            clean_user(uid)
            return

        size_mb = round(os.path.getsize(out_path) / (1024*1024), 2)
        await status.edit_text(
            f"✅ *Tayyor!*\n\n🔇 Ovoz to'liq o'chirildi\n📦 Hajmi: *{size_mb} MB*\n📤 *Yuborilmoqda...*",
            parse_mode=ParseMode.MARKDOWN
        )
        await client.send_video(
            uid, out_path,
            caption=f"🔇 *Ovoz o'chirilgan video*\n📦 {size_mb} MB\n\n✅ Endi YouTube'ga yuklay olasiz!",
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
                [InlineKeyboardButton("🟢 Yengil", callback_data="bp_soft")],
                [InlineKeyboardButton("🟡 O'rta",  callback_data="bp_medium")],
                [InlineKeyboardButton("🔴 Kuchli", callback_data="bp_hard")],
                [InlineKeyboardButton("❌ Bekor",  callback_data="cr_cancel")],
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
            f"🔧 *ContentID chetlab o'tilmoqda...*\n\nDaraja: {level_text}\n\n{make_bar(0)} **0%**",
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
            f"🔍 *Tekshirilmoqda...*\n\nRejim: *{mode_text}*\n{make_bar(0)} **0%**",
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
                vb = max(int((target * 8000) / dur - 128), 200)
                if vb >= 2500:   crf = 18
                elif vb >= 1500: crf = 21
                elif vb >= 900:  crf = 23
                elif vb >= 500:  crf = 26
                else:            crf = 28
                cmd = [
                    "ffmpeg", "-y", "-i", path,
                    "-vf", "scale=-2:1080",
                    "-c:v", "libx264",
                    "-preset", "ultrafast",
                    "-crf", str(crf),
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
        "Videolarni tartib bilan yuboring → Birlashtir\n\n"
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
#  RUN
# ──────────────────────────────────────────────

if __name__ == "__main__":
    os.makedirs("downloads", exist_ok=True)
    print("🤖 Bot ishga tushdi!")
    app.run()
