import os
import datetime

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.route("/")
@login_required
def index():
    userid = session["user_id"]
    username = db.execute("SELECT username FROM users WHERE id = :userid", userid=userid)[0]['username']
    rows = db.execute("SELECT * FROM transactions WHERE user = :username", username=username)
    cash = db.execute("SELECT cash FROM users WHERE username = :username", username=username)[0]['cash']

    symbols = set()
    symbol_sets =set()
    symbols_name = {}
    api = {}
    prices = {}
    number = {}
    total_cost = {}
    total = list()

    # Create set of uniqe symbols in portfolio
    for row in rows:
        symbol_sets.add(row['symbol'])

    for symbol_set in symbol_sets:
        count = db.execute("SELECT sum(shares) FROM transactions WHERE symbol = :symbol_set AND user = :username",
                            username=username, symbol_set=symbol_set)[0]['sum(shares)']
        if count > 0:
            symbols.add(symbol_set)

    for symbol in symbols:

        # Count total number of shares of each symbol and add to count dictionary
        count = db.execute("SELECT sum(shares) FROM transactions WHERE symbol = :symbol AND user = :username",
                            username=username, symbol=symbol)[0]['sum(shares)']

        number.update({symbol:count})

        # Lookup the price and name of each stock symbol from stock API
        api.update(lookup(symbol))

        # Add price to price dictionary
        prices.update({api['symbol']:api['price']})

        # Add name to name dictionary
        symbols_name.update({symbol:api['name']})

        # Calculate total stock value of assets and add to total cost dictionary
        sum_total = count * prices[symbol]
        total_cost.update({symbol:sum_total})
        total.append(sum_total)

    # Calculate total value of stock portfolio
    total = cash + sum(total)

    return render_template("index.html", total_cost=total_cost, symbols=symbols, number=number, cash=cash, total=total,
                            prices=prices, username=username, symbols_name=symbols_name)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():

    userid = session["user_id"]
    username = db.execute("SELECT username FROM users WHERE id = :userid", userid=userid)[0]['username']
    cash = db.execute("SELECT cash FROM users WHERE id = :userid", userid=userid)[0]['cash']
    now = datetime.datetime.now()
    date = now.strftime("%Y-%m-%d %H:%M")

    if request.method == "POST":

        symbol = request.form.get("symbol")
        cart = lookup(symbol)
        if not cart:
            return apology("That stock does not exist", 400)

        name = str(cart['name'])
        shares = request.form.get("shares")
        if not shares:
            shares = 0

        if shares.isnumeric() == False:
            return apology("Please enter a numeric number of shares.", 400)
        elif float(shares) < 1 or float(shares) % float(shares) != 0:
            return apology("Please enter a valid number of shares.", 400)

        price = cart['price']
        total = float(cart['price']) * float(shares)
        updated_cash = float(cash) - float(total)
        type = "buy"

        if cash > total:
            result = db.execute("INSERT INTO transactions (symbol, user, date, name, shares, price, total, type) VALUES(:symbol, :username, :date, :name, :shares, :price, :total, :type)",
                                symbol=symbol.upper(), date=date, username=username, name=name, shares=shares, price=price,
                                total=total, type=type)
            update = db.execute("UPDATE users SET cash = :updated_cash WHERE id = :userid",
                                updated_cash=updated_cash, userid=userid)
            return render_template("bought.html", cart=cart, total=total, shares=shares, updated_cash=updated_cash)

        else:
            return apology("Sorry, you don't have enough cash to buy that.", 403)

    else:
        return render_template("buy.html", cash=cash, date=date, username=username)


@app.route("/check", methods=["GET"])
def check():

    username = request.args['username']
    rows = db.execute("SELECT * FROM users")

    if len(username) < 1:
        return jsonify("false")

    for row in rows:
        if username == row['username']:
            return jsonify("false")

    return jsonify("true")


@app.route("/history")
@login_required
def history():
    userid = session["user_id"]
    username = db.execute("SELECT username FROM users WHERE id = :userid", userid=userid)[0]['username']
    rows = db.execute("SELECT * FROM transactions WHERE user = :username", username=username)
    cash = db.execute("SELECT cash FROM users WHERE username = :username", username=username)[0]['cash']
    total = None

    if not rows:
        return render_template("history.html", username=username, rows=rows, cash=cash, total=total)

    total = (db.execute("SELECT sum(total) FROM transactions WHERE user = :username", username=username)[0]['sum(total)']) + cash
    return render_template("history.html", username=username, rows=rows, cash=cash, total=total)


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
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

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
    if request.method == "POST":
        symbol = request.form.get("symbol")
        quantity = 1

        if not symbol or symbol.isalpha() == False:
            return apology("Invalid stock symbol.", 400)

        else:
            symbol = symbol.upper();
            quote = lookup(str(symbol))
            if not quote:
                return apology("Invalid stock symbol.", 400)
            total = float(quote['price'])
            return render_template("quoted.html", quote=quote, total=total, quantity=quantity)

    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    username = request.form.get("username")
    password = request.form.get("password")
    hashed = generate_password_hash(str(password))
    check = request.form.get("confirmation")

    if request.method == "POST":
        if not username:
            return apology("You forgot to enter a username!", 400)
        elif not password:
            return apology("You forgot to enter a password!", 400)
        elif not check:
            return apology("You forgot to re-enter your password!", 400)
        elif password != check:
            return apology("Your passwords do not match.", 400)

        result = db.execute("INSERT INTO users (username, hash) VALUES(:username, :hashed)", username=username, hashed=hashed)
        if not result:
            return apology("Sorry, that username already exists.", 400)

        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=username)

        session["user_id"] = rows[0]["id"]

    else:
        return render_template("register.html")

    return login()



@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    userid = session["user_id"]
    username = db.execute("SELECT username FROM users WHERE id = :userid", userid=userid)[0]['username']
    cash = db.execute("SELECT cash FROM users WHERE id = :userid", userid=userid)[0]['cash']
    now = datetime.datetime.now()
    date = now.strftime("%Y-%m-%d %H:%M")
    rows = db.execute("SELECT * FROM transactions WHERE user = :username", username=username)

    symbols = set()
    symbol_sets =set()
    for row in rows:
        symbol_sets.add(row['symbol'])

    for symbol_set in symbol_sets:
        count = db.execute("SELECT sum(shares) FROM transactions WHERE symbol = :symbol_set AND user = :username",
                            username=username, symbol_set=symbol_set)[0]['sum(shares)']
        if count > 0:
            symbols.add(symbol_set)

    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares = int(request.form.get("shares")) * -1
        total_sold = float(shares) * float(lookup(symbol)['price'])
        sum_shares = db.execute("SELECT sum(shares) FROM transactions WHERE symbol = :symbol AND user = :username",
                                symbol=symbol, username=username)[0]['sum(shares)']
        type = "sell"
        current_share = lookup(symbol)
        total = float(current_share['price']) * float(shares)

        if sum_shares > 0 and -(shares) <= sum_shares:
            db.execute("INSERT INTO transactions (symbol, user, date, name, shares, price, total, type) VALUES(:symbol, :username, :date, :name, :shares, :price, :total, :type)",
                        symbol=symbol, date=date, username=username, name=current_share['name'], shares=shares,
                        price=(current_share['price']), total=total, type=type)
            db.execute("UPDATE users SET cash = :total WHERE username = :username", total=(-1*total+cash), username=username)
            return render_template("sold.html", sum_shares=sum_shares, symbol=symbol, shares=shares,
                                    total_sold=total_sold)

        else:
            return apology("Sorry, you do not own that many shares.", 400)

    else:
        return render_template("sell.html", symbols=symbols, cash=cash, date=date, username=username)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
