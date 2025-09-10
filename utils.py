# utils.py
import os
import unicodedata
import subprocess
import threading
from datetime import datetime, timedelta
import re
import xml.etree.ElementTree as ET
from io import BytesIO
from urllib.request import pathname2url
import glob
from PIL import Image
import cairosvg
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
import pyotp
import qrcode
import io
import base64

from flask import flash, redirect, url_for
from sqlalchemy import desc
from models import db, User, GenerationTask, Banknote, SerialNumber
from sqlalchemy import desc  # <-- Add this if using desc in utility functions
import bleach
from bleach.sanitizer import ALLOWED_TAGS, ALLOWED_ATTRIBUTES
# Configuration
IMAGES_ROOT = "./images"
GENERATION_LOCK = threading.Lock()
GENERATION_THREADS = {}




def sanitize_bio(text):
    """
    Sanitize bio text, allowing some BBCode-like formatting
    """
    if not text:
        return ""
    
    # First, convert BBCode to HTML
    text = bbcode_to_html(text)
    
    # Define allowed HTML tags (convert frozenset to set and add new tags)
    allowed_tags = set(ALLOWED_TAGS) | {
        'br', 'p', 'div', 'span', 'ul', 'ol', 'li', 
        'strong', 'em', 'u', 's', 'blockquote', 'code'
    }
    
    # Define allowed attributes
    allowed_attributes = {
        'a': ['href', 'title', 'target', 'rel'],
        'img': ['src', 'alt', 'title', 'width', 'height'],
        'span': ['style', 'class'],
        'div': ['style', 'class'],
        'p': ['style', 'class'],
        '*': ['class', 'style']  # Allow class and style on all elements
    }
    
    # Sanitize the HTML
    clean_text = bleach.clean(
        text,
        tags=allowed_tags,
        attributes=allowed_attributes,
        strip=True
    )
    
    # Linkify URLs
    clean_text = bleach.linkify(clean_text)
    
    return clean_text
def get_user_by_username(username):
    """Get user object by username"""
    return User.query.filter_by(username=username).first()
def bbcode_to_html(text):
    """
    Convert basic BBCode to HTML
    """
    if not text:
        return ""
    
    # Basic BBCode replacements
    replacements = [
        (r'\[b\](.*?)\[/b\]', r'<strong>\1</strong>'),
        (r'\[i\](.*?)\[/i\]', r'<em>\1</em>'),
        (r'\[u\](.*?)\[/u\]', r'<u>\1</u>'),
        (r'\[s\](.*?)\[/s\]', r'<s>\1</s>'),
        (r'\[url\](.*?)\[/url\]', r'<a href="\1">\1</a>'),
        (r'\[url=(.*?)\](.*?)\[/url\]', r'<a href="\1">\2</a>'),
        (r'\[img\](.*?)\[/img\]', r'<img src="\1" alt="Image">'),
        (r'\[quote\](.*?)\[/quote\]', r'<blockquote>\1</blockquote>'),
        (r'\[code\](.*?)\[/code\]', r'<code>\1</code>'),
        (r'\[color=(.*?)\](.*?)\[/color\]', r'<span style="color:\1">\2</span>'),
        (r'\[size=(.*?)\](.*?)\[/size\]', r'<span style="font-size:\1px">\2</span>'),
        (r'\n', r'<br>'),  # Convert newlines to <br>
        (r'\[pulse\](.*?)\[/pulse\]', r'<span class="text-pulse">\1</span>'),
        (r'\[rainbow\](.*?)\[/rainbow\]', r'<span class="rainbow-text">\1</span>'),
    ]
    
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text, flags=re.DOTALL)
    
    return text
def get_user_avatar(username):
    """
    Get the avatar image path for a user from portraits directory
    """
    clean_username = re.sub(r'[^\w\-_]', '_', username)
    
    # Check each file extension
    for ext in ['.png', '.jpg', '.jpeg', '.svg']:
        # Build the path with forward slashes
        portrait_path = f"portraits/portrait_{clean_username}{ext}"
        if os.path.exists(portrait_path):
            return portrait_path
        
        # Also check without portrait_ prefix
        simple_path = f"portraits/{clean_username}{ext}"
        if os.path.exists(simple_path):
            return simple_path
    
    return None
def get_initials(username):
    """
    Convert a username to initials format (e.g., "Ling Lin" -> "L.L.")
    """
    if not username:
        return "?"
    
    # Split the name by spaces and common separators
    name_parts = re.split(r'[\s_\-\.]+', username)
    
    # Filter out empty parts and take the first character of each part
    initials = [part[0].upper() for part in name_parts if part]
    
    if not initials:
        return "?"
    
    # Format as "L.L." style
    return '.'.join(initials) + '.'
def get_formatted_initials(username):
    """
    Convert username to formatted initials:
    - "Ling Lin" -> "L.L."
    - "linglin" -> "L" 
    - "John Doe Smith" -> "J.D.S."
    - "mary" -> "M"
    """
    if not username:
        return "?"
    
    # Split by spaces, underscores, hyphens, and dots
    import re
    name_parts = re.split(r'[\s_\-\.]+', username.strip())
    
    # Filter out empty parts and get first letter of each part
    initials = [part[0].upper() for part in name_parts if part]
    
    if not initials:
        return "?"
    
    # If only one initial, return just that letter
    if len(initials) == 1:
        return initials[0]
    
    # If multiple initials, format as "L.L." style
    return '.'.join(initials) + '.'
def get_user_avatar_or_default(username):
    """
    Get avatar URL or return a default with initials
    """
    avatar_path = get_user_avatar(username)
    
    if avatar_path:
        relative_path = os.path.relpath(avatar_path, '.')
        return url_for('serve_static', filename=relative_path)
    
    # Return a data URL with initials as fallback
    import base64
    from io import BytesIO
    from PIL import Image, ImageDraw, ImageFont
    import random
    
    # Create a simple avatar with initials
    initials = get_initials(username) if username else "?"
    bg_color = f"hsl({random.randint(0, 360)}, 70%, 60%)"
    
    # Create image
    img = Image.new('RGB', (100, 100), color=bg_color)
    draw = ImageDraw.Draw(img)
    
    # Try to use a font, fallback to default
    try:
        font = ImageFont.truetype("arial.ttf", 40)
    except:
        font = ImageFont.load_default()
    
    # Draw initials
    bbox = draw.textbbox((0, 0), initials, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    position = ((100 - text_width) // 2, (100 - text_height) // 2)
    
    draw.text(position, initials, fill="white", font=font)
    
    # Convert to data URL
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    
    return f"data:image/png;base64,{img_str}"
def get_user_avatar_url(username):
    """
    Get the URL for a user's avatar using the portraits route
    """
    avatar_path = get_user_avatar(username)
    
    if avatar_path:
        # Extract just the filename (e.g., "portrait_Ling_Lin.png")
        filename = os.path.basename(avatar_path)
        return url_for('serve_portrait', filename=filename)
    
    return None


# Helper Functions
def get_current_user():
    """Get current user from session"""
    from flask import session
    if 'user_id' in session:
        return User.query.get(session['user_id'])
    return None

def generate_qr_code(uri):
    """Generate QR code from URI and return as base64"""
    img = qrcode.make(uri)
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()

def extract_qr_from_svg(svg_path):
    """Extract QR code data from SVG file"""
    try:
        tree = ET.parse(svg_path)
        root = tree.getroot()
        
        for elem in root.iter():
            if 'qr' in elem.get('id', '').lower() or 'qrcode' in elem.get('id', '').lower():
                return elem.text or elem.get('data') or "QR data extracted"
                
        for text_elem in root.findall('.//{http://www.w3.org/2000/svg}text'):
            text_content = text_elem.text or ""
            if text_content.startswith('SN-'):
                return text_content
                
    except Exception as e:
        print(f"Error extracting QR from SVG: {e}")
    
    return None

def generate_thumbnail(svg_path, png_path, size=(600, 300)):
    """Generate PNG thumbnail from SVG file"""
    try:
        svg_url = f"file:{pathname2url(os.path.abspath(svg_path))}"
        cairosvg.svg2png(url=svg_url, write_to=png_path, output_width=size[0], output_height=size[1])
        print(f"Generated PNG: {png_path}")
        return True
    except Exception as e:
        print(f"Error generating PNG thumbnail for {svg_path}: {e}")
        return False

def generate_pdf(svg_path, pdf_path):
    """Convert SVG to PDF"""
    try:
        png_buffer = BytesIO()
        cairosvg.svg2png(url=svg_path, write_to=png_buffer)
        png_buffer.seek(0)
        
        c = canvas.Canvas(pdf_path, pagesize=letter)
        img = ImageReader(png_buffer)
        c.drawImage(img, 50, 50, width=500, height=250, preserveAspectRatio=True)
        c.save()
        return True
    except Exception as e:
        print(f"Error generating PDF: {e}")
        return False

def generate_combined_pdf(banknotes, pdf_path):
    """Generate combined PDF for multiple banknotes"""
    try:
        c = canvas.Canvas(pdf_path, pagesize=letter)
        
        for i, banknote in enumerate(banknotes):
            if i > 0:
                c.showPage()
            
            if os.path.exists(banknote.png_path):
                img = ImageReader(banknote.png_path)
                c.drawImage(img, 50, 50, width=500, height=250, preserveAspectRatio=True)
            
            c.setFont("Helvetica", 12)
            c.drawString(50, 30, f"Serial: {banknote.serial_number}")
            c.drawString(50, 15, f"Denomination: {banknote.denomination}")
        
        c.save()
        return True
    except Exception as e:
        print(f"Error generating combined PDF: {e}")
        return False

def process_generated_files(user_id, username):
    """Process all generated SVG files after banknote generation"""
    user = User.query.get(user_id)
    name_path = os.path.join(IMAGES_ROOT, username)
    
    if not os.path.exists(name_path):
        return
    
    for denom in os.listdir(name_path):
        denom_path = os.path.join(name_path, denom)
        if not os.path.isdir(denom_path):
            continue
            
        for svg_file in os.listdir(denom_path):
            if svg_file.lower().endswith('.svg'):
                svg_path = os.path.join(denom_path, svg_file)
                side = 'front' if '_FRONT' in svg_file.upper() else 'back'
                
                # Extract QR code data
                qr_data = extract_qr_from_svg(svg_path)
                
                # For front notes, use the extracted QR data or generate a fallback
                if side == 'front':
                    serial_number = qr_data if qr_data and qr_data.startswith('SN-') else f"SN-{username}-{denom}-{side}"
                
                # For back notes, try to extract from QR code first
                # If that fails, look for the corresponding front note
                else:
                    if qr_data and qr_data.startswith('SN-'):
                        serial_number = qr_data
                    else:
                        # Try to find the front note for this denomination
                        front_svg_files = [f for f in os.listdir(denom_path) 
                                         if f.upper().endswith('.SVG') and '_FRONT' in f.upper()]
                        
                        if front_svg_files:
                            front_svg_path = os.path.join(denom_path, front_svg_files[0])
                            front_qr_data = extract_qr_from_svg(front_svg_path)
                            if front_qr_data and front_qr_data.startswith('SN-'):
                                serial_number = front_qr_data
                            else:
                                serial_number = f"SN-{username}-{denom}-{side}"
                        else:
                            serial_number = f"SN-{username}-{denom}-{side}"
                
                png_filename = f"{os.path.splitext(svg_file)[0]}.png"
                png_path = os.path.join(denom_path, png_filename)
                
                pdf_filename = f"{os.path.splitext(svg_file)[0]}.pdf"
                pdf_path = os.path.join(denom_path, pdf_filename)
                
                generate_thumbnail(svg_path, png_path, size=(1600,600))
                generate_pdf(svg_path, pdf_path)
                
                banknote = Banknote(
                    user_id=user_id,
                    serial_number=serial_number,
                    seed_text=username,
                    denomination=denom,
                    side=side,
                    svg_path=svg_path,
                    png_path=png_path,
                    pdf_path=pdf_path,
                    qr_data=qr_data
                )
                db.session.add(banknote)
                
                serial = SerialNumber(
                    serial=serial_number,
                    user_id=user_id,
                    banknote_id=banknote.id,
                    is_active=True
                )
                db.session.add(serial)
    
    db.session.commit()
    
    user_banknotes = Banknote.query.filter_by(user_id=user_id).all()
    combined_pdf_path = os.path.join(name_path, f"{username}_all_banknotes.pdf")
    generate_combined_pdf(user_banknotes, combined_pdf_path)
def has_banknotes(user_id):
    """Check if a user has any banknotes"""
    return Banknote.query.filter_by(user_id=user_id).first() is not None
def run_generation_task(user_id, username):
    """Run the banknote generation process in a separate thread"""
    from app import app
    with app.app_context():
        task = None
        try:
            task = GenerationTask(user_id=user_id, status='processing', message="Starting generation...")
            db.session.add(task)
            db.session.commit()
            print(f"Starting generation for user {user_id}, username {username}")
            
            command = ["python", "main.py", "--name", username]
            print(f"Running command: {command}")
            
            result = subprocess.run(command, capture_output=True, text=True, cwd=os.getcwd(), timeout=5555)
            
            print(f"Command finished with return code: {result.returncode}")
            print(f"STDOUT: {result.stdout}")
            print(f"STDERR: {result.stderr}")
            
            if result.returncode == 0:
                process_generated_files(user_id, username)
                task.status = 'completed'
                user = db.session.get(User, user_id)
                user.last_generation = datetime.utcnow()
                user.balance += 111111111
                task.message = "Banknotes generated successfully! 111,111,111 Luna Coin added to your balance."
                print("Generation completed successfully")
            else:
                task.status = 'failed'
                error_msg = result.stderr if result.stderr else result.stdout
                task.message = f"Banknote generation failed: {error_msg}"
                print(f"Generation failed: {error_msg}")
                
            task.completed_at = datetime.utcnow()
            db.session.commit()
            
        except subprocess.TimeoutExpired:
            if task:
                task.status = 'failed'
                task.completed_at = datetime.utcnow()
                task.message = "Generation timed out after 5 minutes"
                db.session.commit()
                print("Generation timed out")
                
        except Exception as e:
            if task:
                task.status = 'failed'
                task.completed_at = datetime.utcnow()
                task.message = f"Banknote generation error: {str(e)}"
                db.session.commit()
                print(f"Generation error: {str(e)}")
                import traceback
                traceback.print_exc()
        
        finally:
            with GENERATION_LOCK:
                if user_id in GENERATION_THREADS:
                    del GENERATION_THREADS[user_id]

def validate_serial_id(serial_id):
    """Validate serial number format"""
    if not serial_id.startswith("SN-"):
        return {"valid": False, "reason": "Missing prefix 'SN-'"}

    parts = serial_id.split('-')[1:]
    parts = [p for p in parts if p]
    
    if not parts:
        return {"valid": False, "reason": "No valid groups after SN- prefix"}

    if len(parts) == 2:
        body, checksum = parts
        if re.match(r'^[A-Za-z0-9_-]+$', body) and re.match(r'^[A-Za-z0-9_-]+$', checksum):
            return {
                "valid": True,
                "type": "with_checksum",
                "serial_body": body,
                "checksum": checksum
            }

    if all(re.match(r'^[A-Za-z0-9_-]+$', p) for p in parts):
        return {
            "valid": True,
            "type": "combined",
            "groups": parts,
            "checksum": None
        }

    return {"valid": False, "reason": "Invalid format"}

def regenerate_all_pngs():
    """Regenerate all PNG thumbnails from SVG files"""
    from app import app
    with app.app_context():
        svg_files = glob.glob('./images/**/*.svg', recursive=True)
        print(f"Found {len(svg_files)} SVG files")
        
        for svg_path in svg_files:
            png_path = svg_path.replace('.svg', '.png')
            
            if not os.path.exists(png_path):
                print(f"Generating PNG for: {svg_path}")
                if generate_thumbnail(svg_path, png_path):
                    print(f"✓ Created {png_path}")
                else:
                    print(f"✗ Failed to create {png_path}")
            else:
                print(f"✓ PNG already exists: {png_path}")