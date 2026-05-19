"""
Finance Expense Tracker — Flask application entry point.
Keeps routes readable; database access is grouped in helpers for clarity.
"""

import os
from datetime import date, datetime
from functools import wraps

import pymysql
from dotenv import load_dotenv
from flask import (
    Flask,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from pymysql.cursors import DictCursor
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-change-me-in-production")
app.config["MYSQL_HOST"] = os.environ.get("MYSQL_HOST", "localhost")
app.config["MYSQL_USER"] = os.environ.get("MYSQL_USER", "root")
app.config["MYSQL_PASSWORD"] = os.environ.get("MYSQL_PASSWORD", "")
app.config["MYSQL_DB"] = os.environ.get("MYSQL_DB", "finance_tracker")


def get_connection():
    return pymysql.connect(
        host=app.config["MYSQL_HOST"],
        user=app.config["MYSQL_USER"],
        password=app.config["MYSQL_PASSWORD"],
        database=app.config["MYSQL_DB"],
        cursorclass=DictCursor,
        charset="utf8mb4",
    )


def get_db():
    if "db" not in g:
        g.db = get_connection()
    return g.db


@app.teardown_appcontext
def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped


def fetch_user_totals(user_id):
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total FROM income WHERE user_id = %s",
            (user_id,),
        )
        total_income = float(cur.fetchone()["total"])
        cur.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total FROM expenses WHERE user_id = %s",
            (user_id,),
        )
        total_expense = float(cur.fetchone()["total"])
    balance = total_income - total_expense
    return balance, total_income, total_expense


def fetch_recent_transactions(user_id, limit=12):
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT 'expense' AS type, id, title AS label, amount, category AS extra,
                   expense_date AS tx_date, created_at
            FROM expenses WHERE user_id = %s
            UNION ALL
            SELECT 'income' AS type, id, source AS label, amount, NULL AS extra,
                   income_date AS tx_date, created_at
            FROM income WHERE user_id = %s
            ORDER BY tx_date DESC, created_at DESC
            LIMIT %s
            """,
            (user_id, user_id, limit),
        )
        return cur.fetchall()


def expense_category_breakdown(user_id):
    """Return [{category, total}] for pie chart.

    Enforces a fixed set of dashboard categories; everything else rolls into "Other".
    """
    allowed = ("Food", "Shopping", "Travel", "Bills", "Entertainment", "Education")
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT
              CASE
                WHEN category IN ('Food','Shopping','Travel','Bills','Entertainment','Education') THEN category
                ELSE 'Other'
              END AS category,
              COALESCE(SUM(amount), 0) AS total
            FROM expenses
            WHERE user_id = %s
            GROUP BY 1
            ORDER BY total DESC
            """,
            (user_id,),
        )
        rows = cur.fetchall()
    mapped = [{"category": r["category"], "total": float(r["total"])} for r in rows]

    # Ensure consistent ordering / presence for the fixed categories (even if 0),
    # then include Other at the end if present.
    totals = {r["category"]: r["total"] for r in mapped}
    ordered = [{"category": c, "total": float(totals.get(c, 0.0))} for c in allowed]
    if "Other" in totals:
        ordered.append({"category": "Other", "total": float(totals["Other"])})
    return ordered


def bucket_with_largest_total(category_breakdown):
    """Return category name with the highest spend, or None."""
    if not category_breakdown:
        return None
    nonzero = [r for r in category_breakdown if float(r.get("total") or 0) > 0]
    if not nonzero:
        return None
    return max(nonzero, key=lambda r: float(r["total"]))["category"]


def expense_category_breakdown_month(user_id, year, month):
    """Return [{category, total}] for a specific month (used for insights)."""
    allowed = ("Food", "Shopping", "Travel", "Bills", "Entertainment", "Education")
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT
              CASE
                WHEN category IN ('Food','Shopping','Travel','Bills','Entertainment','Education') THEN category
                ELSE 'Other'
              END AS category,
              COALESCE(SUM(amount), 0) AS total
            FROM expenses
            WHERE user_id = %s AND YEAR(expense_date) = %s AND MONTH(expense_date) = %s
            GROUP BY 1
            ORDER BY total DESC
            """,
            (user_id, year, month),
        )
        rows = cur.fetchall()
    mapped = [{"category": r["category"], "total": float(r["total"])} for r in rows]
    totals = {r["category"]: r["total"] for r in mapped}
    ordered = [{"category": c, "total": float(totals.get(c, 0.0))} for c in allowed]
    if "Other" in totals:
        ordered.append({"category": "Other", "total": float(totals["Other"])})
    # For insight comparisons we want descending meaningful categories:
    ordered.sort(key=lambda r: r["total"], reverse=True)
    return ordered


def last_n_months_overview(user_id, months=12):
    """Return last N months [{label, year, month, income, expense}] ending current month."""
    today = date.today()
    y = today.year
    m = today.month

    keys = []
    for i in range(months - 1, -1, -1):
        mm = m - i
        yy = y
        while mm <= 0:
            mm += 12
            yy -= 1
        keys.append((yy, mm))

    db = get_db()
    income_map = {}
    expense_map = {}

    with db.cursor() as cur:
        cur.execute(
            """
            SELECT YEAR(income_date) AS y, MONTH(income_date) AS m, COALESCE(SUM(amount), 0) AS total
            FROM income
            WHERE user_id = %s
              AND income_date >= DATE_SUB(CURDATE(), INTERVAL %s MONTH)
            GROUP BY YEAR(income_date), MONTH(income_date)
            """,
            (user_id, months + 1),
        )
        for r in cur.fetchall():
            income_map[(int(r["y"]), int(r["m"]))] = float(r["total"])

        cur.execute(
            """
            SELECT YEAR(expense_date) AS y, MONTH(expense_date) AS m, COALESCE(SUM(amount), 0) AS total
            FROM expenses
            WHERE user_id = %s
              AND expense_date >= DATE_SUB(CURDATE(), INTERVAL %s MONTH)
            GROUP BY YEAR(expense_date), MONTH(expense_date)
            """,
            (user_id, months + 1),
        )
        for r in cur.fetchall():
            expense_map[(int(r["y"]), int(r["m"]))] = float(r["total"])

    overview = []
    for (yy, mm) in keys:
        overview.append(
            {
                "year": yy,
                "month": mm,
                "label": datetime(yy, mm, 1).strftime("%b"),
                "income": income_map.get((yy, mm), 0.0),
                "expense": expense_map.get((yy, mm), 0.0),
            }
        )
    return overview


def month_totals(user_id, year, month):
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT COALESCE(SUM(amount), 0) AS total
            FROM income
            WHERE user_id=%s AND YEAR(income_date)=%s AND MONTH(income_date)=%s
            """,
            (user_id, year, month),
        )
        inc = float(cur.fetchone()["total"])
        cur.execute(
            """
            SELECT COALESCE(SUM(amount), 0) AS total
            FROM expenses
            WHERE user_id=%s AND YEAR(expense_date)=%s AND MONTH(expense_date)=%s
            """,
            (user_id, year, month),
        )
        exp = float(cur.fetchone()["total"])
    return inc, exp


def expense_meta_this_month(user_id, year, month):
    """Return (tx_count, most_used_category, largest_expense_amount)."""
    db = get_db()
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*) AS c
            FROM expenses
            WHERE user_id=%s AND YEAR(expense_date)=%s AND MONTH(expense_date)=%s
            """,
            (user_id, year, month),
        )
        count_exp = int(cur.fetchone()["c"])

        cur.execute(
            """
            SELECT category, COUNT(*) AS c
            FROM expenses
            WHERE user_id=%s AND YEAR(expense_date)=%s AND MONTH(expense_date)=%s
            GROUP BY category
            ORDER BY c DESC
            LIMIT 1
            """,
            (user_id, year, month),
        )
        row = cur.fetchone()
        most_used = row["category"] if row else None

        cur.execute(
            """
            SELECT COALESCE(MAX(amount), 0) AS max_amount
            FROM expenses
            WHERE user_id=%s AND YEAR(expense_date)=%s AND MONTH(expense_date)=%s
            """,
            (user_id, year, month),
        )
        largest = float(cur.fetchone()["max_amount"])

    return count_exp, most_used, largest


def safe_percent_change(current, previous):
    if previous is None or previous == 0:
        return None
    return ((current - previous) / previous) * 100.0


def build_spending_insights(user_id):
    """Small insight tiles based on this vs last month. Returns list of {title, detail, tone}."""
    today = date.today()
    y, m = today.year, today.month
    prev_y, prev_m = (y - 1, 12) if m == 1 else (y, m - 1)

    inc_now, exp_now = month_totals(user_id, y, m)
    inc_prev, exp_prev = month_totals(user_id, prev_y, prev_m)

    insights = []
    delta_exp = safe_percent_change(exp_now, exp_prev)
    if delta_exp is not None:
        tone = "neutral"
        if delta_exp > 5:
            tone = "warn"
        elif delta_exp < -5:
            tone = "good"
        insights.append(
            {
                "title": "Spending trend",
                "detail": f"Expenses changed by {delta_exp:.0f}% vs last month.",
                "tone": tone,
            }
        )

    savings_now = inc_now - exp_now
    savings_prev = inc_prev - exp_prev
    delta_sav = safe_percent_change(savings_now, savings_prev)
    if delta_sav is not None:
        tone = "good" if delta_sav > 5 else "neutral"
        insights.append(
            {
                "title": "Savings",
                "detail": f"Savings changed by {delta_sav:.0f}% vs last month.",
                "tone": tone,
            }
        )

    by_cat_now = expense_category_breakdown_month(user_id, y, m)
    by_cat_prev = {r["category"]: r["total"] for r in expense_category_breakdown_month(user_id, prev_y, prev_m)}
    if by_cat_now:
        top = by_cat_now[0]
        insights.append(
            {
                "title": "Highest category",
                "detail": f"{top['category']} is highest this month.",
                "tone": "neutral",
            }
        )
        if top["category"] in by_cat_prev:
            d = safe_percent_change(top["total"], by_cat_prev.get(top["category"], 0))
            if d is not None:
                tone = "warn" if d > 8 else ("good" if d < -8 else "neutral")
                insights.append(
                    {
                        "title": f"{top['category']} change",
                        "detail": f"{top['category']} changed by {d:.0f}% vs last month.",
                        "tone": tone,
                    }
                )

    if not insights:
        insights = [
            {"title": "Tip", "detail": "Add a few transactions to unlock insights.", "tone": "neutral"}
        ]
    return insights[:6]

def monthly_totals_current_year(user_id):
    """Return list of {month, income, expense} for charts / overview (current year)."""
    db = get_db()
    year = date.today().year
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT MONTH(income_date) AS m, COALESCE(SUM(amount), 0) AS total
            FROM income
            WHERE user_id = %s AND YEAR(income_date) = %s
            GROUP BY MONTH(income_date)
            """,
            (user_id, year),
        )
        income_by_month = {int(r["m"]): float(r["total"]) for r in cur.fetchall()}
        cur.execute(
            """
            SELECT MONTH(expense_date) AS m, COALESCE(SUM(amount), 0) AS total
            FROM expenses
            WHERE user_id = %s AND YEAR(expense_date) = %s
            GROUP BY MONTH(expense_date)
            """,
            (user_id, year),
        )
        expense_by_month = {int(r["m"]): float(r["total"]) for r in cur.fetchall()}

    overview = []
    for m in range(1, 13):
        overview.append(
            {
                "month": m,
                "month_label": datetime(year, m, 1).strftime("%b"),
                "income": income_by_month.get(m, 0.0),
                "expense": expense_by_month.get(m, 0.0),
            }
        )
    return overview


@app.route("/")
def index():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/healthz")
def healthz():
    return {"status": "ok"}


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm_password") or ""

        if not username or not email or not password:
            flash("All fields are required.", "error")
            return render_template("register.html")

        if password != confirm:
            flash("Passwords do not match.", "error")
            return render_template("register.html")

        if len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
            return render_template("register.html")

        hashed = generate_password_hash(password)
        try:
            db = get_db()
            with db.cursor() as cur:
                cur.execute(
                    "INSERT INTO users (username, email, password) VALUES (%s, %s, %s)",
                    (username, email, hashed),
                )
            db.commit()
            flash("Account created. You can log in now.", "success")
            return redirect(url_for("login"))
        except pymysql.err.IntegrityError:
            flash("Username or email already registered.", "error")
        except pymysql.err.OperationalError:
            flash(
                "Could not connect to the database. Check MySQL is running and .env settings.",
                "error",
            )

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""

        if not username or not password:
            flash("Enter username and password.", "error")
            return render_template("login.html")

        try:
            db = get_db()
            with db.cursor() as cur:
                cur.execute(
                    "SELECT id, username, password FROM users WHERE username = %s",
                    (username,),
                )
                row = cur.fetchone()
        except pymysql.err.OperationalError:
            flash("Database connection failed. Verify MySQL and credentials.", "error")
            return render_template("login.html")

        if row and check_password_hash(row["password"], password):
            session.clear()
            session["user_id"] = row["id"]
            session["username"] = row["username"]
            flash("Welcome back!", "success")
            return redirect(url_for("dashboard"))

        flash("Invalid username or password.", "error")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    uid = session["user_id"]
    balance, total_income, total_expense = fetch_user_totals(uid)
    recent = fetch_recent_transactions(uid, limit=10)
    monthly = last_n_months_overview(uid, months=12)
    category_breakdown = expense_category_breakdown(uid)

    today = date.today()
    this_inc, this_exp = month_totals(uid, today.year, today.month)
    monthly_savings = this_inc - this_exp

    highest_category = bucket_with_largest_total(category_breakdown)
    avg_monthly_spend = (total_expense / 12.0) if total_expense > 0 else 0.0

    tx_count_month, most_used_cat, largest_expense = expense_meta_this_month(uid, today.year, today.month)
    days_so_far = max(today.day, 1)
    avg_daily_spend = (this_exp / days_so_far) if this_exp > 0 else 0.0

    monthly_budget = float(os.environ.get("MONTHLY_BUDGET", "2000") or 2000)
    budget_spent_pct = min(100.0, (this_exp / monthly_budget * 100.0)) if monthly_budget > 0 else 0.0
    budget_remaining = max(0.0, monthly_budget - this_exp)

    savings_goal = float(os.environ.get("SAVINGS_GOAL", "5000") or 5000)
    savings_goal_pct = min(100.0, (monthly_savings / savings_goal * 100.0)) if savings_goal > 0 else 0.0

    insights = build_spending_insights(uid)

    has_data = (total_income > 0) or (total_expense > 0)
    if not has_data:
        # Professional empty-state sample data to keep dashboard balanced.
        monthly = [
            {"year": today.year, "month": ((today.month - 5 - 1) % 12) + 1, "label": "Jan", "income": 3200, "expense": 2100},
            {"year": today.year, "month": ((today.month - 4 - 1) % 12) + 1, "label": "Feb", "income": 3300, "expense": 1900},
            {"year": today.year, "month": ((today.month - 3 - 1) % 12) + 1, "label": "Mar", "income": 3250, "expense": 2300},
            {"year": today.year, "month": ((today.month - 2 - 1) % 12) + 1, "label": "Apr", "income": 3400, "expense": 2200},
            {"year": today.year, "month": ((today.month - 1 - 1) % 12) + 1, "label": "May", "income": 3350, "expense": 2050},
            {"year": today.year, "month": today.month, "label": datetime(today.year, today.month, 1).strftime("%b"), "income": 3450, "expense": 2150},
        ]
        category_breakdown = [
            {"category": "Food", "total": 520},
            {"category": "Bills", "total": 610},
            {"category": "Shopping", "total": 280},
            {"category": "Travel", "total": 190},
            {"category": "Entertainment", "total": 160},
            {"category": "Education", "total": 120},
        ]
        insights = [
            {"title": "Food", "detail": "Food expenses increased by 12%.", "tone": "warn"},
            {"title": "Savings", "detail": "You saved more this month.", "tone": "good"},
            {"title": "Travel", "detail": "Travel spending decreased.", "tone": "good"},
            {"title": "Routine", "detail": "Highest spending day: Friday.", "tone": "neutral"},
        ]

    return render_template(
        "dashboard.html",
        balance=balance,
        total_income=total_income,
        total_expense=total_expense,
        recent_transactions=recent,
        monthly_overview=monthly,
        category_breakdown=category_breakdown,
        monthly_savings=monthly_savings,
        highest_category=highest_category,
        avg_monthly_spend=avg_monthly_spend,
        tx_count_month=tx_count_month,
        most_used_cat=most_used_cat,
        largest_expense=largest_expense,
        avg_daily_spend=avg_daily_spend,
        monthly_budget=monthly_budget,
        budget_spent_pct=budget_spent_pct,
        budget_remaining=budget_remaining,
        savings_goal=savings_goal,
        savings_goal_pct=savings_goal_pct,
        insights=insights,
        has_data=has_data,
    )


@app.route("/expenses", methods=["GET", "POST"])
@login_required
def expenses():
    uid = session["user_id"]
    db = get_db()

    if request.method == "POST":
        action = request.form.get("action")
        if action == "add":
            title = (request.form.get("title") or "").strip()
            try:
                amount = float(request.form.get("amount") or 0)
            except ValueError:
                amount = 0
            category = (request.form.get("category") or "").strip() or "Other"
            expense_date = request.form.get("expense_date") or str(date.today())

            if not title or amount <= 0:
                flash("Title and a positive amount are required.", "error")
            else:
                with db.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO expenses (user_id, title, amount, category, expense_date)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (uid, title, amount, category, expense_date),
                    )
                db.commit()
                flash("Expense added.", "success")
        elif action == "update":
            eid = request.form.get("expense_id")
            title = (request.form.get("title") or "").strip()
            try:
                amount = float(request.form.get("amount") or 0)
            except ValueError:
                amount = 0
            category = (request.form.get("category") or "").strip() or "Other"
            expense_date = request.form.get("expense_date") or str(date.today())
            if eid and title and amount > 0:
                with db.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE expenses SET title=%s, amount=%s, category=%s, expense_date=%s
                        WHERE id=%s AND user_id=%s
                        """,
                        (title, amount, category, expense_date, eid, uid),
                    )
                db.commit()
                flash("Expense updated.", "success")
            else:
                flash("Could not update expense.", "error")
        elif action == "delete":
            eid = request.form.get("expense_id")
            if eid:
                with db.cursor() as cur:
                    cur.execute(
                        "DELETE FROM expenses WHERE id=%s AND user_id=%s",
                        (eid, uid),
                    )
                db.commit()
                flash("Expense deleted.", "success")

        return redirect(url_for("expenses"))

    with db.cursor() as cur:
        cur.execute(
            """
            SELECT id, title, amount, category, expense_date
            FROM expenses WHERE user_id = %s ORDER BY expense_date DESC, id DESC
            """,
            (uid,),
        )
        expense_rows = cur.fetchall()

    categories = [
        "Food",
        "Transport",
        "Entertainment",
        "Bills",
        "Healthcare",
        "Shopping",
        "Other",
    ]
    return render_template(
        "expenses.html",
        expenses=expense_rows,
        categories=categories,
    )


@app.route("/income", methods=["GET", "POST"])
@login_required
def income():
    uid = session["user_id"]
    db = get_db()

    if request.method == "POST":
        source = (request.form.get("source") or "").strip()
        try:
            amount = float(request.form.get("amount") or 0)
        except ValueError:
            amount = 0
        income_date = request.form.get("income_date") or str(date.today())

        if not source or amount <= 0:
            flash("Source and a positive amount are required.", "error")
        else:
            with db.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO income (user_id, source, amount, income_date)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (uid, source, amount, income_date),
                )
            db.commit()
            flash("Income recorded.", "success")
        return redirect(url_for("income"))

    with db.cursor() as cur:
        cur.execute(
            """
            SELECT id, source, amount, income_date
            FROM income WHERE user_id = %s ORDER BY income_date DESC, id DESC
            """,
            (uid,),
        )
        income_rows = cur.fetchall()

    return render_template("income.html", income_rows=income_rows)


@app.route("/analytics")
@login_required
def analytics():
    uid = session["user_id"]
    balance, total_income, total_expense = fetch_user_totals(uid)
    monthly = last_n_months_overview(uid, months=12)
    category_breakdown = expense_category_breakdown(uid)

    today = date.today()
    this_inc, this_exp = month_totals(uid, today.year, today.month)
    monthly_savings = this_inc - this_exp
    highest_category = bucket_with_largest_total(category_breakdown)
    avg_monthly_spend = (total_expense / 12.0) if total_expense > 0 else 0.0

    tx_count_month, most_used_cat, largest_expense = expense_meta_this_month(uid, today.year, today.month)
    days_so_far = max(today.day, 1)
    avg_daily_spend = (this_exp / days_so_far) if this_exp > 0 else 0.0

    monthly_budget = float(os.environ.get("MONTHLY_BUDGET", "2000") or 2000)
    budget_spent_pct = min(100.0, (this_exp / monthly_budget * 100.0)) if monthly_budget > 0 else 0.0
    budget_remaining = max(0.0, monthly_budget - this_exp)

    savings_goal = float(os.environ.get("SAVINGS_GOAL", "5000") or 5000)
    savings_goal_pct = min(100.0, (monthly_savings / savings_goal * 100.0)) if savings_goal > 0 else 0.0

    insights = build_spending_insights(uid)

    has_data = (total_income > 0) or (total_expense > 0)
    if not has_data:
        monthly = [
            {"year": today.year, "month": ((today.month - 5 - 1) % 12) + 1, "label": "Jan", "income": 3200, "expense": 2100},
            {"year": today.year, "month": ((today.month - 4 - 1) % 12) + 1, "label": "Feb", "income": 3300, "expense": 1900},
            {"year": today.year, "month": ((today.month - 3 - 1) % 12) + 1, "label": "Mar", "income": 3250, "expense": 2300},
            {"year": today.year, "month": ((today.month - 2 - 1) % 12) + 1, "label": "Apr", "income": 3400, "expense": 2200},
            {"year": today.year, "month": ((today.month - 1 - 1) % 12) + 1, "label": "May", "income": 3350, "expense": 2050},
            {"year": today.year, "month": today.month, "label": datetime(today.year, today.month, 1).strftime("%b"), "income": 3450, "expense": 2150},
        ]
        category_breakdown = [
            {"category": "Food", "total": 520},
            {"category": "Shopping", "total": 280},
            {"category": "Travel", "total": 190},
            {"category": "Bills", "total": 610},
            {"category": "Entertainment", "total": 160},
            {"category": "Education", "total": 120},
        ]
        insights = [
            {"title": "Food", "detail": "Food expenses increased by 12%.", "tone": "warn"},
            {"title": "Savings", "detail": "You saved more this month.", "tone": "good"},
            {"title": "Travel", "detail": "Travel spending decreased.", "tone": "good"},
            {"title": "Routine", "detail": "Highest spending day: Friday.", "tone": "neutral"},
        ]

    return render_template(
        "analytics.html",
        balance=balance,
        total_income=total_income,
        total_expense=total_expense,
        monthly_overview=monthly,
        category_breakdown=category_breakdown,
        monthly_savings=monthly_savings,
        highest_category=highest_category,
        avg_monthly_spend=avg_monthly_spend,
        tx_count_month=tx_count_month,
        most_used_cat=most_used_cat,
        largest_expense=largest_expense,
        avg_daily_spend=avg_daily_spend,
        monthly_budget=monthly_budget,
        budget_spent_pct=budget_spent_pct,
        budget_remaining=budget_remaining,
        savings_goal=savings_goal,
        savings_goal_pct=savings_goal_pct,
        insights=insights,
        has_data=has_data,
    )


@app.route("/reports")
@login_required
def reports():
    """Placeholder for exports / printable summaries."""
    return render_template("reports.html")


@app.route("/settings")
@login_required
def settings():
    return render_template("settings.html")


@app.context_processor
def inject_globals():
    return {
        "current_year": date.today().year,
        "expense_categories": [
            "Food",
            "Transport",
            "Entertainment",
            "Bills",
            "Healthcare",
            "Shopping",
            "Other",
        ],
    }


if __name__ == "__main__":
    app.run(
        debug=os.environ.get("FLASK_DEBUG") == "1",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
    )
