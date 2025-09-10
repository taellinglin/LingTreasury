# app.py
import os
from flask import Flask, render_template, send_from_directory, url_for, request, redirect, flash, session
from flask_migrate import Migrate
from models import db, User, GenerationTask, Banknote, SerialNumber
from utils import (
    get_current_user, generate_qr_code, validate_serial_id, 
    GENERATION_LOCK, GENERATION_THREADS, run_generation_task, get_user_avatar_or_default, get_user_avatar_url, get_user_by_username, has_banknotes,
    IMAGES_ROOT
)
from datetime import timedelta
from sqlalchemy import desc  # <-- Add this if using desc in utility functions
import pyotp
import threading
from utils import get_formatted_initials, get_user_avatar, get_user_avatar_url, sanitize_bio # Add this import
from urllib.parse import unquote

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///bank.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

# Initialize db with app
db.init_app(app)
migrate = Migrate(app, db)

@app.context_processor
def utility_processor():
    def has_banknotes(user_id):
        from models import Banknote
        return Banknote.query.filter_by(user_id=user_id).first() is not None
    """
    Make functions available to all templates
    """
    return {
        'get_user_avatar': get_user_avatar,  # Add this
        'get_formatted_initials': get_formatted_initials,  # Add this
        'get_user_avatar_url': get_user_avatar_url,
        'get_user_by_username': get_user_by_username,
        'has_banknotes': has_banknotes
        
    }
    
# Routes
@app.route("/")
def landing():
    return render_template('landing.html', title="灵国国库 [Ling Country Treasury]", current_user=get_current_user())
# Add this import at the top
@app.route("/portraits/<path:filename>")
def serve_portrait(filename):
    """
    Serve portrait images from the portraits directory
    """
    return send_from_directory('portraits', filename)
# Add this route
@app.route("/static/<path:filename>")
def serve_static(filename):
    """
    Serve static files from the root directory.
    This allows serving portraits from ./portraits/
    """
    return send_from_directory('.', filename)
@app.route("/gallery")
def gallery_index():
    # Get all users from the database instead of folder names
    users = User.query.order_by(User.username).all()
    return render_template('gallery_index.html', users=users, title="Banknote Gallery", current_user=get_current_user())

@app.route("/gallery/<name>")
def show_name(name):
    import unicodedata
    name = unicodedata.normalize("NFC", name)
    name_path = os.path.join(IMAGES_ROOT, name)
    if not os.path.exists(name_path):
        return f"<h1 style='color:red'>Name {name} not found</h1><a href='/gallery'>← Gallery</a>"

    fronts, backs = [], []
    for denom in sorted(os.listdir(name_path)):
        denom_path = os.path.join(name_path, denom)
        if not os.path.isdir(denom_path):
            continue
        for f in sorted(os.listdir(denom_path)):
            if f.lower().endswith(".svg"):
                side = "front" if "_FRONT" in f else "back"
                bill = {
                    "file": url_for("serve_image", filename=f"{name}/{denom}/{f}"),
                    "side": side,
                    "denom": denom
                }
                if side == "front":
                    fronts.append(bill)
                else:
                    backs.append(bill)

    return render_template('name_detail.html', name=name, fronts=fronts, backs=backs, title=f"Gallery - {name}", current_user=get_current_user())

@app.route("/images/<path:filename>")
def serve_image(filename):
    return send_from_directory(IMAGES_ROOT, filename)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            if user.two_factor_secret:
                session["pre_2fa_user_id"] = user.id
                return redirect(url_for("verify_2fa_login"))
            else:
                session["user_id"] = user.id
                flash("Logged in successfully!", "success")
                return redirect(url_for("landing"))
        else:
            flash("Invalid username or password", "error")
    
    return render_template('login.html', title="Login", current_user=get_current_user())


import os
from flask import current_app
from glob import glob

@app.route("/my-wallet")
def my_wallet():
    current_user = get_current_user()
    
    if not current_user:
        flash("Please log in to access your wallet", "error")
        return redirect(url_for("login"))
    
    # Debug: Print the current working directory and check if images folder exists
    print(f"Current working directory: {os.getcwd()}")
    
    # Check if the images directory exists at the expected path
    images_base_path = './images'  # This is relative to your application root
    print(f"Looking for images in: {images_base_path}")
    print(f"Directory exists: {os.path.exists(images_base_path)}")
    
    if os.path.exists(images_base_path):
        print("Contents of images directory:")
        for item in os.listdir(images_base_path):
            print(f"  - {item}")
    
    # Scan for the user's specific folder
    user_images_path = os.path.join(images_base_path, current_user.username)
    print(f"Looking for user folder: {user_images_path}")
    print(f"User folder exists: {os.path.exists(user_images_path)}")
    
    # Dictionary to store all found images by denomination
    denomination_images = {}
    
    if os.path.exists(user_images_path):
        print("User folder contents:")
        for item in os.listdir(user_images_path):
            item_path = os.path.join(user_images_path, item)
            print(f"  - {item} (is_dir: {os.path.isdir(item_path)})")
            
            if os.path.isdir(item_path):
                # This is a denomination folder
                svg_files = glob(os.path.join(item_path, '*.svg'))
                print(f"    SVG files in {item}: {svg_files}")
                
                front_files = [f for f in svg_files if '_FRONT.svg' in f]
                back_files = [f for f in svg_files if '_BACK.svg' in f]
                
                if front_files or back_files:
                    denomination_images[item] = {
                        'front': sorted(front_files),
                        'back': sorted(back_files)
                    }
    
    print(f"Found denominations: {list(denomination_images.keys())}")
    
    denominations = sorted(denomination_images.keys())
    
    if not denominations:
        flash("No banknotes found in your wallet", "warning")
        return redirect(url_for("profile", username=current_user.username))
    
    # Helper functions to get images
    def get_front_image(denom):
        files = denomination_images.get(denom, {}).get('front', [])
        if files:
            filename = os.path.basename(files[-1])
            return f"./images/{current_user.username}/{denom}/{filename}"
        return None
    
    def get_back_image(denom):
        files = denomination_images.get(denom, {}).get('back', [])
        if files:
            filename = os.path.basename(files[-1])
            return f"./images/{current_user.username}/{denom}/{filename}"
        return None
    
    return render_template('my_wallet.html', 
                         denominations=denominations,
                         get_front_image=get_front_image,
                         get_back_image=get_back_image,
                         current_user=current_user,
                         title=f"{current_user.username}'s Wallet")
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")
        
        if password != confirm_password:
            flash("Passwords do not match", "error")
            return render_template('register.html', title="Register", current_user=get_current_user())
        
        if User.query.filter_by(username=username).first():
            flash("Username already exists", "error")
            return render_template('register.html', title="Register", current_user=get_current_user())
        
        if User.query.filter_by(email=email).first():
            flash("Email already registered", "error")
            return render_template('register.html', title="Register", current_user=get_current_user())
        
        user = User(username=username, email=email)
        user.set_password(password)
        user.two_factor_secret = pyotp.random_base32()
        
        db.session.add(user)
        db.session.commit()
        
        session["pre_2fa_user_id"] = user.id
        return redirect(url_for("setup_2fa"))
    
    return render_template('register.html', title="Register", current_user=get_current_user())

@app.route("/setup-2fa")
def setup_2fa():
    if "pre_2fa_user_id" not in session:
        return redirect(url_for("login"))
    
    user = User.query.get(session["pre_2fa_user_id"])
    if not user:
        return redirect(url_for("login"))
    
    uri = user.get_totp_uri()
    qr_code = generate_qr_code(uri)
    
    return render_template('two_factor_setup.html', qr_code=qr_code, title="Setup 2FA", current_user=get_current_user())

@app.route("/setup-2fa", methods=["POST"])
def verify_2fa_setup():
    if "pre_2fa_user_id" not in session:
        return redirect(url_for("login"))
    
    user = User.query.get(session["pre_2fa_user_id"])
    if not user:
        return redirect(url_for("login"))
    
    token = request.form.get("token")
    
    import pyotp
    totp = pyotp.TOTP(user.two_factor_secret)
    
    is_valid = False
    if totp.verify(token):
        is_valid = True
    elif totp.verify(token, valid_window=1):
        is_valid = True
    elif totp.verify(token, valid_window=2):
        is_valid = True
    
    if is_valid:
        session.pop("pre_2fa_user_id")
        session["user_id"] = user.id
        flash("Two-factor authentication setup complete!", "success")
        return redirect(url_for("landing"))
    else:
        flash("Invalid token. Please check that your authenticator app time is synchronized with the server.", "error")
        return redirect(url_for("setup_2fa"))
    
@app.route("/verify-2fa", methods=["GET", "POST"])
def verify_2fa_login():
    if "pre_2fa_user_id" not in session:
        return redirect(url_for("login"))
    
    user = User.query.get(session["pre_2fa_user_id"])
    if not user:
        return redirect(url_for("login"))
    
    if request.method == "POST":
        token = request.form.get("token")
        
        if user.verify_totp(token):
            session.pop("pre_2fa_user_id")
            session["user_id"] = user.id
            flash("Logged in successfully!", "success")
            return redirect(url_for("landing"))
        else:
            flash("Invalid token. Please try again.", "error")
    
    return render_template('two_factor_verify.html', title="Verify 2FA", current_user=get_current_user())

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully", "success")
    return redirect(url_for("landing"))

@app.route("/generate-money", methods=["POST"])
def generate_money():
    current_user = get_current_user()
    if not current_user:
        flash("Please log in to generate money", "error")
        return redirect(url_for("login"))
    
    if not current_user.can_generate_money():
        flash(f"You can generate money again in {current_user.days_until_next_generation()} days", "error")
        return redirect(url_for("profile", username=current_user.username))
    
    with GENERATION_LOCK:
        if current_user.id in GENERATION_THREADS:
            flash("You already have a generation in progress", "error")
            return redirect(url_for("profile", username=current_user.username))
    
    thread = threading.Thread(
        target=run_generation_task,
        args=(current_user.id, current_user.username)
    )
    thread.daemon = True
    thread.start()
    
    with GENERATION_LOCK:
        GENERATION_THREADS[current_user.id] = thread
    
    flash("Banknote generation started! This may take a few moments.", "success")
    return redirect(url_for("profile", username=current_user.username))

@app.route("/banknote-image/<path:filename>")
def serve_banknote_image(filename):
    # Decode URL-encoded characters
    filename = unquote(filename)
    # Convert backslashes to forward slashes for cross-platform compatibility
    filename = filename.replace('\\', '/')
    # Remove any leading "images/" if it exists
    if filename.startswith('images/'):
        filename = filename[7:]
    # Ensure we're not dealing with directory traversal attacks
    if '..' in filename or filename.startswith('/'):
        abort(404)
    return send_from_directory(IMAGES_ROOT, filename)

@app.route("/toggle-banknote/<int:banknote_id>")
def toggle_banknote_visibility(banknote_id):
    current_user = get_current_user()
    if not current_user:
        return redirect(url_for('login'))
    
    banknote = Banknote.query.get_or_404(banknote_id)
    if banknote.user_id != current_user.id:
        flash("You don't have permission to modify this banknote", "error")
        return redirect(url_for('profile', username=current_user.username))
    
    banknote.is_public = not banknote.is_public
    db.session.commit()
    
    flash(f"Banknote visibility set to {'public' if banknote.is_public else 'private'}", "success")
    return redirect(url_for('profile', username=current_user.username))


@app.route("/<username>", methods=["GET", "POST"])
def profile(username):
    user = User.query.filter_by(username=username).first()
    if not user:
        flash("User not found", "error")
        return redirect(url_for("landing"))
    
    current_user_obj = get_current_user()
    
    if request.method == "POST":
        if current_user_obj and current_user_obj.id == user.id:
            raw_bio = request.form.get("bio", "")
            # Sanitize the bio before saving
            user.bio = sanitize_bio(raw_bio)
            db.session.commit()
            flash("Bio updated successfully", "success")
            return redirect(url_for("profile", username=username))
    
    generation_tasks = GenerationTask.query.filter_by(user_id=user.id).order_by(desc(GenerationTask.created_at)).limit(10).all()
    
    if current_user_obj and current_user_obj.id == user.id:
        banknotes = Banknote.query.filter_by(user_id=user.id).all()
    else:
        banknotes = Banknote.query.filter_by(user_id=user.id, is_public=True).all()
    
    # Custom sorting: first by denomination, then by side (fronts first)
    def banknote_sort_key(banknote):
        # Extract numeric value from denomination for proper numeric sorting
        # Handle denominations like "$1", "1 dollar", "10", etc.
        import re
        denomination = str(banknote.denomination)
        
        # Extract numbers from denomination string
        numbers = re.findall(r'\d+', denomination)
        if numbers:
            numeric_value = int(numbers[0])
        else:
            numeric_value = 0  # Default if no numbers found
            
        # Define the order of sides: front first, then back
        side_order = {'front': 0, 'back': 1}
        
        # Return a tuple for sorting: (numeric_value, side_order, original_denomination)
        return (numeric_value, side_order.get(banknote.side.lower(), 2), denomination)
    
    # Sort the banknotes using our custom key
    banknotes.sort(key=banknote_sort_key)
    
    # Generate SVG paths for each banknote
    for banknote in banknotes:
        # Create SVG path from PNG path
        if hasattr(banknote, 'png_path') and banknote.png_path:
            banknote.svg_path = banknote.png_path.replace('.png', '.svg')
        else:
            banknote.svg_path = None
    
    return render_template('profile.html', user=user, generation_tasks=generation_tasks, 
                         banknotes=banknotes, title=f"Profile - {username}", current_user=current_user_obj)

@app.route("/verify/<serial_id>", methods=["GET"])
def verify_serial_get(serial_id):
    result = validate_serial_id(serial_id)
    return render_template('verify.html', result=result, serial_input=serial_id, title="Verify Serial", current_user=get_current_user())

@app.route("/verify", methods=["GET", "POST"])
def verify_serial():
    result = None
    serial_input = ""
    banknote = None

    if request.method == "POST":
        serial_input = request.form.get("serial", "").strip()
        result = validate_serial_id(serial_input)
        
        if result and result.get('valid'):
            serial_record = SerialNumber.query.filter_by(serial=serial_input, is_active=True).first()
            if serial_record:
                banknote = serial_record.banknote

    return render_template('verify.html', result=result, serial_input=serial_input, 
                         banknote=banknote, title="Verify Serial", current_user=get_current_user())

# Initialize Database
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)