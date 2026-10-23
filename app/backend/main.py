"""
♟ Turniej Szachowy — Backend API
FastAPI + PostgreSQL + JWT

Endpointy zgodne z tym czego wymaga App.jsx (zastępstwo Supabase)
"""

from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Literal, Optional
import asyncpg
import bcrypt
import jwt
import os
import time
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

# ─── CONFIG ──────────────────────────────────────────────────────────────────
DB_URL     = os.getenv("DATABASE_URL", "postgresql://chess:chess_pass@localhost:5432/chess_db")
JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGO   = "HS256"
JWT_EXPIRE = 60 * 24  # minuty → 1 dzień
_INSECURE_DEFAULT_SECRET = "zmien-ten-sekret-na-vps"

if not JWT_SECRET:
    JWT_SECRET = _INSECURE_DEFAULT_SECRET
if JWT_SECRET == _INSECURE_DEFAULT_SECRET and os.getenv("ALLOW_INSECURE_JWT_SECRET") != "1":
    raise RuntimeError(
        "JWT_SECRET nie jest ustawiony (lub ma domyślną, publiczną wartość). "
        "Ustaw bezpieczny, losowy JWT_SECRET w zmiennych środowiskowych przed startem. "
        "Dla lokalnych testów można obejść to ustawiając ALLOW_INSECURE_JWT_SECRET=1."
    )

CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]

# ─── RATE LIMITING (login brute-force protection) ────────────────────────────
LOGIN_MAX_ATTEMPTS = 5
LOGIN_WINDOW_SECONDS = 60
_login_attempts: dict[str, list[float]] = {}

def _check_login_rate_limit(key: str):
    now = time.time()
    attempts = [t for t in _login_attempts.get(key, []) if now - t < LOGIN_WINDOW_SECONDS]
    if len(attempts) >= LOGIN_MAX_ATTEMPTS:
        raise HTTPException(
            status_code=429,
            detail="Za wiele nieudanych logowań. Spróbuj ponownie za minutę.",
        )
    _login_attempts[key] = attempts

def _record_login_failure(key: str):
    _login_attempts.setdefault(key, []).append(time.time())

def _clear_login_attempts(key: str):
    _login_attempts.pop(key, None)

# ─── LIFESPAN ────────────────────────────────────────────────────────────────
pool: asyncpg.Pool = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global pool
    pool = await asyncpg.create_pool(DB_URL, min_size=2, max_size=10)
    yield
    await pool.close()

app = FastAPI(title="Turniej Szachowy API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer(auto_error=False)

# ─── JWT HELPERS ─────────────────────────────────────────────────────────────
def create_token(user_id: int, email: str, role: str) -> str:
    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "exp": datetime.utcnow() + timedelta(minutes=JWT_EXPIRE),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)

def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token wygasł")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Nieprawidłowy token")

async def get_current_user(creds: HTTPAuthorizationCredentials = Depends(security)):
    if not creds:
        raise HTTPException(status_code=401, detail="Brak tokenu")
    return decode_token(creds.credentials)

async def require_teacher(user=Depends(get_current_user)):
    if user["role"] not in ("teacher", "superadmin"):
        raise HTTPException(status_code=403, detail="Brak uprawnień")
    return user

async def require_superadmin(user=Depends(get_current_user)):
    if user["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Tylko superadmin")
    return user

# ─── SCHEMAS ─────────────────────────────────────────────────────────────────
RESULT_VALUES = Literal["", "1-0", "0-1", "0.5-0.5", "wolny los"]

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)

class ParticipantCreate(BaseModel):
    imie: str = Field(min_length=1, max_length=100)
    klasa: str = Field(min_length=1, max_length=20)

class PairCreate(BaseModel):
    round_number: int = Field(gt=0)
    white_id: int
    black_id: Optional[int] = None
    result: RESULT_VALUES = ""

class PairsInsert(BaseModel):
    pairs: list[PairCreate] = Field(min_length=1, max_length=500)

class ResultUpdate(BaseModel):
    result: RESULT_VALUES

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=256)
    role: Literal["teacher", "superadmin"] = "teacher"

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Hasło musi mieć min. 8 znaków.")
        return v

# ─── AUTH ────────────────────────────────────────────────────────────────────
@app.post("/auth/login")
async def login(body: LoginRequest, request: Request):
    rate_key = f"{request.client.host if request.client else 'unknown'}:{body.email.lower()}"
    _check_login_rate_limit(rate_key)

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, email, password_hash, role FROM users WHERE email = $1",
            body.email
        )
    if not row or not bcrypt.checkpw(body.password.encode(), row["password_hash"].encode()):
        _record_login_failure(rate_key)
        raise HTTPException(status_code=401, detail="Nieprawidłowy email lub hasło")

    _clear_login_attempts(rate_key)
    token = create_token(row["id"], row["email"], row["role"])
    return {
        "access_token": token,
        "user": {"id": row["id"], "email": row["email"]},
        "role": row["role"],
    }

@app.get("/auth/me")
async def me(user=Depends(get_current_user)):
    return user

@app.post("/auth/logout")
async def logout():
    # JWT jest bezstanowy — klient po prostu usuwa token
    return {"ok": True}

# ─── USERS (tylko superadmin) ────────────────────────────────────────────────
@app.post("/users", status_code=201)
async def create_user(body: UserCreate, _=Depends(require_superadmin)):
    hashed = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode()
    async with pool.acquire() as conn:
        try:
            row = await conn.fetchrow(
                "INSERT INTO users (email, password_hash, role) VALUES ($1,$2,$3) RETURNING id, email, role",
                body.email, hashed, body.role
            )
        except asyncpg.UniqueViolationError:
            raise HTTPException(status_code=409, detail="Email już istnieje")
    return dict(row)

@app.get("/users")
async def list_users(_=Depends(require_superadmin)):
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT id, email, role FROM users ORDER BY email")
    return [dict(r) for r in rows]

@app.delete("/users/{user_id}", status_code=204)
async def delete_user(user_id: int, _=Depends(require_superadmin)):
    async with pool.acquire() as conn:
        async with conn.transaction():
            target = await conn.fetchrow("SELECT role FROM users WHERE id = $1", user_id)
            if target and target["role"] == "superadmin":
                count = await conn.fetchval("SELECT count(*) FROM users WHERE role = 'superadmin'")
                if count <= 1:
                    raise HTTPException(
                        status_code=409,
                        detail="Nie można usunąć ostatniego konta superadmina.",
                    )
            await conn.execute("DELETE FROM users WHERE id = $1", user_id)

# ─── PARTICIPANTS ────────────────────────────────────────────────────────────
@app.get("/participants")
async def get_participants():
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM participants ORDER BY imie")
    return [dict(r) for r in rows]

@app.post("/participants", status_code=201)
async def add_participant(body: ParticipantCreate, _=Depends(require_teacher)):
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO participants (imie, klasa) VALUES ($1,$2) RETURNING *",
            body.imie, body.klasa
        )
    return dict(row)

@app.delete("/participants/{pid}", status_code=204)
async def delete_participant(pid: int, _=Depends(require_superadmin)):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM participants WHERE id = $1", pid)

@app.delete("/participants", status_code=204)
async def delete_all_participants(_=Depends(require_superadmin)):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM participants")

# ─── PAIRS ───────────────────────────────────────────────────────────────────
@app.get("/pairs")
async def get_pairs():
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM pairs ORDER BY round_number, id")
    return [dict(r) for r in rows]

@app.post("/pairs", status_code=201)
async def insert_pairs(body: PairsInsert, _=Depends(require_teacher)):
    async with pool.acquire() as conn:
        async with conn.transaction():
            inserted = []
            for p in body.pairs:
                try:
                    row = await conn.fetchrow(
                        """INSERT INTO pairs (round_number, white_id, black_id, result)
                           VALUES ($1,$2,$3,$4) RETURNING *""",
                        p.round_number, p.white_id, p.black_id, p.result
                    )
                except asyncpg.UniqueViolationError:
                    raise HTTPException(
                        status_code=409,
                        detail=f"Para dla rundy {p.round_number} z udziałem zawodnika "
                               f"już istnieje (możliwe podwójne wygenerowanie).",
                    )
                inserted.append(dict(row))
    return inserted

@app.patch("/pairs/{pair_id}")
async def update_pair_result(pair_id: int, body: ResultUpdate, _=Depends(require_teacher)):
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "UPDATE pairs SET result=$1 WHERE id=$2 RETURNING *",
            body.result, pair_id
        )
    if not row:
        raise HTTPException(status_code=404, detail="Para nie istnieje")
    return dict(row)

@app.delete("/pairs", status_code=204)
async def delete_all_pairs(_=Depends(require_superadmin)):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM pairs")

# ─── HEALTH ──────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok"}
