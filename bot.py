import logging
import os
import json
import re
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes, ConversationHandler

import gspread
from google.oauth2.service_account import Credentials

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID")
GOOGLE_CREDS_JSON = os.environ.get("GOOGLE_CREDS_JSON")

CATEGORIES = {
    "🏠 Жильё": [
        "Аренда квартиры", "Уют", "Быт", "Уборка / клининг", "Ремонт",
    ],
    "🍽 Еда": [
        "Продукты (супермаркет)", "Ресторан / кафе", "Кофе / снеки", "Доставка еды", "Алкоголь",
    ],
    "🚕 Транспорт": [
        "Такси", "Аренда авто", "Бензин", "Парковка", "Общественный транспорт", "Ремонт авто", "Страховка авто",
    ],
    "🧗 Спорт": [
        "Скалолазание", "Снаряжение для скалолазания", "Бассейн", "Теннис", "Другой спорт",
    ],
    "💊 Здоровье": [
        "Аптека/косметика", "Врач / клиника", "Анализы / обследования", "Страховка медицинская", "Витамины / БАД",
    ],
    "📱 Подписки": [
        "Видео стриминг", "Музыка", "AI инструменты", "iCloud / Google One", "Мобильная связь", "Другая подписка",
    ],
    "👕 Одежда и уход": [
        "Одежда", "Обувь", "Аксессуары", "Барбер / салон", "Химчистка",
    ],
    "💳 Долги и переводы": [
        "Кредит ТБанк (обяз.)", "Кредит ТБанк (доп.)", "Кредитка погашение", "Долг 2000 QAR", "Перевод в Россию", "Крипто-комиссии",
    ],
    "📈 Инвестиции": [
        "Акции (eToro)", "Крипто", "Накопления (отложил)", "Другое",
    ],
    "🎬 Развлечения": [
        "Кино / театр / выставка", "Путешествия (билеты)", "Отель / жильё в поездке", "Хобби", "Игры",
    ],
    "📷 Фото / фриланс": [
        "Аренда техники", "Аренда студии / реквизит", "ПО и подписки", "Покупка техники", "Обучение / курсы", "Реклама и продвижение", "Прочие расходы",
    ],
    "✈️ Путешествия": [
        "Виза / разрешение", "Жилье", "Аренда машины", "Бензин", "Кафе/рестики", "Продукты/Перекусы", "Билеты", "Связь-путешествие", "Другое",
    ],
    "🎁 Другое": [
        "Подарки", "Благотворительность", "Штрафы", "Разное",
    ],
}

# ─── Словарь ключевых слов ────────────────────────────────────
KEYWORDS = {
    # Еда
    "продукт": ("🍽 Еда", "Продукты (супермаркет)"),
    "супермаркет": ("🍽 Еда", "Продукты (супермаркет)"),
    "ресторан": ("🍽 Еда", "Ресторан / кафе"),
    "кафе": ("🍽 Еда", "Ресторан / кафе"),
    "кофе": ("🍽 Еда", "Кофе / снеки"),
    "снек": ("🍽 Еда", "Кофе / снеки"),
    "доставка": ("🍽 Еда", "Доставка еды"),
    "алкоголь": ("🍽 Еда", "Алкоголь"),
    "пиво": ("🍽 Еда", "Алкоголь"),
    "вино": ("🍽 Еда", "Алкоголь"),
    "еда": ("🍽 Еда", "Продукты (супермаркет)"),
    "обед": ("🍽 Еда", "Ресторан / кафе"),
    "ужин": ("🍽 Еда", "Ресторан / кафе"),
    "завтрак": ("🍽 Еда", "Кофе / снеки"),
    "перекус": ("🍽 Еда", "Кофе / снеки"),
    # Транспорт
    "такси": ("🚕 Транспорт", "Такси"),
    "uber": ("🚕 Транспорт", "Такси"),
    "карва": ("🚕 Транспорт", "Такси"),
    "karwa": ("🚕 Транспорт", "Такси"),
    "бензин": ("🚕 Транспорт", "Бензин"),
    "заправк": ("🚕 Транспорт", "Бензин"),
    "парковк": ("🚕 Транспорт", "Парковка"),
    "аренда авто": ("🚕 Транспорт", "Аренда авто"),
    "аренда машин": ("🚕 Транспорт", "Аренда авто"),
    "ремонт авто": ("🚕 Транспорт", "Ремонт авто"),
    "автобус": ("🚕 Транспорт", "Общественный транспорт"),
    "метро": ("🚕 Транспорт", "Общественный транспорт"),
    # Жильё
    "аренда": ("🏠 Жильё", "Аренда квартиры"),
    "квартир": ("🏠 Жильё", "Аренда квартиры"),
    "уборк": ("🏠 Жильё", "Уборка / клининг"),
    "клининг": ("🏠 Жильё", "Уборка / клининг"),
    "ремонт": ("🏠 Жильё", "Ремонт"),
    "мебель": ("🏠 Жильё", "Уют"),
    "быт": ("🏠 Жильё", "Быт"),
    "интернет": ("📱 Подписки", "Мобильная связь"),
    # Спорт
    "боулдер": ("🧗 Спорт", "Скалолазание"),
    "скалолазан": ("🧗 Спорт", "Скалолазание"),
    "скалодром": ("🧗 Спорт", "Скалолазание"),
    "снаряжени": ("🧗 Спорт", "Снаряжение для скалолазания"),
    "бассейн": ("🧗 Спорт", "Бассейн"),
    "теннис": ("🧗 Спорт", "Теннис"),
    "спорт": ("🧗 Спорт", "Другой спорт"),
    "зал": ("🧗 Спорт", "Другой спорт"),
    "абонемент": ("🧗 Спорт", "Скалолазание"),
    # Здоровье
    "аптек": ("💊 Здоровье", "Аптека/косметика"),
    "лекарств": ("💊 Здоровье", "Аптека/косметика"),
    "врач": ("💊 Здоровье", "Врач / клиника"),
    "клиник": ("💊 Здоровье", "Врач / клиника"),
    "анализ": ("💊 Здоровье", "Анализы / обследования"),
    "витамин": ("💊 Здоровье", "Витамины / БАД"),
    "косметик": ("💊 Здоровье", "Аптека/косметика"),
    # Подписки
    "netflix": ("📱 Подписки", "Видео стриминг"),
    "нетфликс": ("📱 Подписки", "Видео стриминг"),
    "spotify": ("📱 Подписки", "Музыка"),
    "спотифай": ("📱 Подписки", "Музыка"),
    "музык": ("📱 Подписки", "Музыка"),
    "claude": ("📱 Подписки", "AI инструменты"),
    "chatgpt": ("📱 Подписки", "AI инструменты"),
    "чатгпт": ("📱 Подписки", "AI инструменты"),
    "icloud": ("📱 Подписки", "iCloud / Google One"),
    "айклауд": ("📱 Подписки", "iCloud / Google One"),
    "adobe": ("📱 Подписки", "Другая подписка"),
    "подписк": ("📱 Подписки", "Другая подписка"),
    "связь": ("📱 Подписки", "Мобильная связь"),
    "телефон": ("📱 Подписки", "Мобильная связь"),
    "симкарт": ("📱 Подписки", "Мобильная связь"),
    # Одежда
    "одежд": ("👕 Одежда и уход", "Одежда"),
    "обувь": ("👕 Одежда и уход", "Обувь"),
    "кроссовк": ("👕 Одежда и уход", "Обувь"),
    "барбер": ("👕 Одежда и уход", "Барбер / салон"),
    "стрижк": ("👕 Одежда и уход", "Барбер / салон"),
    "салон": ("👕 Одежда и уход", "Барбер / салон"),
    "химчистк": ("👕 Одежда и уход", "Химчистка"),
    # Долги
    "кредит тбанк": ("💳 Долги и переводы", "Кредит ТБанк (обяз.)"),
    "тбанк": ("💳 Долги и переводы", "Кредит ТБанк (обяз.)"),
    "кредитк": ("💳 Долги и переводы", "Кредитка погашение"),
    "перевод": ("💳 Долги и переводы", "Перевод в Россию"),
    "крипто": ("💳 Долги и переводы", "Крипто-комиссии"),
    "долг": ("💳 Долги и переводы", "Долг 2000 QAR"),
    # Инвестиции
    "акци": ("📈 Инвестиции", "Акции (eToro)"),
    "etoro": ("📈 Инвестиции", "Акции (eToro)"),
    "накоплени": ("📈 Инвестиции", "Накопления (отложил)"),
    "отложил": ("📈 Инвестиции", "Накопления (отложил)"),
    # Развлечения
    "кино": ("🎬 Развлечения", "Кино / театр / выставка"),
    "театр": ("🎬 Развлечения", "Кино / театр / выставка"),
    "выставк": ("🎬 Развлечения", "Кино / театр / выставка"),
    "хобби": ("🎬 Развлечения", "Хобби"),
    "игр": ("🎬 Развлечения", "Игры"),
    # Фото
    "фото": ("📷 Фото / фриланс", "Прочие расходы"),
    "съёмк": ("📷 Фото / фриланс", "Прочие расходы"),
    "съемк": ("📷 Фото / фриланс", "Прочие расходы"),
    "студи": ("📷 Фото / фриланс", "Аренда студии / реквизит"),
    "реквизит": ("📷 Фото / фриланс", "Аренда студии / реквизит"),
    "курс": ("📷 Фото / фриланс", "Обучение / курсы"),
    "обучени": ("📷 Фото / фриланс", "Обучение / курсы"),
    # Путешествия
    "виза": ("✈️ Путешествия", "Виза / разрешение"),
    "билет": ("✈️ Путешествия", "Билеты"),
    "отель": ("🎬 Развлечения", "Отель / жильё в поездке"),
    "гостиниц": ("🎬 Развлечения", "Отель / жильё в поездке"),
    # Другое
    "подарок": ("🎁 Другое", "Подарки"),
    "штраф": ("🎁 Другое", "Штрафы"),
}

CURRENCIES = ["QAR 🇶🇦", "USD 🇺🇸", "RUB 🇷🇺"]
CURRENCY_MAP = {"QAR 🇶🇦": "QAR", "USD 🇺🇸": "USD", "RUB 🇷🇺": "RUB"}
RATES = {"QAR": 1, "USD": 3.64, "RUB": 0.039}

AMOUNT, CURRENCY, CATEGORY, SUBCATEGORY, NOTE = range(5)
BACK = "◀️ Назад"
CANCEL = "❌ Отмена"
SKIP = "Пропустить ➡️"

# ─── Google Sheets ────────────────────────────────────────────
def get_sheet():
    creds_info = json.loads(GOOGLE_CREDS_JSON)
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SPREADSHEET_ID).sheet1
    if not sheet.row_values(1):
        sheet.append_row(["Дата", "Сумма", "Валюта", "Категория", "Подкатегория", "Комментарий", "Сумма в QAR"])
    return sheet

def add_row(date, amount, currency, category, subcategory, note):
    sheet = get_sheet()
    if not sheet.row_values(1):
        sheet.append_row(["Дата", "Сумма", "Валюта", "Категория", "Подкатегория", "Комментарий", "Сумма в QAR"])
    amount_qar = round(amount * RATES.get(currency, 1), 2)
    sheet.append_row([date, amount, currency, category, subcategory, note, amount_qar])

def get_stats():
    sheet = get_sheet()
    rows = sheet.get_all_records()
    if not rows:
        return None
    now = datetime.now()
    ym = now.strftime("%Y-%m")
    month_rows = [r for r in rows if str(r.get("Дата", "")).startswith(ym)]

    def to_qar(r):
        try:
            def parse_num(v):
                return float(str(v).replace(",", ".").replace(" ", "")) if v else 0
            qar = r.get("Сумма в QAR")
            if qar:
                return parse_num(qar)
            return parse_num(r["Сумма"]) * RATES.get(r["Валюта"], 1)
        except:
            return 0

    total_month = sum(to_qar(r) for r in month_rows)
    total_all = sum(to_qar(r) for r in rows)
    cat_totals = {}
    for r in month_rows:
        cat = r["Категория"]
        cat_totals[cat] = cat_totals.get(cat, 0) + to_qar(r)
    top_cats = sorted(cat_totals.items(), key=lambda x: x[1], reverse=True)[:5]
    return {
        "month": round(total_month, 2),
        "total": round(total_all, 2),
        "count": len(rows),
        "month_count": len(month_rows),
        "top": top_cats,
    }

# ─── Парсинг текста по ключевым словам ───────────────────────
def parse_text(text: str) -> dict | None:
    text_lower = text.lower().strip()

    # Извлекаем сумму
    amount_match = re.search(r'(\d+[.,]?\d*)', text_lower)
    if not amount_match:
        return None
    amount = float(amount_match.group(1).replace(",", "."))

    # Определяем валюту
    currency = "QAR"
    if any(w in text_lower for w in ["руб", "rub", "рублей", "р."]):
        currency = "RUB"
    elif any(w in text_lower for w in ["usd", "долл", "$", "бакс"]):
        currency = "USD"

    # Ищем все совпадения с позицией в тексте, берём самое раннее
    matches = []
    for kw in KEYWORDS.keys():
        pos = text_lower.find(kw)
        if pos != -1:
            matches.append((pos, len(kw), kw))

    if not matches:
        return None

    # Берём ключевое слово которое встречается первым в тексте
    matches.sort(key=lambda x: (x[0], -x[1]))
    _, _, best_kw = matches[0]
    category, subcategory = KEYWORDS[best_kw]

    # Комментарий — текст без суммы, валюты и первого ключевого слова
    note_text = re.sub(r'\d+[.,]?\d*', '', text_lower)
    note_text = re.sub(r'\b(qar|usd|rub|руб|рублей|долл)\b', '', note_text)
    note_text = note_text.replace(best_kw, '')
    note_text = re.sub(r'\s+', ' ', note_text).strip(" .,")

    return {
        "amount": amount,
        "currency": currency,
        "category": category,
        "subcategory": subcategory,
        "note": note_text if len(note_text) > 3 else "",
    }

# ─── Клавиатуры ──────────────────────────────────────────────
def make_kb(items, cols=2, extra_rows=None):
    kb = []
    row = []
    for item in items:
        row.append(KeyboardButton(item))
        if len(row) == cols:
            kb.append(row)
            row = []
    if row:
        kb.append(row)
    if extra_rows:
        kb.extend(extra_rows)
    return kb

def main_kb():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("➕ Добавить расход"), KeyboardButton("⚡️ Быстрый ввод")],
            [KeyboardButton("📊 Статистика"), KeyboardButton("📅 За месяц")],
        ],
        resize_keyboard=True
    )

# ─── Старт ───────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привет! Я твой трекер расходов.\n\n"
        "➕ *Добавить расход* — пошагово с кнопками\n"
        "⚡️ *Быстрый ввод* — одной строкой\n\n"
        "_Например: такси 45, кофе 12 QAR, тбанк 9920 руб_",
        reply_markup=main_kb(),
        parse_mode="Markdown"
    )

# ─── Быстрый ввод ────────────────────────────────────────────
async def quick_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚡️ *Быстрый ввод*\n\nНапиши расход одной строкой:\n"
        "_такси 45_\n_кофе 12 QAR_\n_тбанк 9920 руб_\n_боулдер 800_",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton(CANCEL)]], resize_keyboard=True)
    )
    context.user_data["mode"] = "quick"

async def handle_quick_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("mode") != "quick":
        return
    if update.message.text == CANCEL:
        context.user_data.clear()
        await update.message.reply_text("Отменено.", reply_markup=main_kb())
        return

    text = update.message.text.strip()
    parsed = parse_text(text)

    if not parsed:
        # Не распознал — переключаем на пошаговый ввод
        context.user_data.clear()
        await update.message.reply_text(
            "🤔 Не смог распознать. Переключаю на пошаговый ввод...",
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton(CANCEL)]], resize_keyboard=True)
        )
        context.user_data["mode"] = "step"
        await update.message.reply_text(
            "💰 *Шаг 1/4* — Введи сумму:\n_(например: 45 или 12.50)_",
            parse_mode="Markdown",
        )
        return

    context.user_data["quick_parsed"] = parsed
    context.user_data["mode"] = "quick_confirm"

    amount_qar = round(parsed["amount"] * RATES.get(parsed["currency"], 1), 2)
    caption = (
        f"Вот что я понял:\n\n"
        f"💰 {parsed['amount']} {parsed['currency']}"
        + (f" (~{amount_qar} QAR)" if parsed['currency'] != 'QAR' else "") + "\n"
        f"📂 {parsed['category']}\n"
        f"📌 {parsed['subcategory']}\n"
        + (f"📝 {parsed['note']}\n" if parsed.get('note') else "")
        + "\nВсё верно?"
    )

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Сохранить", callback_data="quick_save"),
            InlineKeyboardButton("✏️ Изменить", callback_data="quick_edit"),
        ],
        [InlineKeyboardButton("❌ Отменить", callback_data="quick_cancel")],
    ])
    await update.message.reply_text(caption, reply_markup=kb)

async def quick_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action = query.data

    if action == "quick_save":
        parsed = context.user_data.get("quick_parsed", {})
        date = datetime.now().strftime("%Y-%m-%d")
        try:
            add_row(date, parsed["amount"], parsed["currency"], parsed["category"], parsed["subcategory"], parsed.get("note", ""))
            amount_qar = round(parsed["amount"] * RATES.get(parsed["currency"], 1), 2)
            await query.edit_message_text(
                f"✅ *Записано!*\n\n"
                f"📅 {date}\n"
                f"💰 {parsed['amount']} {parsed['currency']} (~{amount_qar} QAR)\n"
                f"📂 {parsed['category']}\n"
                f"📌 {parsed['subcategory']}\n"
                + (f"📝 {parsed['note']}" if parsed.get('note') else ""),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Ошибка записи: {e}")
            await query.edit_message_text("❌ Ошибка записи. Попробуй ещё раз.")
        context.user_data.clear()
        await query.message.reply_text("Что дальше?", reply_markup=main_kb())

    elif action == "quick_edit":
        await query.edit_message_text("Переключаю на пошаговый ввод...")
        parsed = context.user_data.get("quick_parsed", {})
        context.user_data.clear()
        context.user_data["amount"] = parsed.get("amount")
        context.user_data["currency"] = parsed.get("currency", "QAR")
        context.user_data["mode"] = "step"
        kb = make_kb(list(CATEGORIES.keys()), cols=2, extra_rows=[[KeyboardButton(BACK), KeyboardButton(CANCEL)]])
        await query.message.reply_text(
            f"📂 *Шаг 3/4* — Выбери категорию:",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
        )

    elif action == "quick_cancel":
        context.user_data.clear()
        await query.edit_message_text("Отменено.")
        await query.message.reply_text("Что дальше?", reply_markup=main_kb())

# ─── Пошаговый ввод ──────────────────────────────────────────
async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data["mode"] = "step"
    await update.message.reply_text(
        "💰 *Шаг 1/4* — Введи сумму:\n_(например: 45 или 12.50)_",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton(CANCEL)]], resize_keyboard=True)
    )
    return AMOUNT

async def get_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == CANCEL:
        return await cancel(update, context)
    text = update.message.text.replace(",", ".").strip()
    try:
        amount = float(text)
        if amount <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Введи корректную сумму, например: 45 или 12.5")
        return AMOUNT
    context.user_data["amount"] = amount
    kb = make_kb(CURRENCIES, cols=3, extra_rows=[[KeyboardButton(CANCEL)]])
    await update.message.reply_text(
        "💱 *Шаг 2/4* — Выбери валюту:",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
    )
    return CURRENCY

async def get_currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == CANCEL:
        return await cancel(update, context)
    if update.message.text == BACK:
        return await add_start(update, context)
    cur_raw = update.message.text.strip()
    cur = CURRENCY_MAP.get(cur_raw)
    if not cur:
        await update.message.reply_text("Выбери из кнопок 👆")
        return CURRENCY
    context.user_data["currency"] = cur
    kb = make_kb(list(CATEGORIES.keys()), cols=2, extra_rows=[[KeyboardButton(BACK), KeyboardButton(CANCEL)]])
    await update.message.reply_text(
        "📂 *Шаг 3/4* — Выбери категорию:",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
    )
    return CATEGORY

async def get_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == CANCEL:
        return await cancel(update, context)
    if update.message.text == BACK:
        kb = make_kb(CURRENCIES, cols=3, extra_rows=[[KeyboardButton(CANCEL)]])
        await update.message.reply_text(
            "💱 *Шаг 2/4* — Выбери валюту:",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
        )
        return CURRENCY
    cat = update.message.text.strip()
    if cat not in CATEGORIES:
        await update.message.reply_text("Выбери категорию из списка 👆")
        return CATEGORY
    context.user_data["category"] = cat
    subs = CATEGORIES[cat]
    kb = make_kb(subs, cols=2, extra_rows=[[KeyboardButton(BACK), KeyboardButton(CANCEL)]])
    await update.message.reply_text(
        f"📌 *Шаг 4/4* — Подкатегория\n_{cat}_:",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
    )
    return SUBCATEGORY

async def get_subcategory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == CANCEL:
        return await cancel(update, context)
    if update.message.text == BACK:
        kb = make_kb(list(CATEGORIES.keys()), cols=2, extra_rows=[[KeyboardButton(BACK), KeyboardButton(CANCEL)]])
        await update.message.reply_text(
            "📂 *Шаг 3/4* — Выбери категорию:",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
        )
        return CATEGORY
    sub = update.message.text.strip()
    context.user_data["subcategory"] = sub
    kb = [[KeyboardButton(SKIP)], [KeyboardButton(BACK), KeyboardButton(CANCEL)]]
    await update.message.reply_text(
        "📝 Комментарий (необязательно):\n_Например: такси до работы_",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
    )
    return NOTE

async def get_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == CANCEL:
        return await cancel(update, context)
    if update.message.text == BACK:
        cat = context.user_data.get("category", "")
        subs = CATEGORIES.get(cat, [])
        kb = make_kb(subs, cols=2, extra_rows=[[KeyboardButton(BACK), KeyboardButton(CANCEL)]])
        await update.message.reply_text(
            f"📌 *Шаг 4/4* — Подкатегория\n_{cat}_:",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
        )
        return SUBCATEGORY
    note = "" if update.message.text == SKIP else update.message.text.strip()
    date = datetime.now().strftime("%Y-%m-%d")
    d = context.user_data
    amount_qar = round(d["amount"] * RATES.get(d["currency"], 1), 2)
    try:
        add_row(date, d["amount"], d["currency"], d["category"], d["subcategory"], note)
        await update.message.reply_text(
            f"✅ *Записано!*\n\n"
            f"📅 {date}\n"
            f"💰 {d['amount']} {d['currency']} (~{amount_qar} QAR)\n"
            f"📂 {d['category']}\n"
            f"📌 {d['subcategory']}\n"
            + (f"📝 {note}" if note else ""),
            reply_markup=main_kb(),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Ошибка записи: {e}")
        await update.message.reply_text("❌ Ошибка записи. Попробуй ещё раз.")
    return ConversationHandler.END

# ─── Статистика ───────────────────────────────────────────────
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Загружаю...")
    try:
        s = get_stats()
        if not s:
            await update.message.reply_text("Пока нет записей. Добавь первый расход!")
            return
        top_text = "\n".join([f"  {cat}: {round(amt)} QAR" for cat, amt in s["top"]])
        await update.message.reply_text(
            f"📊 *Статистика за всё время*\n\n"
            f"Всего: *{s['total']} QAR* ({s['count']} записей)\n\n"
            f"🏆 Топ категорий этого месяца:\n{top_text}",
            parse_mode="Markdown",
            reply_markup=main_kb()
        )
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await update.message.reply_text("❌ Ошибка загрузки.")

async def month_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Загружаю месяц...")
    try:
        s = get_stats()
        if not s:
            await update.message.reply_text("Пока нет записей.")
            return
        now = datetime.now()
        month_name = now.strftime("%B %Y")
        top_text = "\n".join([f"  {cat}: {round(amt)} QAR" for cat, amt in s["top"]])
        await update.message.reply_text(
            f"📅 *{month_name}*\n\n"
            f"Потрачено: *{s['month']} QAR*\n"
            f"Записей: {s['month_count']}\n\n"
            f"По категориям:\n{top_text}",
            parse_mode="Markdown",
            reply_markup=main_kb()
        )
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await update.message.reply_text("❌ Ошибка загрузки.")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Отменено.", reply_markup=main_kb())
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
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Regex("^📊 Статистика$"), stats))
    app.add_handler(MessageHandler(filters.Regex("^📅 За месяц$"), month_stats))
    app.add_handler(MessageHandler(filters.Regex("^⚡️ Быстрый ввод$"), quick_start))
    app.add_handler(CallbackQueryHandler(quick_callback, pattern="^quick_"))
    app.add_handler(conv)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_quick_text))

    logger.info("Бот запущен")
    app.run_polling()

if __name__ == "__main__":
    main()
