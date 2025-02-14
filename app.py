import os
import requests
from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import atexit
import secrets

app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(16)

# Database configuration
DB_HOST = os.environ.get("DB_HOST", "db")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "postgres")
DB_NAME = os.environ.get("DB_NAME", "notability_db")  # Changed database name
app.config['SQLALCHEMY_DATABASE_URI'] = f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}'

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.init_app(app)

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True)
    password = db.Column(db.Text)

class Entry(db.Model):
    __tablename__ = 'entries'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    notability_link = db.Column(db.String(500))
    schedule_minutes = db.Column(db.Integer, nullable=True)
    filename = db.Column(db.String(200))
    share_token = db.Column(db.String(32), unique=True)

    def __init__(self, user_id, notability_link, schedule_minutes=None, filename=""):
        self.user_id = user_id
        self.notability_link = notability_link
        self.schedule_minutes = schedule_minutes
        self.filename = filename
        self.share_token = secrets.token_hex(16)
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def init_db():
    with app.app_context():
        db.create_all()

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username:
            flash('Username is required', 'error')
            return redirect(url_for('register'))
            
        if not password:
            flash('Password is required', 'error')
            return redirect(url_for('register'))
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'error')
            return redirect(url_for('register'))
        
        new_user = User(
            username=username,
            password=generate_password_hash(password, method='pbkdf2:sha256')
        )
        
        try:
            db.session.add(new_user)
            db.session.commit()
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            flash('An error occurred during registration', 'error')
            return redirect(url_for('register'))
            
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if not User.query.first():
        return redirect(url_for('register'))
    if request.method == 'POST':
        username = request.form.get("username")
        password = request.form.get("password")
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash("Invalid credentials")
    return render_template("login.html")

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def dashboard():
    entries = Entry.query.filter_by(user_id=current_user.id).all()
    return render_template("dashboard.html", entries=entries)

@app.route('/add', methods=['GET', 'POST'])
@login_required
def add_entry():
    if request.method == 'POST':
        try:
            notability_link = request.form.get("notability_link", "").strip()
            schedule_minutes = request.form.get("schedule_minutes", "").strip()
            
            if not notability_link:
                flash("Notability link is required", "error")
                return render_template("add_entry.html")
            
            if not notability_link.startswith("https://notability.com/n/"):
                flash("Invalid Notability link format", "error")
                return render_template("add_entry.html")
            
            try:
                schedule_minutes = int(schedule_minutes) if schedule_minutes else None
                if schedule_minutes is not None:
                    if schedule_minutes < 1:
                        flash("Schedule minutes must be positive", "error")
                        return render_template("add_entry.html")
                    if schedule_minutes < 5:
                        flash("Warning: Very frequent syncing may cause issues", "error")
            except ValueError:
                flash("Invalid schedule minutes value", "error")
                return render_template("add_entry.html")
            
            new_entry = Entry(
                user_id=current_user.id,
                notability_link=notability_link,
                schedule_minutes=schedule_minutes,
                filename=""
            )
            
            try:
                db.session.add(new_entry)
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                flash("Could not save entry to database", "error")
                return render_template("add_entry.html")
            
            if download_pdf(new_entry):
                flash("Entry added and initial download completed", "success")
            else:
                flash("Entry added but initial download failed", "error")
            
            if schedule_minutes:
                try:
                    add_job_for_entry(new_entry)
                    flash(f"Scheduled to sync every {schedule_minutes} minutes", "success")
                except Exception as e:
                    flash(f"Entry added but scheduling failed: {str(e)}", "error")
            
            return redirect(url_for('dashboard'))
            
        except Exception as e:
            flash(f"Error adding entry: {str(e)}", "error")
            return render_template("add_entry.html")
            
    return render_template("add_entry.html")

@app.route('/sync/<int:entry_id>')
@login_required
def sync_entry(entry_id):
    try:
        entry = Entry.query.filter_by(id=entry_id, user_id=current_user.id).first()
        if not entry:
            flash("Entry not found", "error")
            return redirect(url_for('dashboard'))
        
        if download_pdf(entry):
            flash("Sync completed successfully - PDF updated", "success")
        
    except Exception as e:
        flash(f"Sync failed: {str(e)}", "error")
        print(f"Sync error for entry {entry_id}: {str(e)}")
    
    return redirect(url_for('dashboard'))

@app.route('/pdf/<int:entry_id>')
@login_required
def serve_pdf(entry_id):
    entry = Entry.query.filter_by(id=entry_id, user_id=current_user.id).first_or_404()
    if entry.filename and os.path.exists(entry.filename):
        return send_file(entry.filename)
    flash("PDF not found")
    return redirect(url_for('dashboard'))

@app.route('/delete/<int:entry_id>', methods=['POST'])
@login_required
def delete_entry(entry_id):
    entry = Entry.query.filter_by(id=entry_id, user_id=current_user.id).first_or_404()
    
    job_id = f"entry_{entry.id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
    
    if entry.filename and os.path.exists(entry.filename):
        try:
            os.remove(entry.filename)
        except OSError as e:
            print(f"Error removing file: {e}")
    
    db.session.delete(entry)
    db.session.commit()
    flash("Entry deleted successfully")
    return redirect(url_for('dashboard'))

# Function to download the PDF from the Notability link
def download_pdf(entry):
    try:
        if not entry.notability_link or 'notability.com/n/' not in entry.notability_link:
            raise ValueError("Invalid Notability link format")
        
        try:
            note_id = entry.notability_link.split('/')[-1]
            if not note_id:
                raise ValueError("Could not extract note ID from link")
        except Exception as e:
            raise ValueError(f"Invalid link format: {str(e)}")
        
        download_url = f"https://notability.com/n/download/pdf/{note_id}/note_{entry.id}.pdf"
        print(f"Attempting to download from: {download_url}")
        
        try:
            if not os.path.exists("pdfs"):
                os.makedirs("pdfs")
        except Exception as e:
            raise IOError(f"Could not create pdfs directory: {str(e)}")
        
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(download_url, headers=headers, timeout=30)
            response.raise_for_status()
            
            content_type = response.headers.get('content-type', '')
            if 'application/pdf' not in content_type.lower():
                raise ValueError(f"Received non-PDF response: {content_type}")
            
            if not response.content:
                raise ValueError("Received empty response from server")
            
        except requests.Timeout:
            raise TimeoutError("Download timed out - server took too long to respond")
        except requests.RequestException as e:
            raise ConnectionError(f"Download failed: {str(e)}")
        
        filename = f"pdfs/note_{entry.id}.pdf"
        try:
            with open(filename, "wb") as f:
                f.write(response.content)
        except IOError as e:
            raise IOError(f"Could not save PDF file: {str(e)}")
        
        try:
            entry.filename = filename
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise DatabaseError(f"Could not update database: {str(e)}")
        
        print(f"Successfully downloaded PDF to {filename}")
        flash("Successfully downloaded PDF", "success")
        return True
        
    except ValueError as e:
        print(f"Validation error: {str(e)}")
        flash(f"Invalid link or format: {str(e)}", "error")
        return False
    except TimeoutError as e:
        print(f"Timeout error: {str(e)}")
        flash("Server took too long to respond", "error")
        return False
    except ConnectionError as e:
        print(f"Connection error: {str(e)}")
        flash("Could not connect to Notability server", "error")
        return False
    except IOError as e:
        print(f"File error: {str(e)}")
        flash("Could not save the PDF file", "error")
        return False
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        flash("An unexpected error occurred", "error")
        return False

# Initialize scheduler
scheduler = BackgroundScheduler()
scheduler.start()

def add_job_for_entry(entry):
    if entry.schedule_minutes:
        job_id = f"entry_{entry.id}"
        try:
            scheduler.remove_job(job_id)
        except:
            pass
        
        scheduler.add_job(
            download_pdf,
            trigger=IntervalTrigger(minutes=entry.schedule_minutes),
            args=[entry],
            id=job_id,
            replace_existing=True
        )
        print(f"Scheduled sync every {entry.schedule_minutes} minutes for entry {entry.id}")

atexit.register(lambda: scheduler.shutdown())

@app.route('/public/<share_token>')
def public_pdf(share_token):
    entry = Entry.query.filter_by(share_token=share_token).first_or_404()
    
    if entry.filename and os.path.exists(entry.filename):
        return send_file(entry.filename)
    else:
        return "PDF not found", 404

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', debug=True)