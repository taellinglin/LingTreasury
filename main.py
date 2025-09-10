#!/usr/bin/env python3
import os
import random
import subprocess
import time
import glob
import re
import shutil
import requests
import base64
import json
import argparse
from io import BytesIO
from PIL import Image
from PyPDF2 import PdfMerger

# -----------------------
# Configuration
# -----------------------
FRONT_SCRIPT = "generate_banknote_front.py"
BACK_SCRIPT = "generate_banknote_back.py"
NAMES_FILE = "master.txt"
OUTPUT_ROOT = "./images"  # single folder per name
PORTRAITS_DIR = "./portraits"
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".bmp")
SD_API_URL = "http://localhost:3014/sdapi/v1/txt2img"

# -----------------------
# Argument parsing
# -----------------------
def parse_arguments():
    parser = argparse.ArgumentParser(description="Generate banknotes for names")
    parser.add_argument("--name", type=str, help="Generate notes for a specific name only")
    parser.add_argument("--force-regenerate", action="store_true", 
                       help="Force regeneration of portraits even if they exist")
    return parser.parse_args()

# -----------------------
# Portrait generation functions
# -----------------------
def read_prompt_file(filename, default_prompt=""):
    """Read prompt from file, return default if file doesn't exist"""
    try:
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                return f.read().strip()
        else:
            safe_print(f"[!] Prompt file {filename} not found, using default")
            return default_prompt
    except Exception as e:
        safe_print(f"[!] Error reading {filename}: {e}")
        return default_prompt

def generate_character_portrait(name: str, width: int = 512, height: int = 512, 
                               seed: int = -1, save_path: str = "./portraits"):
    """
    Generate a character portrait based on the name using Stable Diffusion API
    """
    os.makedirs(save_path, exist_ok=True)
    
    # Read prompts from files
    portrait_prompt = read_prompt_file(
        "portrait_prompt.txt",
        "portrait of {name}, elegant character, official portrait, banknote portrait, currency art, detailed face, professional, serious expression, high detail, official document style"
    )
    negative_prompt = read_prompt_file(
        "negative_prompt.txt",
        "text, words, letters, numbers, blurry, low quality, watermark, signature, ugly, deformed, cartoon, anime, modern, casual"
    )
    
    # Format the prompt with the name
    formatted_prompt = portrait_prompt.format(name=name)
    
    payload = {
        "prompt": formatted_prompt,
        "negative_prompt": negative_prompt,
        "width": width,
        "height": height,
        "seed": seed if seed != -1 else random.randint(0, 2**32 - 1),
        "steps": 30,
        "cfg_scale": 8,
        "sampler_name": "DPM++ 2M Karras",
        "batch_size": 1,
        "n_iter": 1,
        "restore_faces": True,
        "tiling": False,

        # Highres fix (with safe denoising_strength)
        "enable_hr": True,
        "hr_scale": 1.5,
        "hr_upscaler": "ESRGAN_4x",
        "denoising_strength": 0.4,  # <-- needed to avoid NoneType crash
    }

    try:
        safe_print(f"[+] Generating portrait for: {name}")
        response = requests.post(SD_API_URL, json=payload, timeout=1800)
        response.raise_for_status()
        
        result = response.json()
        images = result.get('images', [])
        
        if images:
            image_data = base64.b64decode(images[0])
            image = Image.open(BytesIO(image_data))
            
            # Clean name for filename
            clean_name = re.sub(r'[^\w\-_]', '_', name)
            filename = f"portrait_{clean_name}.png"  # Consistent filename without timestamp
            filepath = os.path.join(save_path, filename)
            
            image.save(filepath)
            safe_print(f"[+] Generated portrait: {filepath}")
            return filepath
        
    except Exception as e:
        safe_print(f"[!] Error generating portrait for {name}: {e}")
        return None

def get_portrait_for_name(name, force_regenerate=False):
    """
    Get a portrait for the given name - use existing or generate new
    Returns the same portrait path for all denominations
    """
    # Clean name for filename matching (handle Unicode)
    try:
        clean_name = re.sub(r'[^\w\-_]', '_', name)
    except UnicodeEncodeError:
        # Fallback for Unicode names
        try:
            clean_name = re.sub(r'[^\w\-_]', '_', name.encode('ascii', 'ignore').decode('ascii'))
        except:
            clean_name = "unknown"
    
    # Look for existing portrait for this name (without timestamp)
    portrait_patterns = [
        os.path.join(PORTRAITS_DIR, f"portrait_{clean_name}.png"),
        os.path.join(PORTRAITS_DIR, f"portrait_{clean_name}.jpg"),
        os.path.join(PORTRAITS_DIR, f"portrait_{clean_name}.jpeg"),
        os.path.join(PORTRAITS_DIR, f"*{clean_name}*.png"),  # Fallback to any pattern
        os.path.join(PORTRAITS_DIR, f"*{clean_name}*.jpg"),
        os.path.join(PORTRAITS_DIR, f"*{clean_name}*.jpeg"),
    ]
    
    if not force_regenerate:
        for pattern in portrait_patterns:
            existing_portraits = glob.glob(pattern)
            if existing_portraits:
                safe_print(f"[+] Using existing portrait: {existing_portraits[0]}")
                return existing_portraits[0]
    
    # Generate new portrait with consistent filename
    return generate_character_portrait(name)

# -----------------------
# Helper: parse denomination from filename
# -----------------------
def parse_denomination_from_filename(filename):
    """Extract denomination from filename patterns like '1.svg', '10.svg', etc."""
    basename = os.path.splitext(filename)[0]
    
    # Look for numbers in the filename
    match = re.search(r'(\d+)', basename)
    if match:
        return match.group(1)
    
    return "1"  # Default fallback

# -----------------------
# Helper: Create proper filename
# -----------------------
def create_proper_filename(name, denom, timestamp, side):
    """Create filename in format: {name}_-_{denom}_-_{timestamp}_{side}.svg"""
    return f"{name}_-_{denom}_-_{timestamp}_{side}.svg"
def safe_print(message):
    """Print message with Unicode fallback handling"""
    try:
        print(message)
    except UnicodeEncodeError:
        # Replace Unicode characters with ASCII equivalents
        safe_message = message.encode('ascii', 'replace').decode('ascii')
        print(safe_message)
# -----------------------
# Main function
# -----------------------
def main():
    args = parse_arguments()
    
    # -----------------------
    # Load or generate portraits
    # -----------------------
    images = []
    if os.path.exists(PORTRAITS_DIR):
        images = [os.path.join(PORTRAITS_DIR, f) for f in os.listdir(PORTRAITS_DIR)
                  if f.lower().endswith(IMAGE_EXTS) and os.path.isfile(os.path.join(PORTRAITS_DIR, f))]

    # -----------------------
    # Read names with proper Unicode handling
    # -----------------------
    try:
        with open(NAMES_FILE, "r", encoding="utf-8") as f:
            all_names = [line.strip() for line in f if line.strip()]
    except UnicodeDecodeError:
        # Fallback for different encodings
        try:
            with open(NAMES_FILE, "r", encoding="latin-1") as f:
                all_names = [line.strip() for line in f if line.strip()]
        except:
            safe_print(f"[!] Could not read {NAMES_FILE} with any encoding!")
            exit(1)
    
    if not all_names:
        safe_print(f"[!] No names found in {NAMES_FILE}!")
        exit(1)
    
        # Filter names if --name flag is provided
    if args.name:
        # Case-insensitive matching with Unicode normalization
        target_name = args.name.strip()
        names_to_process = []
        
        for name in all_names:
            try:
                if name.lower() == target_name.lower():
                    names_to_process.append(name)
                    break
            except UnicodeError:
                # Skip names that cause encoding issues during comparison
                continue
        
        if not names_to_process:
            safe_print(f"[!] Name '{target_name}' not found in {NAMES_FILE}")
            safe_print(f"[+] Adding '{target_name}' to {NAMES_FILE}...")
            
            # Add the name to master.txt
            try:
                with open(NAMES_FILE, "a", encoding="utf-8") as f:
                    f.write(f"\n{target_name}")
                safe_print(f"[+] Added '{target_name}' to {NAMES_FILE}")
                
                # Add to our processing list
                names_to_process = [target_name]
                all_names.append(target_name)  # Also add to current session's list
                
            except Exception as e:
                safe_print(f"[!] Failed to add name to {NAMES_FILE}: {e}")
                exit(1)
    else:
        names_to_process = all_names

    # Safe printing of processing info
    try:
        safe_print(f"[+] Processing {len(names_to_process)} name(s): {', '.join(names_to_process)}")
    except UnicodeEncodeError:
        safe_processing = []
        for name in names_to_process:
            try:
                safe_name = name.encode('ascii', 'replace').decode('ascii')
                safe_processing.append(safe_name)
            except:
                safe_processing.append("?")
        safe_print(f"[+] Processing {len(names_to_process)} name(s): {', '.join(safe_processing)}")

    # -----------------------
    # Main batch generation
    # -----------------------
    for name in names_to_process:
        # Safe printing
        try:
            safe_print(f"\n[+] Processing: {name}")
            safe_print("=" * 50)
        except UnicodeEncodeError:
            safe_name = name.encode('ascii', 'replace').decode('ascii')
            safe_print(f"\n[+] Processing: {safe_name}")
            safe_print("=" * 50)

        # Get or generate ONE portrait for this name (will be used for all 9 bills)
        img_path = get_portrait_for_name(name, args.force_regenerate)
        if not img_path:
            safe_print(f"[!] Failed to get portrait for {name}, using random existing one")
            if images:
                img_path = random.choice(images)
            else:
                safe_print(f"[!] No portraits available for {name}, skipping")
                continue

        safe_print(f"[+] Using portrait for all bills: {img_path}")

        name_folder = os.path.join(OUTPUT_ROOT, name)
        os.makedirs(name_folder, exist_ok=True)

        timestamp = time.strftime("%Y%m%d_%H%M%S")

        # Generate ALL 9 FRONT SVGs at once with --yen_model using the SAME portrait
        try:
            safe_print(f"[+] Generating all 9 front SVGs with the same portrait...")
            import sys
            subprocess.run([
                sys.executable, FRONT_SCRIPT,
                name,
                img_path,  # Same portrait for all denominations
                "--yen_model"
            ], check=True, timeout=1800)
            safe_print(f"[+] Generated all front SVGs for {name}")
            
            # Move and organize the generated SVGs
            front_svgs_created = []
            for svg_file in glob.glob("*.svg"):
                if "BACK" in svg_file:
                    continue
                    
                # Parse denomination from filename
                denom = parse_denomination_from_filename(svg_file)
                
                # Create denomination folder
                denom_folder = os.path.join(name_folder, denom)
                os.makedirs(denom_folder, exist_ok=True)
                
                # Create proper filename and move to denomination folder
                front_new_filename = create_proper_filename(name, denom, timestamp, "FRONT")
                front_svg_new = os.path.join(denom_folder, front_new_filename)
                
                shutil.move(svg_file, front_svg_new)
                front_svgs_created.append(front_svg_new)
                safe_print(f"[+] Organized front: {front_svg_new}")
            
            safe_print(f"[+] Created {len(front_svgs_created)} front SVGs for {name}")
                
        except subprocess.CalledProcessError as e:
            safe_print(f"[!] Failed to generate front SVGs for {name}: {e}")
            continue
        except subprocess.TimeoutExpired:
            safe_print(f"[!] Front SVG generation timed out for {name}")
            continue

        # Generate BACK SVGs - call it once and let it generate all denominations
        try:
            safe_print(f"[+] Generating back SVGs for all denominations...")
            subprocess.run([
                sys.executable, BACK_SCRIPT,
                "--outdir", name_folder,  # Output to main name folder, not denomination folder
                "--basename", f"{name}_-_{timestamp}_BACK"
            ], check=True, timeout=1800)
            
            # Now move the generated back SVGs to their respective denomination folders
            back_files = glob.glob(os.path.join(name_folder, "*BACK*.svg"))
            for back_file in back_files:
                # Extract denomination from filename (e.g., "Dylan_Cheetah_-_20250904_BACK_100.svg")
                filename = os.path.basename(back_file)
                match = re.search(r'BACK_(\d+)\.svg$', filename)
                if match:
                    denom = match.group(1)
                    denom_folder = os.path.join(name_folder, denom)
                    os.makedirs(denom_folder, exist_ok=True)
                    
                    # Move to denomination folder with proper name
                    new_filename = f"{name}_-_{denom}_-_{timestamp}_BACK.svg"
                    new_path = os.path.join(denom_folder, new_filename)
                    shutil.move(back_file, new_path)
                    safe_print(f"[+] Moved back to: {new_path}")
                
        except subprocess.CalledProcessError as e:
            safe_print(f"[!] Failed to generate back SVGs for {name}: {e}")
            continue
        except subprocess.TimeoutExpired:
            safe_print(f"[!] Back SVG generation timed out for {name}")
            continue

        # Process each FRONT/BACK pair
        pdfs_created = 0
        for denom_folder in glob.glob(os.path.join(name_folder, "*")):
            if not os.path.isdir(denom_folder):
                continue
                
            denom = os.path.basename(denom_folder)
            
            # Find front SVG
            front_pattern = os.path.join(denom_folder, f"*FRONT*.svg")
            front_svgs = glob.glob(front_pattern)
            
            if not front_svgs:
                safe_print(f"[!] No front SVG found for {name} denomination {denom}")
                continue
                
            front_svg_path = front_svgs[0]
            
            # Find back SVGs
            back_pattern = os.path.join(denom_folder, f"*BACK*.svg")
            back_svgs = glob.glob(back_pattern)
            
            if not back_svgs:
                safe_print(f"[!] No back SVG found for {name} denomination {denom}")
                continue
                
            # Process each back variant
            for back_svg_path in back_svgs:
                safe_print(f"[+] Processing {denom}卢纳币: {os.path.basename(front_svg_path)} + {os.path.basename(back_svg_path)}")

                # Generate PDFs with proper filenames
                front_pdf = front_svg_path.replace('.svg', '.pdf')
                back_pdf = back_svg_path.replace('.svg', '.pdf')
                final_pdf = os.path.join(denom_folder, f"{name}_-_{denom}_-_{timestamp}_COMBINED.pdf")

                try:
                    import cairosvg
                    cairosvg.svg2pdf(url=front_svg_path, write_to=front_pdf)
                    cairosvg.svg2pdf(url=back_svg_path, write_to=back_pdf)
                    merger = PdfMerger()
                    merger.append(front_pdf)
                    merger.append(back_pdf)
                    merger.write(final_pdf)
                    merger.close()
                    safe_print(f"[✓] Generated PDF: {final_pdf}")
                    pdfs_created += 1
                    
                    # Clean up individual PDFs
                    if os.path.exists(front_pdf):
                        os.remove(front_pdf)
                    if os.path.exists(back_pdf):
                        os.remove(back_pdf)
                        
                except Exception as e:
                    safe_print(f"[!] Failed to generate PDF for {name} denomination {denom}: {e}")

        # Clean up any temporary files
        for temp_file in glob.glob(os.path.join(name_folder, "temp_*")):
            if os.path.isfile(temp_file):
                os.remove(temp_file)

        safe_print(f"[+] Completed {name}: {pdfs_created} PDFs created")

    safe_print("\n[+] All banknotes generation finished!")

if __name__ == "__main__":
    main()