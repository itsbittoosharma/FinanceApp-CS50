import datetime
import os
from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
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

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    cash = db.execute("SELECT * FROM users WHERE id=?", session["user_id"])[0]["cash"]
    userStocks = db.execute(
        "SELECT symbol, SUM(shares) AS shares FROM transactions WHERE id=? GROUP BY symbol",
        session["user_id"],
    )
    currPriceOfStocks = {}
    currHoldings = cash

    for stock in userStocks:
        currPriceOfStocks[stock["symbol"]] = lookup(stock["symbol"])["price"]
        currHoldings += stock["shares"] * currPriceOfStocks[stock["symbol"]]

    """Show portfolio of stocks"""
    return render_template(
        "index.html",
        cash=cash,
        currHoldings=currHoldings,
        userStocks=userStocks,
        currPriceOfStocks=currPriceOfStocks,
    )


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "GET":
        return render_template("buy.html", db=db)
    if request.method == "POST":
        stock_info = lookup(request.form.get("symbol"))
        if stock_info == None:
            return apology("Invalid Symbol")
        try:
            stocks = float(request.form.get("shares"))
            if stocks < 0:
                return apology("Invalid no. of stocks requested")
            elif not stocks.is_integer():
                return apology("Invalid no. of stocks requested")
        except:
            return apology("Enter a valid number of shares to buy")

        currBalance = db.execute(
            "SELECT cash FROM users WHERE id=?", session["user_id"]
        )[0]["cash"]
        currStockPrice = stock_info["price"]
        if currStockPrice * int(request.form.get("shares")) > currBalance:
            return apology(f"Insufficient Balance")
        db.execute(
            "INSERT INTO transactions VALUES(?,?,?,?,?,?)",
            session["user_id"],
            stock_info["symbol"].upper(),
            "buy",
            float(request.form.get("shares")),
            stock_info["price"],
            datetime.datetime.now(),
        )
        db.execute(
            "UPDATE users SET cash=? WHERE id=?",
            currBalance - stock_info["price"] * int(request.form.get("shares")),
            session["user_id"],
        )

        return redirect("/")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    return apology("TODO")


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
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html", db=db)


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
    if request.method == "GET":
        return render_template("quote.html", db=db)
    if request.method == "POST":
        symbol = request.form.get("symbol")
        quote = lookup(symbol)
        if quote == None:
            return apology("Symbol not found", 404)
        else:
            return render_template("quoted.html", quote=quote, db=db)


@app.route("/register", methods=["GET", "POST"])
def register():
    session.clear()
    """Register user"""
    if request.method == "POST":
        if not request.form.get("username"):
            return apology("You must provide username", 403)
        elif not request.form.get("password"):
            return apology("You must provide a password", 403)
        elif not request.form.get("confirmation"):
            return apology("Please confirm your password", 403)
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("Passwords do not match", 403)
        elif len(request.form.get("password")) < 8:
            return apology("Password should be greater than 8 characters")
        elif (
            len(
                db.execute(
                    "SELECT * FROM users WHERE username = ?",
                    request.form.get("username"),
                )
            )
            != 0
        ):
            return apology("Username already exists")

        db.execute(
            "INSERT INTO users (username,hash) VALUES(?,?)",
            request.form.get("username"),
            generate_password_hash(request.form.get("password")),
        )

        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        session["user_id"] = rows[0]["id"]

        return redirect("/")

    else:
        return render_template("register.html", db=db)


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "GET":
        symbols = db.execute(
            "SELECT DISTINCT symbol from transactions WHERE id=?", session["user_id"]
        )
        return render_template("sell.html", symbols=symbols, db=db)

    if request.method == "POST":
        symbol = request.form.get("symbol")

        if symbol == None:
            return apology("Select a symbol to sell")
        stock_info = lookup(symbol)
        if stock_info == None:
            return apology("Invalid Symbol")
        symbol.upper()
        try:
            stocks = float(request.form.get("shares"))

            if stocks < 0:
                return apology("Invalid no. of stocks requested")
            elif not stocks.is_integer():
                return apology("Invalid no. of stocks requested")
        except ValueError:
            return apology("Invalid no. of stocks requested")

        currBalance = db.execute(
            "SELECT cash FROM users WHERE id=?", session["user_id"]
        )[0]["cash"]
        stocksHoldings = db.execute(
            "SELECT SUM(shares) as holdings from transactions where id=? and symbol=?",
            session["user_id"],
            symbol,
        )

        if stocksHoldings[0]["holdings"] < stocks:
            return apology("Insufficient stocks available to sell")

        db.execute(
            "UPDATE users SET cash=? where id=?",
            currBalance + (stocks * stock_info["price"]),
            session["user_id"],
        )
        db.execute(
            "INSERT INTO transactions VALUES(?,?,?,?,?,?)",
            session["user_id"],
            symbol,
            "sell",
            -stocks,
            stock_info["price"],
            datetime.datetime.now(),
        )

        return redirect("/")
