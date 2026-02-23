from flask import Flask, render_template, redirect, url_for, request
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from models import db, User
from sqlalchemy import text
from datetime import datetime, timedelta
import os

# =========================================================
# APP CONFIG
# =========================================================

app = Flask(__name__)

# 🔥 KRİTİK: SABİT SECRET KEY
app.config["SECRET_KEY"] = "supersecret-fixed-key"

# 🔥 DATABASE
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# 🔥 SESSION FIX (LOGIN LOOP ÇÖZÜMÜ)
app.config["SESSION_COOKIE_SECURE"] = False
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

with app.app_context():
    db.create_all()

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

    if current_user.is_authenticated:
        if current_user.role == "admin":
            return redirect(url_for("admin_dashboard"))
        return redirect(url_for("dashboard"))

    if request.method == "POST":

        username = request.form.get("username")
        password = request.form.get("password")

        user = User.query.filter_by(username=username).first()

        if user and user.password == password:
            login_user(user)   # 🔥 remember kaldırıldı

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

    return render_template(
        "admin_dashboard.html",
        users=users,
        total_users=total_users
    )

# =========================================================
# USER DASHBOARD
# =========================================================

@app.route("/dashboard")
@login_required
def dashboard():

    today = datetime.now().date()

    try:
        today_count = db.session.execute(text("""
            SELECT COUNT(*)
            FROM query_log
            WHERE user_id = :uid
            AND DATE(created_at) = :today
        """), {
            "uid": current_user.id,
            "today": today
        }).scalar() or 0

        total_queries = db.session.execute(text("""
            SELECT COUNT(*)
            FROM query_log
            WHERE user_id = :uid
        """), {
            "uid": current_user.id
        }).scalar() or 0

    except:
        today_count = 0
        total_queries = 0

    daily_limit = current_user.daily_limit or 1
    percent = int((today_count / daily_limit) * 100) if daily_limit else 0

    # Grafik için son 7 gün
    labels = []
    data = []

    for i in range(6, -1, -1):
        day = today - timedelta(days=i)

        try:
            count = db.session.execute(text("""
                SELECT COUNT(*)
                FROM query_log
                WHERE user_id = :uid
                AND DATE(created_at) = :day
            """), {
                "uid": current_user.id,
                "day": day
            }).scalar() or 0
        except:
            count = 0

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
    
@app.route("/search-user")
@login_required
def search_user():

    keyword = request.args.get("q", "").strip()

    if not keyword:
        return {"results": []}

    users = User.query.filter(
        User.username.ilike(f"%{keyword}%")
    ).all()

    return {
        "results": [
            {
                "id": u.id,
                "username": u.username,
                "role": u.role
            } for u in users
        ]
    }    

# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

# =========================================================
# CREATE ADMIN
# =========================================================

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