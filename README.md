# Ling County Treasury

A Flask application for creating and collecting digital banknotes.

## Quick Start

```bash
# Clone and setup
git clone <your-repo-url>
cd LingBanknotes
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Mac/Linux
pip install -r requirements.txt

# Configure (create .env file)
echo "SECRET_KEY=your-secret-key-here" > .env
echo "DEBUG=True" >> .env

# Initialize database
python -c "from app import db; db.create_all()"

# Run application
python app.py
```
Visit http://localhost:5000 in your browser.
# Configuration

Create a .env file with:
env

SECRET_KEY=your-random-secret-key
DATABASE_URL=sqlite:///lingbanknotes.db
DEBUG=True
IMAGES_ROOT=./images

# Key Features
```
    User registration & authentication

    Digital banknote generation

    Profile customization

    Banknote gallery

    Two-factor authentication
```
#Project Structure
```text

app.py          # Main application
models.py       # Database models
utils.py        # Banknote generation logic
templates/      # HTML templates
images/         # Generated banknotes
```
# Default Admin Account

First-time setup creates an admin user:
```bash
python install_database.py
```

# Troubleshooting

    Database issues: python -c "from app import db; db.create_all()"

    Missing dependencies: pip install -r requirements.txt

    Port already in use: Change port in app.py
