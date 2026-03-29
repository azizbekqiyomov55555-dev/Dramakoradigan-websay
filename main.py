import os
import logging
import asyncio
import subprocess
from aiogram import Bot, Dispatcher, executor, types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage

# BOT TOKEN
API_TOKEN = '8766647589:AAHmY6x59GgKA25K3e737-7jomufi9wRv2Y'

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Holatlarni boshqarish
class CompressState(StatesGroup):
    waiting_for_size = State()

# Video davomiyligini aniqlash funksiyasi
def get_video_duration(file_path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", file_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT
    )
    return float(result.stdout)

# Videoni siqish funksiyasi
def compress_video(input_path, output_path, target_size_mb):
    duration = get_video_duration(input_path)
    # Bitreytni hisoblash: (Hajm * 8192) / vaqt (sekundda)
    # 8192 = 1024 * 8 (megabaytdan kilobitga o'tkazish)
    target_total_bitrate = (target_size_mb * 8192) / duration
    
    # Audio uchun 128k ajratamiz, qolgani video uchun
    video_bitrate = max(target_total_bitrate - 128, 10) # Kamida 10k bo'lsin
    
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-b:v", f"{video_bitrate}k",
        "-vcodec", "libx264",
        "-preset", "medium",
        "-acodec", "aac",
        "-b:a", "128k",
        output_path
    ]
    subprocess.run(cmd)

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    await message.answer("Salom! 🎬 Menga video yuboring, men uni siz xohlagan hajmgacha siqib beraman.")

@dp.message_handler(content_types=['video'])
async def handle_video(message: types.Message, state: FSMContext):
    msg = await message.answer("📥 Video qabul qilindi. Uni yuklab olyapman...")
    
    file_id = message.video.file_id
    input_path = f"video_{message.chat.id}.mp4"
    
    # Videoni serverga yuklab olish
    await bot.download_file_by_id(file_id, input_path)
    
    await state.update_data(video_path=input_path)
    await CompressState.waiting_for_size.set()
    
    await msg.edit_text("✅ Video yuklandi.\n\nBu video necha Megabayt (MB) bo'lsin? (Faqat raqam yozing, masalan: 15)")

@dp.message_handler(state=CompressState.waiting_for_size)
async def process_size(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Iltimos, faqat raqam yozing (masalan: 10, 15, 20).")
        return

    target_mb = int(message.text)
    user_data = await state.get_data()
    input_path = user_data['video_path']
    output_path = f"compressed_{message.chat.id}.mp4"
    
    status_msg = await message.answer(f"⏳ Video {target_mb} MB gacha siqilmoqda. Bu biroz vaqt olishi mumkin...")
    
    try:
        # Videoni siqish (bloklamaslik uchun loopda ishlatamiz)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, compress_video, input_path, output_path, target_mb)
        
        await status_msg.edit_text("📤 Tayyor! Telegramga yuborilmoqda...")
        
        with open(output_path, 'rb') as video:
            await bot.send_video(message.chat.id, video, caption=f"✅ Video {target_mb} MB gacha siqildi.")
            
        # Fayllarni tozalash
        os.remove(input_path)
        os.remove(output_path)
        await status_msg.delete()
        await state.finish()

    except Exception as e:
        logging.error(e)
        await status_msg.edit_text("❌ Xatolik yuz berdi. Video juda qisqa yoki hajm juda kichik tanlangan bo'lishi mumkin.")
        if os.path.exists(input_path): os.remove(input_path)
        if os.path.exists(output_path): os.remove(output_path)
        await state.finish()

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
