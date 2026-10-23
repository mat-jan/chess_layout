"""
Testy jednostkowe walidacji i reguł biznesowych backendu.

Nie wymagają działającej bazy danych — testują wyłącznie modele Pydantic
i pomocnicze funkcje rate-limitera z main.py. Testy integracyjne endpointów
(z realnym Postgresem) wymagałyby docker-compose / pytest-postgresql i nie są
objęte tym plikiem.

Uruchomienie:  ALLOW_INSECURE_JWT_SECRET=1 pytest app/backend/test_main.py
"""
import os
import time

os.environ.setdefault("ALLOW_INSECURE_JWT_SECRET", "1")
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")

import pytest
from pydantic import ValidationError

import main


def test_login_request_rejects_invalid_email():
    with pytest.raises(ValidationError):
        main.LoginRequest(email="not-an-email", password="secret123")


def test_user_create_rejects_short_password():
    with pytest.raises(ValidationError):
        main.UserCreate(email="a@b.com", password="short", role="teacher")


def test_user_create_rejects_invalid_role():
    with pytest.raises(ValidationError):
        main.UserCreate(email="a@b.com", password="longenough1", role="hacker")


def test_user_create_accepts_valid_payload():
    u = main.UserCreate(email="a@b.com", password="longenough1", role="teacher")
    assert u.role == "teacher"


def test_participant_create_rejects_empty_or_overlong_fields():
    with pytest.raises(ValidationError):
        main.ParticipantCreate(imie="", klasa="1A")
    with pytest.raises(ValidationError):
        main.ParticipantCreate(imie="a" * 101, klasa="1A")


def test_result_update_rejects_arbitrary_strings():
    with pytest.raises(ValidationError):
        main.ResultUpdate(result="not-a-real-result")
    # all legal values must be accepted
    for v in ["", "1-0", "0-1", "0.5-0.5", "wolny los"]:
        main.ResultUpdate(result=v)


def test_pair_create_requires_positive_round_number():
    with pytest.raises(ValidationError):
        main.PairCreate(round_number=0, white_id=1)
    main.PairCreate(round_number=1, white_id=1)


def test_login_rate_limiter_blocks_after_max_attempts():
    key = f"test-key-{time.time()}"
    for _ in range(main.LOGIN_MAX_ATTEMPTS):
        main._check_login_rate_limit(key)
        main._record_login_failure(key)
    with pytest.raises(Exception):
        main._check_login_rate_limit(key)
    main._clear_login_attempts(key)
    # after clearing, should be allowed again
    main._check_login_rate_limit(key)


def test_jwt_secret_fails_fast_on_insecure_default(monkeypatch):
    """Re-importing main with the public default secret and no override must raise."""
    import importlib
    import sys

    monkeypatch.delenv("ALLOW_INSECURE_JWT_SECRET", raising=False)
    monkeypatch.delenv("JWT_SECRET", raising=False)
    sys.modules.pop("main", None)
    with pytest.raises(RuntimeError):
        importlib.import_module("main")
    # restore for any subsequent tests importing main
    sys.modules.pop("main", None)
    monkeypatch.setenv("ALLOW_INSECURE_JWT_SECRET", "1")
    importlib.import_module("main")
