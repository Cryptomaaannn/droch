import sqlite3
from datetime import datetime, timedelta, time
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler,
    ContextTypes, MessageHandler, filters
)

DB = "stats.db"

# ---------------------- БАЗА ДАННЫХ ---------------------- #
def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            chat_id INTEGER,
            timestamp DATETIME
        )
    """)
    conn.commit()
    conn.close()

def add_event(user_id, username, chat_id):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute(
        "INSERT INTO events (user_id, username, chat_id, timestamp) VALUES (?, ?, ?, ?)",
        (user_id, username, chat_id, datetime.utcnow())
    )
    conn.commit()
    conn.close()

def get_streak(user_id, chat_id):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT timestamp FROM events WHERE user_id=? AND chat_id=? ORDER BY timestamp DESC LIMIT 7", (user_id, chat_id))
    rows = c.fetchall()
    conn.close()
    if len(rows) < 7:
        return 0
    # Проверяем, что 7 последних дней подряд есть отметки (по дням)
    days = set()
    for row in rows:
        dt = datetime.fromisoformat(row[0])
        days.add(dt.date())
    if len(days) == 7:
        # Проверяем, что это 7 подряд идущих дней
        sorted_days = sorted(days)
        for i in range(6):
            if (sorted_days[i+1] - sorted_days[i]).days != 1:
                return 0
        return 7
    return 0

def get_stats(chat_id, days=None):
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    if days is None:
        c.execute("SELECT username, COUNT(*) FROM events WHERE chat_id=? GROUP BY user_id ORDER BY COUNT(*) DESC", (chat_id,))
    else:
        since = datetime.utcnow() - timedelta(days=days)
        c.execute("SELECT username, COUNT(*) FROM events WHERE chat_id=? AND timestamp>=? GROUP BY user_id ORDER BY COUNT(*) DESC",
                  (chat_id, since))

    data = c.fetchall()
    conn.close()
    return data

# ---------------------- КОМАНДЫ ---------------------- #
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("Я подрочил")],
        [KeyboardButton("Показать таблицу")],
        [KeyboardButton("Обновить")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "Привет! Я бот учёта результатов.\n"
        "Команды:\n"
        "/mark — отметить, что сделал дело\n"
        "/week — статистика за неделю\n"
        "/month — статистика за месяц\n"
        "/top — общий топ",
        reply_markup=reply_markup
    )

async def auto_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("Я подрочил")],
        [KeyboardButton("Показать таблицу")],
        [KeyboardButton("Обновить")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Выберите действие:", reply_markup=reply_markup)

async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user = update.effective_user
    chat = update.effective_chat
    if text == "Я подрочил":
        add_event(user.id, user.username or user.full_name, chat.id)
        streak = get_streak(user.id, chat.id)
        if streak == 7:
            await update.message.reply_text(f"{user.username or user.full_name} подрочил! 🍆💦\n7 в ряд того рот ебал")
        else:
            await update.message.reply_text(f"{user.username or user.full_name} подрочил! 🍆💦")
    elif text == "Показать таблицу":
        stats = get_stats(chat.id)
        if not stats:
            await update.message.reply_text("Нет данных для таблицы.")
            return
        table = "<b>Дрочильня ИКТР-21</b>\n\n"
        table += "онанист     | количество дрочек\n"
        table += "-----------------------------\n"
        for name, cnt in stats:
            table += f"{name:<10} | {cnt}\n"
        await update.message.reply_text(f"<pre>{table}</pre>", parse_mode="HTML")
    elif text == "Обновить":
        await auto_menu(update, context)

async def mark(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat

    add_event(user.id, user.username or user.full_name, chat.id)
    await update.message.reply_text(f"{user.username or user.full_name} отметил результат! 👀")

async def week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    stats = get_stats(chat.id, days=7)

    if not stats:
        await update.message.reply_text("За неделю никто не отметился 😢")
        return

    txt = "📅 Статистика за неделю:\n\n"
    for name, cnt in stats:
        txt += f"— {name}: {cnt}\n"

    await update.message.reply_text(txt)

async def month(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    stats = get_stats(chat.id, days=30)

    if not stats:
        await update.message.reply_text("За месяц пусто 😢")
        return

    txt = "📊 Статистика за месяц:\n\n"
    for name, cnt in stats:
        txt += f"— {name}: {cnt}\n"

    await update.message.reply_text(txt)

async def top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    stats = get_stats(chat.id)

    if not stats:
        await update.message.reply_text("Никто ещё не отметился 😢")
        return

    txt = "🏆 Общий топ:\n\n"
    for name, cnt in stats:
        txt += f"— {name}: {cnt}\n"

    await update.message.reply_text(txt)

# ---------------------- ПЛАНИРОВЩИК ---------------------- #
async def weekly_reminder(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id
    await context.bot.send_message(chat_id, "Не забываем гонять лысого! 🦲💪")

async def monthly_summary(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id
    stats = get_stats(chat_id, days=30)

    if not stats:
        await context.bot.send_message(chat_id, "За месяц нет данных 😢")
        return

    winner, count = stats[0]

    text = "📅 Итоги месяца!\n\n"
    for name, cnt in stats:
        text += f"{name}: {cnt}\n"
    text += f"\n🏆 Победитель месяца: **{winner}** с результатом {count}!"

    await context.bot.send_message(chat_id, text)

def set_jobs(app, chat_id):
    # 3 напоминания в день: 8:00, 16:00, 23:00
    app.job_queue.run_daily(
        weekly_reminder,
        time=time(hour=8, minute=0, second=0),
        chat_id=chat_id
    )
    app.job_queue.run_daily(
        weekly_reminder,
        time=time(hour=16, minute=0, second=0),
        chat_id=chat_id
    )
    app.job_queue.run_daily(
        weekly_reminder,
        time=time(hour=23, minute=0, second=0),
        chat_id=chat_id
    )

    # итог месяца — 1-е число в 10:00
    app.job_queue.run_daily(
        monthly_summary,
        time=time(hour=10, minute=0, second=0),
        days=(1,),
        chat_id=chat_id
    )

# ---------------------- ЗАПУСК БОТА ---------------------- #
def main():
    init_db()
    TOKEN = "8221752968:AAEcw8Ors0rt4NEFvDp6jCWbrHxWrsRMXKA"  # вставьте сюда токен от BotFather
    CHAT_ID = 1269053810      # вставьте chat_id вашего чата
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("mark", mark))
    app.add_handler(CommandHandler("week", week))
    app.add_handler(CommandHandler("month", month))
    app.add_handler(CommandHandler("top", top))
    app.add_handler(MessageHandler(filters.Regex("^(Я подрочил|Показать таблицу|Обновить)$"), handle_button))
    set_jobs(app, CHAT_ID)
    app.run_polling()

if __name__ == "__main__":
    main()
