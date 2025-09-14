import os
import io
from urllib.parse import quote
from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_login import LoginManager, login_user, login_required, logout_user, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker, scoped_session
import boto3
from botocore.exceptions import ClientError

from config import Config   # Import Config class
from models import Base, User, File   # Import models

# Flask app setup
app = Flask(__name__)
app.config.from_object(Config)

# Database setup
engine = create_engine(app.config['SQLALCHEMY_DATABASE_URI'])
Base.metadata.create_all(engine)
Session = scoped_session(sessionmaker(bind=engine))

# Flask-Login setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"


@login_manager.user_loader
def load_user(user_id):
    session = Session()
    return session.query(User).get(int(user_id))


# Routes
@app.route("/")
def home():
    return "Hello, Flask App is Running! 🚀"


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        session = Session()
        if session.query(User).filter_by(username=username).first():
            flash("Username already exists!", "danger")
            return redirect(url_for("register"))

        hashed_pw = generate_password_hash(password, method="sha256")
        new_user = User(username=username, password=hashed_pw)
        session.add(new_user)
        session.commit()

        flash("Registration successful! Please login.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        session = Session()
        user = session.query(User).filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            flash("Login successful!", "success")
            return redirect(url_for("home"))
        else:
            flash("Invalid username or password!", "danger")

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)

