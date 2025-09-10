from flask import Blueprint, flash, redirect, url_for
from models import User, GenerationTask
import threading
from app import GENERATION_LOCK, GENERATION_THREADS
from app import get_current_user, run_generation_task

main_bp = Blueprint('main', __name__)

@main_bp.route("/generate-money", methods=["POST"])
def generate_money():
    current_user = get_current_user()
    if not current_user:
        flash("Please log in to generate money", "error")
        return redirect(url_for("main.login"))
    
    if not current_user.can_generate_money():
        flash(f"You can generate money again in {current_user.days_until_next_generation()} days", "error")
        return redirect(url_for("main.profile", username=current_user.username))
    
    with GENERATION_LOCK:
        if current_user.id in GENERATION_THREADS:
            flash("You already have a generation in progress", "error")
            return redirect(url_for("main.profile", username=current_user.username))
    
    thread = threading.Thread(
        target=run_generation_task,
        args=(current_user.id, current_user.username)
    )
    thread.daemon = True
    thread.start()
    
    with GENERATION_LOCK:
        GENERATION_THREADS[current_user.id] = thread
    
    flash("Banknote generation started! This may take a few moments.", "success")
    return redirect(url_for("main.profile", username=current_user.username))