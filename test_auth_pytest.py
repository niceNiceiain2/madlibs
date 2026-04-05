import pytest
import json
import os
import tempfile
import sys

sys.path.insert(0, os.path.dirname(__file__))
import app as novalib_app


@pytest.fixture
def client():
    """Create a fresh test client with a temporary database for each test."""
    db_fd, db_path = tempfile.mkstemp()
    novalib_app.DB_PATH = db_path
    novalib_app.init_db()
    novalib_app.app.config['TESTING']  = True
    novalib_app.app.config['SECRET_KEY'] = 'test-secret'

    with novalib_app.app.test_client() as client:
        yield client

    os.close(db_fd)
    os.unlink(db_path)


# ── Registration tests ────────────────────────────────────────────────────────

def test_register_success(client):
    """A new user can register with a valid username and password."""
    res  = client.post('/api/register',
                       data=json.dumps({'username': 'testuser', 'password': 'secret123'}),
                       content_type='application/json')
    data = json.loads(res.data)
    assert res.status_code == 200
    assert data['username'] == 'testuser'

def test_register_duplicate_username(client):
    """Registering with a username that already exists should fail."""
    client.post('/api/register',
                data=json.dumps({'username': 'testuser', 'password': 'secret123'}),
                content_type='application/json')
    res  = client.post('/api/register',
                       data=json.dumps({'username': 'testuser', 'password': 'different'}),
                       content_type='application/json')
    data = json.loads(res.data)
    assert res.status_code == 400
    assert 'error' in data

def test_register_short_password(client):
    """Password shorter than 6 characters should be rejected."""
    res  = client.post('/api/register',
                       data=json.dumps({'username': 'testuser', 'password': '123'}),
                       content_type='application/json')
    data = json.loads(res.data)
    assert res.status_code == 400
    assert 'error' in data

def test_register_empty_username(client):
    """Empty username should be rejected."""
    res  = client.post('/api/register',
                       data=json.dumps({'username': '', 'password': 'secret123'}),
                       content_type='application/json')
    data = json.loads(res.data)
    assert res.status_code == 400
    assert 'error' in data

def test_register_password_with_spaces(client):
    """Password with spaces should be allowed."""
    res  = client.post('/api/register',
                       data=json.dumps({'username': 'testuser', 'password': 'hello world'}),
                       content_type='application/json')
    data = json.loads(res.data)
    assert res.status_code == 200
    assert data['username'] == 'testuser'

def test_username_with_numbers(client):
    """Username with numbers should be allowed."""
    res  = client.post('/api/register',
                       data=json.dumps({'username': 'user123', 'password': 'secret123'}),
                       content_type='application/json')
    data = json.loads(res.data)
    assert res.status_code == 200
    assert data['username'] == 'user123'

# ── Login tests ───────────────────────────────────────────────────────────────

def test_login_success(client):
    """A registered user can log in with the correct password."""
    client.post('/api/register',
                data=json.dumps({'username': 'testuser', 'password': 'secret123'}),
                content_type='application/json')
    res  = client.post('/api/login',
                       data=json.dumps({'username': 'testuser', 'password': 'secret123'}),
                       content_type='application/json')
    data = json.loads(res.data)
    assert res.status_code == 200
    assert data['username'] == 'testuser'

def test_login_wrong_password(client):
    """Login with the wrong password should be rejected."""
    client.post('/api/register',
                data=json.dumps({'username': 'testuser', 'password': 'secret123'}),
                content_type='application/json')
    res  = client.post('/api/login',
                       data=json.dumps({'username': 'testuser', 'password': 'wrongpassword'}),
                       content_type='application/json')
    data = json.loads(res.data)
    assert res.status_code == 401
    assert 'error' in data

def test_login_nonexistent_user(client):
    """Login with a username that doesn't exist should be rejected."""
    res  = client.post('/api/login',
                       data=json.dumps({'username': 'nobody', 'password': 'secret123'}),
                       content_type='application/json')
    data = json.loads(res.data)
    assert res.status_code == 401
    assert 'error' in data

def test_login_empty_fields(client):
    """Login with empty username or password should be rejected."""
    res  = client.post('/api/login',
                       data=json.dumps({'username': '', 'password': ''}),
                       content_type='application/json')
    data = json.loads(res.data)
    assert res.status_code == 400
    assert 'error' in data

# ── Password hashing tests ────────────────────────────────────────────────────

def test_password_is_hashed(client):
    """Password should never be stored as plain text in the database."""
    client.post('/api/register',
                data=json.dumps({'username': 'testuser', 'password': 'secret123'}),
                content_type='application/json')
    with novalib_app.get_db() as db:
        user = db.execute("SELECT password FROM users WHERE username='testuser'").fetchone()
    assert user['password'] != 'secret123'
    assert ':' in user['password']

# ── Session tests ─────────────────────────────────────────────────────────────

def test_me_not_logged_in(client):
    """/api/me should return null user when not logged in."""
    res  = client.get('/api/me')
    data = json.loads(res.data)
    assert data['user'] is None

def test_me_logged_in(client):
    """/api/me should return user info when logged in."""
    client.post('/api/register',
                data=json.dumps({'username': 'testuser', 'password': 'secret123'}),
                content_type='application/json')
    res  = client.get('/api/me')
    data = json.loads(res.data)
    assert data['user'] is not None
    assert data['user']['username'] == 'testuser'

def test_logout(client):
    """After logging out /api/me should return null user."""
    client.post('/api/register',
                data=json.dumps({'username': 'testuser', 'password': 'secret123'}),
                content_type='application/json')
    client.post('/api/logout')
    res  = client.get('/api/me')
    data = json.loads(res.data)
    assert data['user'] is None
