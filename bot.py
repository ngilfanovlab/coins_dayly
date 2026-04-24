import logging
import os
import json
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

import gspread
from google.oauth2.service_account import Credentials

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── Настройки ───────────────────────────────────────────────
BOT_TOKEN = os.environ.get("BOT_TOKEN")
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID")
GOOGLE_CREDS_JSON = os.environ.get("GOOGLE_CREDS_JSON")

# ─── Категории ───────────────────────────────────────────────
CATEGORIES = {
    "🏠 Жильё": ["Аренда", "Коммунальные", "Интернет", "Мебель/быт"],
    "🍔 Еда": ["Продукты", "Рестораны", "Кафе/кофе", "Доставка"],
    "🚕 Транспорт": ["Такси", "Метро/автобус", "Парковка"],
    "🧗 Спорт": ["Боулдер-зал", "Снаряжение", "Другой спорт"],
    "💊 Здоровье": ["Аптека", "Врач", "Страховка"],
    "👕 Одежда": ["Одежда", "Обувь", "Аксессуары"],
    "💳 Долги": ["Кредит ТБанк", "Кредитка", "Долг 2000 QAR", "Перевод в РФ"],
    "📈 Инвестиции": ["Акции", "Крипто", "Другое"],
    "🎬 Развлечения": ["Кино/культура", "Подписки", "Путешествия", "Хобби"],
    "📷 Фото/работа": ["Оборудование", "ПО", "Обучение", "Реклама"],
    "📱 Связь": ["Телефон", "Приложения", "Облако"],
    "❓ Другое": ["Разное", "Подарки"],
}

CURRENCIES = ["QAR", "USD", "RUB"]

# ─── Состояния диалога ───────────────────────────────────────
AMOUNT, CURRENCY, CATEGORY, SUBCATEGORY, NOTE = range(5)

# ─── Google Sheets ───────────────────────────────────────────
def get_sheet():
    creds_info = json.loads(GOOGLE_CREDS_JSON)
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SPREADSHEET_ID).sheet1
    # Создаём заголовки если таблица пустая
    if sheet.row_count == 0 or not sheet.row_values(1):
        sheet.append_row(["Дата", "Сумма", "Валюта", "Категория", "Подкатегория", "Комментарий"])
    return sheet

def add_row(date, amount, currency, category, subcategory, note):
    sheet = get_sheet()
    # Заголовки если нужно
    if not sheet.row_values(1):
        sheet.append_row(["Дата", "Сумма", "Валюта", "Категория", "Подкатегория", "Комментарий"])
    sheet.append_row([date, amount, currency, category, subcategory, note])

def get_stats():
    sheet = get_sheet()
    rows = sheet.get_all_records()
    if not rows:
        return None
    now = datetime.now()
    month_rows = [r for r in rows if str(r.get("Дата","")).startswith(now.strftime("%Y-%m"))]
    
    # Курсы к QAR
    rates = {"QAR": 1, "USD": 3.64, "RUB": 0.039}
    
    total_month = sum(float(r["Сумма"]) * rates.get(r["Валюта"], 1) for r in month_rows)
    total_all = sum(float(r["Сумма"]) * rates.get(r["Валюта"], 1) for r in rows)
    
    cat_totals = {}
    for r in month_rows:
        cat = r["Категория"]
        cat_totals[cat] = cat_totals.get(cat, 0) + float(r["Сумма"]) * rates.get(r["Валюта"], 1)
    
    top_cats = sorted(cat_totals.items(), key=lambda x: x[1], reverse=True)[:5]
    return {
        "month": round(total_month, 2),
        "total": round(total_all, 2),
        "count": len(rows),
        "month_count": len(month_rows),
        "top": top_cats,
    }

# ─── Хендлеры ────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[KeyboardButton("➕ Добавить расход")], [KeyboardButton("📊 Статистика"), KeyboardButton("❌ Отмена")]]
    await update.message.reply_text(
        "Привет! Я трекер расходов.\n\nНажми *➕ Добавить расход* чтобы записать трату.",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True),
        parse_mode="Markdown"
    )

async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("💰 Введи сумму (только цифры, например: 45 или 12.5):")
    return AMOUNT

async def get_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.replace(",", ".").strip()
    try:
        amount = float(text)
        if amount <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Введи корректную сумму, например: 45 или 12.5")
        return AMOUNT
    context.user_data["amount"] = amount
    kb = [[KeyboardButton(c)] for c in CURRENCIES]
    await update.message.reply_text("💱 Выбери валюту:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True, one_time_keyboard=True))
    return CURRENCY

async def get_currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cur = update.message.text.strip()
    if cur not in CURRENCIES:
        await update.message.reply_text("Выбери из кнопок: QAR, USD или RUB")
        return CURRENCY
    context.user_data["currency"] = cur
    kb = [[KeyboardButton(cat)] for cat in CATEGORIES.keys()]
    await update.message.reply_text("📂 Выбери категорию:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True, one_time_keyboard=True))
    return CATEGORY

async def get_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cat = update.message.text.strip()
    if cat not in CATEGORIES:
        await update.message.reply_text("Выбери категорию из списка")
        return CATEGORY
    context.user_data["category"] = cat
    subs = CATEGORIES[cat]
    kb = [[KeyboardButton(s)] for s in subs]
    await update.message.reply_text("📌 Выбери подкатегорию:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True, one_time_keyboard=True))
    return SUBCATEGORY

async def get_subcategory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sub = update.message.text.strip()
    context.user_data["subcategory"] = sub
    kb = [[KeyboardButton("Пропустить")]]
    await update.message.reply_text("📝 Добавь комментарий (или нажми Пропустить):", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True, one_time_keyboard=True))
    return NOTE

async def get_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    note = update.message.text.strip()
    if note == "Пропустить":
        note = ""
    
    date = datetime.now().strftime("%Y-%m-%d")
    d = context.user_data
    
    try:
        add_row(date, d["amount"], d["currency"], d["category"], d["subcategory"], note)
        await update.message.reply_text(
            f"✅ Записано!\n\n"
            f"📅 {date}\n"
            f"💰 {d['amount']} {d['currency']}\n"
            f"📂 {d['category']} → {d['subcategory']}\n"
            f"{'📝 '+note if note else ''}",
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton("➕ Добавить расход")], [KeyboardButton("📊 Статистика")]], resize_keyboard=True)
        )
    except Exception as e:
        logger.error(f"Ошибка записи: {e}")
        await update.message.reply_text("❌ Ошибка записи в таблицу. Попробуй ещё раз.")
    
    return ConversationHandler.END

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Загружаю статистику...")
    try:
        s = get_stats()
        if not s:
            await update.message.reply_text("Пока нет записей. Добавь первый расход!")
            return
        
        top_text = "\n".join([f"  {cat}: {round(amt)} QAR" for cat, amt in s["top"]])
        await update.message.reply_text(
            f"📊 *Статистика*\n\n"
            f"За этот месяц: *{s['month']} QAR* ({s['month_count']} записей)\n"
            f"За всё время: *{s['total']} QAR* ({s['count']} записей)\n\n"
            f"🏆 Топ категорий (месяц):\n{top_text}",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Ошибка статистики: {e}")
        await update.message.reply_text("❌ Ошибка загрузки. Попробуй позже.")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    kb = [[KeyboardButton("➕ Добавить расход")], [KeyboardButton("📊 Статистика")]]
    await update.message.reply_text("Отменено.", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
    return ConversationHandler.END

# ─── Запуск ──────────────────────────────────────────────────
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^➕ Добавить расход$"), add_start)],
        states={
            AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_amount)],
            CURRENCY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_currency)],
            CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_category)],
            SUBCATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_subcategory)],
            NOTE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_note)],
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ Отмена$"), cancel), CommandHandler("cancel", cancel)],
    )
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Regex("^📊 Статистика$"), stats))
    app.add_handler(conv)
    
    logger.info("Бот запущен")
    app.run_polling()

if __name__ == "__main__":
    main()
