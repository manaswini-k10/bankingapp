import os
import datetime as dt
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash, check_password_hash

DB_URL = os.environ.get("DATABASE_URL", "sqlite:///bank.db")

app = Flask(__name__)
app.secret_key = os.environ.get("APP_SECRET_KEY", "dev-secret-change-me")
app.config["SQLALCHEMY_DATABASE_URI"] = DB_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# ---------- Models ----------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    accounts = db.relationship("Account", backref="user", lazy=True)

class Account(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    name = db.Column(db.String(32), nullable=False)   # e.g., "Checking", "Savings"
    balance = db.Column(db.Integer, default=0)        # store cents as int

class Tx(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=dt.datetime.utcnow)
    from_account_id = db.Column(db.Integer, db.ForeignKey("account.id"), nullable=True)
    to_account_id = db.Column(db.Integer, db.ForeignKey("account.id"), nullable=True)
    amount = db.Column(db.Integer, nullable=False)  # cents
    memo = db.Column(db.String(140), default="")

# ---------- Helpers ----------
def seed_demo():
    # Only seed if missing; don’t crash if a race inserts first.
    if not User.query.filter_by(username="alice").first():
        try:
            mkuser("alice", 150_000, 20_000)  # $1,500.00 / $200.00
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
    if not User.query.filter_by(username="bob").first():
        try:
            mkuser("bob",   80_000, 10_000)   # $800.00 / $100.00
            db.session.commit()
        except IntegrityError:
            db.session.rollback()

with app.app_context():
    db.create_all()
    seed_demo()

def cents_to_str(cents):
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    return f"{sign}${cents//100:,}.{cents%100:02d}"

def require_login():
    return "user_id" in session

# ---------- Routes ----------
@app.route("/healthz")
def healthz():
    return "ok", 200

@app.route("/", methods=["GET"])
def home():
    return render_template("registration.html")

@app.route("/start", methods=["POST"])
def start():
    username = (request.form.get("username") or "").strip().lower()
    password = request.form.get("password") or ""
    if not username or not password:
        flash("Enter username and password.")
        return redirect(url_for("home"))
    user = User.query.filter_by(username=username).first()
    if not user or not check_password_hash(user.password_hash, password):
        flash("Invalid credentials. (Hint for demo users: password is 'password')")
        return redirect(url_for("home"))
    session.clear()
    session["user_id"] = user.id
    session["username"] = user.username
    return redirect(url_for("dashboard"))

@app.route("/game", methods=["GET"])  # keeping path name used earlier; this is the dashboard
def dashboard():
    if not require_login():
        return redirect(url_for("home"))
    user = User.query.get(session["user_id"])
    accts = Account.query.filter_by(user_id=user.id).all()
    acct_data = [{"id": a.id, "name": a.name, "balance": cents_to_str(a.balance)} for a in accts]
    # recent transactions involving user's accounts
    acct_ids = [a.id for a in accts]
    txs = (Tx.query
           .filter((Tx.from_account_id.in_(acct_ids)) | (Tx.to_account_id.in_(acct_ids)))
           .order_by(Tx.timestamp.desc())
           .limit(10)
           .all())
    def label(tx):
        direction = "IN" if tx.to_account_id in acct_ids else "OUT"
        return {
            "when": tx.timestamp.strftime("%Y-%m-%d %H:%M"),
            "direction": direction,
            "amount": cents_to_str(tx.amount),
            "memo": tx.memo or "",
        }
    return render_template("greetings.html",
                           name=session["username"],
                           accounts=acct_data,
                           txs=[label(t) for t in txs])

@app.route("/transfer", methods=["POST"])
def transfer():
    if not require_login():
        return jsonify({"error": "not logged in"}), 401

    src_id = int(request.form.get("fromAccount"))
    dst_user = (request.form.get("toUser") or "").strip().lower()
    dst_acct_name = (request.form.get("toAccount") or "").strip()
    memo = (request.form.get("memo") or "").strip()
    try:
        amount_cents = int(float(request.form.get("amount")) * 100)
    except Exception:
        return jsonify({"error": "invalid amount"}), 400
    if amount_cents <= 0:
        return jsonify({"error": "amount must be positive"}), 400

    src = Account.query.get(src_id)
    if not src or src.user_id != session["user_id"]:
        return jsonify({"error": "invalid source account"}), 400

    # find destination
    dst_user_obj = User.query.filter_by(username=dst_user).first()
    if not dst_user_obj:
        return jsonify({"error": "destination user not found"}), 404
    dst = Account.query.filter_by(user_id=dst_user_obj.id, name=dst_acct_name).first()
    if not dst:
        return jsonify({"error": "destination account not found"}), 404

    if src.balance < amount_cents:
        return jsonify({"error": "insufficient funds"}), 400

    # apply transfer
    src.balance -= amount_cents
    dst.balance += amount_cents
    tx = Tx(from_account_id=src.id, to_account_id=dst.id, amount=amount_cents, memo=memo)
    db.session.add(tx)
    db.session.commit()
    return jsonify({
        "ok": True,
        "srcBalance": cents_to_str(src.balance),
        "dstBalance": cents_to_str(dst.balance),
    })

@app.route("/reset", methods=["POST"])
def reset():
    session.clear()
    return redirect(url_for("home"))

# ---------- App start ----------
with app.app_context():
    db.create_all()
    seed_demo()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)



