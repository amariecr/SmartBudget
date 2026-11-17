
import pytest
from app import create_app, db, money


@pytest.fixture
def app(tmp_path):
    database_path = tmp_path / "test.db"

    application = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{database_path}",
        "WTF_CSRF_ENABLED": False,
        "SECRET_KEY": "test-only-secret-key",
    })

    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def test_home_redirects_to_login(client):
    response = client.get("/")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_login_page_loads(client):
    response = client.get("/login")
    assert response.status_code == 200


def test_registration_page_loads(client):
    response = client.get("/register")
    assert response.status_code == 200


def test_dashboard_requires_login(client):
    response = client.get("/dashboard")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_valid_money():
    assert money("100.50") == 100.50
    assert money("25") == 25


def test_invalid_money():
    with pytest.raises(ValueError):
        money("-10")

    with pytest.raises(ValueError):
        money("invalid")

