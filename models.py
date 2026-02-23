from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()


# ---------------- USER ----------------
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150))
    password = db.Column(db.String(150))
    role = db.Column(db.String(50))

    daily_limit = db.Column(db.Integer, default=50)
    hourly_limit = db.Column(db.Integer, default=20)
    premium_until = db.Column(db.DateTime, nullable=True)
    plan = db.Column(db.String(50), default="free")
    
    from datetime import datetime

class QueryLog(db.Model):
    __tablename__ = "query_log"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    query_type = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ---------------- PRODUCT ----------------
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    title = db.Column(db.String(200))
    price = db.Column(db.String(100))
    description = db.Column(db.Text)

    seller_name = db.Column(db.String(150))
    seller_phone = db.Column(db.String(50))

    city = db.Column(db.String(100))
    category = db.Column(db.String(150))

    iban = db.Column(db.String(50))
    site_type = db.Column(db.String(50))

    status = db.Column(db.String(20), default="aktif")

    image = db.Column(db.String(300))

    features = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    image = db.Column(db.String(255))
    



# ---------------- LINK ----------------
class Link(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(255))
    product_id = db.Column(db.Integer)
    user_id = db.Column(db.Integer)
    expires_at = db.Column(db.DateTime)
    site_type = db.Column(db.String(100))  # 👈 EKLE





