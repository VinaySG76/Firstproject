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

from config import Config
from models import Base, User, File

# Flask app setup
app = Flask(__name__)
app.config.from_object(Config)

# DB setup
engine = create_engine(app.config['SQLALCHEMY_DATABASE_URI'], pool_pre_ping=True)
SessionLocal = scoped_session(sessionmaker(bind=engine, autoflush=False, autocommit=False))
Base.metadata.create_all(engine)

# Auth setup
login_manager = LoginManager(app)
login_manager.login_view = 'login'

class AuthUser(UserMixin):
    def __init__(self, user):
        self._user = user
        self.id = str(user.id)
        self.email = user.email
        self.used_bytes = user.used_bytes

@login_manager.user_loader
def load_user(user_id):
    db = SessionLocal()
    try:
        user = db.get(User, int(user_id))
        return AuthUser(user) if user else None
    finally:
        db.close()

# S3 client
s3 = boto3.client(
    's3',
    region_name=app.config['AWS_REGION'],
    aws_access_key_id=app.config['AWS_ACCESS_KEY_ID'],
    aws_secret_access_key=app.config['AWS_SECRET_ACCESS_KEY']
)
BUCKET = app.config['S3_BUCKET_NAME']

# Helpers
def user_s3_prefix(user_id:int) -> str:
    return f"users/{user_id}/"

def ensure_bucket():
    # Validates access to the bucket at runtime; won't create it implicitly in prod
    try:
        s3.head_bucket(Bucket=BUCKET)
    except ClientError as e:
        raise RuntimeError(f"S3 bucket '{BUCKET}' not accessible: {e}")

@app.route('/')
@login_required
def dashboard():
    db = SessionLocal()
    try:
        files = db.query(File).filter(File.user_id == int(current_user.id)).order_by(File.uploaded_at.desc()).all()
        quota = app.config['USER_STORAGE_QUOTA_BYTES']
        used = db.get(User, int(current_user.id)).used_bytes
        return render_template('dashboard.html', files=files, used=used, quota=quota)
    finally:
        db.close()

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        if not email or not password:
            flash('Email and password are required', 'error')
            return redirect(url_for('register'))
        db = SessionLocal()
        try:
            existing = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
            if existing:
                flash('Email already registered', 'error')
                return redirect(url_for('register'))
            user = User(email=email, password_hash=generate_password_hash(password))
            db.add(user)
            db.commit()
            flash('Registration successful. Please login.', 'success')
            return redirect(url_for('login'))
        finally:
            db.close()
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        db = SessionLocal()
        try:
            user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
            if user and check_password_hash(user.password_hash, password):
                login_user(AuthUser(user))
                return redirect(url_for('dashboard'))
            flash('Invalid credentials', 'error')
        finally:
            db.close()
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file selected', 'error')
            return redirect(url_for('upload'))
        f = request.files['file']
        if f.filename == '':
            flash('No file selected', 'error')
            return redirect(url_for('upload'))
        data = f.read()
        size_bytes = len(data)
        db = SessionLocal()
        try:
            user = db.get(User, int(current_user.id))
            quota = app.config['USER_STORAGE_QUOTA_BYTES']
            if user.used_bytes + size_bytes > quota:
                flash('Upload would exceed your 2GB quota', 'error')
                return redirect(url_for('dashboard'))

            ensure_bucket()
            key = user_s3_prefix(user.id) + f.filename
            s3.put_object(Bucket=BUCKET, Key=key, Body=data)

            file_rec = File(user_id=user.id, filename=f.filename, s3_key=key, size_bytes=size_bytes)
            user.used_bytes += size_bytes
            db.add(file_rec)
            db.commit()
            flash('File uploaded successfully', 'success')
            return redirect(url_for('dashboard'))
        except ClientError as e:
            flash(f'S3 error: {e}', 'error')
            return redirect(url_for('upload'))
        finally:
            db.close()
    return render_template('upload.html')

@app.route('/download/<int:file_id>')
@login_required
def download(file_id):
    db = SessionLocal()
    try:
        rec = db.get(File, file_id)
        if not rec or rec.user_id != int(current_user.id):
            flash('File not found', 'error')
            return redirect(url_for('dashboard'))
        try:
            obj = s3.get_object(Bucket=BUCKET, Key=rec.s3_key)
            bytes_io = io.BytesIO(obj['Body'].read())
            bytes_io.seek(0)
            return send_file(bytes_io, as_attachment=True, download_name=rec.filename)
        except ClientError as e:
            flash(f'S3 error: {e}', 'error')
            return redirect(url_for('dashboard'))
    finally:
        db.close()

@app.route('/delete/<int:file_id>', methods=['POST'])
@login_required
def delete(file_id):
    db = SessionLocal()
    try:
        rec = db.get(File, file_id)
        if not rec or rec.user_id != int(current_user.id):
            flash('File not found', 'error')
            return redirect(url_for('dashboard'))
        try:
            s3.delete_object(Bucket=BUCKET, Key=rec.s3_key)
        except ClientError as e:
            flash(f'S3 error: {e}', 'error')
            return redirect(url_for('dashboard'))
        size = rec.size_bytes
        user = db.get(User, int(current_user.id))
        db.delete(rec)
        user.used_bytes = max(0, (user.used_bytes or 0) - size)
        db.commit()
        flash('File deleted', 'success')
        return redirect(url_for('dashboard'))
    finally:
        db.close()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
