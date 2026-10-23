"""
Testy integracyjne API na prawdziwym PostgreSQL.

Uruchomienie (pomijane, gdy brak TEST_DATABASE_URL):
  docker run -d --rm --name chesspg -e POSTGRES_PASSWORD=pw -e POSTGRES_USER=chess \
      -e POSTGRES_DB=chess_db -p 55432:5432 postgres:15
  TEST_DATABASE_URL=postgresql://chess:pw@localhost:55432/chess_db pytest test_api_integration.py
"""
import os
import pathlib

DB = os.getenv("TEST_DATABASE_URL")
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")
os.environ["ALLOW_INSECURE_JWT_SECRET"] = "1"
if DB:
    os.environ["DATABASE_URL"] = DB

import asyncpg
import bcrypt
import pytest
from fastapi.testclient import TestClient

import main

pytestmark = pytest.mark.skipif(not DB, reason="TEST_DATABASE_URL nie ustawiony")
SCHEMA = (pathlib.Path(__file__).parent.parent / "scripts" / "schema.sql").read_text()


@pytest.fixture()
def client():
    import asyncio

    async def reset():
        c = await asyncpg.connect(DB)
        await c.execute("DROP TABLE IF EXISTS pairs, participants, users CASCADE")
        await c.execute(SCHEMA)
        await c.execute(SCHEMA)  # schemat musi być idempotentny
        h = bcrypt.hashpw(b"adminpass1", bcrypt.gensalt()).decode()
        await c.execute("INSERT INTO users (email,password_hash,role) VALUES ('admin@x.pl',$1,'superadmin')", h)
        await c.execute("INSERT INTO users (email,password_hash,role) VALUES ('t@x.pl',$1,'teacher')", h)
        await c.close()

    asyncio.run(reset())
    main._login_attempts.clear()
    with TestClient(main.app) as c:
        yield c


def login(client, email):
    r = client.post("/auth/login", json={"email": email, "password": "adminpass1"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def add_players(client, h, n):
    return [client.post("/participants", json={"imie": f"P{i}", "klasa": "1A"}, headers=h).json()["id"] for i in range(n)]


def test_login_wrong_password_and_rate_limit(client):
    for _ in range(5):
        assert client.post("/auth/login", json={"email": "t@x.pl", "password": "bad"}).status_code == 401
    assert client.post("/auth/login", json={"email": "t@x.pl", "password": "adminpass1"}).status_code == 429


def test_role_enforcement(client):
    t = login(client, "t@x.pl")
    assert client.post("/participants", json={"imie": "A", "klasa": "1"}).status_code == 401
    assert client.get("/users", headers=t).status_code == 403
    pid = add_players(client, t, 1)[0]
    assert client.delete(f"/participants/{pid}", headers=t).status_code == 403
    assert client.delete("/pairs", headers=t).status_code == 403


def test_pairs_validation_and_duplicates(client):
    h = login(client, "admin@x.pl")
    a, b, c = add_players(client, h, 3)
    ok = {"pairs": [{"round_number": 1, "white_id": a, "black_id": b}, {"round_number": 1, "white_id": c, "black_id": None, "result": "wolny los"}]}
    assert client.post("/pairs", json=ok, headers=h).status_code == 201
    # ten sam zawodnik kolejny raz w rundzie 1 (jako czarny) -> 409
    dup = {"pairs": [{"round_number": 1, "white_id": c, "black_id": a}]}
    assert client.post("/pairs", json=dup, headers=h).status_code == 409
    # zawodnik dwa razy w jednym żądaniu / sam ze sobą -> 422
    assert client.post("/pairs", json={"pairs": [{"round_number": 2, "white_id": a, "black_id": a}]}, headers=h).status_code == 422
    twice = {"pairs": [{"round_number": 2, "white_id": a, "black_id": b}, {"round_number": 2, "white_id": b, "black_id": c}]}
    assert client.post("/pairs", json=twice, headers=h).status_code == 422
    # nieznany zawodnik -> 422, nieprawidłowy wynik -> 422
    assert client.post("/pairs", json={"pairs": [{"round_number": 3, "white_id": 9999, "black_id": a}]}, headers=h).status_code == 422
    assert client.post("/pairs", json={"pairs": [{"round_number": 3, "white_id": a, "black_id": b, "result": "9-9"}]}, headers=h).status_code == 422


def test_pairs_insert_is_atomic(client):
    h = login(client, "admin@x.pl")
    a, b = add_players(client, h, 2)
    bad = {"pairs": [{"round_number": 1, "white_id": a, "black_id": b}, {"round_number": 1, "white_id": 9999, "black_id": None, "result": "wolny los"}]}
    assert client.post("/pairs", json=bad, headers=h).status_code == 422
    assert client.get("/pairs").json() == []  # nic nie zostało zapisane


def test_patch_result_and_validation(client):
    h = login(client, "t@x.pl")
    a, b = add_players(client, h, 2)
    pair = client.post("/pairs", json={"pairs": [{"round_number": 1, "white_id": a, "black_id": b}]}, headers=h).json()[0]
    assert client.patch(f"/pairs/{pair['id']}", json={"result": "1-0"}, headers=h).json()["result"] == "1-0"
    assert client.patch(f"/pairs/{pair['id']}", json={"result": "garbage"}, headers=h).status_code == 422
    assert client.patch("/pairs/99999", json={"result": "1-0"}, headers=h).status_code == 404


def test_cannot_delete_last_superadmin_and_user_validation(client):
    h = login(client, "admin@x.pl")
    admin_id = next(u["id"] for u in client.get("/users", headers=h).json() if u["role"] == "superadmin")
    assert client.delete(f"/users/{admin_id}", headers=h).status_code == 409
    assert client.post("/users", json={"email": "n@x.pl", "password": "short", "role": "teacher"}, headers=h).status_code == 422
    assert client.post("/users", json={"email": "n@x.pl", "password": "longenough1", "role": "root"}, headers=h).status_code == 422
    assert client.post("/users", json={"email": "t@x.pl", "password": "longenough1"}, headers=h).status_code == 409


def test_db_constraints_reject_bad_rows(client):
    import asyncio

    async def go():
        c = await asyncpg.connect(DB)
        pid = await c.fetchval("INSERT INTO participants (imie,klasa) VALUES ('A','1') RETURNING id")
        with pytest.raises(asyncpg.CheckViolationError):
            await c.execute("INSERT INTO pairs (round_number,white_id,black_id) VALUES (1,$1,$1)", pid)
        with pytest.raises(asyncpg.CheckViolationError):
            await c.execute("INSERT INTO pairs (round_number,white_id,result) VALUES (1,$1,'xx')", pid)
        await c.close()

    asyncio.run(go())
