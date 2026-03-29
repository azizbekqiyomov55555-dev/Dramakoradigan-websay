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

class CompressState(StatesGroup):
    waiting_for_size = State()

def get_video_duration(file_path):
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", file_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        return float(result.stdout.strip())
    except:
        return 0

def compress_video(input_path, output_path, target_size_mb):
    duration = get_video_duration(input_path)
    if duration == 0: return False
    
    # Bitreyt hisobi
    target_total_bitrate = (target_size_mb * 8192) / duration
    video_bitrate = max(target_total_bitrate - 128, 50) 
    
    # "ultrafast" presetini qo'shdik (Railway tezroq ishlashi uchun)
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-b:v", f"{int(video_bitrate)}k",
        "-vcodec", "libx264",
        "-preset", "ultrafast", 
        "-acodec", "aac",
        "-b:a", "128k",
        output_path
    ]
    subprocess.run(cmd)
    return True

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    await message.answer("Salom! 🎬 Menga video yuboring (Max: 20MB).\n\n⚠️ Eslatma: Telegram botlar faqat 20MB gacha bo'lgan videolarni yuklab ola oladi!")

@dp.message_handler(content_types=['video'])
async def handle_video(message: types.Message, state: FSMContext):
    # Fayl hajmini tekshirish (Telegram API limiti 20MB)
    file_size_mb = message.video.file_size / (1024 * 1024)
    
    if file_size_mb > 20:
        await message.answer(f"❌ Video juda katta ({round(file_size_mb, 2)} MB).\nTelegram botlar faqat 20 MB gacha bo'lgan videolarni qabul qila oladi. Iltimos, kichikroq video yuboring.")
        return

    msg = await message.answer("📥 Video qabul qilindi. Yuklanmoqda...")
    
    input_path = f"in_{message.chat.id}.mp4"
    try:
        await message.video.download(destination_file=input_path)
        await state.update_data(video_path=input_path)
        await CompressState.waiting_for_size.set()
        await msg.edit_text(f"✅ Yuklandi ({round(file_size_mb, 2)} MB).\n\nBu video necha MB bo'lsin? (Masalan: 5 yoki 10)")
    except Exception as e:
        await msg.edit_text(f"❌ Yuklashda xatolik: {e}")

@dp.message_handler(state=CompressState.waiting_for_size)
async def process_size(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Faqat raqam yozing!")
        return

    target_mb = int(message.text)
    data = await state.get_data()
    input_path = data.get('video_path')
    output_path = f"out_{message.chat.id}.mp4"
    
    status = await message.answer("⏳ Siqilmoqda (bu Railway'da 1-2 daqiqa olishi mumkin)...")
    
    try:
        loop = asyncio.get_event_loop()
        success = await loop.run_in_executor(None, compress_video, input_path, output_path, target_mb)
        
        if success and os.path.exists(output_path):
            await status.edit_text("📤 Yuborilmoqda...")
            with open(output_path, 'rb') as v:
                await bot.send_video(message.chat.id, v, caption=f"✅ {target_mb} MB formatga siqildi.")
        else:
            await status.edit_text("❌ Siqib bo'lmadi.")
            
    except Exception as e:
        await status.edit_text(f"❌ Xato: {e}")
    
    # Tozalash
    if os.path.exists(input_path): os.remove(input_path)
    if os.path.exists(output_path): os.remove(output_path)
    await state.finish()

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
