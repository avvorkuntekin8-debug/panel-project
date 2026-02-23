from flask import Flask, render_template, redirect, url_for, request
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from models import db, User
from sqlalchemy import text
from datetime import datetime, timedelta
import requests
import json
import os

# =========================================================
# APP INIT (DÜZELTİLDİ)
# =========================================================

app = Flask(__name__)

app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY", "super-secret-key")
app.config['SESSION_COOKIE_SECURE'] = False
app.config['SESSION_COOKIE_SAMESITE'] = "Lax"
app.config['SESSION_COOKIE_HTTPONLY'] = True

db.init_app(app)

with app.app_context():
    db.create_all()
    
@app.route("/init-db")
def init_db():
    db.create_all()
    return "Database initialized"     

# =========================================================
# LOGIN MANAGER
# =========================================================

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# =========================================================
# TELEGRAM ADMIN MESAJ
# =========================================================

def send_admin_message(user_id, username, plan):

    bot_token = "8596108342:AAGZaHxY0iIPE-U4jitnNk3Lipjj4Qpm_CM"
    admin_id = "7595556701"

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
# PREMIUM EXPIRE CHECK
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

            next_page = request.args.get("next")
            if next_page:
                return redirect(next_page)

            if user.role == "admin":
                return redirect(url_for("admin_dashboard"))

            return redirect(url_for("dashboard"))

        return render_template("login.html", error="Hatalı giriş")

    return render_template("login.html")
    
    

# =========================================================
# REGISTER (BOT DOĞRULAMALI)
# =========================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        telegram = request.form.get("telegram", "").strip()

        telegram_clean = telegram.replace("@", "").lower()

        if not username or not password or not telegram_clean:
            return render_template("register.html", error="Tüm alanları doldurun")

        if not telegram_verified(telegram_clean):
            return render_template("register.html", error="Telegram botunu başlatmalısınız")

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
# TELEGRAM VERIFY
# =========================================================

def telegram_verified(username):

    username = username.strip().replace("@", "").lower()

    try:
        with open("telegram_users.json", "r") as f:
            for line in f:
                data = json.loads(line.strip())
                if (data.get("username") or "").lower() == username:
                    return True
    except:
        pass

    return False
    
@app.route("/admin-dashboard")
@login_required
def admin_dashboard():

    if user.role == "admin":
         return redirect(url_for("admin_dashboard"))

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
# DASHBOARD
# =========================================================

@app.route("/dashboard")
@login_required
def dashboard():
    
    print("CURRENT USER:", current_user.is_authenticated)

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

    total_queries = db.session.execute(text("""
        SELECT COUNT(*)
        FROM query_log
        WHERE user_id = :uid
    """), {"uid": current_user.id}).scalar() or 0

    labels = []
    data = []

    for i in range(6, -1, -1):
        day = today - timedelta(days=i)

        count = db.session.execute(text("""
            SELECT COUNT(*)
            FROM query_log
            WHERE user_id = :uid
            AND DATE(created_at) = :day
        """), {
            "uid": current_user.id,
            "day": day
        }).scalar() or 0

        labels.append(day.strftime("%d.%m"))
        data.append(count)

    remaining_days = 0
    if current_user.premium_until:
        remaining_days = (current_user.premium_until - datetime.now()).days

    return render_template(
        "dashboard.html",
        user=current_user,
        today_count=today_count,
        daily_limit=daily_limit,
        percent=percent,
        total_queries=total_queries,
        remaining_days=remaining_days,
        chart_labels=labels,
        chart_data=data
    )

# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

@app.route("/create-admin")
def create_admin():

    existing = User.query.filter_by(username="admin").first()
    if existing:
        return "Admin already exists"

    user = User(
        username="admin",
        password="1234",
        role="admin",
        daily_limit=99999,
        hourly_limit=9999
    )

    db.session.add(user)
    db.session.commit()

    return "Admin created"

# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":
    app.run()