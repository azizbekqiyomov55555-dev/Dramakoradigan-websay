import os
import asyncio
from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.raw import types as raw_types, functions as raw_funcs

API_ID    = 37366974
API_HASH  = "08d09c7ed8b7cb414ed6a99c104f1bd6"
BOT_TOKEN = "8766213463:AAGtuC1RWpd-QCCb6oLMOjYDH553Pbam8V0"

app = Client("bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ─────────────────────────────────────────────
#  RANGLI TUGMA YASOVCHI
#  color: 0=kulrang, 1=qizil, 2=to'q sariq, 3=binafsha, 4=yashil, 5=ko'k
# ─────────────────────────────────────────────

def btn(text: str, color: int = 0) -> raw_types.KeyboardButton:
    """
    Rangli reply-keyboard tugma.
    color qiymatlari:
      0 = default (kulrang/oq)
      1 = qizil   (🔴)
      2 = to'q sariq / orange
      3 = binafsha / violet
      4 = yashil  (🟢)
      5 = ko'k    (🔵)
    """
    # Telegram MTProto da rang "color" field orqali uzatiladi
    # pyrogram raw types orqali to'g'ridan-to'g'ri yuborilamiz
    b = raw_types.KeyboardButton(text=text)
    b.color = color          # Raw field — Telegram app ko'radi
    return b


def row(*buttons) -> raw_types.KeyboardButtonRow:
    return raw_types.KeyboardButtonRow(buttons=list(buttons))


# ─────────────────────────────────────────────
#  ASOSIY MENYU KLAVIATURASI
#  (rasmga o'xshash — yashil, ko'k, qizil)
# ─────────────────────────────────────────────

def main_keyboard() -> raw_types.ReplyKeyboardMarkup:
    return raw_types.ReplyKeyboardMarkup(
        rows=[
            row(btn("🛒 Buyurtma berish",      color=4)),   # yashil
            row(btn("📦 Buyurtmalar",           color=5),
                btn("👤 Hisobim",               color=5)),   # ko'k ko'k
            row(btn("💰 Pul ishlash",           color=4),
                btn("💳 Hisob to'ldirish",      color=1)),   # yashil, qizil
            row(btn("📩 Murojaat",              color=5),
                btn("📖 Qo'llanma",             color=4)),   # ko'k, yashil
            row(btn("🖥 Boshqaruv",             color=1)),   # qizil (admin)
        ],
        resize=True,
        persistent=True,        # Har doim ko'rinib tursin
    )


# ─────────────────────────────────────────────
#  RAW API ORQALI XABAR YUBORISH
# ─────────────────────────────────────────────

async def send_with_colored_kb(client: Client, chat_id: int, text: str):
    """
    Rangli klaviatura bilan xabar yuborish.
    Pyrogram standart send_message color ni qo'llab-quvvatlamaydi,
    shuning uchun raw invoke ishlatiladi.
    """
    peer = await client.resolve_peer(chat_id)

    await client.invoke(
        raw_funcs.messages.SendMessage(
            peer=peer,
            message=text,
            random_id=client.rnd_id(),
            reply_markup=main_keyboard(),
            no_webpage=True,
        )
    )


async def edit_with_colored_kb(client: Client, chat_id: int,
                                 message_id: int, text: str):
    """Mavjud xabarni tahrirlash + rangli klaviatura"""
    peer = await client.resolve_peer(chat_id)

    await client.invoke(
        raw_funcs.messages.EditMessage(
            peer=peer,
            id=message_id,
            message=text,
            reply_markup=main_keyboard(),
            no_webpage=True,
        )
    )


# ─────────────────────────────────────────────
#  /start HANDLER
# ─────────────────────────────────────────────

@app.on_message(filters.command("start") & filters.private)
async def cmd_start(client, message):
    uid  = message.from_user.id
    name = message.from_user.first_name or "Do'stim"

    await send_with_colored_kb(
        client, uid,
        f"👋 Xush kelibsiz, *{name}*!\n\n"
        "⬇️ Asosiy menyudasiz!\n"
        "Kerakli bo'limni tanlang:"
    )


# ─────────────────────────────────────────────
#  TUGMA HANDLERLARI
# ─────────────────────────────────────────────

@app.on_message(filters.regex("🛒 Buyurtma berish") & filters.private)
async def h_order(client, message):
    await message.reply_text(
        "🛒 *Buyurtma berish*\n\nMahsulot yoki xizmatni tanlang:",
        parse_mode=ParseMode.MARKDOWN,
    )

@app.on_message(filters.regex("📦 Buyurtmalar") & filters.private)
async def h_orders(client, message):
    await message.reply_text(
        "📦 *Buyurtmalaringiz ro'yxati:*\n\n_(Hozircha buyurtma yo'q)_",
        parse_mode=ParseMode.MARKDOWN,
    )

@app.on_message(filters.regex("👤 Hisobim") & filters.private)
async def h_account(client, message):
    uid = message.from_user.id
    await message.reply_text(
        f"👤 *Hisobingiz:*\n\n🆔 ID: `{uid}`\n💰 Balans: `0 So'm`",
        parse_mode=ParseMode.MARKDOWN,
    )

@app.on_message(filters.regex("💰 Pul ishlash") & filters.private)
async def h_earn(client, message):
    await message.reply_text(
        "💰 *Pul ishlash:*\n\nReferal havolangizni do'stlaringizga yuboring!",
        parse_mode=ParseMode.MARKDOWN,
    )

@app.on_message(filters.regex("💳 Hisob to'ldirish") & filters.private)
async def h_deposit(client, message):
    await message.reply_text(
        "💳 *Hisob to'ldirish:*\n\nSumma kiriting (So'mda):",
        parse_mode=ParseMode.MARKDOWN,
    )

@app.on_message(filters.regex("📩 Murojaat") & filters.private)
async def h_support(client, message):
    await message.reply_text(
        "📩 *Murojaat:*\n\nSavolingizni yuboring, tez orada javob beramiz.",
        parse_mode=ParseMode.MARKDOWN,
    )

@app.on_message(filters.regex("📖 Qo'llanma") & filters.private)
async def h_guide(client, message):
    await message.reply_text(
        "📖 *Qo'llanma:*\n\n"
        "1. Ro'yxatdan o'ting\n"
        "2. Hisob to'ldiring\n"
        "3. Buyurtma bering\n"
        "4. Natijani kuting",
        parse_mode=ParseMode.MARKDOWN,
    )

@app.on_message(filters.regex("🖥 Boshqaruv") & filters.private)
async def h_admin(client, message):
    # Admin tekshiruvi
    ADMIN_IDS = [123456789]   # ← o'z admin ID'ingizni yozing
    if message.from_user.id not in ADMIN_IDS:
        await message.reply_text("⛔ Ruxsat yo'q.")
        return
    await message.reply_text(
        "🖥 *Admin panel:*\n\n"
        "• /stats — statistika\n"
        "• /broadcast — xabar yuborish\n"
        "• /users — foydalanuvchilar",
        parse_mode=ParseMode.MARKDOWN,
    )


# ─────────────────────────────────────────────
#  ISHGA TUSHIRISH
# ─────────────────────────────────────────────

if __name__ == "__main__":
    os.makedirs("downloads", exist_ok=True)
    print("🤖 Bot ishga tushdi (rangli tugmalar bilan)!")
    app.run()
