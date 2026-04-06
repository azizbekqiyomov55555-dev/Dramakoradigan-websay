#!/usr/bin/env python3
# ============================================================
#   SMM BOT - Yangilangan versiya v3 (TUZATILGAN)
#   Tuzatishlar:
#     1. API o'chib qayta qo'shilsa xizmatlar bajariladi
#        (api_id o'rniga api_url+key bo'yicha avtomatik topadi)
#     2. plat_ren_save bug tuzatildi (yangi qo'shish + edit ajratildi)
#     3. Xizmat qo'shishda API ni URL bo'yicha topadi (ID emas)
#     4. Barcha mavjud funksionallik saqlanadi
#   Ishlatish: pip install aiogram aiohttp
# ============================================================

import asyncio
import logging
import sqlite3
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardRemove,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================
#  ⚙️  SOZLAMALAR
# ============================================================
BOT_TOKEN = "8766213463:AAGtuC1RWpd-QCCb6oLMOjYDH553Pbam8V0"
ADMIN_IDS = [8537782289]

def get_platforms():
    conn = db(); c = conn.cursor()
    c.execute("SELECT key, name FROM platforms ORDER BY sort_order, id")
    rows = c.fetchall(); conn.close()
    if not rows:
        return {
            "telegram":  "✈️ Telegram",
            "instagram": "📸 Instagram",
            "youtube":   "▶️ Youtube",
            "tiktok":    "🎵 Tik tok",
        }
    return {row[0]: row[1] for row in rows}

def get_platforms_list():
    conn = db(); c = conn.cursor()
    c.execute("SELECT id, key, name FROM platforms ORDER BY sort_order, id")
    rows = c.fetchall(); conn.close()
    return rows

DB = "smm_bot.db"

# ─────────────────────────────────────────────────────────────
#  JSONBIN
# ─────────────────────────────────────────────────────────────
JSONBIN_API_KEY = "$2a$10$mQZC26SFNwuUJbIo3fANVO3eiIMW4jWdJTva4/6tBlESt4AAde.mi"
JSONBIN_BIN_ID  = "69cc43a2856a682189e936f0"
JSONBIN_URL     = f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}"

async def jsonbin_save():
    try:
        conn = db(); c = conn.cursor()

        c.execute("SELECT key,name,sort_order FROM platforms")
        platforms = [{"key":r[0],"name":r[1],"sort_order":r[2]} for r in c.fetchall()]

        c.execute("SELECT id,name,platform,is_active FROM categories")
        categories = [{"id":r[0],"name":r[1],"platform":r[2],"is_active":r[3]} for r in c.fetchall()]

        c.execute("SELECT id,name,url,api_key,price_per1000 FROM apis")
        apis = [{"id":r[0],"name":r[1],"url":r[2],"api_key":r[3],"price_per1000":r[4]} for r in c.fetchall()]

        c.execute("SELECT id,category_id,api_id,api_service_id,name,min_qty,max_qty,price_per1000,is_active FROM services")
        services = [{"id":r[0],"category_id":r[1],"api_id":r[2],"api_service_id":r[3],"name":r[4],"min_qty":r[5],"max_qty":r[6],"price_per1000":r[7],"is_active":r[8]} for r in c.fetchall()]

        c.execute("SELECT id,pay_type,name,card_number,card_expiry,card_holder,is_active FROM manual_payments")
        payments = [{"id":r[0],"pay_type":r[1],"name":r[2],"card_number":r[3],"card_expiry":r[4],"card_holder":r[5],"is_active":r[6]} for r in c.fetchall()]

        c.execute("SELECT channel_id,channel_name,channel_link FROM channels")
        channels = [{"channel_id":r[0],"channel_name":r[1],"channel_link":r[2]} for r in c.fetchall()]

        c.execute("SELECT key,value FROM settings")
        settings = {r[0]:r[1] for r in c.fetchall()}

        c.execute("SELECT id,title,content FROM guides")
        guides = [{"id":r[0],"title":r[1],"content":r[2]} for r in c.fetchall()]

        conn.close()

        data = {
            "platforms": platforms,
            "categories": categories,
            "apis": apis,
            "services": services,
            "payments": payments,
            "channels": channels,
            "settings": settings,
            "guides": guides,
        }

        async with aiohttp.ClientSession() as s:
            async with s.put(
                JSONBIN_URL,
                headers={"Content-Type": "application/json", "X-Master-Key": JSONBIN_API_KEY},
                json=data,
                timeout=aiohttp.ClientTimeout(total=15)
            ) as r:
                if r.status == 200:
                    logger.info("✅ JSONBin ga saqlandi!")
                    return True
                else:
                    logger.error(f"JSONBin xato: {r.status}")
                    return False
    except Exception as e:
        logger.error(f"jsonbin_save xato: {e}")
        return False

async def jsonbin_restore():
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(
                JSONBIN_URL + "/latest",
                headers={"X-Master-Key": JSONBIN_API_KEY},
                timeout=aiohttp.ClientTimeout(total=15)
            ) as r:
                if r.status != 200:
                    logger.warning(f"JSONBin o'qish xato: {r.status}")
                    return False
                result = await r.json()
                data = result.get("record", {})

        conn = db(); c = conn.cursor()

        if data.get("platforms"):
            c.execute("SELECT COUNT(*) FROM platforms"); cnt = c.fetchone()[0]
            if cnt == 0:
                for p in data["platforms"]:
                    c.execute("INSERT OR IGNORE INTO platforms(key,name,sort_order) VALUES(?,?,?)",
                              (p["key"], p["name"], p.get("sort_order",0)))

        if data.get("categories"):
            c.execute("SELECT COUNT(*) FROM categories"); cnt = c.fetchone()[0]
            if cnt == 0:
                for cat in data["categories"]:
                    c.execute("INSERT INTO categories(id,name,platform,is_active) VALUES(?,?,?,?)",
                              (cat["id"],cat["name"],cat["platform"],cat["is_active"]))

        if data.get("apis"):
            c.execute("SELECT COUNT(*) FROM apis"); cnt = c.fetchone()[0]
            if cnt == 0:
                for api in data["apis"]:
                    c.execute("INSERT INTO apis(id,name,url,api_key,price_per1000) VALUES(?,?,?,?,?)",
                              (api["id"],api["name"],api["url"],api["api_key"],api["price_per1000"]))

        if data.get("services"):
            c.execute("SELECT COUNT(*) FROM services"); cnt = c.fetchone()[0]
            if cnt == 0:
                for svc in data["services"]:
                    c.execute("INSERT INTO services(id,category_id,api_id,api_service_id,name,min_qty,max_qty,price_per1000,is_active) VALUES(?,?,?,?,?,?,?,?,?)",
                              (svc["id"],svc["category_id"],svc["api_id"],svc["api_service_id"],svc["name"],svc["min_qty"],svc["max_qty"],svc["price_per1000"],svc["is_active"]))

        if data.get("payments"):
            c.execute("SELECT COUNT(*) FROM manual_payments"); cnt = c.fetchone()[0]
            if cnt == 0:
                for p in data["payments"]:
                    c.execute("INSERT INTO manual_payments(id,pay_type,name,card_number,card_expiry,card_holder,is_active) VALUES(?,?,?,?,?,?,?)",
                              (p["id"],p["pay_type"],p["name"],p["card_number"],p["card_expiry"],p["card_holder"],p["is_active"]))

        if data.get("channels"):
            c.execute("SELECT COUNT(*) FROM channels"); cnt = c.fetchone()[0]
            if cnt == 0:
                for ch in data["channels"]:
                    c.execute("INSERT INTO channels(channel_id,channel_name,channel_link) VALUES(?,?,?)",
                              (ch["channel_id"],ch["channel_name"],ch["channel_link"]))

        if data.get("settings"):
            for k, v in data["settings"].items():
                c.execute("INSERT OR REPLACE INTO settings VALUES(?,?)", (k, v))

        if data.get("guides"):
            c.execute("SELECT COUNT(*) FROM guides"); cnt = c.fetchone()[0]
            if cnt == 0:
                for g in data["guides"]:
                    c.execute("INSERT INTO guides(id,title,content) VALUES(?,?,?)",
                              (g["id"],g["title"],g["content"]))

        conn.commit(); conn.close()
        logger.info("✅ JSONBin dan ma'lumotlar tiklandi!")
        return True
    except Exception as e:
        logger.error(f"jsonbin_restore xato: {e}")
        return False

async def jsonbin_autosave_loop():
    while True:
        await asyncio.sleep(600)
        await jsonbin_save()


# ─────────────────────────────────────────────────────────────
#  RANGLI TUGMA YORDAMCHILARI
# ─────────────────────────────────────────────────────────────
def ibtn(text: str, callback_data: str = None, url: str = None, style: str = None) -> InlineKeyboardButton:
    kwargs = {"text": text}
    if callback_data is not None:
        kwargs["callback_data"] = callback_data
    if url is not None:
        kwargs["url"] = url
    if style is not None:
        kwargs["style"] = style
    return InlineKeyboardButton(**kwargs)

# ─────────────────────────────────────────────────────────────
#  DATABASE
# ─────────────────────────────────────────────────────────────
def db():
    return sqlite3.connect(DB, check_same_thread=False)

def init_db():
    conn = db()
    c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id        INTEGER PRIMARY KEY,
        username       TEXT,
        full_name      TEXT,
        balance        REAL    DEFAULT 0,
        referral_id    INTEGER DEFAULT 0,
        referral_count INTEGER DEFAULT 0,
        total_dep      REAL    DEFAULT 0,
        created_at     TEXT    DEFAULT CURRENT_TIMESTAMP
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS categories (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        name      TEXT NOT NULL,
        platform  TEXT NOT NULL DEFAULT 'telegram',
        is_active INTEGER DEFAULT 1
    )""")

    try:
        c.execute("ALTER TABLE categories ADD COLUMN platform TEXT NOT NULL DEFAULT 'telegram'")
    except Exception:
        pass

    c.execute("""CREATE TABLE IF NOT EXISTS apis (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        name          TEXT NOT NULL,
        url           TEXT NOT NULL,
        api_key       TEXT NOT NULL,
        price_per1000 REAL DEFAULT 0
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS services (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        category_id     INTEGER,
        api_id          INTEGER,
        api_service_id  TEXT,
        name            TEXT NOT NULL,
        min_qty         INTEGER DEFAULT 100,
        max_qty         INTEGER DEFAULT 10000,
        price_per1000   REAL    DEFAULT 0,
        is_active       INTEGER DEFAULT 1
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS orders (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id      INTEGER,
        service_id   INTEGER,
        api_order_id TEXT,
        link         TEXT,
        quantity     INTEGER,
        amount       REAL,
        status       TEXT DEFAULT 'pending',
        created_at   TEXT DEFAULT CURRENT_TIMESTAMP
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS transactions (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id     INTEGER,
        amount      REAL,
        type        TEXT,
        description TEXT,
        created_at  TEXT DEFAULT CURRENT_TIMESTAMP
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS topup_requests (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id     INTEGER,
        amount      REAL,
        pay_id      INTEGER,
        check_file_id TEXT,
        status      TEXT DEFAULT 'pending',
        created_at  TEXT DEFAULT CURRENT_TIMESTAMP
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS manual_payments (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        pay_type    TEXT NOT NULL DEFAULT 'uzcart',
        name        TEXT NOT NULL DEFAULT '',
        card_number TEXT NOT NULL,
        card_expiry TEXT NOT NULL DEFAULT '',
        card_holder TEXT NOT NULL,
        is_active   INTEGER DEFAULT 1
    )""")

    try:
        c.execute("ALTER TABLE manual_payments ADD COLUMN name TEXT NOT NULL DEFAULT ''")
    except Exception:
        pass
    try:
        c.execute("ALTER TABLE manual_payments ADD COLUMN pay_type TEXT NOT NULL DEFAULT 'uzcart'")
    except Exception:
        pass

    c.execute("""CREATE TABLE IF NOT EXISTS settings (
        key   TEXT PRIMARY KEY,
        value TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS channels (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        channel_id   TEXT,
        channel_name TEXT,
        channel_link TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS guides (
        id      INTEGER PRIMARY KEY AUTOINCREMENT,
        title   TEXT,
        content TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS platforms (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        key       TEXT NOT NULL UNIQUE,
        name      TEXT NOT NULL,
        sort_order INTEGER DEFAULT 0
    )""")

    default_plats = [
        ("telegram",  "✈️ Telegram",  1),
        ("instagram", "📸 Instagram", 2),
        ("youtube",   "▶️ Youtube",   3),
        ("tiktok",    "🎵 Tik tok",   4),
    ]
    for pk, pn, po in default_plats:
        c.execute("INSERT OR IGNORE INTO platforms(key,name,sort_order) VALUES(?,?,?)", (pk, pn, po))

    defaults = [
        ("referral_bonus",   "2500"),
        ("currency",         "Sum"),
        ("service_time",     "1"),
        ("premium_emoji",    "1"),
        ("payme_active",     "0"),
        ("click_active",     "0"),
    ]
    for k, v in defaults:
        c.execute("INSERT OR IGNORE INTO settings VALUES (?,?)", (k, v))

    c.execute("INSERT OR IGNORE INTO guides(id,title,content) VALUES(1,?,?)", (
        "Botdan foydalanish qo'llanmasi",
        "1. Buyurtma berish uchun 'Buyurtma berish' tugmasini bosing\n"
        "2. Ijtimoiy tarmoqni tanlang (Telegram, Instagram va h.k)\n"
        "3. Bo'limni tanlang → Xizmatni tanlang\n"
        "4. Link va miqdorni kiriting\n"
        "5. Tasdiqlang – pul hisobingizdan yechiladi"
    ))

    conn.commit()
    conn.close()

# ─── Yordamchi funksiyalar ───────────────────────────────────
def get_setting(key, default=""):
    conn = db(); c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key=?", (key,))
    row = c.fetchone(); conn.close()
    return row[0] if row else default

def set_setting(key, value):
    conn = db(); c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings VALUES(?,?)", (key, str(value)))
    conn.commit(); conn.close()

def cur(): return get_setting("currency", "Sum")

def get_user(uid):
    conn = db(); c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id=?", (uid,))
    row = c.fetchone(); conn.close()
    return row

def reg_user(uid, username, full_name, ref_id=0):
    conn = db(); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users(user_id,username,full_name,referral_id) VALUES(?,?,?,?)",
              (uid, username, full_name, ref_id))
    if ref_id and ref_id != uid:
        bonus = float(get_setting("referral_bonus", "2500"))
        c.execute("UPDATE users SET balance=balance+?, referral_count=referral_count+1 WHERE user_id=?",
                  (bonus, ref_id))
        c.execute("INSERT INTO transactions(user_id,amount,type,description) VALUES(?,?,?,?)",
                  (ref_id, bonus, "referral", f"Referal bonus: {uid}"))
    conn.commit(); conn.close()

def orders_count(uid):
    conn = db(); c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM orders WHERE user_id=?", (uid,))
    n = c.fetchone()[0]; conn.close(); return n

async def auto_delete(message: types.Message, delay: int = 10):
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except Exception:
        pass

async def delete_msg_by_id(chat_id: int, message_id: int, delay: int = 0):
    if delay:
        await asyncio.sleep(delay)
    try:
        await bot.delete_message(chat_id, message_id)
    except Exception:
        pass

# ─────────────────────────────────────────────────────────────
#  ✅ TUZATILGAN: API ni service orqali avtomatik topish
#  api_id bo'yicha emas, services.api_id → apis jadvali orqali
#  Agar api_id=NULL yoki API o'chirilgan bo'lsa, URL bo'yicha topadi
# ─────────────────────────────────────────────────────────────
def get_api_for_service(service_id: int):
    """
    Berilgan service_id uchun API url va key ni qaytaradi.
    Avval service.api_id bo'yicha qidiradi.
    Topilmasa yoki NULL bo'lsa, DB dagi birinchi API ni ishlatadi.
    """
    conn = db(); c = conn.cursor()
    c.execute("SELECT api_id FROM services WHERE id=?", (service_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return None, None, None

    api_id = row[0]

    if api_id:
        c.execute("SELECT id, url, api_key FROM apis WHERE id=?", (api_id,))
        api_row = c.fetchone()
        if api_row:
            conn.close()
            return api_row[0], api_row[1], api_row[2]

    # api_id NULL yoki API o'chirilgan — birinchi mavjud API ni ol
    c.execute("SELECT id, url, api_key FROM apis LIMIT 1")
    api_row = c.fetchone()
    conn.close()
    if api_row:
        logger.warning(f"Service {service_id} uchun api_id topilmadi, fallback API {api_row[0]} ishlatilmoqda")
        return api_row[0], api_row[1], api_row[2]

    return None, None, None

async def check_order_status_loop(uid: int, order_id: int, api_order_id: str,
                                   api_url: str, api_key: str):
    max_checks = 120
    for _ in range(max_checks):
        await asyncio.sleep(60)
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(
                    api_url,
                    data={"key": api_key, "action": "status", "order": api_order_id},
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as r:
                    res = await r.json(content_type=None)
            status = res.get("status", "").lower() if isinstance(res, dict) else ""
            if status in ("completed", "partial"):
                conn = db(); c = conn.cursor()
                c.execute("UPDATE orders SET status=? WHERE id=?", (status, order_id))
                conn.commit(); conn.close()
                emoji = "✅" if status == "completed" else "♻️"
                stat_text = "bajarildi" if status == "completed" else "qisman bajarildi"
                try:
                    await bot.send_message(uid,
                        f"{emoji} <b>#{order_id}</b> raqamli buyurtmangiz {stat_text}!",
                        parse_mode="HTML")
                except Exception:
                    pass
                return
            elif status in ("cancelled", "fail"):
                conn = db(); c = conn.cursor()
                c.execute("UPDATE orders SET status='cancelled' WHERE id=?", (order_id,))
                conn.commit(); conn.close()
                try:
                    await bot.send_message(uid,
                        f"❌ <b>#{order_id}</b> raqamli buyurtmangiz bekor qilindi!",
                        parse_mode="HTML")
                except Exception:
                    pass
                return
        except Exception:
            pass

# ─────────────────────────────────────────────────────────────
#  STATES
# ─────────────────────────────────────────────────────────────
class US(StatesGroup):
    select_platform  = State()
    select_category  = State()
    select_service   = State()
    enter_link       = State()
    enter_quantity   = State()
    topup_amount     = State()
    topup_check      = State()
    support_msg      = State()

class AS(StatesGroup):
    add_cat_platform   = State()
    add_category       = State()
    api_name           = State()
    api_url            = State()
    api_key            = State()
    api_price          = State()
    svc_api_id         = State()
    svc_name           = State()
    svc_min            = State()
    svc_max            = State()
    svc_price          = State()
    set_referral       = State()
    set_currency       = State()
    broadcast_msg      = State()
    broadcast_uid      = State()
    broadcast_uid_msg  = State()
    user_id_input      = State()
    balance_amount     = State()
    mpay_name          = State()
    mpay_card          = State()
    mpay_expiry        = State()
    mpay_holder        = State()
    mpay_type          = State()
    add_channel        = State()
    guide_title        = State()
    guide_content      = State()
    plat_rename_key    = State()
    plat_rename_val    = State()
    topup_reply_uid    = State()
    topup_reply_msg    = State()
    svc_percent_input  = State()

# ─────────────────────────────────────────────────────────────
#  KEYBOARDS
# ─────────────────────────────────────────────────────────────
def kbtn(text: str, style: str = None) -> KeyboardButton:
    if style:
        return KeyboardButton(text=text, **{"style": style})
    return KeyboardButton(text=text)

def main_kb(is_admin=False):
    rows = [
        [kbtn("Buyurtma berish", "success")],
        [kbtn("📱 Nomer olish", "primary")],
        [kbtn("Buyurtmalar", "primary"), kbtn("Hisobim", "primary")],
        [kbtn("Pul ishlash", "success"), kbtn("Hisob to'ldirish", "danger")],
        [kbtn("Murojaat", "primary"), kbtn("Qo'llanma", "success")],
    ]
    if is_admin:
        rows.append([kbtn("🗄 Boshqaruv", "danger")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)

def admin_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [kbtn("⚙️ Asosiy sozlamalar", "primary")],
        [kbtn("📊 Statistika", "success"), kbtn("📨 Xabar yuborish", "primary")],
        [kbtn("🔒 Majbur obuna kanallar", "danger")],
        [kbtn("💳 To'lov tizimlar", "success"), kbtn("🔑 API", "primary")],
        [kbtn("👩‍💻 Foydalanuvchini boshqarish", "primary")],
        [kbtn("📚 Qo'llanmalar", "success"), kbtn("📈 Buyurtmalar", "primary")],
        [kbtn("📁 Xizmatlar", "success")],
        [kbtn("◀️ Orqaga", "danger")],
    ], resize_keyboard=True)

def back_kb():
    return ReplyKeyboardMarkup(keyboard=[[kbtn("◀️ Orqaga", "danger")]], resize_keyboard=True)

def cancel_kb():
    return ReplyKeyboardMarkup(keyboard=[[kbtn("❌ Bekor qilish", "danger")]], resize_keyboard=True)

def platforms_inline_kb():
    plats = get_platforms_list()
    rows = []
    for i in range(0, len(plats), 2):
        row = []
        row.append(InlineKeyboardButton(text=plats[i][2], callback_data=f"plat_{plats[i][1]}", style="primary"))
        if i+1 < len(plats):
            row.append(InlineKeyboardButton(text=plats[i+1][2], callback_data=f"plat_{plats[i+1][1]}", style="primary"))
        rows.append(row)
    rows.append([InlineKeyboardButton(text="◀️ Orqaga", callback_data="order_back_main", style="danger")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

# ─────────────────────────────────────────────────────────────
#  API HELPERS
# ─────────────────────────────────────────────────────────────
async def api_services(url, key):
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(url, data={"key": key, "action": "services"},
                              timeout=aiohttp.ClientTimeout(total=10)) as r:
                return await r.json(content_type=None)
    except Exception as e:
        logger.error(f"api_services error: {e}")
        return None

async def api_order(url, key, service_id, link, qty):
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(url, data={"key": key, "action": "add",
                                          "service": service_id, "link": link, "quantity": qty},
                              timeout=aiohttp.ClientTimeout(total=15)) as r:
                return await r.json(content_type=None)
    except Exception as e:
        logger.error(f"api_order error: {e}")
        return None

async def api_balance(url, key):
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(url, data={"key": key, "action": "balance"},
                              timeout=aiohttp.ClientTimeout(total=10)) as r:
                data = await r.json(content_type=None)
                if isinstance(data, dict):
                    bal = data.get("balance", data.get("funds", data.get("Balance", None)))
                    cur_val = data.get("currency", data.get("Currency", "USD"))
                    if bal is not None:
                        return float(bal), str(cur_val)
        return None, None
    except Exception as e:
        logger.error(f"api_balance error: {e}")
        return None, None

# ─────────────────────────────────────────────────────────────
#  BOT & DISPATCHER
# ─────────────────────────────────────────────────────────────
bot = Bot(token=BOT_TOKEN)
dp  = Dispatcher(storage=MemoryStorage())

# ── Obunani tekshirish ──────────────────────────────────────
async def check_sub(uid):
    conn = db(); c = conn.cursor()
    c.execute("SELECT channel_id FROM channels")
    chs = c.fetchall(); conn.close()
    for (ch,) in chs:
        try:
            m = await bot.get_chat_member(ch, uid)
            if m.status in ("left", "kicked", "banned"):
                return False
        except:
            pass
    return True

async def sub_kb():
    conn = db(); c = conn.cursor()
    c.execute("SELECT channel_id,channel_name,channel_link FROM channels")
    chs = c.fetchall(); conn.close()
    b = InlineKeyboardBuilder()
    for cid, cname, clink in chs:
        b.button(text=f"📢 {cname}", url=clink, style="primary")
    b.button(text="✅ Tekshirish", callback_data="check_sub", style="success")
    b.adjust(1)
    return b.as_markup()

# ═══════════════════════════════════════════════════════════
#  /start
# ═══════════════════════════════════════════════════════════
@dp.message(Command("start"))
async def cmd_start(msg: types.Message, state: FSMContext):
    await state.clear()
    uid  = msg.from_user.id
    args = msg.text.split()
    ref  = 0
    if len(args) > 1:
        try: ref = int(args[1])
        except: pass

    if not get_user(uid):
        reg_user(uid, msg.from_user.username or "", msg.from_user.full_name or "", ref)

    asyncio.create_task(auto_delete(msg, 40))

    if not await check_sub(uid):
        await msg.answer("⚠️ Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:",
                         reply_markup=await sub_kb())
        return

    await msg.answer(
        f"👋 Xush kelibsiz, {msg.from_user.full_name}!\n\n"
        f"🖥 Asosiy menyudasiz!",
        reply_markup=main_kb(uid in ADMIN_IDS)
    )

@dp.callback_query(F.data == "check_sub")
async def cb_check_sub(cb: types.CallbackQuery):
    if await check_sub(cb.from_user.id):
        try:
            await cb.message.delete()
        except Exception:
            pass
        await cb.message.answer(
            "✅ Siz barcha kanallarga obuna bo'ldingiz, rahmat!\n\n"
            "Pastki menyulardan foydalanishingiz mumkin 👇",
            reply_markup=main_kb(cb.from_user.id in ADMIN_IDS)
        )
        await cb.answer("✅ Tasdiqlandi!")
    else:
        await cb.answer("❌ Siz hali obuna bo'lmadingiz!", show_alert=True)

# ═══════════════════════════════════════════════════════════
#  USER — Hisobim
# ═══════════════════════════════════════════════════════════
@dp.message(F.text == "Hisobim")
async def my_account(msg: types.Message):
    u = get_user(msg.from_user.id)
    if not u: return
    b = InlineKeyboardBuilder()
    b.button(text="💳 Hisobni to'ldirish", callback_data="go_topup", style="success")
    b.adjust(1)
    sent = await msg.answer(
        f"👤 Sizning ID raqamingiz: {u[0]}\n\n"
        f"💵 Balansingiz: {u[3]:.2f} {cur()}\n"
        f"📊 Buyurtmalaringiz: {orders_count(u[0])} ta\n"
        f"👥 Referallaringiz: {u[5]} ta\n"
        f"💰 Kiritgan pullaringiz: {u[6]:.2f} {cur()}",
        reply_markup=b.as_markup()
    )
    asyncio.create_task(auto_delete(sent, 40))

@dp.callback_query(F.data == "go_topup")
async def go_topup_cb(cb: types.CallbackQuery):
    await cb.answer()
    await show_topup(cb.message, cb.from_user.id)

# ═══════════════════════════════════════════════════════════
#  USER — Pul ishlash
# ═══════════════════════════════════════════════════════════
@dp.message(F.text == "Pul ishlash")
async def earn(msg: types.Message):
    u = get_user(msg.from_user.id)
    if not u: return
    bonus = get_setting("referral_bonus", "2500")
    bi    = await bot.get_me()
    link  = f"https://t.me/{bi.username}?start={u[0]}"
    sent = await msg.answer(
        f"🔗 Sizning referal havolangiz:\n\n{link}\n\n"
        f"1 ta referal uchun {bonus} {cur()} beriladi\n\n"
        f"👥 Referallaringiz: {u[5]} ta",
        reply_markup=main_kb(msg.from_user.id in ADMIN_IDS)
    )
    asyncio.create_task(auto_delete(sent, 40))

# ═══════════════════════════════════════════════════════════
#  USER — Hisob to'ldirish
# ═══════════════════════════════════════════════════════════
async def show_topup(message: types.Message, uid: int):
    conn = db(); c = conn.cursor()
    c.execute("SELECT id, pay_type, name FROM manual_payments WHERE is_active=1")
    mpays = c.fetchall(); conn.close()

    rows = []
    if get_setting("payme_active") == "1" or get_setting("click_active") == "1":
        rows.append([InlineKeyboardButton(text="💠 Avto-to'lov (Payme, Click)", callback_data="pay_auto", style="primary")])

    pair = []
    for pid, ptype, pname in mpays:
        icon = "💳" if ptype == "uzcart" else "🟠"
        disp = pname if pname else ("Uzcart" if ptype == "uzcart" else "Humo")
        pair.append(InlineKeyboardButton(text=f"{icon} {disp}", callback_data=f"pay_manual_{pid}", style="success"))
        if len(pair) == 2:
            rows.append(pair); pair = []
    if pair:
        rows.append(pair)

    if not rows:
        sent = await message.answer("❌ Hozirda to'lov tizimlari faol emas.",
                                    reply_markup=main_kb(uid in ADMIN_IDS))
        asyncio.create_task(auto_delete(sent, 40)); return

    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    sent = await message.answer("💳 Quyidagilardan birini tanlang:", reply_markup=kb)
    asyncio.create_task(auto_delete(sent, 40))

@dp.message(F.text.in_(["Hisob to'ldirish", "Hisobni to'ldirish"]))
async def topup(msg: types.Message):
    asyncio.create_task(auto_delete(msg, 40))
    await show_topup(msg, msg.from_user.id)

@dp.callback_query(F.data == "pay_noop")
async def pay_noop(cb: types.CallbackQuery):
    await cb.answer()

@dp.callback_query(F.data.startswith("pay_manual_"))
async def pay_manual(cb: types.CallbackQuery, state: FSMContext):
    pid_str = cb.data.replace("pay_manual_", "")
    try:
        pid = int(pid_str)
    except ValueError:
        await cb.answer(); return
    conn = db(); c = conn.cursor()
    c.execute("SELECT pay_type, name, card_number, card_holder FROM manual_payments WHERE id=?", (pid,))
    pay = c.fetchone(); conn.close()
    if not pay:
        await cb.answer("❌ Topilmadi", show_alert=True); return
    ptype, pname, pcard, pholder = pay
    type_name    = "Uzcart" if ptype == "uzcart" else "Humo"
    display_name = pname if pname else type_name

    await state.update_data(topup_pay_id=pid, topup_pay_name=display_name,
                            topup_card=pcard, topup_holder=pholder, topup_type=type_name)
    await state.set_state(US.topup_amount)
    sent = await cb.message.answer(
        f"💳 {display_name} ({type_name})\n\n"
        f"Qancha miqdorda to'ldirmoqchisiz? ({cur()})\n"
        f"Minimal: 1000 {cur()}",
        reply_markup=main_kb(cb.from_user.id in ADMIN_IDS)
    )
    asyncio.create_task(auto_delete(sent, 40))
    await cb.answer()

@dp.callback_query(F.data == "pay_auto")
async def pay_auto(cb: types.CallbackQuery, state: FSMContext):
    await state.update_data(pay_method="pay_auto")
    await state.set_state(US.topup_amount)
    sent = await cb.message.answer(f"💰 Qancha {cur()} kiritmoqchisiz?",
                                    reply_markup=main_kb(cb.from_user.id in ADMIN_IDS))
    asyncio.create_task(auto_delete(sent, 40))
    await cb.answer()

@dp.message(US.topup_amount)
async def do_topup(msg: types.Message, state: FSMContext):
    asyncio.create_task(auto_delete(msg, 40))
    main_btns = {"Buyurtma berish", "Buyurtmalar", "Hisobim", "Pul ishlash",
                 "Hisob to'ldirish", "Murojaat", "Qo'llanma", "🗄 Boshqaruv",
                 "❌ Bekor qilish", "◀️ Orqaga"}
    if msg.text in main_btns:
        await state.clear()
        sent = await msg.answer("Bekor qilindi", reply_markup=main_kb(msg.from_user.id in ADMIN_IDS))
        asyncio.create_task(auto_delete(sent, 40))
        return
    try:
        amount = float(msg.text.replace(" ", "").replace(",", "."))
        if amount < 1000: raise ValueError
    except:
        err = await msg.answer(f"❌ Minimal miqdor 1000 {cur()}, faqat raqam kiriting")
        asyncio.create_task(auto_delete(err, 40)); return

    data = await state.get_data()
    pay_id   = data.get("topup_pay_id")
    pay_name = data.get("topup_pay_name", "")
    pcard    = data.get("topup_card", "")
    pholder  = data.get("topup_holder", "")
    ptype    = data.get("topup_type", "")

    await state.update_data(topup_amount=amount)
    await state.set_state(US.topup_check)

    sent = await msg.answer(
        f"💳 <b>{pay_name}</b> ({ptype})\n\n"
        f"🔢 Karta raqami: <code>{pcard}</code>\n"
        f"👤 Karta egasi: <b>{pholder}</b>\n\n"
        f"💰 To'lov miqdori: <b>{amount:.0f} {cur()}</b>\n\n"
        f"Ushbu kartaga pul o'tkazing va chek (skrinshot) yuboring 👇",
        parse_mode="HTML",
        reply_markup=main_kb(msg.from_user.id in ADMIN_IDS)
    )
    asyncio.create_task(auto_delete(sent, 40))

@dp.message(US.topup_check)
async def do_topup_check(msg: types.Message, state: FSMContext):
    main_btns = {"Buyurtma berish", "Buyurtmalar", "Hisobim", "Pul ishlash",
                 "Hisob to'ldirish", "Murojaat", "Qo'llanma", "🗄 Boshqaruv",
                 "❌ Bekor qilish", "◀️ Orqaga"}
    if msg.text and msg.text in main_btns:
        await state.clear()
        await msg.answer("Bekor qilindi", reply_markup=main_kb(msg.from_user.id in ADMIN_IDS)); return

    file_id = None
    if msg.photo:
        file_id = msg.photo[-1].file_id
    elif msg.document:
        file_id = msg.document.file_id
    else:
        err = await msg.answer("❌ Iltimos, chek rasmini yuboring (foto yoki fayl)")
        asyncio.create_task(auto_delete(err, 40)); return

    data   = await state.get_data()
    amount = data.get("topup_amount", 0)
    pay_id = data.get("topup_pay_id", 0)
    uid    = msg.from_user.id

    conn = db(); c = conn.cursor()
    c.execute("INSERT INTO topup_requests(user_id, amount, pay_id, check_file_id, status) VALUES(?,?,?,?,?)",
              (uid, amount, pay_id, file_id, "pending"))
    req_id = c.lastrowid
    conn.commit(); conn.close()

    await state.clear()

    await msg.answer(
        f"✅ Chekingiz qabul qilindi!\n\n"
        f"💰 Miqdor: {amount:.0f} {cur()}\n"
        f"🆔 So'rov ID: #{req_id}\n\n"
        f"Admin tasdiqlashini kuting ⏳",
        reply_markup=main_kb(uid in ADMIN_IDS)
    )

    u = get_user(uid)
    uname = f"@{u[1]}" if u and u[1] else f"ID: {uid}"
    caption = (
        f"💰 Yangi to'ldirish so'rovi!\n\n"
        f"👤 Foydalanuvchi: {u[2] if u else uid} ({uname})\n"
        f"🆔 ID: {uid}\n"
        f"💵 Miqdor: {amount:.0f} {cur()}\n"
        f"🆔 So'rov: #{req_id}"
    )
    b = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Tasdiqlash",  callback_data=f"topup_ok_{req_id}", style="success"),
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"topup_no_{req_id}", style="danger"),
    ],[
        InlineKeyboardButton(text="💬 Foydalanuvchiga xabar", callback_data=f"topup_msg_{uid}", style="primary"),
    ]])
    for admin_id in ADMIN_IDS:
        try:
            if msg.photo:
                await bot.send_photo(admin_id, file_id, caption=caption, reply_markup=b)
            else:
                await bot.send_document(admin_id, file_id, caption=caption, reply_markup=b)
        except Exception:
            pass

# ═══════════════════════════════════════════════════════════
#  USER — Buyurtmalar
# ═══════════════════════════════════════════════════════════
@dp.message(F.text == "Buyurtmalar")
async def my_orders(msg: types.Message):
    uid  = msg.from_user.id
    conn = db(); c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM orders WHERE user_id=?", (uid,))
    total = c.fetchone()[0]
    if total == 0:
        sent = await msg.answer("❌ Sizda buyurtmalar mavjud emas.",
                                 reply_markup=main_kb(uid in ADMIN_IDS))
        asyncio.create_task(auto_delete(sent, 40)); return
    st = {}
    for s in ("completed", "cancelled", "pending", "processing", "partial"):
        c.execute("SELECT COUNT(*) FROM orders WHERE user_id=? AND status=?", (uid, s))
        st[s] = c.fetchone()[0]
    conn.close()
    sent = await msg.answer(
        f"📈 Buyurtmalar: {total} ta\n\n"
        f"✅ Bajarilganlar: {st['completed']} ta\n"
        f"🚫 Bekor qilinganlar: {st['cancelled']} ta\n"
        f"⏳ Kutilayotganlar: {st['pending']} ta\n"
        f"🔄 Jarayondagilar: {st['processing']} ta\n"
        f"♻️ Qisman: {st['partial']} ta",
        reply_markup=main_kb(uid in ADMIN_IDS)
    )
    asyncio.create_task(auto_delete(sent, 40))

# ═══════════════════════════════════════════════════════════
#  USER — Buyurtma berish
# ═══════════════════════════════════════════════════════════
@dp.message(F.text == "Buyurtma berish")
async def place_order(msg: types.Message, state: FSMContext):
    asyncio.create_task(auto_delete(msg, 40))
    await state.set_state(US.select_platform)
    sent = await msg.answer(
        "📱 Quyidagi ijtimoiy tarmoqlardan birini tanlang:",
        reply_markup=platforms_inline_kb()
    )
    asyncio.create_task(auto_delete(sent, 40))

@dp.callback_query(F.data == "order_back_main")
async def order_back_main(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await cb.message.answer("🖥 Asosiy menyudasiz!", reply_markup=main_kb(cb.from_user.id in ADMIN_IDS))
    await cb.answer()

@dp.callback_query(F.data.startswith("plat_") & ~F.data.startswith("plat_ren_") & ~F.data.startswith("plat_del_") & ~F.data.startswith("plat_add"))
async def platform_selected(cb: types.CallbackQuery, state: FSMContext):
    platform = cb.data.replace("plat_", "")
    plat_name = get_platforms().get(platform, platform.capitalize())

    conn = db(); c = conn.cursor()
    c.execute("SELECT id, name FROM categories WHERE is_active=1 AND platform=?", (platform,))
    cats = c.fetchall()
    conn.close()

    if not cats:
        await cb.answer(f"❌ {plat_name} uchun bo'limlar yo'q!", show_alert=True)
        return

    b = InlineKeyboardBuilder()
    for cid, cname in cats:
        b.button(text=cname, callback_data=f"order_cat_{cid}", style="primary")
    b.button(text="◀️ Orqaga", callback_data="back_to_platforms", style="danger")
    b.adjust(1)

    await state.update_data(platform=platform, plat_name=plat_name)
    await state.set_state(US.select_category)

    try:
        await cb.message.edit_text(
            f"{plat_name} — bo'limlar:",
            reply_markup=b.as_markup()
        )
    except Exception:
        sent = await cb.message.answer(
            f"{plat_name} — bo'limlar:",
            reply_markup=b.as_markup()
        )
        asyncio.create_task(auto_delete(sent, 40))
    await cb.answer()

@dp.callback_query(F.data == "back_to_platforms")
async def back_to_platforms(cb: types.CallbackQuery, state: FSMContext):
    await state.set_state(US.select_platform)
    try:
        await cb.message.edit_text(
            "📱 Quyidagi ijtimoiy tarmoqlardan birini tanlang:",
            reply_markup=platforms_inline_kb()
        )
    except Exception:
        await cb.message.answer(
            "📱 Quyidagi ijtimoiy tarmoqlardan birini tanlang:",
            reply_markup=platforms_inline_kb()
        )
    await cb.answer()

@dp.callback_query(F.data.startswith("order_cat_"))
async def order_cat_selected(cb: types.CallbackQuery, state: FSMContext):
    cat_id = int(cb.data.replace("order_cat_", ""))
    conn = db(); c = conn.cursor()
    c.execute(
        "SELECT id, name, price_per1000, min_qty, max_qty FROM services "
        "WHERE category_id=? AND is_active=1", (cat_id,)
    )
    svcs = c.fetchall()
    c.execute("SELECT name, platform FROM categories WHERE id=?", (cat_id,))
    cat_row = c.fetchone()
    conn.close()

    if not svcs:
        await cb.answer("❌ Bu bo'limda xizmatlar yo'q.", show_alert=True); return

    cat_name  = cat_row[0] if cat_row else "Bo'lim"
    platform  = cat_row[1] if cat_row else "telegram"
    plat_name = get_platforms().get(platform, platform.capitalize())

    b = InlineKeyboardBuilder()
    for sid, sname, price, mn, mx in svcs:
        b.button(text=f"{sname} - {price:.2f} {cur()}", callback_data=f"sel_svc_{sid}", style="primary")
    b.button(text="◀️ Orqaga", callback_data=f"plat_{platform}", style="danger")
    b.adjust(1)

    await state.update_data(
        svcs={str(sid): (sid, sname, price, mn, mx) for sid, sname, price, mn, mx in svcs},
        last_cat_id=cat_id,
        cat_name=cat_name,
        platform=platform,
        plat_name=plat_name,
    )
    await state.set_state(US.select_service)

    text = f"📋 {cat_name} — xizmatlar:\n(Narxlar 1000 tasi uchun)"
    try:
        await cb.message.edit_text(text, reply_markup=b.as_markup())
    except Exception:
        await cb.message.answer(text, reply_markup=b.as_markup())
    await cb.answer()

@dp.callback_query(F.data.startswith("sel_svc_"))
async def sel_svc(cb: types.CallbackQuery, state: FSMContext):
    svc_id = int(cb.data.replace("sel_svc_", ""))
    conn = db(); c = conn.cursor()
    c.execute(
        "SELECT s.id, s.category_id, s.api_id, s.api_service_id, s.name, "
        "s.min_qty, s.max_qty, s.price_per1000, s.is_active, cat.name, cat.platform "
        "FROM services s LEFT JOIN categories cat ON s.category_id=cat.id "
        "WHERE s.id=?", (svc_id,)
    )
    row = c.fetchone(); conn.close()
    if not row:
        await cb.answer("❌ Xizmat topilmadi", show_alert=True); return

    svc       = row[:9]
    cat_name  = row[9] or ""
    platform  = row[10] or "telegram"
    plat_name = get_platforms().get(platform, platform.capitalize())

    await state.update_data(svc=svc, svc_cat_name=cat_name, platform=platform, plat_name=plat_name)
    await state.set_state(US.enter_quantity)

    b = InlineKeyboardBuilder()
    b.button(text="✅ Buyurtma berish", callback_data=f"start_order_{svc_id}", style="success")
    b.button(text="◀️ Orqaga",          callback_data=f"order_cat_{svc[1]}", style="danger")
    b.adjust(1)

    text = (
        f"{plat_name} — {svc[4]}\n\n"
        f"💰 Narxi (1000x): {svc[7]:.2f} {cur()}\n"
        f"⬇️ Minimal: {svc[5]} ta\n"
        f"⬆️ Maksimal: {svc[6]} ta"
    )
    try:
        await cb.message.edit_text(text, reply_markup=b.as_markup())
    except Exception:
        await cb.message.answer(text, reply_markup=b.as_markup())
    await cb.answer()

@dp.callback_query(F.data.startswith("start_order_"))
async def start_order(cb: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    svc  = data.get("svc")
    if not svc:
        await cb.answer("❌ Xizmat topilmadi", show_alert=True); return

    plat_name = data.get("plat_name", "")
    await state.set_state(US.enter_quantity)

    b = InlineKeyboardBuilder()
    b.button(text="◀️ Orqaga", callback_data=f"sel_svc_{svc[0]}", style="danger")

    text = (
        f"{plat_name} — {svc[4]}\n\n"
        f"🔢 Buyurtma miqdorini kiriting:\n\n"
        f"⬇️ Minimal: {svc[5]} ta\n"
        f"⬆️ Maksimal: {svc[6]} ta"
    )
    try:
        await cb.message.edit_text(text, reply_markup=b.as_markup())
        await state.update_data(qty_ask_msg_id=cb.message.message_id,
                                qty_ask_chat_id=cb.message.chat.id)
    except Exception:
        sent = await cb.message.answer(text)
        await state.update_data(qty_ask_msg_id=sent.message_id,
                                qty_ask_chat_id=sent.chat.id)
    await cb.answer()

@dp.message(US.enter_quantity)
async def enter_qty(msg: types.Message, state: FSMContext):
    main_btns = {"Buyurtma berish", "Buyurtmalar", "Hisobim", "Pul ishlash",
                 "Hisob to'ldirish", "Murojaat", "Qo'llanma", "🗄 Boshqaruv",
                 "❌ Bekor qilish", "◀️ Orqaga"}
    if msg.text in main_btns:
        await state.clear()
        await msg.answer("Bekor qilindi", reply_markup=main_kb(msg.from_user.id in ADMIN_IDS))
        asyncio.create_task(auto_delete(msg, 40))
        return
    data = await state.get_data()
    svc  = data.get("svc")
    if not svc:
        await state.clear()
        await msg.answer("❌ Xatolik, qaytadan boshlang.", reply_markup=main_kb(msg.from_user.id in ADMIN_IDS))
        return
    try:
        qty = int(msg.text)
        if not (svc[5] <= qty <= svc[6]):
            raise ValueError
    except (ValueError, TypeError):
        err = await msg.answer(f"❌ Miqdor {svc[5]} – {svc[6]} orasida bo'lishi kerak")
        asyncio.create_task(auto_delete(msg, 40))
        asyncio.create_task(auto_delete(err, 40))
        return

    asyncio.create_task(auto_delete(msg, 40))

    qty_ask_msg_id  = data.get("qty_ask_msg_id")
    qty_ask_chat_id = data.get("qty_ask_chat_id")
    if qty_ask_msg_id and qty_ask_chat_id:
        asyncio.create_task(delete_msg_by_id(qty_ask_chat_id, qty_ask_msg_id, delay=0))

    await state.update_data(qty=qty)
    await state.set_state(US.enter_link)

    plat_name = data.get("plat_name", "")
    amount    = (qty / 1000) * svc[7]

    sent = await msg.answer(
        f"{plat_name} — {svc[4]}\n\n"
        f"📊 Miqdor: {qty} ta\n"
        f"💰 Narx: {amount:.2f} {cur()}\n\n"
        f"🔗 Linkni yuboring:\n(Masalan: https://t.me/username)",
        reply_markup=main_kb(msg.from_user.id in ADMIN_IDS)
    )
    asyncio.create_task(auto_delete(sent, 40))
    await state.update_data(link_ask_msg_id=sent.message_id,
                            link_ask_chat_id=sent.chat.id)

@dp.message(US.enter_link)
async def enter_link(msg: types.Message, state: FSMContext):
    if msg.text in ("❌ Bekor qilish", "◀️ Orqaga"):
        data = await state.get_data()
        svc  = data.get("svc")
        link_ask_id   = data.get("link_ask_msg_id")
        link_ask_chat = data.get("link_ask_chat_id")
        if link_ask_id and link_ask_chat:
            asyncio.create_task(delete_msg_by_id(link_ask_chat, link_ask_id))
        asyncio.create_task(auto_delete(msg, 40))
        await state.set_state(US.enter_quantity)
        if svc:
            plat_name = data.get("plat_name", "")
            b = InlineKeyboardBuilder()
            b.button(text="◀️ Orqaga", callback_data=f"sel_svc_{svc[0]}", style="danger")
            sent = await msg.answer(
                f"{plat_name} — {svc[4]}\n\n"
                f"🔢 Buyurtma miqdorini kiriting:\n\n"
                f"⬇️ Minimal: {svc[5]} ta\n"
                f"⬆️ Maksimal: {svc[6]} ta",
                reply_markup=b.as_markup()
            )
            asyncio.create_task(auto_delete(sent, 40))
            await state.update_data(qty_ask_msg_id=sent.message_id,
                                    qty_ask_chat_id=sent.chat.id)
        else:
            await msg.answer("Bekor qilindi", reply_markup=main_kb(msg.from_user.id in ADMIN_IDS))
        return

    link_text = msg.text or ""
    if msg.entities:
        for ent in msg.entities:
            if ent.type == "url":
                link_text = msg.text[ent.offset:ent.offset + ent.length]
                break

    if not (link_text.startswith("http") or link_text.startswith("@")):
        err = await msg.answer(
            f"⚠️ Buyurtma havolasi noto'g'ri formatda kiritilmoqda!\n\n"
            f"❗ Namuna: https://havol & @havol"
        )
        asyncio.create_task(auto_delete(msg, 40))
        asyncio.create_task(auto_delete(err, 40))
        return

    data      = await state.get_data()
    svc       = data["svc"]
    qty       = data["qty"]
    amount    = (qty / 1000) * svc[7]
    u         = get_user(msg.from_user.id)
    plat_name = data.get("plat_name", "")

    link_ask_id   = data.get("link_ask_msg_id")
    link_ask_chat = data.get("link_ask_chat_id")
    if link_ask_id and link_ask_chat:
        asyncio.create_task(delete_msg_by_id(link_ask_chat, link_ask_id))

    asyncio.create_task(auto_delete(msg, 40))

    await state.update_data(link=link_text, amount=amount)

    if u[3] < amount:
        err = await msg.answer(
            f"❌ Balansingiz yetarli emas!\n\n"
            f"💵 Balans: {u[3]:.2f} {cur()}\n"
            f"💰 Kerak: {amount:.2f} {cur()}\n"
            f"➖ Yetishmaydi: {amount - u[3]:.2f} {cur()}\n\n"
            f"Hisob to'ldirish uchun asosiy menyudan foydalaning.",
            reply_markup=main_kb(msg.from_user.id in ADMIN_IDS)
        )
        asyncio.create_task(auto_delete(err, 15))
        await state.clear(); return

    b = InlineKeyboardBuilder()
    b.button(text="✅ Tasdiqlash", callback_data="order_yes", style="success")
    b.button(text="❌ Bekor qilish", callback_data="order_no", style="danger")
    b.adjust(1)

    confirm_msg = await msg.answer(
        f"ℹ️ Buyurtmam haqida malumot:\n\n"
        f"{plat_name} — {svc[4]}\n\n"
        f"💰 Narxi: {amount:.2f} {cur()}\n"
        f"🔗 Havola: {link_text}\n"
        f"🔢 Miqdor: {qty} ta\n\n"
        f"⚠️ Malumotlar to'g'ri bo'lsa (✅ Tasdiqlash) tugmasini bosing, "
        f"hisobingizdan {amount:.2f} {cur()} yechib olinadi va buyurtma qabul qilinadi, "
        f"buyurtmani bekor qilish imkoni yo'q.",
        reply_markup=b.as_markup()
    )
    asyncio.create_task(auto_delete(confirm_msg, 40))
    await state.update_data(confirm_msg_id=confirm_msg.message_id,
                            confirm_chat_id=confirm_msg.chat.id)

@dp.callback_query(F.data == "order_yes")
async def order_confirm(cb: types.CallbackQuery, state: FSMContext):
    data      = await state.get_data()
    svc       = data["svc"]
    link      = data["link"]
    qty       = data["qty"]
    amount    = data["amount"]
    uid       = cb.from_user.id
    plat_name = data.get("plat_name", "")

    try:
        await cb.message.delete()
    except Exception:
        pass

    conn = db(); c = conn.cursor()
    c.execute("UPDATE users SET balance=balance-? WHERE user_id=?", (amount, uid))

    api_order_id = None
    api_error    = None
    api_url_val  = None
    api_key_val  = None

    # ✅ TUZATILGAN: API ni avtomatik topish
    # svc[0] = service.id, svc[2] = api_id, svc[3] = api_service_id
    found_api_id, api_url_val, api_key_val = get_api_for_service(svc[0])

    if api_url_val and api_key_val and svc[3]:
        res = await api_order(api_url_val, api_key_val, svc[3], link, qty)
        if res and "order" in res:
            api_order_id = str(res["order"])
        elif res and "error" in res:
            api_error = str(res["error"])
            logger.error(f"API order xato: {api_error}")

        # Agar xizmatdagi api_id noto'g'ri bo'lsa, to'g'rilash
        if found_api_id and svc[2] != found_api_id:
            c.execute("UPDATE services SET api_id=? WHERE id=?", (found_api_id, svc[0]))

    c.execute(
        "INSERT INTO orders(user_id,service_id,api_order_id,link,quantity,amount,status) "
        "VALUES(?,?,?,?,?,?,?)",
        (uid, svc[0], api_order_id, link, qty, amount, "pending")
    )
    order_id = c.lastrowid
    c.execute(
        "INSERT INTO transactions(user_id,amount,type,description) VALUES(?,?,?,?)",
        (uid, -amount, "order", f"Buyurtma #{order_id}")
    )
    conn.commit(); conn.close()

    await cb.message.answer(
        f"✅ Buyurtma qabul qilindi!\n\n"
        f"🆔 Buyurtma ID si: {order_id}",
        reply_markup=main_kb(uid in ADMIN_IDS)
    )

    if api_order_id and api_url_val and api_key_val:
        asyncio.create_task(
            check_order_status_loop(uid, order_id, api_order_id, api_url_val, api_key_val)
        )

    await state.clear()
    await cb.answer()

@dp.callback_query(F.data == "order_no")
async def order_cancel(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await cb.message.delete()
    except Exception:
        pass
    cancel_msg = await cb.message.answer(
        "❌ Buyurtma bekor qilindi.",
        reply_markup=main_kb(cb.from_user.id in ADMIN_IDS)
    )
    asyncio.create_task(auto_delete(cancel_msg, 40))
    await cb.answer()

# ═══════════════════════════════════════════════════════════
#  USER — Murojaat
# ═══════════════════════════════════════════════════════════
@dp.message(F.text == "Murojaat")
async def support(msg: types.Message, state: FSMContext):
    asyncio.create_task(auto_delete(msg, 40))
    await state.set_state(US.support_msg)
    sent = await msg.answer(
        "📝 Murojaat matnini yoki rasmini yuboring.\n\n"
        "Matn, rasm yoki rasm+izoh yuborishingiz mumkin.",
        reply_markup=main_kb(msg.from_user.id in ADMIN_IDS)
    )
    asyncio.create_task(auto_delete(sent, 40))

@dp.message(US.support_msg)
async def do_support(msg: types.Message, state: FSMContext):
    asyncio.create_task(auto_delete(msg, 40))
    main_btns = {"Buyurtma berish", "Buyurtmalar", "Hisobim", "Pul ishlash",
                 "Hisob to'ldirish", "Murojaat", "Qo'llanma", "🗄 Boshqaruv",
                 "❌ Bekor qilish", "◀️ Orqaga"}
    if msg.text and msg.text in main_btns:
        await state.clear()
        await msg.answer("Bekor qilindi", reply_markup=main_kb(msg.from_user.id in ADMIN_IDS)); return

    uid   = msg.from_user.id
    uname = f"@{msg.from_user.username}" if msg.from_user.username else f"ID: {uid}"
    header = f"📩 Yangi murojaat!\n👤 {msg.from_user.full_name} ({uname})\n🆔 {uid}"

    b = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="💬 Javob berish", callback_data=f"topup_msg_{uid}", style="primary")
    ]])

    for admin in ADMIN_IDS:
        try:
            if msg.photo:
                caption = header + (f"\n📝 {msg.caption}" if msg.caption else "")
                await bot.send_photo(admin, msg.photo[-1].file_id, caption=caption, reply_markup=b)
            elif msg.document:
                caption = header + (f"\n📝 {msg.caption}" if msg.caption else "")
                await bot.send_document(admin, msg.document.file_id, caption=caption, reply_markup=b)
            else:
                await bot.send_message(admin, header + f"\n📝 {msg.text}", reply_markup=b)
        except Exception:
            pass

    await state.clear()
    sent = await msg.answer("✅ Murojaatingiz qabul qilindi!", reply_markup=main_kb(uid in ADMIN_IDS))
    asyncio.create_task(auto_delete(sent, 40))

# ═══════════════════════════════════════════════════════════
#  USER — Qo'llanma
# ═══════════════════════════════════════════════════════════
@dp.message(F.text == "Qo'llanma")
async def guides(msg: types.Message):
    asyncio.create_task(auto_delete(msg, 40))
    conn = db(); c = conn.cursor()
    c.execute("SELECT id,title FROM guides")
    gs = c.fetchall(); conn.close()
    if not gs:
        await msg.answer("📚 Qo'llanmalar yo'q"); return
    b = InlineKeyboardBuilder()
    for gid, gtitle in gs:
        b.button(text=f"📖 {gtitle}", callback_data=f"guide_{gid}", style="primary")
    b.adjust(1)
    sent = await msg.answer(f"📚 Qo'llanmalar ro'yhati: {len(gs)} ta", reply_markup=b.as_markup())
    asyncio.create_task(auto_delete(sent, 40))

@dp.callback_query(F.data.startswith("guide_"))
async def show_guide(cb: types.CallbackQuery):
    gid  = int(cb.data.replace("guide_", ""))
    conn = db(); c = conn.cursor()
    c.execute("SELECT title,content FROM guides WHERE id=?", (gid,))
    g = c.fetchone(); conn.close()
    if g:
        sent = await cb.message.answer(f"📖 {g[0]}\n\n{g[1]}")
        asyncio.create_task(auto_delete(sent, 40))
    await cb.answer()

# ═══════════════════════════════════════════════════════════
#  ADMIN — To'ldirish tasdiqlash
# ═══════════════════════════════════════════════════════════
@dp.callback_query(F.data.startswith("topup_ok_"))
async def topup_ok(cb: types.CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS: return
    req_id = int(cb.data.replace("topup_ok_", ""))
    conn = db(); c = conn.cursor()
    c.execute("SELECT user_id, amount, status FROM topup_requests WHERE id=?", (req_id,))
    row = c.fetchone()
    if not row:
        await cb.answer("❌ Topilmadi", show_alert=True); conn.close(); return
    uid, amount, status = row
    if status != "pending":
        await cb.answer("⚠️ Bu so'rov allaqachon ko'rib chiqilgan!", show_alert=True)
        conn.close(); return
    c.execute("UPDATE topup_requests SET status='approved' WHERE id=?", (req_id,))
    c.execute("UPDATE users SET balance=balance+?, total_dep=total_dep+? WHERE user_id=?", (amount, amount, uid))
    c.execute("INSERT INTO transactions(user_id,amount,type,description) VALUES(?,?,?,?)",
              (uid, amount, "deposit", f"To'ldirish #{req_id} tasdiqlandi"))
    conn.commit(); conn.close()
    try:
        await bot.send_message(uid,
            f"✅ Hisobingizga <b>{amount:.0f} {cur()}</b> qo'shildi!\n"
            f"🆔 So'rov #{req_id} tasdiqlandi.",
            parse_mode="HTML")
    except Exception:
        pass
    try:
        await cb.message.edit_caption(
            caption=(cb.message.caption or "") + f"\n\n✅ TASDIQLANDI — {cb.from_user.full_name}",
            reply_markup=None
        )
    except Exception:
        try:
            await cb.message.edit_text(
                (cb.message.text or "") + f"\n\n✅ TASDIQLANDI",
                reply_markup=None
            )
        except Exception:
            pass
    await cb.answer("✅ Tasdiqlandi!")

@dp.callback_query(F.data.startswith("topup_no_"))
async def topup_no(cb: types.CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS: return
    req_id = int(cb.data.replace("topup_no_", ""))
    conn = db(); c = conn.cursor()
    c.execute("SELECT user_id, amount, status FROM topup_requests WHERE id=?", (req_id,))
    row = c.fetchone()
    if not row:
        await cb.answer("❌ Topilmadi", show_alert=True); conn.close(); return
    uid, amount, status = row
    if status != "pending":
        await cb.answer("⚠️ Bu so'rov allaqachon ko'rib chiqilgan!", show_alert=True)
        conn.close(); return
    c.execute("UPDATE topup_requests SET status='rejected' WHERE id=?", (req_id,))
    conn.commit(); conn.close()
    try:
        await bot.send_message(uid,
            f"❌ #{req_id} so'rovingiz rad etildi.\n"
            f"💰 Miqdor: {amount:.0f} {cur()}\n\n"
            f"Muammo bo'lsa admin bilan bog'laning.")
    except Exception:
        pass
    try:
        await cb.message.edit_caption(
            caption=(cb.message.caption or "") + f"\n\n❌ BEKOR QILINDI — {cb.from_user.full_name}",
            reply_markup=None
        )
    except Exception:
        try:
            await cb.message.edit_text(
                (cb.message.text or "") + f"\n\n❌ BEKOR QILINDI",
                reply_markup=None
            )
        except Exception:
            pass
    await cb.answer("❌ Bekor qilindi!")

@dp.callback_query(F.data.startswith("topup_msg_"))
async def topup_msg_start(cb: types.CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS: return
    target_uid = int(cb.data.replace("topup_msg_", ""))
    await state.update_data(topup_reply_uid=target_uid)
    await state.set_state(AS.topup_reply_msg)
    await cb.message.answer(f"💬 {target_uid} ga xabar kiriting:", reply_markup=cancel_kb())
    await cb.answer()

@dp.message(AS.topup_reply_msg)
async def topup_reply_msg(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear(); await msg.answer("Bekor qilindi", reply_markup=admin_kb()); return
    data = await state.get_data()
    uid  = data.get("topup_reply_uid")
    try:
        await bot.send_message(uid, f"💬 Admin xabari:\n\n{msg.text}")
        await msg.answer("✅ Xabar yuborildi!", reply_markup=admin_kb())
    except Exception as e:
        await msg.answer(f"❌ Xato: {e}", reply_markup=admin_kb())
    await state.clear()

@dp.message(F.text == "◀️ Orqaga")
async def go_back(msg: types.Message, state: FSMContext):
    asyncio.create_task(auto_delete(msg, 40))
    await state.clear()
    is_admin = msg.from_user.id in ADMIN_IDS
    sent = await msg.answer("🖥 Asosiy menyudasiz!", reply_markup=main_kb(is_admin))
    asyncio.create_task(auto_delete(sent, 40))

# ═══════════════════════════════════════════════════════════
#  ADMIN — Boshqaruv
# ═══════════════════════════════════════════════════════════
@dp.message(F.text == "🗄 Boshqaruv")
async def admin_panel(msg: types.Message, state: FSMContext):
    if msg.from_user.id not in ADMIN_IDS:
        await msg.answer("❌ Siz admin emassiz!"); return
    asyncio.create_task(auto_delete(msg, 40))
    await state.clear()
    sent = await msg.answer("Admin paneliga xush kelibsiz!", reply_markup=admin_kb())
    asyncio.create_task(auto_delete(sent, 40))

# ── Statistika ─────────────────────────────────────────────
@dp.message(F.text == "📊 Statistika")
async def stat(msg: types.Message):
    if msg.from_user.id not in ADMIN_IDS: return
    conn = db(); c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users"); total = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE created_at>=datetime('now','-1 day')"); h24 = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM orders"); orders = c.fetchone()[0]
    c.execute("SELECT SUM(amount) FROM transactions WHERE type='deposit'"); dep = c.fetchone()[0] or 0
    conn.close()
    b = InlineKeyboardBuilder()
    b.button(text="👥 TOP-50 Referal", callback_data="top_ref", style="primary")
    b.adjust(1)
    await msg.answer(
        f"📊 Statistika:\n\n"
        f"👥 Jami foydalanuvchilar: {total} ta\n"
        f"🆕 So'nggi 24 soat: {h24} ta\n"
        f"📦 Jami buyurtmalar: {orders} ta\n"
        f"💰 Jami depozit: {dep:.2f} {cur()}",
        reply_markup=b.as_markup()
    )

@dp.callback_query(F.data == "top_ref")
async def top_ref(cb: types.CallbackQuery):
    conn = db(); c = conn.cursor()
    c.execute("SELECT user_id,full_name,referral_count FROM users ORDER BY referral_count DESC LIMIT 50")
    rows = c.fetchall(); conn.close()
    text = "👥 TOP-50 Referal:\n\n"
    for i, (uid, name, rc) in enumerate(rows, 1):
        text += f"{i}. {name or uid} — {rc} ta\n"
    await cb.message.answer(text[:4096]); await cb.answer()

# ── Xabar yuborish ─────────────────────────────────────────
@dp.message(F.text == "📨 Xabar yuborish")
async def broadcast_menu(msg: types.Message):
    if msg.from_user.id not in ADMIN_IDS: return
    b = InlineKeyboardBuilder()
    b.button(text="💬 1 foydalanuvchiga xabar",   callback_data="bc_single", style="primary")
    b.button(text="📨 Barchaga xabar (forward)", callback_data="bc_forward_all", style="success")
    b.adjust(1)
    await msg.answer("Xabar yuborish turini tanlang:", reply_markup=b.as_markup())

@dp.callback_query(F.data == "bc_forward_all")
async def bc_forward_start(cb: types.CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS: return
    await state.update_data(bc_type="forward")
    await state.set_state(AS.broadcast_msg)
    await cb.message.answer("📨 Forward qilinadigan xabarni yuboring:", reply_markup=cancel_kb())
    await cb.answer()

@dp.callback_query(F.data == "bc_single")
async def bc_single_start(cb: types.CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS: return
    await state.set_state(AS.broadcast_uid)
    await cb.message.answer("👤 Foydalanuvchi ID sini kiriting:", reply_markup=cancel_kb())
    await cb.answer()

@dp.message(AS.broadcast_uid)
async def bc_uid(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear(); await msg.answer("Bekor qilindi", reply_markup=admin_kb()); return
    try:
        uid = int(msg.text)
        await state.update_data(single_uid=uid)
        await state.set_state(AS.broadcast_uid_msg)
        await msg.answer(f"📝 {uid} ga xabar matnini kiriting:")
    except:
        await msg.answer("❌ Noto'g'ri ID")

@dp.message(AS.broadcast_uid_msg)
async def bc_uid_msg(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear(); await msg.answer("Bekor qilindi", reply_markup=admin_kb()); return
    data = await state.get_data()
    uid  = data["single_uid"]
    try:
        await bot.send_message(uid, msg.text)
        await msg.answer(f"✅ Xabar {uid} ga yuborildi!", reply_markup=admin_kb())
    except Exception as e:
        await msg.answer(f"❌ Xato: {e}", reply_markup=admin_kb())
    await state.clear()

@dp.message(AS.broadcast_msg)
async def do_broadcast(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear(); await msg.answer("Bekor qilindi", reply_markup=admin_kb()); return
    conn = db(); c = conn.cursor()
    c.execute("SELECT user_id FROM users")
    users = c.fetchall(); conn.close()
    sent = fail = 0
    for (uid,) in users:
        try:
            await bot.forward_message(uid, msg.chat.id, msg.message_id)
            sent += 1
        except:
            fail += 1
        await asyncio.sleep(0.05)
    await state.clear()
    await msg.answer(f"✅ Xabar yuborildi!\n✔️ Muvaffaqiyatli: {sent}\n❌ Xato: {fail}",
                     reply_markup=admin_kb())

# ── Foydalanuvchini boshqarish ────────────────────────────
@dp.message(F.text == "👩‍💻 Foydalanuvchini boshqarish")
async def admin_users(msg: types.Message, state: FSMContext):
    if msg.from_user.id not in ADMIN_IDS: return
    await state.set_state(AS.user_id_input)
    await msg.answer("👤 Foydalanuvchi ID sini kiriting:", reply_markup=cancel_kb())

@dp.message(AS.user_id_input)
async def do_user_manage(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear(); await msg.answer("Bekor qilindi", reply_markup=admin_kb()); return
    try:
        uid = int(msg.text)
    except:
        await msg.answer("❌ Noto'g'ri ID"); return
    u = get_user(uid)
    if not u:
        await msg.answer("❌ Foydalanuvchi topilmadi"); await state.clear(); return
    await state.clear()
    b = InlineKeyboardBuilder()
    b.button(text="➕ Balans qo'shish", callback_data=f"uadd_{uid}", style="success")
    b.button(text="➖ Balans ayirish",  callback_data=f"usub_{uid}", style="danger")
    b.button(text="📩 Xabar yuborish",  callback_data=f"umsg_{uid}", style="primary")
    b.adjust(2)
    await msg.answer(
        f"👤 {u[2] or 'Nomsiz'}\n"
        f"🆔 ID: {u[0]}\n"
        f"💵 Balans: {u[3]:.2f} {cur()}\n"
        f"📊 Buyurtmalar: {orders_count(uid)} ta\n"
        f"👥 Referallar: {u[5]} ta",
        reply_markup=b.as_markup()
    )

@dp.callback_query(F.data.startswith("uadd_"))
async def u_add(cb: types.CallbackQuery, state: FSMContext):
    uid = int(cb.data.replace("uadd_", ""))
    await state.update_data(target_uid=uid, bal_action="add")
    await state.set_state(AS.balance_amount)
    await cb.message.answer("💰 Qo'shmoqchi bo'lgan miqdor:", reply_markup=cancel_kb())
    await cb.answer()

@dp.callback_query(F.data.startswith("usub_"))
async def u_sub(cb: types.CallbackQuery, state: FSMContext):
    uid = int(cb.data.replace("usub_", ""))
    await state.update_data(target_uid=uid, bal_action="sub")
    await state.set_state(AS.balance_amount)
    await cb.message.answer("💰 Ayirmoqchi bo'lgan miqdor:", reply_markup=cancel_kb())
    await cb.answer()

@dp.callback_query(F.data.startswith("umsg_"))
async def u_msg(cb: types.CallbackQuery, state: FSMContext):
    uid = int(cb.data.replace("umsg_", ""))
    await state.update_data(single_uid=uid)
    await state.set_state(AS.broadcast_uid_msg)
    await cb.message.answer(f"📝 {uid} ga xabar matnini kiriting:", reply_markup=cancel_kb())
    await cb.answer()

@dp.message(AS.balance_amount)
async def do_balance(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear(); await msg.answer("Bekor qilindi", reply_markup=admin_kb()); return
    try: amount = float(msg.text)
    except: await msg.answer("❌ Noto'g'ri miqdor"); return
    data   = await state.get_data()
    uid    = data["target_uid"]
    action = data["bal_action"]
    conn   = db(); c = conn.cursor()
    if action == "add":
        c.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (amount, uid))
        c.execute("INSERT INTO transactions(user_id,amount,type,description) VALUES(?,?,?,?)",
                  (uid, amount, "admin_add", "Admin tomonidan qo'shildi"))
        try: await bot.send_message(uid, f"✅ Hisobingizga {amount:.2f} {cur()} qo'shildi!")
        except: pass
    else:
        c.execute("UPDATE users SET balance=balance-? WHERE user_id=?", (amount, uid))
        c.execute("INSERT INTO transactions(user_id,amount,type,description) VALUES(?,?,?,?)",
                  (uid, -amount, "admin_sub", "Admin tomonidan ayirildi"))
        try: await bot.send_message(uid, f"⚠️ Hisobingizdan {amount:.2f} {cur()} ayirildi!")
        except: pass
    conn.commit(); conn.close()
    act_text = "qo'shildi" if action == "add" else "ayirildi"
    await state.clear()
    await msg.answer(f"✅ {uid} ga {amount:.2f} {cur()} {act_text}!", reply_markup=admin_kb())

# ── Majbur obuna ──────────────────────────────────────────
@dp.message(F.text == "🔒 Majbur obuna kanallar")
async def forced_channels(msg: types.Message):
    if msg.from_user.id not in ADMIN_IDS: return
    conn = db(); c = conn.cursor()
    c.execute("SELECT id,channel_name,channel_id FROM channels")
    chs = c.fetchall(); conn.close()
    b = InlineKeyboardBuilder()
    for cid, cname, ch_id in chs:
        b.button(text=f"🗑 {cname}", callback_data=f"del_ch_{cid}", style="danger")
    b.button(text="➕ Kanal qo'shish", callback_data="add_channel", style="success")
    b.adjust(1)
    await msg.answer(f"📢 Kanallar: {len(chs)} ta", reply_markup=b.as_markup())

@dp.callback_query(F.data == "add_channel")
async def start_add_channel(cb: types.CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS: return
    await state.set_state(AS.add_channel)
    await cb.message.answer(
        "📢 Kanal ma'lumotlarini quyidagi formatda yuboring:\n\n"
        "<code>@kanal_username | Kanal Nomi | https://t.me/kanal_link</code>",
        parse_mode="HTML", reply_markup=cancel_kb()
    )
    await cb.answer()

@dp.message(AS.add_channel)
async def do_add_channel(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear(); await msg.answer("Bekor qilindi", reply_markup=admin_kb()); return
    parts = [p.strip() for p in msg.text.split("|")]
    if len(parts) != 3:
        await msg.answer("❌ Format noto'g'ri. Qayta kiriting:"); return
    conn = db(); c = conn.cursor()
    c.execute("INSERT INTO channels(channel_id,channel_name,channel_link) VALUES(?,?,?)",
              (parts[0], parts[1], parts[2]))
    conn.commit(); conn.close()
    await state.clear()
    await msg.answer(f"✅ Kanal qo'shildi: {parts[1]}", reply_markup=admin_kb())
    asyncio.create_task(jsonbin_save())

@dp.callback_query(F.data.startswith("del_ch_"))
async def del_ch(cb: types.CallbackQuery):
    cid = int(cb.data.replace("del_ch_", ""))
    conn = db(); c = conn.cursor()
    c.execute("DELETE FROM channels WHERE id=?", (cid,))
    conn.commit(); conn.close()
    await cb.message.answer("✅ Kanal o'chirildi!"); await cb.answer()

# ═══════════════════════════════════════════════════════════
#  ADMIN — To'lov tizimlari
# ═══════════════════════════════════════════════════════════
@dp.message(F.text == "💳 To'lov tizimlar")
async def payment_methods(msg: types.Message):
    if msg.from_user.id not in ADMIN_IDS: return
    b = InlineKeyboardBuilder()
    b.button(text="⚡ Avtomatik to'lov tizimlari", callback_data="pay_auto_settings", style="primary")
    b.button(text="📝 Oddiy to'lov tizimlari",     callback_data="mpay_settings", style="success")
    b.adjust(1)
    await msg.answer("⚙️ To'lov tizim sozlamalarisiz:", reply_markup=b.as_markup())

@dp.callback_query(F.data == "mpay_settings")
async def pay_manual_settings(cb: types.CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS: return
    conn = db(); c = conn.cursor()
    c.execute("SELECT id, pay_type, name, card_number, is_active FROM manual_payments")
    pays = c.fetchall(); conn.close()
    b = InlineKeyboardBuilder()
    for pid, ptype, pname, pcard, pact in pays:
        st       = "✅" if pact else "❌"
        type_nm  = "Uzcart" if ptype == "uzcart" else "Humo"
        disp_nm  = pname if pname else type_nm
        b.button(text=f"{st} {disp_nm} ({type_nm})", callback_data=f"pay_tog_{pid}", style="success")
    b.button(text="➕ To'lov qo'shish", callback_data="add_mpay", style="success")
    b.adjust(1)
    try:
        await cb.message.edit_text(f"📝 Oddiy to'lov tizimlari: {len(pays)} ta", reply_markup=b.as_markup())
    except Exception:
        await cb.message.answer(f"📝 Oddiy to'lov tizimlari: {len(pays)} ta", reply_markup=b.as_markup())
    await cb.answer()

@dp.callback_query(F.data == "pay_auto_settings")
async def pay_auto_settings(cb: types.CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS: return
    payme_on = get_setting("payme_active") == "1"
    click_on = get_setting("click_active") == "1"
    b = InlineKeyboardBuilder()
    b.button(text=f"{'✅' if payme_on else '❌'} Payme", callback_data="tog_payme", style="success" if payme_on else "primary")
    b.button(text=f"{'✅' if click_on else '❌'} Click", callback_data="tog_click", style="success" if click_on else "primary")
    b.adjust(2)
    try:
        await cb.message.edit_text(
            f"⚡ Avtomatik to'lov tizimlari:\n\n"
            f"Payme: {'✅ Faol' if payme_on else '❌ Nofaol'}\n"
            f"Click: {'✅ Faol' if click_on else '❌ Nofaol'}",
            reply_markup=b.as_markup()
        )
    except Exception:
        await cb.message.answer(f"⚡ Avtomatik to'lov tizimlari:", reply_markup=b.as_markup())
    await cb.answer()

@dp.callback_query(F.data == "tog_payme")
async def tog_payme(cb: types.CallbackQuery):
    v = "0" if get_setting("payme_active") == "1" else "1"
    set_setting("payme_active", v)
    await pay_auto_settings(cb)

@dp.callback_query(F.data == "tog_click")
async def tog_click(cb: types.CallbackQuery):
    v = "0" if get_setting("click_active") == "1" else "1"
    set_setting("click_active", v)
    await pay_auto_settings(cb)

@dp.callback_query(F.data == "add_mpay")
async def add_mpay(cb: types.CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS: return
    b = InlineKeyboardBuilder()
    b.button(text="💳 Uzcart", callback_data="mpay_type_uzcart", style="primary")
    b.button(text="🟠 Humo",   callback_data="mpay_type_humo", style="success")
    b.adjust(2)
    await cb.message.answer("To'lov turini tanlang:", reply_markup=b.as_markup())
    await cb.answer()

@dp.callback_query(F.data.startswith("mpay_type_"))
async def mpay_type_select(cb: types.CallbackQuery, state: FSMContext):
    ptype = cb.data.replace("mpay_type_", "")
    await state.update_data(mpay_type=ptype)
    await state.set_state(AS.mpay_name)
    type_name = "Uzcart" if ptype == "uzcart" else "Humo"
    await cb.message.answer(
        f"💳 {type_name} to'lov qo'shish\n\n"
        f"📝 To'lov nomini kiriting:\n(Masalan: Asosiy karta, Shaxsiy karta)",
        reply_markup=cancel_kb()
    )
    await cb.answer()

@dp.message(AS.mpay_name)
async def mpay_name_h(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear(); await msg.answer("Bekor qilindi", reply_markup=admin_kb()); return
    await state.update_data(mpay_name=msg.text)
    await state.set_state(AS.mpay_card)
    await msg.answer("🔢 Karta raqamini kiriting:\n(Masalan: 8600 1234 5678 9012)")

@dp.message(AS.mpay_card)
async def mpay_card_h(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear(); await msg.answer("Bekor qilindi", reply_markup=admin_kb()); return
    await state.update_data(mpay_card=msg.text)
    await state.set_state(AS.mpay_expiry)
    await msg.answer("📅 Karta muddatini kiriting:\n(Masalan: 12/26)")

@dp.message(AS.mpay_expiry)
async def mpay_expiry_h(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear(); await msg.answer("Bekor qilindi", reply_markup=admin_kb()); return
    await state.update_data(mpay_expiry=msg.text)
    await state.set_state(AS.mpay_holder)
    await msg.answer("👤 Karta egasining Ism Familiyasini kiriting:\n(Masalan: AZIZ KARIMOV)")

@dp.message(AS.mpay_holder)
async def mpay_holder_h(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear(); await msg.answer("Bekor qilindi", reply_markup=admin_kb()); return
    data = await state.get_data()
    conn = db(); c = conn.cursor()
    c.execute("INSERT INTO manual_payments(pay_type, name, card_number, card_expiry, card_holder) VALUES(?,?,?,?,?)",
              (data.get("mpay_type", "uzcart"), data.get("mpay_name",""), data["mpay_card"], data["mpay_expiry"], msg.text))
    conn.commit(); conn.close()
    await state.clear()
    type_name = "Uzcart" if data.get("mpay_type") == "uzcart" else "Humo"
    pname     = data.get("mpay_name", type_name)
    await msg.answer(
        f"✅ To'lov tizimi qo'shildi!\n\n"
        f"💳 Turi: {type_name}\n"
        f"📝 Nomi: {pname}\n"
        f"🔢 Karta: {data['mpay_card']}\n"
        f"📅 Muddat: {data['mpay_expiry']}\n"
        f"👤 Egasi: {msg.text}",
        reply_markup=admin_kb()
    )
    asyncio.create_task(jsonbin_save())

@dp.callback_query(F.data.startswith("pay_tog_"))
async def pay_toggle(cb: types.CallbackQuery):
    pid = int(cb.data.replace("pay_tog_", ""))
    conn = db(); c = conn.cursor()
    c.execute("SELECT is_active FROM manual_payments WHERE id=?", (pid,))
    v = c.fetchone()[0]
    c.execute("UPDATE manual_payments SET is_active=? WHERE id=?", (0 if v else 1, pid))
    conn.commit(); conn.close()
    await cb.answer("✅ O'zgartirildi!")
    await pay_manual_settings(cb)

# ═══════════════════════════════════════════════════════════
#  ADMIN — API boshqaruvi
# ═══════════════════════════════════════════════════════════
@dp.message(F.text == "🔑 API")
async def api_menu(msg: types.Message):
    if msg.from_user.id not in ADMIN_IDS: return
    conn = db(); c = conn.cursor()
    c.execute("SELECT id,name,url FROM apis")
    apis = c.fetchall(); conn.close()
    b = InlineKeyboardBuilder()
    for aid, aname, aurl in apis:
        b.button(text=f"🔑 {aname}", callback_data=f"api_{aid}", style="primary")
    b.button(text="➕ API qo'shish", callback_data="api_add", style="success")
    b.adjust(1)
    await msg.answer(f"🔑 API lar: {len(apis)} ta", reply_markup=b.as_markup())

@dp.callback_query(F.data == "api_add")
async def api_add(cb: types.CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS: return
    await state.set_state(AS.api_name)
    await cb.message.answer("🔑 API nomi:", reply_markup=cancel_kb())
    await cb.answer()

@dp.message(AS.api_name)
async def api_name_h(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear(); await msg.answer("Bekor qilindi", reply_markup=admin_kb()); return
    await state.update_data(api_name=msg.text)
    await state.set_state(AS.api_url)
    await msg.answer("🌐 API URL (masalan: https://panel.uz/api/v2):")

@dp.message(AS.api_url)
async def api_url_h(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear(); await msg.answer("Bekor qilindi", reply_markup=admin_kb()); return
    await state.update_data(api_url=msg.text)
    await state.set_state(AS.api_key)
    await msg.answer("🔐 API kaliti (key):")

@dp.message(AS.api_key)
async def api_key_h(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear(); await msg.answer("Bekor qilindi", reply_markup=admin_kb()); return
    data = await state.get_data()
    conn = db(); c = conn.cursor()
    c.execute("INSERT INTO apis(name,url,api_key) VALUES(?,?,?)",
              (data["api_name"], data["api_url"], msg.text))
    aid = c.lastrowid
    conn.commit(); conn.close()
    await state.clear()

    saving_msg = await msg.answer(
        f"✅ Muvaffaqiyatli saqlandi!\n\n"
        f"🔑 Nomi: {data['api_name']}\n"
        f"🆔 ID: {aid}\n\n"
        f"⏳ API bot hisobi tekshirilmoqda...",
        reply_markup=admin_kb()
    )
    asyncio.create_task(jsonbin_save())

    bal, cur_val = await api_balance(data["api_url"], msg.text)
    if bal is not None:
        try:
            await saving_msg.edit_text(
                f"✅ Muvaffaqiyatli saqlandi!\n\n"
                f"🔑 Nomi: {data['api_name']}\n"
                f"🆔 ID: {aid}\n\n"
                f"💰 API bot hisobi: {bal:.2f} {cur_val}"
            )
        except Exception:
            await msg.answer(f"💰 API bot hisobi: {bal:.2f} {cur_val}", reply_markup=admin_kb())
    else:
        try:
            await saving_msg.edit_text(
                f"✅ Muvaffaqiyatli saqlandi!\n\n"
                f"🔑 Nomi: {data['api_name']}\n"
                f"🆔 ID: {aid}\n\n"
                f"⚠️ API balansini tekshirib bo'lmadi."
            )
        except Exception:
            pass

@dp.callback_query(F.data.startswith("api_") & ~F.data.startswith("api_add") & ~F.data.startswith("api_del_") & ~F.data.startswith("api_bal_") & ~F.data.startswith("api_rekey_"))
async def api_detail(cb: types.CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS: return
    try:
        aid = int(cb.data.replace("api_", ""))
    except:
        await cb.answer(); return
    conn = db(); c = conn.cursor()
    c.execute("SELECT * FROM apis WHERE id=?", (aid,))
    api = c.fetchone(); conn.close()
    if not api: await cb.answer("❌ Topilmadi"); return
    b = InlineKeyboardBuilder()
    b.button(text="🔑 API Key yangilash",  callback_data=f"api_rekey_{aid}", style="primary")
    b.button(text="💰 Balansni ko'rish",   callback_data=f"api_bal_{aid}", style="success")
    b.button(text="❌ O'chirish",          callback_data=f"api_del_{aid}", style="danger")
    b.button(text="◀️ Orqaga",            callback_data="api_back", style="danger")
    b.adjust(1)
    await cb.message.answer(
        f"🔑 {api[1]}\n🌐 {api[2]}\n🔐 {api[3][:15]}...",
        reply_markup=b.as_markup()
    )
    await cb.answer()

@dp.callback_query(F.data == "api_back")
async def api_back(cb: types.CallbackQuery):
    conn = db(); c = conn.cursor()
    c.execute("SELECT id,name,url FROM apis")
    apis = c.fetchall(); conn.close()
    b = InlineKeyboardBuilder()
    for aid, aname, aurl in apis:
        b.button(text=f"🔑 {aname}", callback_data=f"api_{aid}", style="primary")
    b.button(text="➕ API qo'shish", callback_data="api_add", style="success")
    b.adjust(1)
    try:
        await cb.message.edit_text(f"🔑 API lar: {len(apis)} ta", reply_markup=b.as_markup())
    except Exception:
        await cb.message.answer(f"🔑 API lar: {len(apis)} ta", reply_markup=b.as_markup())
    await cb.answer()

@dp.callback_query(F.data.startswith("api_bal_"))
async def api_bal(cb: types.CallbackQuery):
    aid  = int(cb.data.replace("api_bal_", ""))
    conn = db(); c = conn.cursor()
    c.execute("SELECT url,api_key FROM apis WHERE id=?", (aid,))
    api = c.fetchone(); conn.close()
    if not api: await cb.answer("❌ Topilmadi"); return
    bal, cur_val = await api_balance(api[0], api[1])
    if bal is None:
        await cb.answer("❌ API ga ulanib bo'lmadi", show_alert=True)
    else:
        await cb.message.answer(f"💰 API bot hisobi: {bal:.2f} {cur_val}")
    await cb.answer()

@dp.callback_query(F.data.startswith("api_del_"))
async def api_del(cb: types.CallbackQuery):
    aid  = int(cb.data.replace("api_del_", ""))
    conn = db(); c = conn.cursor()
    c.execute("DELETE FROM apis WHERE id=?", (aid,))
    conn.commit(); conn.close()
    await cb.message.answer("✅ API o'chirildi!")
    await cb.answer()

@dp.callback_query(F.data.startswith("api_rekey_"))
async def api_rekey(cb: types.CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS: return
    aid = int(cb.data.replace("api_rekey_", ""))
    await state.update_data(rekey_api_id=aid)
    await state.set_state(AS.api_key)
    await cb.message.answer("🔐 Yangi API kaliti (key)ni kiriting:", reply_markup=cancel_kb())
    await cb.answer()

# ── Qo'llanmalar (Admin) ─────────────────────────────────
@dp.message(F.text == "📚 Qo'llanmalar")
async def admin_guides(msg: types.Message):
    if msg.from_user.id not in ADMIN_IDS: return
    conn = db(); c = conn.cursor()
    c.execute("SELECT id,title FROM guides")
    gs = c.fetchall(); conn.close()
    b = InlineKeyboardBuilder()
    for gid, gtitle in gs:
        b.button(text=f"🗑 {gtitle}", callback_data=f"del_guide_{gid}", style="danger")
    b.button(text="➕ Qo'llanma qo'shish", callback_data="add_guide", style="success")
    b.adjust(1)
    await msg.answer(f"📚 Qo'llanmalar: {len(gs)} ta", reply_markup=b.as_markup())

@dp.callback_query(F.data == "add_guide")
async def start_guide(cb: types.CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS: return
    await state.set_state(AS.guide_title)
    await cb.message.answer("📖 Qo'llanma nomini kiriting:", reply_markup=cancel_kb())
    await cb.answer()

@dp.message(AS.guide_title)
async def guide_title_h(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear(); await admin_guides(msg); return
    await state.update_data(gtitle=msg.text)
    await state.set_state(AS.guide_content)
    await msg.answer("📝 Qo'llanma matnini kiriting:")

@dp.message(AS.guide_content)
async def guide_content_h(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    conn = db(); c = conn.cursor()
    c.execute("INSERT INTO guides(title,content) VALUES(?,?)", (data["gtitle"], msg.text))
    conn.commit(); conn.close()
    await state.clear()
    await msg.answer("✅ Qo'llanma qo'shildi!", reply_markup=admin_kb())

@dp.callback_query(F.data.startswith("del_guide_"))
async def del_guide(cb: types.CallbackQuery):
    gid = int(cb.data.replace("del_guide_", ""))
    conn = db(); c = conn.cursor()
    c.execute("DELETE FROM guides WHERE id=?", (gid,))
    conn.commit(); conn.close()
    await cb.message.answer("✅ Qo'llanma o'chirildi!"); await cb.answer()

# ═══════════════════════════════════════════════════════════
#  ADMIN — Platformalar
# ═══════════════════════════════════════════════════════════
async def show_platforms_menu(target, edit=False):
    plats = get_platforms_list()
    rows = []
    for pid, pkey, pname in plats:
        rows.append([
            InlineKeyboardButton(text=f"✏️ {pname}", callback_data=f"plat_ren_{pid}", style="primary"),
            InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"plat_del_{pid}", style="danger"),
        ])
    rows.append([InlineKeyboardButton(text="➕ Platforma qo'shish", callback_data="plat_add", style="success")])
    kb = InlineKeyboardMarkup(inline_keyboard=rows)

    text = f"🌐 Platformalar: {len(plats)} ta\n\nNomini o'zgartirish yoki o'chirish:"
    if edit:
        try:
            await target.edit_text(text, reply_markup=kb); return
        except Exception:
            pass
    await target.answer(text, reply_markup=kb)

@dp.message(F.text == "🌐 Platformalar")
async def admin_platforms(msg: types.Message):
    if msg.from_user.id not in ADMIN_IDS: return
    await show_platforms_menu(msg)

@dp.callback_query(F.data == "plat_add")
async def plat_add_start(cb: types.CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS: return
    await state.set_state(AS.plat_rename_val)
    await state.update_data(plat_rename_key="__new__")
    await cb.message.answer(
        "➕ Yangi platforma nomini kiriting:\n\n"
        "Masalan: 📱 WhatsApp\n"
        "(Emoji + bo'sh joy + nom)\n\n"
        "Ichki kalit (key) avtomatik yaratiladi.",
        reply_markup=cancel_kb()
    )
    await cb.answer()

@dp.callback_query(F.data.startswith("plat_ren_"))
async def plat_ren_start(cb: types.CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS: return
    pid = cb.data.replace("plat_ren_", "")
    conn = db(); c = conn.cursor()
    c.execute("SELECT key, name FROM platforms WHERE id=?", (pid,))
    row = c.fetchone(); conn.close()
    if not row: await cb.answer("❌ Topilmadi"); return
    await state.update_data(plat_rename_key=pid)
    await state.set_state(AS.plat_rename_val)
    await cb.message.answer(
        f"✏️ Yangi nom kiriting:\n\n"
        f"Hozirgi: {row[1]}\n\n"
        f"Masalan: 📱 Telegram\n"
        f"(Emoji + bo'sh joy + nom)",
        reply_markup=cancel_kb()
    )
    await cb.answer()

# ✅ TUZATILGAN: plat_ren_save — yangi qo'shish va tahrirlash alohida
@dp.message(AS.plat_rename_val)
async def plat_ren_save(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear(); await msg.answer("Bekor qilindi", reply_markup=admin_kb()); return
    data = await state.get_data()
    pid  = data.get("plat_rename_key", "")
    new_name = msg.text.strip()
    conn = db(); c = conn.cursor()

    if pid == "__new__":
        # Yangi platforma qo'shish
        import re, time
        key = re.sub(r'[^a-z0-9]', '', new_name.lower().replace(' ', '_'))[:20]
        if not key:
            key = f"plat_{int(time.time())}"
        c.execute("SELECT id FROM platforms WHERE key=?", (key,))
        if c.fetchone():
            key = f"{key}_{int(time.time()) % 1000}"
        c.execute("INSERT INTO platforms(key,name,sort_order) VALUES(?,?,?)",
                  (key, new_name, 99))
        conn.commit(); conn.close()
        await state.clear()
        await msg.answer(f"✅ Platforma qo'shildi: {new_name}", reply_markup=admin_kb())
        asyncio.create_task(jsonbin_save())
    else:
        # Mavjud platformani tahrirlash
        c.execute("UPDATE platforms SET name=? WHERE id=?", (new_name, pid))
        conn.commit(); conn.close()
        await state.clear()
        await msg.answer(f"✅ Platforma nomi o'zgartirildi: {new_name}", reply_markup=admin_kb())
        asyncio.create_task(jsonbin_save())

@dp.callback_query(F.data.startswith("plat_del_") & ~F.data.startswith("plat_del_confirm_") & ~F.data.startswith("plat_del_cancel"))
async def plat_del(cb: types.CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS: return
    pid = cb.data.replace("plat_del_", "")
    conn = db(); c = conn.cursor()
    c.execute("SELECT key, name FROM platforms WHERE id=?", (pid,))
    row = c.fetchone()
    if not row:
        conn.close(); await cb.answer("❌ Topilmadi"); return
    pkey, pname = row
    b = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Ha, o'chirish", callback_data=f"plat_del_confirm_{pid}", style="danger"),
        InlineKeyboardButton(text="❌ Yo'q",          callback_data="plat_del_cancel", style="success"),
    ]])
    conn.close()
    await cb.message.answer(
        f"⚠️ '{pname}' platformasini o'chirasizmi?\n\n"
        f"Bu platformadagi barcha bo'limlar ham o'chib ketishi mumkin!",
        reply_markup=b
    )
    await cb.answer()

@dp.callback_query(F.data.startswith("plat_del_confirm_"))
async def plat_del_confirm(cb: types.CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS: return
    pid = cb.data.replace("plat_del_confirm_", "")
    conn = db(); c = conn.cursor()
    c.execute("SELECT key, name FROM platforms WHERE id=?", (pid,))
    row = c.fetchone()
    if not row:
        conn.close(); await cb.answer("❌ Topilmadi"); return
    pkey, pname = row
    c.execute("DELETE FROM platforms WHERE id=?", (pid,))
    conn.commit(); conn.close()
    try:
        await cb.message.edit_text(f"✅ '{pname}' platformasi o'chirildi!", reply_markup=None)
    except Exception:
        await cb.message.answer(f"✅ '{pname}' platformasi o'chirildi!")
    await cb.answer()

@dp.callback_query(F.data == "plat_del_cancel")
async def plat_del_cancel(cb: types.CallbackQuery):
    try:
        await cb.message.edit_text("Bekor qilindi.", reply_markup=None)
    except Exception:
        pass
    await cb.answer()

# ═══════════════════════════════════════════════════════════
#  ADMIN — Asosiy sozlamalar
# ═══════════════════════════════════════════════════════════
@dp.message(F.text == "⚙️ Asosiy sozlamalar")
async def main_settings(msg: types.Message):
    if msg.from_user.id not in ADMIN_IDS: return
    ref_bonus  = get_setting("referral_bonus", "2500")
    currency   = get_setting("currency", "Sum")
    svc_time   = get_setting("service_time", "1")
    prem_emoji = get_setting("premium_emoji", "1")

    b = InlineKeyboardBuilder()
    b.button(text=f"💰 Referal bonus: {ref_bonus}", callback_data="set_ref_bonus", style="primary")
    b.button(text=f"💱 Valyuta: {currency}",        callback_data="set_currency", style="primary")
    b.button(text=f"⏱ Xizmat vaqti (kun): {svc_time}", callback_data="set_svc_time", style="success")
    b.button(text=f"{'✅' if prem_emoji=='1' else '❌'} Premium emoji", callback_data="tog_prem_emoji",
             style="success" if prem_emoji=="1" else "primary")
    b.adjust(1)

    await msg.answer(
        f"⚙️ Asosiy sozlamalar:\n\n"
        f"💰 Referal bonus: {ref_bonus} {currency}\n"
        f"💱 Valyuta: {currency}\n"
        f"⏱ Xizmat vaqti: {svc_time} kun\n"
        f"⭐ Premium emoji: {'Faol' if prem_emoji=='1' else 'Nofaol'}",
        reply_markup=b.as_markup()
    )

@dp.callback_query(F.data == "set_ref_bonus")
async def set_ref_bonus_start(cb: types.CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS: return
    await state.set_state(AS.set_referral)
    await cb.message.answer(
        f"💰 Yangi referal bonus miqdorini kiriting:\n"
        f"Hozirgi: {get_setting('referral_bonus', '2500')} {cur()}",
        reply_markup=cancel_kb()
    )
    await cb.answer()

@dp.message(AS.set_referral)
async def do_set_referral(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear(); await msg.answer("Bekor qilindi", reply_markup=admin_kb()); return
    try:
        val = float(msg.text)
        if val < 0: raise ValueError
    except:
        await msg.answer("❌ Noto'g'ri miqdor, faqat musbat son kiriting"); return
    set_setting("referral_bonus", str(val))
    await state.clear()
    await msg.answer(f"✅ Referal bonus o'zgartirildi: {val} {cur()}", reply_markup=admin_kb())
    asyncio.create_task(jsonbin_save())

@dp.callback_query(F.data == "set_currency")
async def set_currency_start(cb: types.CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS: return
    await state.set_state(AS.set_currency)
    await cb.message.answer(
        f"💱 Yangi valyuta nomini kiriting:\n"
        f"Hozirgi: {cur()}\n\n"
        f"Masalan: Sum, UZS, USD, EUR",
        reply_markup=cancel_kb()
    )
    await cb.answer()

@dp.message(AS.set_currency)
async def do_set_currency(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear(); await msg.answer("Bekor qilindi", reply_markup=admin_kb()); return
    set_setting("currency", msg.text.strip())
    await state.clear()
    await msg.answer(f"✅ Valyuta o'zgartirildi: {msg.text.strip()}", reply_markup=admin_kb())
    asyncio.create_task(jsonbin_save())

@dp.callback_query(F.data == "set_svc_time")
async def set_svc_time_start(cb: types.CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS: return
    await cb.message.answer(
        f"⏱ Xizmat vaqtini kiriting (kun):\nHozirgi: {get_setting('service_time','1')}",
        reply_markup=cancel_kb()
    )
    await cb.answer()

@dp.callback_query(F.data == "tog_prem_emoji")
async def tog_prem_emoji(cb: types.CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS: return
    new_val = "0" if get_setting("premium_emoji") == "1" else "1"
    set_setting("premium_emoji", new_val)
    status = "Faol ✅" if new_val == "1" else "Nofaol ❌"
    await cb.answer(f"Premium emoji: {status}", show_alert=True)
    ref_bonus  = get_setting("referral_bonus", "2500")
    currency   = get_setting("currency", "Sum")
    svc_time   = get_setting("service_time", "1")
    b = InlineKeyboardBuilder()
    b.button(text=f"💰 Referal bonus: {ref_bonus}", callback_data="set_ref_bonus", style="primary")
    b.button(text=f"💱 Valyuta: {currency}",        callback_data="set_currency", style="primary")
    b.button(text=f"⏱ Xizmat vaqti (kun): {svc_time}", callback_data="set_svc_time", style="success")
    b.button(text=f"{'✅' if new_val=='1' else '❌'} Premium emoji", callback_data="tog_prem_emoji",
             style="success" if new_val=="1" else "primary")
    b.adjust(1)
    try:
        await cb.message.edit_reply_markup(reply_markup=b.as_markup())
    except Exception:
        pass

# ── Buyurtmalar (Admin) ──────────────────────────────────
@dp.message(F.text == "📈 Buyurtmalar")
async def admin_orders(msg: types.Message):
    if msg.from_user.id not in ADMIN_IDS: return
    conn = db(); c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM orders"); total = c.fetchone()[0]
    st = {}
    for s in ("completed", "cancelled", "pending", "processing", "partial"):
        c.execute("SELECT COUNT(*) FROM orders WHERE status=?", (s,))
        st[s] = c.fetchone()[0]
    conn.close()
    b = InlineKeyboardBuilder()
    b.button(text="🔍 So'nggi buyurtmalar", callback_data="search_orders", style="primary")
    await msg.answer(
        f"📈 Buyurtmalar: {total} ta\n\n"
        f"✅ Bajarilganlar: {st['completed']} ta\n"
        f"🚫 Bekor qilinganlar: {st['cancelled']} ta\n"
        f"⏳ Kutilayotganlar: {st['pending']} ta\n"
        f"🔄 Jarayondagilar: {st['processing']} ta\n"
        f"♻️ Qisman: {st['partial']} ta",
        reply_markup=b.as_markup()
    )

@dp.callback_query(F.data == "search_orders")
async def search_orders(cb: types.CallbackQuery):
    conn = db(); c = conn.cursor()
    c.execute("""SELECT o.id,o.user_id,s.name,o.quantity,o.amount,o.status,o.created_at
                 FROM orders o LEFT JOIN services s ON o.service_id=s.id
                 ORDER BY o.id DESC LIMIT 20""")
    rows = c.fetchall(); conn.close()
    if not rows:
        await cb.message.answer("❌ Buyurtmalar yo'q"); await cb.answer(); return
    text = "📋 So'nggi 20 buyurtma:\n\n"
    for r in rows:
        text += f"#{r[0]} | {r[2] or '?'} | {r[3]} ta | {r[4]:.2f} {cur()} | {r[5]}\n"
    await cb.message.answer(text[:4096]); await cb.answer()

# ═══════════════════════════════════════════════════════════
#  ADMIN — Xizmatlar
# ═══════════════════════════════════════════════════════════
@dp.message(F.text == "📁 Xizmatlar")
async def svc_home(msg: types.Message):
    if msg.from_user.id not in ADMIN_IDS: return
    conn = db(); c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM categories"); nc = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM services");   ns = c.fetchone()[0]
    conn.close()
    kb = ReplyKeyboardMarkup(keyboard=[
        [kbtn("📂 Bo'limlar", "primary"), kbtn("🛠 Barcha xizmatlar", "primary")],
        [kbtn("📊 Foiz qo'shish", "success"), kbtn("🌐 Platformalar")],
        [kbtn("◀️ Orqaga", "danger")],
    ], resize_keyboard=True)
    await msg.answer(
        f"📁 Xizmatlar boshqaruvi\n\n"
        f"📂 Bo'limlar: {nc} ta\n"
        f"🛠 Xizmatlar: {ns} ta",
        reply_markup=kb
    )

@dp.message(F.text == "📊 Foiz qo'shish")
async def svc_percent_start(msg: types.Message, state: FSMContext):
    if msg.from_user.id not in ADMIN_IDS: return
    conn = db(); c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM services WHERE is_active=1")
    ns = c.fetchone()[0]; conn.close()
    b = InlineKeyboardBuilder()
    for p in ["5", "10", "15", "20", "25", "30", "50"]:
        b.button(text=f"+{p}%", callback_data=f"svcp_{p}", style="success")
    b.adjust(4)
    await state.set_state(AS.svc_percent_input)
    await msg.answer(
        f"📊 Barcha xizmatlar narxiga foiz qo'shish\n\n"
        f"🛠 Faol xizmatlar: {ns} ta\n\n"
        f"Quyidagi foizlardan birini tanlang yoki o'z raqamingizni kiriting\n"
        f"(Masalan: 10 yoki 10.5):",
        reply_markup=b.as_markup()
    )

@dp.callback_query(F.data.startswith("svcp_"))
async def svc_percent_quick(cb: types.CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS: return
    percent_str = cb.data.replace("svcp_", "")
    await _apply_percent(cb.message, state, percent_str, cb)

@dp.message(AS.svc_percent_input)
async def svc_percent_input_h(msg: types.Message, state: FSMContext):
    if msg.text in ("❌ Bekor qilish", "◀️ Orqaga"):
        await state.clear()
        await msg.answer("Bekor qilindi", reply_markup=admin_kb())
        return
    await _apply_percent(msg, state, msg.text.strip(), None)

async def _apply_percent(target, state: FSMContext, percent_str: str, cb=None):
    try:
        percent = float(percent_str.replace(",", ".").replace("%", ""))
        if percent <= 0 or percent > 1000:
            raise ValueError
    except (ValueError, TypeError):
        err_text = "❌ Noto'g'ri foiz! Musbat son kiriting (masalan: 10 yoki 10.5)"
        if cb:
            await cb.answer(err_text, show_alert=True)
        else:
            await target.answer(err_text)
        return

    koeff = 1 + percent / 100
    conn = db(); c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM services"); total = c.fetchone()[0]
    c.execute("UPDATE services SET price_per1000 = ROUND(price_per1000 * ?, 2)", (koeff,))
    conn.commit(); conn.close()

    await state.clear()
    asyncio.create_task(jsonbin_save())

    text = (
        f"✅ Barcha xizmatlar narxi +{percent}% ko'tarildi!\n\n"
        f"🛠 Yangilangan xizmatlar: {total} ta\n"
        f"📈 Koeffitsient: x{koeff:.4f}"
    )
    if cb:
        try:
            await cb.message.edit_text(text, reply_markup=None)
        except Exception:
            await cb.message.answer(text)
        await cb.answer("✅ Narxlar yangilandi!")
    else:
        await target.answer(text, reply_markup=admin_kb())

@dp.message(F.text == "📂 Bo'limlar")
async def cat_menu(msg: types.Message):
    if msg.from_user.id not in ADMIN_IDS: return
    conn = db(); c = conn.cursor()
    c.execute("SELECT id,name,platform,is_active FROM categories ORDER BY platform,name")
    cats = c.fetchall(); conn.close()
    b = InlineKeyboardBuilder()
    for cid, cname, cplat, cact in cats:
        status    = "✅" if cact else "❌"
        plat_icon = get_platforms().get(cplat, cplat)
        b.button(text=f"{status} {plat_icon} {cname}", callback_data=f"cat_{cid}", style="primary")
    b.button(text="➕ Bo'lim qo'shish", callback_data="cat_add", style="success")
    b.adjust(1)
    await msg.answer(f"📂 Bo'limlar: {len(cats)} ta", reply_markup=b.as_markup())

@dp.callback_query(F.data == "cat_add")
async def cat_add(cb: types.CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS: return
    plats = get_platforms_list()
    rows = []
    for i in range(0, len(plats), 2):
        row = []
        row.append(InlineKeyboardButton(text=plats[i][2], callback_data=f"cat_plat_{plats[i][1]}", style="primary"))
        if i+1 < len(plats):
            row.append(InlineKeyboardButton(text=plats[i+1][2], callback_data=f"cat_plat_{plats[i+1][1]}", style="primary"))
        rows.append(row)
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    try:
        await cb.message.edit_text("📁 Qaysi platforma uchun bo'lim qo'shmoqchisiz?", reply_markup=kb)
    except Exception:
        await cb.message.answer("📁 Qaysi platforma uchun bo'lim qo'shmoqchisiz?", reply_markup=kb)
    await cb.answer()

@dp.callback_query(F.data.startswith("cat_plat_"))
async def cat_plat_select(cb: types.CallbackQuery, state: FSMContext):
    platform  = cb.data.replace("cat_plat_", "")
    plat_name = get_platforms().get(platform, platform.capitalize())
    await state.update_data(new_cat_platform=platform)
    await state.set_state(AS.add_category)
    try:
        await cb.message.edit_text(
            f"✅ Platforma: {plat_name}\n\n📁 Bo'lim nomini kiriting:",
            reply_markup=None
        )
    except Exception:
        await cb.message.answer(f"✅ Platforma: {plat_name}\n\n📁 Bo'lim nomini kiriting:",
                                reply_markup=cancel_kb())
    await cb.answer()

@dp.message(AS.add_category)
async def do_add_cat(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear(); await msg.answer("Bekor qilindi", reply_markup=admin_kb()); return
    data = await state.get_data()
    platform = data.get("new_cat_platform", "telegram")
    conn = db(); c = conn.cursor()
    c.execute("INSERT INTO categories(name,platform) VALUES(?,?)", (msg.text, platform))
    conn.commit(); conn.close()
    await state.clear()
    await msg.answer(f"✅ Bo'lim qo'shildi: {msg.text}", reply_markup=admin_kb())
    asyncio.create_task(jsonbin_save())

@dp.callback_query(F.data.startswith("cat_") & ~F.data.startswith("cat_add") & ~F.data.startswith("cat_plat_") & ~F.data.startswith("cat_svc") & ~F.data.startswith("cat_svcs_") & ~F.data.startswith("cat_del_") & ~F.data.startswith("cat_tog_"))
async def cat_detail(cb: types.CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS: return
    try:
        cid = int(cb.data.replace("cat_", ""))
    except:
        await cb.answer(); return
    conn = db(); c = conn.cursor()
    c.execute("SELECT id,name,platform,is_active FROM categories WHERE id=?", (cid,))
    cat = c.fetchone()
    c.execute("SELECT COUNT(*) FROM services WHERE category_id=?", (cid,))
    svc_count = c.fetchone()[0]
    conn.close()
    if not cat: await cb.answer("❌ Topilmadi"); return
    status    = "✅ Faol" if cat[3] else "❌ Nofaol"
    plat_icon = get_platforms().get(cat[2], cat[2])
    b = InlineKeyboardBuilder()
    b.button(text="❌ O'chirish" if cat[3] else "✅ Faollashtirish", callback_data=f"cat_tog_{cid}", style="danger" if cat[3] else "success")
    b.button(text="➕ Xizmat qo'shish",  callback_data=f"cat_svc_add_{cid}", style="success")
    b.button(text="📋 Xizmatlar ro'yhat", callback_data=f"cat_svcs_{cid}", style="primary")
    b.button(text="🗑 Bo'limni o'chirish", callback_data=f"cat_del_{cid}", style="danger")
    b.adjust(2)
    try:
        await cb.message.edit_text(
            f"📁 {plat_icon} {cat[1]}\nPlatforma: {cat[2].capitalize()}\n"
            f"Holat: {status}\nXizmatlar: {svc_count} ta",
            reply_markup=b.as_markup()
        )
    except Exception:
        await cb.message.answer(
            f"📁 {plat_icon} {cat[1]}\nPlatforma: {cat[2].capitalize()}\n"
            f"Holat: {status}\nXizmatlar: {svc_count} ta",
            reply_markup=b.as_markup()
        )
    await cb.answer()

@dp.callback_query(F.data.startswith("cat_tog_"))
async def cat_toggle(cb: types.CallbackQuery):
    cid  = int(cb.data.replace("cat_tog_", ""))
    conn = db(); c = conn.cursor()
    c.execute("SELECT is_active FROM categories WHERE id=?", (cid,))
    v    = c.fetchone()[0]
    c.execute("UPDATE categories SET is_active=? WHERE id=?", (0 if v else 1, cid))
    conn.commit(); conn.close()
    await cb.answer("✅ O'zgartirildi!")
    await cat_detail(cb)

@dp.callback_query(F.data.startswith("cat_del_"))
async def cat_del(cb: types.CallbackQuery):
    cid  = int(cb.data.replace("cat_del_", ""))
    conn = db(); c = conn.cursor()
    c.execute("DELETE FROM categories WHERE id=?", (cid,))
    conn.commit(); conn.close()
    try:
        await cb.message.edit_text("✅ Bo'lim o'chirildi!", reply_markup=None)
    except Exception:
        await cb.message.answer("✅ Bo'lim o'chirildi!")
    await cb.answer()

# ── Xizmat qo'shish ───────────────────────────────────────
@dp.callback_query(F.data.startswith("cat_svc_add_"))
async def cat_svc_add(cb: types.CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS: return
    cid  = int(cb.data.replace("cat_svc_add_", ""))
    conn = db(); c = conn.cursor()
    c.execute("SELECT id,name FROM apis")
    apis = c.fetchall(); conn.close()
    if not apis:
        await cb.answer("❌ Avval API qo'shing!", show_alert=True); return
    await state.update_data(new_svc_cat=cid)
    b = InlineKeyboardBuilder()
    for aid, aname in apis:
        b.button(text=f"🔑 {aname}", callback_data=f"svc_api_{aid}", style="primary")
    b.adjust(1)
    try:
        await cb.message.edit_text("🔑 API ni tanlang:", reply_markup=b.as_markup())
    except Exception:
        await cb.message.answer("🔑 API ni tanlang:", reply_markup=b.as_markup())
    await cb.answer()

@dp.callback_query(F.data.startswith("svc_api_"))
async def svc_api_select(cb: types.CallbackQuery, state: FSMContext):
    aid  = int(cb.data.replace("svc_api_", ""))
    await state.update_data(new_svc_api=aid)
    await state.set_state(AS.svc_api_id)
    try:
        await cb.message.edit_text(
            f"🔢 API xizmat ID sini kiriting:\n\n"
            f"💡 Misol: 268, 15, 1024 ...\n"
            f"📋 ID ni bilish uchun API panelidan xizmatlar ro'yhatiga qarang.",
            reply_markup=None
        )
    except Exception:
        await cb.message.answer(
            f"🔢 API xizmat ID sini kiriting:\n\n"
            f"💡 Misol: 268, 15, 1024 ...",
            reply_markup=cancel_kb()
        )
    await cb.answer()

@dp.message(AS.svc_api_id)
async def svc_api_id_h(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear(); await msg.answer("Bekor qilindi", reply_markup=admin_kb()); return
    api_service_id = msg.text.strip()
    data = await state.get_data()
    aid  = data.get("new_svc_api")

    conn = db(); c = conn.cursor()
    c.execute("SELECT url,api_key FROM apis WHERE id=?", (aid,))
    api_row = c.fetchone(); conn.close()

    prefill = {"name": api_service_id, "price": 0.0, "min": 100, "max": 10000}

    if api_row:
        wait_msg = await msg.answer("⏳ API dan ma'lumot olinmoqda...")
        svcs = await api_services(api_row[0], api_row[1])
        try: await wait_msg.delete()
        except: pass
        if isinstance(svcs, list):
            for svc in svcs:
                # ✅ TUZATILGAN: ko'proq field nomlarini tekshiradi
                sid = str(svc.get("service", svc.get("id", svc.get("service_id", ""))))
                if sid == api_service_id:
                    prefill["name"]  = svc.get("name", api_service_id)
                    raw_price = svc.get("rate", svc.get("price", svc.get("cost", 0)))
                    prefill["price"] = float(raw_price) if raw_price else 0.0
                    prefill["min"]   = int(svc.get("min", svc.get("min_order", 100)))
                    prefill["max"]   = int(svc.get("max", svc.get("max_order", 10000)))
                    break

    await state.update_data(new_svc_api_id=api_service_id, prefill=prefill)

    b = InlineKeyboardBuilder()
    b.button(text="✅ Tasdiqlash va saqlash", callback_data="svc_confirm_save", style="success")
    b.button(text="✏️ Nomni o'zgartirish",   callback_data="svc_edit_name", style="primary")
    b.adjust(1)

    await msg.answer(
        f"📋 Xizmat ma'lumotlari:\n\n"
        f"🔢 API ID: {api_service_id}\n"
        f"📌 Nomi: {prefill['name']}\n"
        f"💰 Narx (1000x): {prefill['price']:.2f} {cur()}\n"
        f"⬇️ Minimal: {prefill['min']} ta\n"
        f"⬆️ Maksimal: {prefill['max']} ta\n\n"
        f"Saqlaymizmi?",
        reply_markup=b.as_markup()
    )

@dp.callback_query(F.data == "svc_confirm_save")
async def svc_confirm_save(cb: types.CallbackQuery, state: FSMContext):
    data    = await state.get_data()
    prefill = data.get("prefill", {})
    cat_id  = data["new_svc_cat"]

    conn = db(); c = conn.cursor()
    c.execute("""INSERT INTO services(category_id,api_id,api_service_id,name,min_qty,max_qty,price_per1000)
                 VALUES(?,?,?,?,?,?,?)""",
              (cat_id, data["new_svc_api"], data["new_svc_api_id"],
               prefill.get("name",""), prefill.get("min",100),
               prefill.get("max",10000), prefill.get("price",0)))
    c.execute("SELECT COUNT(*) FROM services WHERE category_id=?", (cat_id,))
    svc_count = c.fetchone()[0]
    c.execute("SELECT name FROM categories WHERE id=?", (cat_id,))
    cat_row = c.fetchone()
    conn.commit(); conn.close()
    cat_name = cat_row[0] if cat_row else "Bo'lim"

    b = InlineKeyboardBuilder()
    b.button(text="➕ Yana xizmat qo'shish", callback_data=f"cat_svc_add_{cat_id}", style="success")
    b.button(text="📋 Xizmatlar ro'yhati",   callback_data=f"cat_svcs_{cat_id}", style="primary")
    b.adjust(2)

    await state.clear()
    try:
        await cb.message.edit_text(
            f"✅ Xizmat saqlandi!\n\n"
            f"📌 {prefill['name']}\n"
            f"💰 {prefill['price']:.2f} {cur()}/1000\n"
            f"📁 {cat_name}  ({svc_count} ta xizmat)",
            reply_markup=b.as_markup()
        )
    except Exception:
        await cb.message.answer(
            f"✅ Xizmat saqlandi!\n\n"
            f"📌 {prefill['name']}\n"
            f"💰 {prefill['price']:.2f} {cur()}/1000\n"
            f"📁 {cat_name}  ({svc_count} ta xizmat)",
            reply_markup=b.as_markup()
        )
    asyncio.create_task(jsonbin_save())
    await cb.answer()

@dp.callback_query(F.data == "svc_edit_name")
async def svc_edit_name(cb: types.CallbackQuery, state: FSMContext):
    await state.set_state(AS.svc_name)
    try:
        await cb.message.edit_text("📌 Yangi nom kiriting:", reply_markup=None)
    except Exception:
        await cb.message.answer("📌 Yangi nom kiriting:", reply_markup=cancel_kb())
    await cb.answer()

@dp.message(AS.svc_name)
async def svc_add_name(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear(); await msg.answer("Bekor qilindi", reply_markup=admin_kb()); return
    data    = await state.get_data()
    prefill = data.get("prefill", {})
    prefill["name"] = msg.text
    await state.update_data(prefill=prefill)

    b = InlineKeyboardBuilder()
    b.button(text="✅ Tasdiqlash va saqlash", callback_data="svc_confirm_save", style="success")
    b.button(text="✏️ Nomni o'zgartirish",   callback_data="svc_edit_name", style="primary")
    b.adjust(1)

    await msg.answer(
        f"📋 Yangilangan ma'lumotlar:\n\n"
        f"📌 Nomi: {prefill['name']}\n"
        f"💰 Narx (1000x): {prefill.get('price',0):.2f} {cur()}\n"
        f"⬇️ Minimal: {prefill.get('min',100)} ta\n"
        f"⬆️ Maksimal: {prefill.get('max',10000)} ta\n\n"
        f"Saqlaymizmi?",
        reply_markup=b.as_markup()
    )

@dp.callback_query(F.data.startswith("cat_svcs_"))
async def cat_svcs(cb: types.CallbackQuery):
    cid  = int(cb.data.replace("cat_svcs_", ""))
    conn = db(); c = conn.cursor()
    c.execute("SELECT id,name,price_per1000,is_active FROM services WHERE category_id=?", (cid,))
    svcs = c.fetchall()
    c.execute("SELECT name FROM categories WHERE id=?", (cid,))
    cat_row = c.fetchone()
    conn.close()
    cat_name = cat_row[0] if cat_row else "Bo'lim"
    if not svcs:
        await cb.answer("❌ Xizmatlar yo'q", show_alert=True); return
    b = InlineKeyboardBuilder()
    for sid, sname, sprice, sact in svcs:
        st = "✅" if sact else "❌"
        b.button(text=f"{st} {sname} — {sprice:.2f} {cur()}", callback_data=f"admin_svc_{sid}", style="primary")
    b.button(text="➕ Xizmat qo'shish", callback_data=f"cat_svc_add_{cid}", style="success")
    b.adjust(1)
    try:
        await cb.message.edit_text(
            f"📋 {cat_name} — xizmatlar ({len(svcs)} ta):",
            reply_markup=b.as_markup()
        )
    except Exception:
        await cb.message.answer(
            f"📋 {cat_name} — xizmatlar ({len(svcs)} ta):",
            reply_markup=b.as_markup()
        )
    await cb.answer()

@dp.message(F.text == "🛠 Barcha xizmatlar")
async def all_svcs(msg: types.Message):
    if msg.from_user.id not in ADMIN_IDS: return
    conn = db(); c = conn.cursor()
    c.execute("""SELECT s.id,s.name,s.price_per1000,s.is_active,cat.name,cat.platform
                 FROM services s LEFT JOIN categories cat ON s.category_id=cat.id
                 ORDER BY cat.platform, cat.name""")
    svcs = c.fetchall(); conn.close()
    if not svcs: await msg.answer("❌ Xizmatlar yo'q"); return
    b = InlineKeyboardBuilder()
    for sid, sname, sprice, sact, cname, cplat in svcs:
        st = "✅" if sact else "❌"
        plat_icon = get_platforms().get(cplat, cplat)
        b.button(text=f"{st} {plat_icon} {sname} — {sprice:.2f} {cur()}", callback_data=f"admin_svc_{sid}", style="primary")
    b.adjust(1)
    await msg.answer(f"📋 Barcha xizmatlar ({len(svcs)} ta):", reply_markup=b.as_markup())

@dp.callback_query(F.data.startswith("admin_svc_"))
async def admin_svc_detail(cb: types.CallbackQuery):
    sid  = int(cb.data.replace("admin_svc_", ""))
    conn = db(); c = conn.cursor()
    c.execute("SELECT * FROM services WHERE id=?", (sid,))
    svc  = c.fetchone(); conn.close()
    if not svc: await cb.answer("❌ Topilmadi"); return
    status = "✅ Faol" if svc[8] else "❌ Nofaol"
    b = InlineKeyboardBuilder()
    b.button(text="❌ O'chirish" if svc[8] else "✅ Faollashtirish", callback_data=f"svc_tog_{sid}", style="danger" if svc[8] else "success")
    b.button(text="🗑 O'chirish", callback_data=f"svc_del_{sid}", style="danger")
    b.adjust(2)
    text = (
        f"🛠 {svc[4]}\n"
        f"Holat: {status}\n"
        f"💰 {svc[7]:.2f} {cur()}/1000\n"
        f"⬇️ Min: {svc[5]} ta  |  ⬆️ Max: {svc[6]} ta\n"
        f"🔢 API Xizmat ID: {svc[3]}"
    )
    try:
        await cb.message.edit_text(text, reply_markup=b.as_markup())
    except Exception:
        await cb.message.answer(text, reply_markup=b.as_markup())
    await cb.answer()

@dp.callback_query(F.data.startswith("svc_tog_"))
async def svc_toggle(cb: types.CallbackQuery):
    sid  = int(cb.data.replace("svc_tog_", ""))
    conn = db(); c = conn.cursor()
    c.execute("SELECT is_active FROM services WHERE id=?", (sid,))
    v    = c.fetchone()[0]
    new_v = 0 if v else 1
    c.execute("UPDATE services SET is_active=? WHERE id=?", (new_v, sid))
    c.execute("SELECT * FROM services WHERE id=?", (sid,))
    svc = c.fetchone()
    conn.commit(); conn.close()
    status = "✅ Faol" if new_v else "❌ Nofaol"
    b = InlineKeyboardBuilder()
    b.button(text="❌ O'chirish" if new_v else "✅ Faollashtirish", callback_data=f"svc_tog_{sid}", style="danger" if new_v else "success")
    b.button(text="🗑 O'chirish", callback_data=f"svc_del_{sid}", style="danger")
    b.adjust(2)
    try:
        await cb.message.edit_text(
            f"🛠 {svc[4]}\nHolat: {status}\n"
            f"💰 {svc[7]:.2f} {cur()}/1000\n"
            f"⬇️ Min: {svc[5]} ta  |  ⬆️ Max: {svc[6]} ta\n"
            f"🔢 API Xizmat ID: {svc[3]}",
            reply_markup=b.as_markup()
        )
    except Exception:
        pass
    await cb.answer("✅ O'zgartirildi!")

@dp.callback_query(F.data.startswith("svc_del_"))
async def svc_del(cb: types.CallbackQuery):
    sid  = int(cb.data.replace("svc_del_", ""))
    conn = db(); c = conn.cursor()
    c.execute("DELETE FROM services WHERE id=?", (sid,))
    conn.commit(); conn.close()
    try:
        await cb.message.edit_text("✅ Xizmat o'chirildi!", reply_markup=None)
    except Exception:
        await cb.message.answer("✅ Xizmat o'chirildi!")
    await cb.answer()

# ═══════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════
async def main():
    init_db()
    logger.info("✅ JSONBin dan ma'lumotlar tiklanmoqda...")
    await jsonbin_restore()
    logger.info("✅ SMM Bot ishga tushdi!")
    asyncio.create_task(jsonbin_autosave_loop())
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
