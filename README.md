# ✦ NovaLib ✦

A gamified Mad Libs word game built with Python and Flask. Players choose from 11 story templates, fill in the blanks with funny words, and generate a hilarious completed story.

Live Demo: https://web-production-ca412.up.railway.app

## Features

- 11 Story Templates — Space Adventure, Pirate Adventure, Superhero Showdown, Haunted House, and more
- User Accounts — Sign up and log in with a username and hashed password
- Story History — Every completed story is saved to a database so you can revisit past games
- Achievements System — Earn badges for using specific words, completing milestones, and more
- Leaderboard — See who has played the most stories
- 14 Pytest Unit Tests — Authentication functionality, edge cases, and failure scenarios tested

## Tech Stack

- Backend: Python, Flask
- Database: SQLite
- Frontend: HTML, CSS, JavaScript
- Testing: pytest
- Deployment: Railway
- Version Control: Git, GitHub

## Getting Started

1. Clone the repository
   git clone https://github.com/niceNiceiain2/madlibs.git
   cd madlibs

2. Install dependencies
   pip install -r requirements.txt

3. Run the app
   python app.py

4. Open http://127.0.0.1:5000 in your browser

## Running Tests

pytest test_auth_pytest.py -v

All 14 tests cover user registration, login, password hashing, and session management.

## API Endpoints

- POST /api/register — Create a new user account
- POST /api/login — Log in to an existing account
- POST /api/logout — Log out
- GET /api/me — Get current logged in user
- GET /api/stories — List all available stories
- POST /api/generate — Submit answers and get completed story
- GET /api/history — Get current user's story history
- GET /api/achievements — Get all achievements
- GET /api/leaderboard — Get all users ranked by stories played

## Built By

Iain Summerlin — built as a personal project to learn full stack web development with Python, Flask, and SQLite.