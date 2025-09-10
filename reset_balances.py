# reset_generation.py
import os
import shutil
from datetime import datetime
from models import db, User, Banknote, SerialNumber, GenerationTask
from app import app

def reset_system():
    """Move images to archive and reset user generation data"""
    with app.app_context():
        try:
            print("Starting system reset...")
            
            # 1. Archive images
            archive_images()
            
            # 2. Reset user data
            reset_user_data()
            
            # 3. Clean up database records
            cleanup_database()
            
            print("System reset completed successfully!")
            
        except Exception as e:
            print(f"Error during system reset: {e}")
            import traceback
            traceback.print_exc()

def archive_images():
    """Move images to archive folder with timestamp"""
    images_dir = "./images"
    archive_base = "./old/old_images"
    
    if not os.path.exists(images_dir):
        print(f"Images directory '{images_dir}' does not exist.")
        return
    
    # Create archive directory with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_dir = os.path.join(archive_base, f"archive_{timestamp}")
    
    os.makedirs(archive_dir, exist_ok=True)
    
    # Move all contents from images to archive
    for item in os.listdir(images_dir):
        source_path = os.path.join(images_dir, item)
        dest_path = os.path.join(archive_dir, item)
        
        if os.path.isdir(source_path):
            shutil.move(source_path, dest_path)
            print(f"Moved directory: {item} -> {archive_dir}/")
        else:
            shutil.move(source_path, dest_path)
            print(f"Moved file: {item} -> {archive_dir}/")
    
    print(f"All images archived to: {archive_dir}")

def reset_user_data():
    """Reset balance and generation timestamps for all users"""
    users = User.query.all()
    
    for user in users:
        user.balance = 0.0
        user.last_generation = None
        print(f"Reset user {user.username}: balance=$0, last_generation=None")
    
    db.session.commit()
    print(f"Reset data for {len(users)} users")

def cleanup_database():
    """Clean up banknote and generation task records"""
    # Delete all banknotes and serial numbers
    banknotes_count = Banknote.query.delete()
    serials_count = SerialNumber.query.delete()
    
    # Delete all generation tasks
    tasks_count = GenerationTask.query.delete()
    
    db.session.commit()
    
    print(f"Cleaned up database:")
    print(f"  - Removed {banknotes_count} banknote records")
    print(f"  - Removed {serials_count} serial number records")
    print(f"  - Removed {tasks_count} generation task records")

def create_backup():
    """Create a backup of the database before reset"""
    backup_dir = "./backups"
    os.makedirs(backup_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(backup_dir, f"bank_backup_{timestamp}.db")
    
    if os.path.exists("bank.db"):
        shutil.copy2("bank.db", backup_file)
        print(f"Database backed up to: {backup_file}")
    else:
        print("No database file found to backup")

if __name__ == "__main__":
    print("=" * 60)
    print("SYSTEM RESET TOOL")
    print("=" * 60)
    print("This will:")
    print("1. Archive all images to ./old/old_images/")
    print("2. Reset all user balances to $0")
    print("3. Clear all generation timestamps")
    print("4. Remove all banknote and task records from database")
    print("=" * 60)
    
    confirmation = input("Are you sure you want to continue? (yes/NO): ")
    
    if confirmation.lower() in ['yes', 'y']:
        # Create backup first
        create_backup()
        
        # Perform reset
        reset_system()
    else:
        print("Reset cancelled.")