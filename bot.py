import logging
import requests
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler
)

# ============================================================
#  الإعدادات
# ============================================================
TELEGRAM_TOKEN = "8655452224:AAFjCupxvWgkgEyG1NqSuetIf-8LqOSYozg"
GROQ_API_KEY   = "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"
GROQ_MODEL     = "llama-3.3-70b-versatile"

logging.basicConfig(level=logging.INFO)

# ============================================================
#  حالات المحادثة
# ============================================================
WAIT_MATN, WAIT_SHARH, REVIEWING = range(3)

# تخزين بيانات المستخدمين مؤقتاً
users = {}

# ============================================================
#  دالة التواصل مع Groq
# ============================================================
def groq(prompt: str) -> str:
    try:
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}",
                     "Content-Type": "application/json"},
            json={
                "model": GROQ_MODEL,
                "messages": [
                    {"role": "system",
                     "content": (
                         "أنت مساعد متخصص في علوم الشريعة الإسلامية، "
                         "تساعد طلاب العلم الشرعي على مراجعة المتون وشروحها. "
                         "أجوبتك دقيقة ومختصرة ومفيدة."
                     )},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 800,
                "temperature": 0.7
            },
            timeout=30
        )
        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"⚠️ حدث خطأ: {e}"

# ============================================================
#  لوحة مفاتيح المراجعة
# ============================================================
REVIEW_KEYBOARD = ReplyKeyboardMarkup(
    [["❓ سؤال وجواب", "✏️ إكمال النص"],
     ["🔍 اكتشف الخطأ", "💡 اشرح المقصود"],
     ["📖 متن جديد"]],
    resize_keyboard=True
)

# ============================================================
#  /start
# ============================================================
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌿 *أهلاً بك في بوت مراجعة المتون الشرعية*\n\n"
        "أنا بوت ذكي يساعدك على مراجعة المتون وشروحها بأساليب متنوعة:\n\n"
        "• ❓ أسئلة وأجوبة\n"
        "• ✏️ إكمال النصوص\n"
        "• 🔍 اكتشاف الأخطاء\n"
        "• 💡 شرح المقصود\n\n"
        "ابدأ بإرسال الأمر /matn لإدخال المتن والشرح.",
        parse_mode="Markdown"
    )

# ============================================================
#  /matn  — بداية إدخال المتن
# ============================================================
async def cmd_matn(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *الخطوة 1/2*\n\nأرسل لي نص *المتن* كاملاً:",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove()
    )
    return WAIT_MATN

async def got_matn(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    users[uid] = {"matn": update.message.text, "sharh": "", "last_q": ""}
    await update.message.reply_text(
        "✅ *تم حفظ المتن!*\n\n📚 *الخطوة 2/2*\n\nأرسل لي نص *الشرح*:",
        parse_mode="Markdown"
    )
    return WAIT_SHARH

async def got_sharh(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    users[uid]["sharh"] = update.message.text
    matn_preview = users[uid]["matn"][:80] + "..." if len(users[uid]["matn"]) > 80 else users[uid]["matn"]
    await update.message.reply_text(
        f"✅ *تم حفظ المتن والشرح!*\n\n"
        f"📖 المتن: _{matn_preview}_\n\n"
        f"اختر طريقة المراجعة:",
        parse_mode="Markdown",
        reply_markup=REVIEW_KEYBOARD
    )
    return REVIEWING

# ============================================================
#  معالج الرسائل أثناء المراجعة
# ============================================================
async def handle_review(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    text = update.message.text

    # إذا لا يوجد متن بعد
    if uid not in users or not users[uid].get("matn"):
        await update.message.reply_text(
            "أرسل /matn أولاً لإدخال المتن والشرح."
        )
        return REVIEWING

    matn  = users[uid]["matn"]
    sharh = users[uid]["sharh"]

    # ── متن جديد ──────────────────────────────────────────
    if text == "📖 متن جديد":
        await update.message.reply_text(
            "📖 أرسل نص المتن الجديد:",
            reply_markup=ReplyKeyboardRemove()
        )
        return WAIT_MATN

    # ── سؤال وجواب ────────────────────────────────────────
    elif text == "❓ سؤال وجواب":
        await update.message.reply_text("⏳ جاري توليد السؤال...")
        prompt = (
            f"المتن:\n{matn}\n\nالشرح:\n{sharh}\n\n"
            "اطرح سؤالاً واحداً مهماً من هذا المتن على طريقة العلماء. "
            "اطرح السؤال فقط بدون إجابة."
        )
        q = groq(prompt)
        users[uid]["last_q"] = q
        users[uid]["mode"]   = "question"
        await update.message.reply_text(
            f"❓ *السؤال:*\n\n{q}\n\n_أرسل إجابتك:_",
            parse_mode="Markdown"
        )

    # ── إكمال النص ────────────────────────────────────────
    elif text == "✏️ إكمال النص":
        await update.message.reply_text("⏳ جاري توليد تمرين الإكمال...")
        prompt = (
            f"المتن:\n{matn}\n\n"
            "خذ جملة أو عبارة منه واحذف كلمة أو عبارة مهمة وضع مكانها (.....) "
            "واطلب من الطالب إكمالها. اعرض الجملة الناقصة فقط."
        )
        q = groq(prompt)
        users[uid]["last_q"] = q
        users[uid]["mode"]   = "complete"
        await update.message.reply_text(
            f"✏️ *أكمل العبارة:*\n\n{q}\n\n_أرسل إجابتك:_",
            parse_mode="Markdown"
        )

    # ── اكتشف الخطأ ──────────────────────────────────────
    elif text == "🔍 اكتشف الخطأ":
        await update.message.reply_text("⏳ جاري توليد تمرين اكتشاف الخطأ...")
        prompt = (
            f"المتن:\n{matn}\n\n"
            "خذ جملة أو مسألة منه وغيّر فيها كلمة أو حكماً ليصبح خطأ، "
            "ثم اطلب من الطالب اكتشاف الخطأ وتصحيحه. "
            "اعرض العبارة المعدّلة فقط بدون ذكر أين الخطأ."
        )
        q = groq(prompt)
        users[uid]["last_q"] = q
        users[uid]["mode"]   = "error"
        await update.message.reply_text(
            f"🔍 *اكتشف الخطأ وصححه:*\n\n{q}\n\n_أرسل إجابتك:_",
            parse_mode="Markdown"
        )

    # ── اشرح المقصود ─────────────────────────────────────
    elif text == "💡 اشرح المقصود":
        await update.message.reply_text("⏳ جاري توليد السؤال...")
        prompt = (
            f"المتن:\n{matn}\n\nالشرح:\n{sharh}\n\n"
            "اختر عبارة أو مصطلحاً من المتن واطلب من الطالب شرح مقصوده. "
            "اذكر العبارة فقط بدون شرحها."
        )
        q = groq(prompt)
        users[uid]["last_q"] = q
        users[uid]["mode"]   = "explain"
        await update.message.reply_text(
            f"💡 *اشرح المقصود من هذه العبارة:*\n\n{q}\n\n_أرسل إجابتك:_",
            parse_mode="Markdown"
        )

    # ── إجابة الطالب على سؤال سابق ───────────────────────
    else:
        last_q = users[uid].get("last_q", "")
        if not last_q:
            await update.message.reply_text(
                "اختر طريقة المراجعة من القائمة 👆",
                reply_markup=REVIEW_KEYBOARD
            )
            return REVIEWING

        await update.message.reply_text("⏳ جاري تقييم إجابتك...")
        prompt = (
            f"المتن:\n{matn}\n\nالشرح:\n{sharh}\n\n"
            f"السؤال/التمرين:\n{last_q}\n\n"
            f"إجابة الطالب:\n{text}\n\n"
            "قيّم إجابة الطالب بإيجاز: هل هي صحيحة؟ "
            "أكمل ما نقص واذكر الصواب من المتن والشرح."
        )
        evaluation = groq(prompt)
        users[uid]["last_q"] = ""
        await update.message.reply_text(
            f"📝 *التقييم:*\n\n{evaluation}",
            parse_mode="Markdown",
            reply_markup=REVIEW_KEYBOARD
        )

    return REVIEWING

# ============================================================
#  تشغيل البوت
# ============================================================
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CommandHandler("matn",  cmd_matn),
        ],
        states={
            WAIT_MATN:  [MessageHandler(filters.TEXT & ~filters.COMMAND, got_matn)],
            WAIT_SHARH: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_sharh)],
            REVIEWING:  [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_review)],
        },
        fallbacks=[
            CommandHandler("start", start),
            CommandHandler("matn",  cmd_matn),
        ],
        allow_reentry=True,
    )

    app.add_handler(conv)
    print("✅ البوت يعمل...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
