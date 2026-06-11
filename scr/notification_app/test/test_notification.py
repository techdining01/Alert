import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine, pool
from ....scr import app  
from ...database import get_session


# 1. Setup a clean, independent In-Memory SQLite Engine for Testing
TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=pool.StaticPool,
)


# 2. Create a session dependency override fixture
def override_get_session():
    with Session(engine) as session:
        yield session


# 3. Create a Pytest fixture to handle database setup and teardown automatically
@pytest.fixture(name="client")
def client_fixture():
    # Force application tables to generate on the test engine
    SQLModel.metadata.create_all(engine)

    # Override the real session with our in-memory session wrapper
    app.dependency_overrides[get_session] = override_get_session

    with TestClient(app) as client:
        yield client

    # Wipe tables clean after the specific test ends
    SQLModel.metadata.drop_all(engine)
    app.dependency_overrides.clear()


# --- THE LOGIC TESTS ---


def test_create_and_update_preferences(client):
    """Verifies that patching a non-existent user profile initializes it properly."""
    user_id = "user_test_445"

    # Send a partial modification patch payload
    response = client.patch(
        f"/users/{user_id}/preferences", json={"email_enabled": False}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["preferences"]["user_id"] == user_id
    assert data["preferences"]["email_enabled"] is False  # Explicitly updated
    assert data["preferences"]["sms_enabled"] is True  # Fell back to schema default


def test_notification_blocked_by_preferences(client):
    """Verifies core logic intercepts and blocks an API call if user has muted a channel."""
    user_id = "user_muted_11"

    # Step A: Mute emails via our preference helper route
    client.patch(f"/users/{user_id}/preferences", json={"email_enabled": False})

    # Step B: Attempt to trigger an email message invocation payload
    notification_payload = {
        "user_id": user_id,
        "recipient_email": "target@example.com",
        "message": "Verify your device login.",
        "channel": "email",
    }

    response = client.post("/notifications/send", json=notification_payload)

    # Assert that core preference engine stops processing and returns 400
    assert response.status_code == 400
    assert "muted email notifications" in response.json()["detail"]
