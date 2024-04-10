import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/", methods=["GET"])
@login_required
def index():
    """Show portfolio of stocks"""
    stocks = []
    rows = db.execute(
        "SELECT symbol, SUM(CASE WHEN type = 'buy' THEN shares ELSE 0 END) - SUM(CASE WHEN type = 'sell' THEN shares ELSE 0 END) AS total_shares FROM purchases WHERE user_id = ? GROUP BY symbol HAVING total_shares > 0",
        session["user_id"]
    )
    grand_total = 0
    cash = db.execute(
        "SELECT cash FROM users WHERE id = ?",
        session["user_id"]
    )[0]["cash"]
    for row in rows:
        data = lookup(row["symbol"])
        price = data.get("price")
        name = data.get("name")
        total = price * int(row["total_shares"])
        stocks.append({
            "symbol": row["symbol"],
            "name": name,
            "shares": row["total_shares"],
            "price": usd(price),
            "total": usd(total)
        })
        grand_total += total

    return render_template("index.html", stocks=stocks, grand_total=usd(grand_total + cash), cash=usd(cash))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        if not request.form.get("symbol"):
            return apology("Fill the symbol", 403)
        if not request.form.get("shares"):
            return apology("Fill the number of shares", 403)

        data = lookup(request.form.get("symbol"))

        if not data:
            return apology("Not Valid Symbol", 403)

        rows = db.execute(
            "SELECT * FROM users WHERE id = ?",
            session["user_id"]
        )
        cash = rows[0]["cash"]
        try:
            _shares = int(request.form.get("shares"))
        except ValueError:
            return apology("Non valid type", 400)

        if _shares <= 0:
            return apology("Non valid shares", 400)

        try:
            total_price = data.get("price") * int(request.form.get("shares"))
        except ValueError:
            return apology("Not valid shares", 403)

        if cash < total_price:
            return apology("Not enough money to purchase", 403)

        db.execute(
            "UPDATE users SET cash = ? WHERE id = ?",
            cash - total_price, session["user_id"]
        )

        db.execute(
            "INSERT INTO purchases (user_id, symbol, shares, price, type) VALUES (?, ?, ?, ?, ?)",
            session["user_id"],
            request.form.get("symbol"),
            request.form.get("shares"),
            float(data.get("price")),
            "buy"
        )
        return redirect("/")

    return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    transactions = db.execute(
        "SELECT * FROM purchases WHERE user_id = ? ORDER BY timestamp DESC",
        session["user_id"]
    )
    for tr in transactions:
        tr["price"] = usd(tr["price"])

    return render_template("history.html", transactions=transactions)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?",
                          request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        quotes = lookup(symbol)
        if not quotes:
            return apology("Not valid symbol", 403)
        quotes["price"] = usd(quotes["price"])
        return render_template("quoted.html", quotes=quotes)
    return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():

    session.clear()

    """Register user"""
    if request.method == "POST":

        if not request.form.get("username"):
            return apology("must provide username", 403)

        elif not request.form.get("password"):
            return apology("must provide password", 403)

        elif not request.form.get("confirmation"):
            return apology("must provide confirmation to password", 403)

        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("must be match confirmation password", 403)

        rows = db.execute(
            "SELECT COUNT(*) AS cnt FROM users WHERE username = ?", request.form.get("username"))

        if (rows[0]["cnt"] > 0):
            return apology("username already exists", 403)

        db.execute(
            "INSERT INTO users (username, hash) VALUES (?, ?)",
            request.form.get("username"), generate_password_hash(
                request.form.get("password"))
        )
        query = db.execute(
            "SELECT id FROM users WHERE username=?",
            request.form.get("username")
        )

        user_id = query[0]["id"]
        session["user_id"] = user_id
        return redirect("/")

    return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    rows = db.execute(
        "SELECT symbol, SUM(CASE WHEN type = 'buy' THEN shares ELSE 0 END) - SUM(CASE WHEN type = 'sell' THEN shares ELSE 0 END) AS total_shares FROM purchases WHERE user_id = ? GROUP BY symbol HAVING total_shares > 0",
        session["user_id"]
    )
    if request.method == "POST":
        if not request.form.get("symbol"):
            return apology("Fill the symbol", 403)

        if not request.form.get("shares"):
            return apology("Fill the number of shares", 403)

        try:
            shares = int(request.form.get("shares"))
        except ValueError:
            return apology("Not valid shares (should be positive int)", 403)

        selected_stock = next(
            (item for item in rows if item["symbol"] == request.form.get("symbol")), None)

        if not selected_stock:
            return apology("Not valid symbol", 403)

        if shares > selected_stock["total_shares"]:
            return apology("You dont have enough shares", 403)

        data = lookup(request.form.get("symbol"))
        try:
            total_price = data.get("price") * int(request.form.get("shares"))
        except ValueError:
            return apology("Not valid shares", 403)

        cash = db.execute(
            "SELECT cash FROM users WHERE id = ?",
            session["user_id"]
        )[0]["cash"]

        db.execute(
            "UPDATE users SET cash = ? WHERE id = ?",
            cash + total_price, session["user_id"]
        )
        db.execute(
            "INSERT INTO purchases (user_id, symbol, shares, price, type) VALUES (?, ?, ?, ?, ?)",
            session["user_id"],
            request.form.get("symbol"),
            request.form.get("shares"),
            data.get("price"),
            "sell"
        )
        return redirect("/")

    return render_template("sell.html", symbols=rows)
