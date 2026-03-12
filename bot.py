import asyncio
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram_calendar import SimpleCalendar, SimpleCalendarCallback
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# --- НАСТРОЙКИ ---
TOKEN = "8621526806:AAGG_YqAXFiZyLVvu3QehjqJv0hjevBYsC0"
logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler(timezone="Europe/Moscow")

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
    await bot.send_message(chat_id, f"🔔 **НАПОМИНАНИЕ!**\n\n{text}")

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("📝 Напиши текст напоминания:")
    await state.set_state(Reminder.waiting_for_text)

@dp.message(Reminder.waiting_for_text)
async def process_text(message: types.Message, state: FSMContext):
    await state.update_data(reminder_text=message.text)
    await state.set_state(Reminder.waiting_for_date)
    await message.answer("📅 Выбери дату события:", reply_markup=await SimpleCalendar().start_calendar())

@dp.callback_query(SimpleCalendarCallback.filter(), Reminder.waiting_for_date)
async def process_date(callback: types.CallbackQuery, callback_data: SimpleCalendarCallback, state: FSMContext):
    selected, date = await SimpleCalendar().process_selection(callback, callback_data)
    if selected:
        await state.update_data(selected_date=date.strftime("%Y-%m-%d"))
        await state.set_state(Reminder.waiting_for_hour)
        await callback.message.edit_text(
            f"📅 Дата: {date.strftime('%d.%m.%Y')}\n🕒 Выбери час:", 
            reply_markup=get_time_keyboard(range(24), "hour")
        )

@dp.callback_query(F.data.startswith("hour_"), Reminder.waiting_for_hour)
async def process_hour(callback: types.CallbackQuery, state: FSMContext):
    hour_val = callback.data.split("_")[1]
    await state.update_data(selected_hour=hour_val)
    await state.set_state(Reminder.waiting_for_minute)
    # Исправлено: добавлены минуты в список
    minutes = [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55]
    await callback.message.edit_text("⏱ Выбери минуты:", reply_markup=get_time_keyboard(minutes, "min"))

@dp.callback_query(F.data.startswith("min_"), Reminder.waiting_for_minute)
async def process_minute(callback: types.CallbackQuery, state: FSMContext):
    minute_val = callback.data.split("_")[1]
    user_data = await state.get_data()
    
    full_date_str = f"{user_data['selected_date']} {user_data['selected_hour']}:{minute_val}"
    remind_at = datetime.strptime(full_date_str, "%Y-%m-%d %H:%M")

    if remind_at <= datetime.now():
        await callback.answer("❌ Время уже в прошлом!", show_alert=True)
        return

    scheduler.add_job(
        send_notification,
        'date',
        run_date=remind_at,
        args=[callback.message.chat.id, user_data['reminder_text']]
    )

    await callback.message.edit_text(f"✅ Готово! Напомню {remind_at.strftime('%d.%m.%Y %H:%M')}")
    await state.clear()

async def main():
    if not scheduler.running:
        scheduler.start()
    await bot.delete_webhook(drop_pending_updates=True)
    print("🚀 Бот успешно запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("\n🛑 Бот остановлен.")


