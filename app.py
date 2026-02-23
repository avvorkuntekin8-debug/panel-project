from flask import Flask, render_template, redirect, url_for, request
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from models import db, User
from sqlalchemy import text
from datetime import datetime, timedelta
import requests
import json
import os

# =========================================================
# APP CONFIG
# =========================================================

app = Flask(__name__)

app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY", "supersecretkey")
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///database.db"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

with app.app_context():
    db.create_all()

# =========================================================
# TELEGRAM ADMIN MESSAGE
# =========================================================

def send_admin_message(user_id, username, plan):

    bot_token = "BOT_TOKEN_BURAYA"
    admin_id = "ADMIN_ID_BURAYA"

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    keyboard = {
        "inline_keyboard": [[
            {"text": "✅ Onayla", "callback_data": f"approve_{user_id}_{plan}"},
            {"text": "❌ Reddet", "callback_data": f"reject_{user_id}_{plan}"}
        ]]
    }

    requests.post(url, json={
        "chat_id": admin_id,
        "text": f"""
💎 Premium Talebi

Kullanıcı: {username}
User ID: {user_id}
Plan: {plan}
""",
        "reply_markup": keyboard
    })

# =========================================================
# PREMIUM EXPIRY CHECK
# =========================================================

@app.before_request
def check_premium_expiry():
    if current_user.is_authenticated:
        if current_user.role == "premium" and current_user.premium_until:
            if datetime.now() > current_user.premium_until:
                current_user.role = "user"
                current_user.daily_limit = 50
                current_user.hourly_limit = 20
                current_user.premium_until = None
                db.session.commit()

# =========================================================
# USER LOADER
# =========================================================

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():
    return redirect(url_for("login"))

# =========================================================
# LOGIN
# =========================================================

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":

        username = request.form.get("username")
        password = request.form.get("password")

        user = User.query.filter_by(username=username).first()

        if user and user.password == password:
            login_user(user, remember=True)

            if user.role == "admin":
                return redirect(url_for("admin_dashboard"))

            return redirect(url_for("dashboard"))

        return render_template("login.html", error="Hatalı giriş")

    return render_template("login.html")

# =========================================================
# REGISTER
# =========================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not username or not password:
            return render_template("register.html", error="Tüm alanları doldurun")

        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            return render_template("register.html", error="Bu kullanıcı adı zaten var")

        new_user = User(
            username=username,
            password=password,
            role="user",
            daily_limit=50,
            hourly_limit=20
        )

        db.session.add(new_user)
        db.session.commit()

        return redirect(url_for("login"))

    return render_template("register.html")

# =========================================================
# ADMIN DASHBOARD
# =========================================================

@app.route("/admin-dashboard")
@login_required
def admin_dashboard():

    if current_user.role != "admin":
        return redirect(url_for("dashboard"))

    users = User.query.all()
    total_users = User.query.count()

    total_queries = db.session.execute(text("""
        SELECT COUNT(*) FROM query_log
    """)).scalar() or 0

    return render_template(
        "admin_dashboard.html",
        users=users,
        total_users=total_users,
        total_queries=total_queries
    )

# =========================================================
# USER DASHBOARD
# =========================================================

@app.route("/dashboard")
@login_required
def dashboard():

    today = datetime.now().date()

    today_count = db.session.execute(text("""
        SELECT COUNT(*)
        FROM query_log
        WHERE user_id = :uid
        AND DATE(created_at) = :today
    """), {
        "uid": current_user.id,
        "today": today
    }).scalar() or 0

    daily_limit = current_user.daily_limit or 1
    percent = int((today_count / daily_limit) * 100)

    remaining_days = 0
    if current_user.premium_until:
        remaining_days = (current_user.premium_until - datetime.now()).days

    return render_template(
        "dashboard.html",
        user=current_user,
        today_count=today_count,
        daily_limit=daily_limit,
        percent=percent,
        remaining_days=remaining_days
    )

# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":
    app.run()