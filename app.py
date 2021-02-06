import os

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

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    # save user id as a variable
    userid = session["user_id"]
    # initialize a counter of how much money altogether is held
    runningtotal = 0
    rows = db.execute("SELECT * FROM holdings WHERE userid = :userid", userid=userid)

    # this loop is for counting up all of the numbers that will need to be displayed and saving them in a displayable format in USD form.
    for row in rows:
        symbol = row["symbol"]
        gettingcurrentprice = lookup(symbol)
        currentprice = float(gettingcurrentprice["price"])
        row["displaycurrentprice"] = usd(currentprice)
        stocktotal = (currentprice*row["shares"])
        runningtotal = (stocktotal+runningtotal)
        row["totalvalue"] = usd(stocktotal)

    displaytotal = usd(runningtotal)
    cashquery = db.execute("SELECT cash FROM users WHERE id = :id", id=userid)
    cash = cashquery[0]["cash"]
    displaycash = usd(cash)
    displaygrandtotal = usd(cash+runningtotal)
    return render_template("index.html", rows=rows, displaygrandtotal=displaygrandtotal, displaytotal=displaytotal, runningtotal=runningtotal, displaycash=displaycash)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "GET":
        function = "Buy"
        return render_template("buy.html", function=function)
    else:
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        dicty = lookup(symbol)
        if not dicty:
            return apology("Invalid symbol")
        symbol = dicty["symbol"]
        price = dicty["price"]
        name = dicty["name"]
        try:
            shares = int(shares)
        except:
            return apology("Shares must be a round number")
        if (shares <= 0):
            return apology("Shares must be positive")
        else:
            userid = session["user_id"]
            total = shares*price
            queryresult = db.execute("SELECT cash FROM users WHERE id = :userid", userid=userid)
            cash = queryresult[0]["cash"]

            if cash >= total:
                newcash = (cash-total)
                alreadyowned = db.execute(
                    "SELECT shares FROM holdings WHERE userid = :userid AND symbol = :symbol", userid=userid, symbol=symbol)
                if not alreadyowned:
                    db.execute("INSERT INTO holdings (userid, symbol, name, shares) VALUES (:userid, :symbol, :name, :shares)",
                               userid=userid, symbol=symbol, name=name, shares=shares)
                else:
                    newshares = (alreadyowned[0]["shares"] + shares)
                    db.execute("UPDATE holdings SET shares = :newshares WHERE userid = :userid AND symbol = :symbol",
                               newshares=newshares, userid=userid, symbol=symbol)
                db.execute("UPDATE users SET cash = :newcash WHERE id = :userid", userid=userid, newcash=newcash)
                db.execute("INSERT INTO history (userid, symbol, buysell, shares, price) VALUES (:userid, :symbol, :buysell, :shares, :price)",
                           userid=userid, symbol=symbol, buysell="Bought", shares=shares, price=price)

                return redirect("/")
            else:
                return apology("Get more money first!")

    """Buy shares of stock"""


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    userid = session["user_id"]
    rows = db.execute("SELECT * FROM history WHERE userid = :userid", userid=userid)
    if not rows:
        return apology("Buy something first!")
    return render_template("history.html", rows=rows)


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
        session["username"] = rows[0]["username"]

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
    if request.method == "GET":
        function = "Quote"
        return render_template("quote.html", function=function)
    elif request.method == "POST":
        symbol = request.form.get("symbol")
        dicty = lookup(symbol)
        if not dicty:
            return apology("Please use a valid stock symbol")
        symbol = dicty["symbol"]
        name = dicty["name"]
        price = dicty["price"]
        return render_template("price.html", symbol=symbol, name=name, price=price)

    else:
        return redirect("/quote")
    """Get stock quote."""


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")
    else:
        name = request.form.get("username")
        if not name:
            return apology("You must provide a name")

        pword1 = request.form.get("password")
        if not pword1:
            return apology("You must provide a password")

        pword2 = request.form.get("confirmation")

        '''Check to make sure passwords match'''
        if not pword1 == pword2:
            return apology("Your passwords must match")

        '''check to make sure username is unique'''
        error = db.execute("SELECT username FROM users WHERE username = :username", username=name)
        if error:
            return apology("This username is already in use")
        else:
            hash = generate_password_hash(pword1)
            db.execute("INSERT INTO users (username, hash) VALUES (:name, :password)", name=name, password=hash)

            ''' If user is successfully registered, automatically log them in. '''
            rows = db.execute("SELECT * FROM users WHERE username = :username", username=name)
            session["user_id"] = rows[0]["id"]

            return redirect("/login")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    if request.method == "GET":
        userid = session["user_id"]
        symbols = db.execute("SELECT symbol, shares FROM holdings WHERE userid = :userid", userid=userid)
        print(symbols)
        if not symbols:
            return apology("You don't own anything yet!")

        return render_template("sell.html", symbols=symbols)

    else:
        userid = session["user_id"]
        symbol = request.form.get("symbol")
        attemptedshares = int(request.form.get("shares"))
        holdings = db.execute("SELECT shares FROM holdings WHERE symbol=:symbol AND userid=:userid", symbol=symbol, userid=userid)
        holdings = int(holdings[0]["shares"])
        if holdings >= attemptedshares:
            # lookup symbol
            dicty = lookup(symbol)
            symbol = dicty["symbol"]
            name = dicty["name"]
            price = dicty["price"]

            # multiply current price by number of shares
            cashaddition = (attemptedshares * price)
            # add amount to cash in users
            currentcash = db.execute("SELECT cash FROM users WHERE id = :userid", userid=userid)
            currentcash = currentcash[0]["cash"]
            currentcash = (cashaddition + currentcash)
            db.execute("UPDATE users SET cash = :currentcash WHERE id = :userid", currentcash=currentcash, userid=userid)
            # subtract number of shares from holdings
            newholdings = holdings - attemptedshares
            db.execute("UPDATE holdings SET shares = :newholdings WHERE symbol = :symbol AND userid = :userid",
                       newholdings=newholdings, symbol=symbol, userid=userid)
            db.execute("DELETE FROM holdings WHERE shares=0")
            # add history entry
            db.execute("INSERT INTO history (userid, symbol, buysell, shares, price) VALUES (:userid, :symbol, :buysell, :shares, :price)",
                       userid=userid, symbol=symbol, buysell="Sold", shares=attemptedshares, price=price)
            return redirect("/")
        else:
            return apology("Too many shares!")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
