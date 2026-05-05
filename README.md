# NovaLib

A gamified Mad Libs word game built as a full-stack web application. Users create stories, fill in random word prompts, save their history, and unlock achievements.

**Live demo:** https://web-production-ca412.up.railway.app/

## Features

- User authentication with hashed passwords (secure sign-up and login)
- Mad Libs story generator with multiple templates
- Story history page — view your previously created stories
- Achievements system that rewards user engagement
- SQLite database for persistent user and story data

## Tech Stack

- **Backend:** Python, Flask
- **Database:** SQLite
- **Frontend:** HTML, CSS, JavaScript
- **Testing:** pytest (14 unit tests covering authentication, edge cases, and failure scenarios)
- **Deployment:** Railway

## Running Locally

1. Clone the repository:
git clone https://github.com/niceNiceiain2/NovaLib.git
cd NovaLib

2. Install dependencies:
pip install -r requirements.txt

3. Run the app:
python app.py

4. Open your browser to `http://localhost:5000`

## Running Tests
pytest

## Project Structure

- `app.py` — main Flask application and routes
- `templates/` — HTML templates
- `static/` — CSS and JavaScript files
- `tests/` — pytest test suite
- `database.db` — SQLite database file

## About

Built by Iain Summerlin as a personal project to practice full-stack development, authentication patterns, and test-driven development.
