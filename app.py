from flask import Flask, render_template, redirect, url_for, request
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from models import db, User
from sqlalchemy import text
from datetime import datetime, timedelta
import requests
import json
from collections import defaultdict
from flask import request, redirect, url_for
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + DB_PATH
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

with app.app_context():
    db.create_all()

def send_admin_message(user_id, username, plan):

    bot_token = "8596108342:AAGZaHxY0iIPE-U4jitnNk3Lipjj4Qpm_CM"
    admin_id = "7595556701"

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    keyboard = {
        "inline_keyboard": [
            [
                {
                    "text": "✅ Onayla",
                    "callback_data": f"approve_{user_id}_{plan}"
                },
                {
                    "text": "❌ Reddet",
                    "callback_data": f"reject_{user_id}_{plan}"
                }
            ]
        ]
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

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY", "fallback")
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///prod_database.db"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

with app.app_context():
    db.create_all()

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

@app.route("/init-db")
def init_db():
    db.create_all()
    return "Database initialized"

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
# LIMIT SYSTEM
# =========================================================
def is_user_in_channel(username):
    bot_token = "8596108342:AAGZaHxY0iIPE-U4jitnNk3Lipjj4Qpm_CM"
    channel_username = "t.me/BigBossCyber"

    url = f"https://api.telegram.org/bot{bot_token}/getChatMember"
    
    try:
        response = requests.get(url, params={
            "chat_id": channel_username,
            "user_id": username
        })
        data = response.json()

        if data.get("ok") and data["result"]["status"] in ["member", "administrator", "creator"]:
            return True
        return False
    except:
        return False

def check_query_limit(user):

    if user.role == "admin":
        return True, None

    now = datetime.now()
    today = now.date()
    one_hour_ago = now - timedelta(hours=1)

    daily_count = db.session.execute(text("""
        SELECT COUNT(*) FROM query_log
        WHERE user_id = :uid
        AND DATE(created_at) = :today
    """), {"uid": user.id, "today": today}).scalar()

    hourly_count = db.session.execute(text("""
        SELECT COUNT(*) FROM query_log
        WHERE user_id = :uid
        AND created_at >= :hour
    """), {"uid": user.id, "hour": one_hour_ago}).scalar()

    if daily_count >= user.daily_limit:
        return False, "daily"

    if hourly_count >= user.hourly_limit:
        return False, "hourly"

    return True, None


def log_query(qtype):
    db.session.execute(text("""
        INSERT INTO query_log (user_id, query_type)
        VALUES (:uid, :type)
    """), {
        "uid": current_user.id,
        "type": qtype
    })
    db.session.commit()

# =========================================================
# UNIVERSAL SEARCH
# =========================================================
@app.route("/search")
@login_required
def universal_search():

    allowed, reason = check_query_limit(current_user)
    if not allowed:
        return {"error": reason}

    search_type = request.args.get("type")
    keyword = request.args.get("q")

    if not keyword or not search_type:
        return {"results": []}

    column_map = {
        "tc": "TC",
        "gsm": "GSM",
        "babaadi": "BABAADI",
        "anneadi": "ANNEADI",
        "adres": "ADRESIL"
    }

    if search_type not in column_map:
        return {"results": []}

    column = column_map[search_type]

    if search_type == "tc" and len(keyword) == 11:
        results = db.session.execute(text("""
            SELECT *
            FROM 109mtcpro
            WHERE TC = :tc
            LIMIT 1
        """), {"tc": keyword}).fetchall()
    else:
        results = db.session.execute(text(f"""
            SELECT *
            FROM 109mtcpro
            WHERE {column} LIKE :kw
            LIMIT 50
        """), {"kw": f"%{keyword}%"}).fetchall()

    log_query(search_type)

    return {"results": [dict(r._mapping) for r in results]}

# =========================================================
# GSM SEARCH
# =========================================================
@app.route("/search-gsm")
@login_required
def search_gsm():

    allowed, reason = check_query_limit(current_user)
    if not allowed:
        return {"error": reason}

    gsm = request.args.get("q")
    if not gsm:
        return {"results": []}

    results = db.session.execute(text("""
        SELECT TC
        FROM gsm
        WHERE GSM = :gsm
        LIMIT 50
    """), {"gsm": gsm}).fetchall()

    log_query("gsm")

    return {"results": [dict(r._mapping) for r in results]}

# =========================================================
# TC → AD SOYAD (GSM detay için)
# =========================================================
@app.route("/search-tc-name")
@login_required
def search_tc_name():

    tc = request.args.get("tc")
    if not tc:
        return {"results": []}

    result = db.session.execute(text("""
        SELECT AD, SOYAD
        FROM 109mtcpro
        WHERE TC = :tc
        LIMIT 1
    """), {"tc": tc}).fetchone()

    if not result:
        return {"results": []}

    return {"results": [dict(result._mapping)]}
    

# =========================================================
# AD SOYAD SEARCH (PAGINATION)
# =========================================================

@app.route("/search-name")
@login_required
def search_name():

    allowed, reason = check_query_limit(current_user)
    if not allowed:
        return {"error": reason}

    keyword = request.args.get("q", "").strip().upper()
    page = request.args.get("page", "1")

    try:
        page = int(page)
    except:
        page = 1

    if page < 1:
        page = 1

    if len(keyword.split()) < 2:
        return {"results": [], "total": 0}

    parts = keyword.split()
    soyad = parts[-1]
    ad = " ".join(parts[:-1])

    limit = 20
    offset = (page - 1) * limit

    # Sonuçlar
    results = db.session.execute(text(f"""
        SELECT TC, ADI, SOYADI, NUFUSIL, NUFUSILCE
        FROM 101m
        WHERE ADI LIKE :ad
        AND SOYADI LIKE :soyad
        LIMIT {limit} OFFSET {offset}
    """), {
        "ad": ad + "%",
        "soyad": soyad + "%"
    }).fetchall()

    # Toplam kayıt
    total = db.session.execute(text("""
        SELECT COUNT(*)
        FROM 101m
        WHERE ADI LIKE :ad
        AND SOYADI LIKE :soyad
    """), {
        "ad": ad + "%",
        "soyad": soyad + "%"
    }).scalar() or 0

    total_pages = (total // limit) + (1 if total % limit > 0 else 0)

    log_query("adsoyad")

    return {
        "results": [dict(r._mapping) for r in results],
        "total": total,
        "page": page,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1,
        "next_page": page + 1 if page < total_pages else None,
        "prev_page": page - 1 if page > 1 else None
    }

@app.route("/search-address")
@login_required
def search_address():

    allowed, reason = check_query_limit(current_user)
    if not allowed:
        return {"error": reason}

    tc = request.args.get("q", "").strip()
    if not tc:
        return {"results": []}

    try:
        result = db.session.execute(text("""
            SELECT 
                TC,
                ADRES2024,
                ADRES2023,
                ADRES2017,
                ADRES2015,
                ADRES2009
            FROM 81madres2009_2024
            WHERE TC = :tc
            LIMIT 1
        """), {"tc": tc}).fetchone()

        if not result:
            return {"results": []}

        log_query("adres")

        return {"results": [dict(result._mapping)]}

    except Exception as e:
        print("ADDRESS ERROR:", e)
        return {"results": []}    

# =========================================================
# FAMILY SEARCH (GENİŞ)
# =========================================================
@app.route("/search-family")
@login_required
def search_family():

    allowed, reason = check_query_limit(current_user)
    if not allowed:
        return {"error": reason}

    tc = request.args.get("q")
    if not tc:
        return {"results": []}

    # ===================== KİŞİ =====================
    person_row = db.session.execute(text("""
        SELECT TC, AD, SOYAD, BABATC, ANNETC
        FROM 109mtcpro
        WHERE TC = :tc
    """), {"tc": tc}).fetchone()

    if not person_row:
        return {"results": []}

    person = dict(person_row._mapping)

    baba_tc = person.get("BABATC")
    anne_tc = person.get("ANNETC")

    # ===================== ANNE & BABA =====================
    parents_rows = db.session.execute(text("""
        SELECT TC, AD, SOYAD, BABATC, ANNETC
        FROM 109mtcpro
        WHERE TC = :b OR TC = :a
    """), {"b": baba_tc, "a": anne_tc}).fetchall()

    parents = [dict(r._mapping) for r in parents_rows]

    # ===================== KARDEŞ =====================
    siblings_rows = db.session.execute(text("""
        SELECT TC, AD, SOYAD
        FROM 109mtcpro
        WHERE BABATC = :b AND ANNETC = :a
        AND TC != :tc
    """), {"b": baba_tc, "a": anne_tc, "tc": tc}).fetchall()

    siblings = [dict(r._mapping) for r in siblings_rows]

    # ===================== ÇOCUK =====================
    children_rows = db.session.execute(text("""
        SELECT TC, AD, SOYAD
        FROM 109mtcpro
        WHERE BABATC = :tc OR ANNETC = :tc
    """), {"tc": tc}).fetchall()

    children = [dict(r._mapping) for r in children_rows]

    # ===================== TORUN =====================
    grandchildren = []
    for child in children:
        torun_rows = db.session.execute(text("""
            SELECT TC, AD, SOYAD
            FROM 109mtcpro
            WHERE BABATC = :tc OR ANNETC = :tc
        """), {"tc": child["TC"]}).fetchall()

        grandchildren.extend([dict(r._mapping) for r in torun_rows])

    # ===================== BABA TARAFI =====================
    paternal_grandparents = []
    paternal_uncles = []
    paternal_cousins = []

    if baba_tc:
        baba_row = db.session.execute(text("""
            SELECT BABATC, ANNETC
            FROM 109mtcpro
            WHERE TC = :b
        """), {"b": baba_tc}).fetchone()

        if baba_row:
            dede_tc = baba_row[0]
            babaanne_tc = baba_row[1]

            # Dede & Babaanne
            gp_rows = db.session.execute(text("""
                SELECT TC, AD, SOYAD
                FROM 109mtcpro
                WHERE TC = :d OR TC = :b
            """), {"d": dede_tc, "b": babaanne_tc}).fetchall()

            paternal_grandparents = [dict(r._mapping) for r in gp_rows]

            # Amca / Hala
            uncle_rows = db.session.execute(text("""
                SELECT TC, AD, SOYAD
                FROM 109mtcpro
                WHERE BABATC = :d
                AND TC != :father
            """), {"d": dede_tc, "father": baba_tc}).fetchall()

            paternal_uncles = [dict(r._mapping) for r in uncle_rows]

            # Kuzenler
            for uncle in paternal_uncles:
                cousin_rows = db.session.execute(text("""
                    SELECT TC, AD, SOYAD
                    FROM 109mtcpro
                    WHERE BABATC = :tc OR ANNETC = :tc
                """), {"tc": uncle["TC"]}).fetchall()

                paternal_cousins.extend([dict(r._mapping) for r in cousin_rows])

    # ===================== ANNE TARAFI =====================
    maternal_grandparents = []
    maternal_uncles = []
    maternal_cousins = []

    if anne_tc:
        anne_row = db.session.execute(text("""
            SELECT BABATC, ANNETC
            FROM 109mtcpro
            WHERE TC = :a
        """), {"a": anne_tc}).fetchone()

        if anne_row:
            dede_tc = anne_row[0]
            anneanne_tc = anne_row[1]

            # Anneanne & Dede
            gp_rows = db.session.execute(text("""
                SELECT TC, AD, SOYAD
                FROM 109mtcpro
                WHERE TC = :d OR TC = :a
            """), {"d": dede_tc, "a": anneanne_tc}).fetchall()

            maternal_grandparents = [dict(r._mapping) for r in gp_rows]

            # Dayı / Teyze
            uncle_rows = db.session.execute(text("""
                SELECT TC, AD, SOYAD
                FROM 109mtcpro
                WHERE BABATC = :d
                AND TC != :mother
            """), {"d": dede_tc, "mother": anne_tc}).fetchall()

            maternal_uncles = [dict(r._mapping) for r in uncle_rows]

            # Kuzen
            for uncle in maternal_uncles:
                cousin_rows = db.session.execute(text("""
                    SELECT TC, AD, SOYAD
                    FROM 109mtcpro
                    WHERE BABATC = :tc OR ANNETC = :tc
                """), {"tc": uncle["TC"]}).fetchall()

                maternal_cousins.extend([dict(r._mapping) for r in cousin_rows])

    log_query("family")

    return {
        "person": person,
        "parents": parents,
        "siblings": siblings,
        "children": children,
        "grandchildren": grandchildren,
        "paternal_grandparents": paternal_grandparents,
        "paternal_uncles": paternal_uncles,
        "paternal_cousins": paternal_cousins,
        "maternal_grandparents": maternal_grandparents,
        "maternal_uncles": maternal_uncles,
        "maternal_cousins": maternal_cousins
    }

# =========================================================
# LOGIN
# =========================================================
# =========================================================
# REGISTER
# =========================================================

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

        print("Form telegram:", telegram_clean)

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

        print("Kayıt başarılı → Login'e yönlendiriliyor")
        print(request.form)

        return redirect(url_for("login"))

    return render_template("register.html")


# =========================================================
# TELEGRAM DOĞRULAMA FONKSİYONU
# =========================================================

def telegram_verified(username):

    username = username.strip().replace("@", "").lower()

    try:
        with open("telegram_users.json", "r") as f:
            for line in f:
                data = json.loads(line.strip())
                file_username = (data.get("username") or "").strip().lower()

                print("Karşılaştırılıyor:", file_username, "==", username)

                if file_username == username:
                    return True
    except Exception as e:
        print("Telegram verification error:", e)

    return False

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

@app.route("/")
def home():
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":

        username = request.form.get("username")
        password = request.form.get("password")

        user = User.query.filter_by(username=username).first()

        if user and user.password == password:
            login_user(user)

            if user.role == "admin":
                return redirect("/admin-dashboard")

            return redirect("/dashboard")

        return render_template("login.html", error="Hatalı giriş")

    return render_template("login.html")
    
# =========================================================
# DASHBOARD
# =========================================================

@app.route("/admin-dashboard")
@login_required
def admin_dashboard():

    if current_user.role != "admin":
        return redirect("/dashboard")

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
    
@app.route("/admin/update-role/<int:user_id>", methods=["POST"])
@login_required
def update_role(user_id):

    if current_user.role != "admin":
        return redirect("/dashboard")

    user = db.session.get(User, user_id)
    new_role = request.form.get("role")

    if user and new_role:
        user.role = new_role
        db.session.commit()

    return redirect("/admin-dashboard")  

@app.route("/admin/update-limit/<int:user_id>", methods=["POST"])
@login_required
def update_limit(user_id):

    if current_user.role != "admin":
        return redirect("/dashboard")

    user = User.query.get(user_id)

    if user:
        user.daily_limit = int(request.form.get("daily_limit"))
        user.hourly_limit = int(request.form.get("hourly_limit"))
        db.session.commit()

    return redirect("/admin-dashboard")

@app.route("/admin/delete/<int:user_id>")
@login_required
def delete_user(user_id):

    if current_user.role != "admin":
        return redirect("/dashboard")

    user = User.query.get(user_id)

    if user:
        db.session.delete(user)
        db.session.commit()

    return redirect("/admin-dashboard")

@app.route("/admin/logs")
@login_required
def view_logs():

    if current_user.role != "admin":
        return redirect("/dashboard")

    logs = db.session.execute(text("""
        SELECT user_id, query_type, created_at
        FROM query_log
        ORDER BY created_at DESC
        LIMIT 100
    """)).fetchall()

    return render_template("admin_logs.html", logs=logs) 
    
@app.route("/premium")
@login_required
def premium_page():
    return render_template("premium.html")    

# =========================================================
# PREMIUM SATIN AL (DEMO)
# =========================================================
@app.route("/premium/<plan>")
@login_required
def choose_payment(plan):
    print("PLAN GELDİ:", plan)
    return render_template("payment_method.html", plan=plan) 
  
    
@app.route("/premium/confirm/<plan>")
@login_required
def premium_confirm(plan):

    plans = {
        "basic": {"days":30, "daily":500, "hourly":100},
        "pro": {"days":30, "daily":5000, "hourly":500},
        "elite": {"days":30, "daily":99999, "hourly":9999}
    }

    if plan not in plans:
        return redirect("/premium")

    data = plans[plan]

    current_user.role = "premium"
    current_user.plan = plan
    current_user.premium_until = datetime.now() + timedelta(days=data["days"])
    current_user.daily_limit = data["daily"]
    current_user.hourly_limit = data["hourly"]

    db.session.commit()

    return redirect("/dashboard") 

@app.route("/request-premium/<plan>")
@login_required
def request_premium(plan):

    send_admin_message(
        current_user.id,
        current_user.username,
        plan
    )

    return render_template("premium_requested.html")

@app.route("/admin/approve/<int:user_id>/<plan>")
def admin_approve(user_id, plan):

    user = db.session.get(User, user_id)

    plans = {
        "basic": {"days":30, "daily":500, "hourly":100},
        "pro": {"days":30, "daily":5000, "hourly":500},
        "elite": {"days":30, "daily":99999, "hourly":9999}
    }

    if user and plan in plans:
        data = plans[plan]

        user.role = "premium"
        user.plan = plan
        user.premium_until = datetime.now() + timedelta(days=data["days"])
        user.daily_limit = data["daily"]
        user.hourly_limit = data["hourly"]

        db.session.commit()

    return "OK"
    
@app.route("/payment/crypto/<plan>")
@login_required
def crypto_payment(plan):
    wallet_address = "TXXXXXXXWalletAddressHere"
    return render_template(
        "crypto_payment.html",
        plan=plan,
        wallet=wallet_address
    )

@app.route("/payment/iban/<plan>")
@login_required
def iban_payment(plan):
    iban_number = "TR00 0000 0000 0000 0000 0000 00"
    return render_template(
        "iban_payment.html",
        plan=plan,
        iban=iban_number
    )

@app.route("/submit-payment", methods=["POST"])
@login_required
def submit_payment():

    plan = request.form.get("plan")
    method = request.form.get("method")
    proof = request.form.get("txid") or request.form.get("reference")

    text = f"""
💳 Yeni Ödeme Bildirimi

Kullanıcı: {current_user.username}
User ID: {current_user.id}
Plan: {plan}
Yöntem: {method}
Bilgi: {proof}
"""

    send_admin_message(current_user.id, current_user.username, plan)

    # ödeme bilgisi ayrı mesaj
    requests.post(f"https://api.telegram.org/botBOT_TOKEN/sendMessage", data={
        "chat_id": "ADMIN_ID",
        "text": text
    })

    return render_template("payment_sent.html")    

@app.route("/admin/reject/<int:user_id>")
def admin_reject(user_id):
    return "Rejected"   

@app.route("/create-admin")
def create_admin():
    from models import User
    from app import db

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

    total_queries = db.session.execute(text("""
        SELECT COUNT(*)
        FROM query_log
        WHERE user_id = :uid
    """), {"uid": current_user.id}).scalar() or 0

    # Son 7 gün verisi (Grafik için)
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
    
@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

@app.route("/user")
@login_required
def user_dashboard():

    today = datetime.now().date()

    today_count = db.session.execute(text("""
        SELECT COUNT(*) FROM query_log
        WHERE user_id = :uid
        AND DATE(created_at) = :today
    """), {
        "uid": current_user.id,
        "today": today
    }).scalar()

    daily_limit = current_user.daily_limit or 1

    percent = int((today_count / daily_limit) * 100)

    return render_template(
        "user.html",
        user=current_user,
        today_count=today_count,
        daily_limit=daily_limit,
        percent=percent
    )
    
 
# =========================================================
if __name__ == "__main__":   
    app.run()
    
    