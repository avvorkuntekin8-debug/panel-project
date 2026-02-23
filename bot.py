from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler
)
import json
import requests

TOKEN = "8596108342:AAGZaHxY0iIPE-U4jitnNk3Lipjj4Qpm_CM"
FLASK_URL = "http://127.0.0.1:5000"  # Flask çalıştığı adres


# ================= REGISTER START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    data = {
        "id": user.id,
        "username": user.username
    }

    with open("telegram_users.json", "a") as f:
        f.write(json.dumps(data) + "\n")

    await update.message.reply_text(
        "✅ Bot doğrulandı. Siteye geri dönüp kayıt işlemini tamamlayabilirsiniz."
    )


# ================= PREMIUM CALLBACK =================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    if data.startswith("approve_"):
        _, user_id, plan = data.split("_")

        # Flask'a onay isteği gönder
        requests.get(f"{FLASK_URL}/admin/approve/{user_id}/{plan}")

        await query.edit_message_text(
            f"✅ Kullanıcı {user_id} için {plan} planı onaylandı."
        )

    elif data.startswith("reject_"):
        _, user_id, plan = data.split("_")

        requests.get(f"{FLASK_URL}/admin/reject/{user_id}")

        await query.edit_message_text(
            f"❌ Kullanıcı {user_id} için talep reddedildi."
        )


# ================= BOT INIT =================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button_handler))

app.run_polling()