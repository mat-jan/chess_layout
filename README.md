# ♟ Turniej Szachowy — migracja na Supabase

Ten projekt przestaje korzystać z własnego backendu FastAPI + PostgreSQL na VPS.
Zamiast tego frontend łączy się bezpośrednio z **Supabase** (Auth + Postgres + RLS),
a jedyna operacja wymagająca uprawnień administratora (tworzenie kont) jest
obsługiwana przez **Edge Function**.

## Co się zmienia

| Wcześniej (VPS)                          | Teraz (Supabase)                              |
|-------------------------------------------|------------------------------------------------|
| `backend/main.py` (FastAPI)               | **usunięte** — niepotrzebne                     |
| Własny JWT (`JWT_SECRET`)                 | Supabase Auth (JWT zarządzany automatycznie)    |
| Tabela `users` + bcrypt                   | `auth.users` (Supabase) + tabela `profiles`     |
| `chess-backend.service` (systemd)         | **usunięte**                                    |
| `scripts/seed.py`                         | ręczne utworzenie pierwszego superadmina (patrz niżej) |
| `DATABASE_URL`, `JWT_SECRET` w `.env`     | `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`   |
| `POST /users` w FastAPI                   | Edge Function `create-user`                     |
| `chess-frontend.service` (serwuje build)  | **zostaje bez zmian**                           |

Dostałeś 4 pliki:

- **`schema-supabase.sql`** — schemat bazy (tabele `profiles`, `participants`, `pairs`) + RLS
- **`App.jsx`** — frontend przepisany pod `supabase-js`, zastępuje `frontend/App.jsx`
- **`create-user/index.ts`** — Edge Function do tworzenia kont (uruchamia się po stronie Supabase, nie na VPS)
- **`frontend.env.example`** — wzór nowego `.env` dla frontendu

---

## Krok 1 — Załóż projekt Supabase

1. Wejdź na [supabase.com](https://supabase.com) → **New project**.
2. Zapisz sobie z **Project Settings → API**:
   - `Project URL`
   - klucz `anon public`
   - (do kroku 3) `Project Reference ID` — widoczny w URL projektu i w ustawieniach

## Krok 2 — Wgraj schemat bazy

1. W Supabase: **SQL Editor → New query**.
2. Wklej całą zawartość `schema-supabase.sql` i kliknij **Run**.
3. To tworzy tabele `profiles`, `participants`, `pairs` oraz reguły RLS (kto co może robić).

## Krok 3 — Utwórz pierwszego superadmina (ręcznie, raz)

Chicken-and-egg: Edge Function do tworzenia kont wymaga, żeby wywołujący *już* był superadminem — więc pierwsze konto zakładasz ręcznie:

1. Supabase → **Authentication → Users → Add user** — podaj e-mail i hasło, zaznacz "Auto Confirm User".
2. Skopiuj **UUID** nowo utworzonego użytkownika (kolumna `id` na liście).
3. Wróć do **SQL Editor** i uruchom (podmieniając wartości):
   ```sql
   insert into public.profiles (id, email, role)
   values ('WKLEJONY-UUID', 'twoj@email.pl', 'superadmin');
   ```
4. Od teraz możesz się tym kontem zalogować w aplikacji i tworzyć kolejne konta (teacher/superadmin) z panelu bocznego.

## Krok 4 — Wdróż Edge Function

Potrzebujesz [Supabase CLI](https://supabase.com/docs/guides/cli) (`npm install -g supabase` albo `brew install supabase/tap/supabase`).

```bash
supabase login
supabase link --project-ref TWOJ-PROJECT-REF

mkdir -p supabase/functions
cp -r create-user supabase/functions/

supabase functions deploy create-user
```

Sekrety (`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_ANON_KEY`) są wstrzykiwane automatycznie przez Supabase — nic nie trzeba ustawiać ręcznie.

## Krok 5 — Podmień frontend

```bash
cd frontend
npm install @supabase/supabase-js
```

- Zamień `frontend/App.jsx` na przesłany plik `App.jsx`.
- Skopiuj `frontend.env.example` jako `frontend/.env` i uzupełnij `VITE_SUPABASE_URL` / `VITE_SUPABASE_ANON_KEY` z Kroku 1.
- Usuń stare zmienne (`VITE_API_URL`) — nie są już używane.

```bash
npm run build
node serve.js    # bez zmian — nadal serwuje dist/ na porcie 3000
```

## Krok 6 — Posprzątaj VPS

Możesz bezpiecznie usunąć:

```bash
systemctl stop chess-backend
systemctl disable chess-backend
rm /etc/systemd/system/chess-backend.service
rm -rf /root/app/backend
```

`chess-frontend.service` **zostaw** — frontend nadal musi być gdzieś serwowany.
PostgreSQL na VPS też możesz odinstalować, jeśli nic innego go nie używa — cała baza teraz żyje w Supabase.

---

## Jak to teraz działa (skrót)

- **Logowanie**: `supabase.auth.signInWithPassword()` — Supabase sam zarządza sesją i tokenem (nic nie trzymamy ręcznie w `localStorage`).
- **Rola** (teacher/superadmin) leży w tabeli `profiles`, powiązanej z `auth.users` przez `id`.
- **Kto co widzi/może robić** — pilnuje tego **RLS** w bazie (polityki w `schema-supabase.sql`), nie kod frontendu. Nawet gdyby ktoś ominął UI, baza i tak odrzuci nieuprawnioną operację.
- **Goście** (niezalogowani) mają dostęp tylko do odczytu (`select`) uczestników i par — zero zmian w logice.
- **Tworzenie kont**: tylko superadmin, przez panel w aplikacji → wywołuje Edge Function `create-user` → ta sprawdza uprawnienia wywołującego i dopiero wtedy tworzy konto kluczem `service_role` (który nigdy nie trafia do przeglądarki).

## Najczęstsze problemy

- **"Tylko superadmin może tworzyć konta"** mimo zalogowania jako superadmin → sprawdź, czy w tabeli `profiles` rola faktycznie jest ustawiona (Krok 3).
- **Puste dane po zalogowaniu** → sprawdź w konsoli przeglądarki błędy RLS (`new row violates row-level security policy`) — zwykle znaczy, że profil użytkownika nie ma poprawnej roli.
- **CORS / błąd wywołania Edge Function** → upewnij się, że `supabase functions deploy create-user` zakończyło się sukcesem (`supabase functions list` pokaże status).