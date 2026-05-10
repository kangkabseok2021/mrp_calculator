import pytest
import os
import sqlite3
from fastapi.testclient import TestClient
from unittest.mock import patch
import sys

# Add the src directory to the python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from api import app
import api
import auth

# We will use a separate test database
TEST_DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), 'test_api.db'))

# Setup the test database
@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    # Patch DB paths in api and auth
    api.DB_PATH = TEST_DB_PATH
    auth.DB_PATH = TEST_DB_PATH
    
    # We can just run db_setup's logic but point to our test DB.
    # To do that cleanly, we patch its DB_FILE before running.
    import db_setup
    db_setup.DB_FILE = TEST_DB_PATH
    db_setup.setup_database()
    
    yield
    
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)

client = TestClient(app)

def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

def test_protected_route_without_token():
    response = client.get("/api/inventory")
    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}

def test_login_success():
    response = client.post(
        "/api/token",
        data={"username": "admin", "password": "admin"},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    return data["access_token"]

def test_login_failure():
    response = client.post(
        "/api/token",
        data={"username": "admin", "password": "wrongpassword"},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    assert response.status_code == 401

def test_protected_route_with_token():
    # Login to get token
    token = test_login_success()
    
    response = client.get(
        "/api/inventory",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    # Check if FG001 is in the seeded test DB
    assert any(item["item_id"] == "FG001" for item in data)

def test_mrp_run():
    token = test_login_success()
    
    response = client.get(
        "/api/mrp/run",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    # It should return a schedule
    assert isinstance(data, list)
    
def test_supplier_crud():
    token = test_login_success()
    headers = {"Authorization": f"Bearer {token}"}
    
    # GET
    res = client.get("/api/suppliers", headers=headers)
    assert res.status_code == 200
    suppliers = res.json()
    initial_count = len(suppliers)
    
    # ADD
    res = client.post(
        "/api/suppliers/add",
        json={"name": "Test Supplier", "contact_email": "test@test.com", "lead_time_modifier": 2},
        headers=headers
    )
    assert res.status_code == 200
    
    res = client.get("/api/suppliers", headers=headers)
    assert len(res.json()) == initial_count + 1
