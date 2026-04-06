import os
from pyrogram import Client, filters
from pyrogram.enums import ParseMode, ButtonStyle
from pyrogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
)

API_ID    = 37366974
API_HASH  = "08d09c7ed8b7cb414ed6a99c104f1bd6"
BOT_TOKEN = "8766213463:AAGtuC1RWpd-QCCb6oLMOjYDH553Pbam8V0"

app = Client("bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)


# ─────────────────────────────────────────────
#  ASOSIY MENYU KLAVIATURASI
# ─────────────────────────────────────────────

def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton("🛒 Buyurtma berish",     style=ButtonStyle.SUCCESS)],
            [
                KeyboardButton("📦 Buyurtmalar",       style=ButtonStyle.PRIMARY),
                KeyboardButton("👤 Hisobim",            style=ButtonStyle.PRIMARY),
            ],
            [
                KeyboardButton("💰 Pul ishlash",       style=ButtonStyle.SUCCESS),
                KeyboardButton("💳 Hisob to'ldirish",  style=ButtonStyle.DANGER),
            ],
            [
                KeyboardButton("📩 Murojaat",          style=ButtonStyle.PRIMARY),
                KeyboardButton("📖 Qo'llanma",         style=ButtonStyle.SUCCESS),
            ],
            [KeyboardButton("🖥 Boshqaruv",            style=ButtonStyle.DANGER)],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


# ─────────────────────────────────────────────
#  /start HANDLER
# ─────────────────────────────────────────────

@app.on_message(filters.command("start") & filters.private)
async def cmd_start(client, message):
    name = message.from_user.first_name or "Do'stim"
    await message.reply(
        f"👋 Xush kelibsiz, **{name}**!\n\n"
        "⬇️ Asosiy menyudasiz!\n"
        "Kerakli bo'limni tanlang:",
        reply_markup=main_keyboard(),
    )


# ─────────────────────────────────────────────
#  TUGMA HANDLERLARI
# ─────────────────────────────────────────────

@app.on_message(filters.regex("🛒 Buyurtma berish") & filters.private)
async def h_order(client, message):
    await message.reply(
        "🛒 **Buyurtma berish**\n\nMahsulot yoki xizmatni tanlang:",
        parse_mode=ParseMode.MARKDOWN,
    )


@app.on_message(filters.regex("📦 Buyurtmalar") & filters.private)
async def h_orders(client, message):
    await message.reply(
        "📦 **Buyurtmalaringiz ro'yxati:**\n\n_(Hozircha buyurtma yo'q)_",
        parse_mode=ParseMode.MARKDOWN,
    )


@app.on_message(filters.regex("👤 Hisobim") & filters.private)
async def h_account(client, message):
    uid = message.from_user.id
    await message.reply(
        f"👤 **Hisobingiz:**\n\n🆔 ID: `{uid}`\n💰 Balans: `0 So'm`",
        parse_mode=ParseMode.MARKDOWN,
    )


@app.on_message(filters.regex("💰 Pul ishlash") & filters.private)
async def h_earn(client, message):
    await message.reply(
        "💰 **Pul ishlash:**\n\nReferal havolangizni do'stlaringizga yuboring!",
        parse_mode=ParseMode.MARKDOWN,
    )


@app.on_message(filters.regex("💳 Hisob to'ldirish") & filters.private)
async def h_deposit(client, message):
    await message.reply(
        "💳 **Hisob to'ldirish:**\n\nSumma kiriting (So'mda):",
        parse_mode=ParseMode.MARKDOWN,
    )


@app.on_message(filters.regex("📩 Murojaat") & filters.private)
async def h_support(client, message):
    await message.reply(
        "📩 **Murojaat:**\n\nSavolingizni yuboring, tez orada javob beramiz.",
        parse_mode=ParseMode.MARKDOWN,
    )


@app.on_message(filters.regex("📖 Qo'llanma") & filters.private)
async def h_guide(client, message):
    await message.reply(
        "📖 **Qo'llanma:**\n\n"
        "1. Ro'yxatdan o'ting\n"
        "2. Hisob to'ldiring\n"
        "3. Buyurtma bering\n"
        "4. Natijani kuting",
        parse_mode=ParseMode.MARKDOWN,
    )


@app.on_message(filters.regex("🖥 Boshqaruv") & filters.private)
async def h_admin(client, message):
    ADMIN_IDS = [123456789]  # ← o'z admin ID'ingizni yozing
    if message.from_user.id not in ADMIN_IDS:
        await message.reply("⛔ Ruxsat yo'q.")
        return
    await message.reply(
        "🖥 **Admin panel:**\n\n"
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
