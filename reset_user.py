#!/usr/bin/env python3
"""
Script to remove GenerationTasks for a specific user, reset their generation ability,
and delete their image folder.
"""

import sys
import os
import shutil
from datetime import datetime, timedelta

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def delete_user_folder(username):
    """
    Delete the user's image folder if it exists.
    
    Args:
        username (str): The username whose folder to delete
    """
    folder_path = os.path.join('images', username)
    
    if os.path.exists(folder_path):
        try:
            shutil.rmtree(folder_path)
            print(f"Deleted user folder: {folder_path}")
            return True
        except Exception as e:
            print(f"Error deleting folder {folder_path}: {e}")
            return False
    else:
        print(f"User folder does not exist: {folder_path}")
        return True  # Consider it successful if folder doesn't exist

def reset_user_generation(user_identifier):
    """
    Remove all GenerationTasks for a user, reset balance, reset generation ability,
    and delete their image folder.
    
    Args:
        user_identifier: Can be user ID (int) or username (str)
    """
    try:
        # Import inside function to avoid circular imports
        from app import app, db
        from models import GenerationTask, User
        
        with app.app_context():
            # Find the user by ID or username
            if isinstance(user_identifier, int) or user_identifier.isdigit():
                user = User.query.get(int(user_identifier))
            else:
                user = User.query.filter_by(username=user_identifier).first()
            
            if not user:
                print(f"Error: User '{user_identifier}' not found.")
                return False
            
            print(f"Found user: {user.id} (username: {user.username})")
            
            # Remove all generation tasks for this user
            tasks_deleted = GenerationTask.query.filter_by(user_id=user.id).delete()
            print(f"Deleted {tasks_deleted} generation tasks for user {user.username}")
            
            # Reset the last_generation timestamp to allow immediate generation
            if hasattr(user, 'last_generation'):
                user.last_generation = None
                print("Reset last_generation timestamp")
            else:
                print("Warning: User model doesn't have last_generation attribute")
            
            # Reset balance to 0 - try common field names
            balance_reset = False
            for field_name in ['balance', 'money', 'coins', 'credits', 'points']:
                if hasattr(user, field_name):
                    setattr(user, field_name, 0)
                    print(f"Reset {field_name} to 0")
                    balance_reset = True
                    break
            
            if not balance_reset:
                print("Warning: User model doesn't have a recognizable balance attribute")
            
            # Commit database changes first
            db.session.commit()
            print(f"Successfully reset generation ability and balance for user {user.username}")
            
            # Delete the user's image folder after successful DB commit
            folder_deleted = delete_user_folder(user.username)
            if not folder_deleted:
                print("Warning: Could not delete user folder, but database changes were committed")
            
            return True
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    if len(sys.argv) != 2:
        print("Usage: python reset_user.py <user_id_or_username>")
        print("Example: python reset_user.py 123")
        print("Example: python reset_user.py LingLinOfficial")
        sys.exit(1)
    
    user_identifier = sys.argv[1]
    print(f"Attempting to reset generation for: {user_identifier}")
    
    success = reset_user_generation(user_identifier)
    if success:
        print("Operation completed successfully!")
    else:
        print("Operation failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()