"""Tests run against throwaway schemas inside starter_app; no other database is created."""

import base64
import os
import uuid

_run_id = uuid.uuid4().hex[:10]
os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_SCHEMA"] = f"test_admin_{_run_id}"
os.environ["CLIENT_DATABASE_SCHEMA"] = f"test_client_{_run_id}"
os.environ["MFA_ENCRYPTION_KEY"] = base64.urlsafe_b64encode(os.urandom(32)).decode()
os.environ["MFA_ENCRYPTION_KEY_ID"] = "k1"
os.environ["COOKIE_SECURE"] = "false"
os.environ["CORS_ORIGINS"] = "http://localhost:5173"
os.environ["ARGON2_TIME_COST"] = "1"
os.environ["ARGON2_MEMORY_COST_KIB"] = "64"
os.environ["ARGON2_PARALLELISM"] = "1"
os.environ["LOG_LEVEL"] = "WARNING"
