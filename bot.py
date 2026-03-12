import asyncio
import logging
from datetime import datetime
import pytz

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram_calendar import SimpleCalendar, SimpleCalendarCallback
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# --- НАСТРОЙКИ ---
TOKEN = "8621526806:AAGG_YqAXFiZyLVvu3QehjqJv0hjevBYsC0"
MOSCOW_TZ = pytz.timezone("Europe/Moscow")

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler(timezone=MOSCOW_TZ)

class Reminder(StatesGroup):
    waiting_for_text = State()
    waiting_for_date = State()
    waiting_for_hour = State()
    waiting_for_minute = State()

def get_time_keyboard(items, prefix):
    builder = InlineKeyboardBuilder()
    for item in items:
        builder.button(text=f"{item:02d}", callback_data=f"{prefix}_{item}")
    builder.adjust(4)
    return builder.as_markup()

async def send_notification(chat_id, text):
    logging.info(f"!!! ПОПЫТКА ОТПРАВКИ: {chat_id}")
    try:
        await bot.send_message(chat_id, f"🔔 **НАПОМИНАНИЕ!**\n\n{text}")
        logging.info(f"УСПЕШНО ОТПРАВЛЕНО: {chat_id}")
    except Exception as e:
        logging.error(f"ОШИБКА ПРИ ОТПРАВКЕ: {e}")

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("📝 О чем напомнить?")
    await state.set_state(Reminder.waiting_for_text)

@dp.message(Reminder.waiting_for_text)
async def process_text(message: types.Message, state: FSMContext):
    await state.update_data(reminder_text=message.text)
    await state.set_state(Reminder.waiting_for_date)
    await message.answer("📅 Выбери дату:", reply_markup=await SimpleCalendar().start_calendar())

@dp.callback_query(SimpleCalendarCallback.filter(), Reminder.waiting_for_date)
async def process_date(callback: types.CallbackQuery, callback_data: SimpleCalendarCallback, state: FSMContext):
    selected, date = await SimpleCalendar().process_selection(callback, callback_data)
    if selected:
        await state.update_data(selected_date=date.strftime("%Y-%m-%d"))
        await state.set_state(Reminder.waiting_for_hour)
        await callback.message.edit_text(f"🕒 Час (МСК):", reply_markup=get_time_keyboard(range(24), "hour"))

@dp.callback_query(F.data.startswith("hour_"), Reminder.waiting_for_hour)
async def process_hour(callback: types.CallbackQuery, state: FSMContext):
    h = callback.data.split("_")[1]
    await state.update_data(selected_hour=h)
    await state.set_state(Reminder.waiting_for_minute)
    minutes = [0, 10, 20, 30, 40, 50]
    await callback.message.edit_text("⏱ Минуты:", reply_markup=get_time_keyboard(minutes, "min"))

@dp.callback_query(F.data.startswith("min_"), Reminder.waiting_for_minute)
async def process_minute(callback: types.CallbackQuery, state: FSMContext):
    m = callback.data.split("_")[1]
    user_data = await state.get_data()
    dt_str = f"{user_data['selected_date']} {user_data['selected_hour']}:{m}"
    
    naive_dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
    remind_at = MOSCOW_TZ.localize(naive_dt)

    if remind_at <= datetime.now(MOSCOW_TZ):
        return await callback.answer("❌ Время в прошлом!", show_alert=True)

    # Добавляем задачу
    scheduler.add_job(
        send_notification,
        'date',
        run_date=remind_at,
        args=[callback.message.chat.id, user_data['reminder_text']]
    )
    
    logging.info(f"--- ЗАПЛАНИРОВАНО НА {remind_at} ---")
    await callback.message.edit_text(f"✅ Напомню в {remind_at.strftime('%H:%M')}!")
    await state.clear()

async def main():
    # Запускаем планировщик
    scheduler.start()
    
    # Сброс вебхуков
    await bot.delete_webhook(drop_pending_updates=True)
    
    logging.info("🚀 ФИНАЛЬНАЯ ВЕРСИЯ ЗАПУЩЕНА")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())









