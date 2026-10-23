# ♟ Turniej Szachowy

Aplikacja React (Vite) + **Supabase** (Auth + Postgres + RLS). Wdrożenie: Vercel.

> Wersja z własnym backendem FastAPI + PostgreSQL na VPS znajduje się w gałęzi **`vps`**.

## Struktura

```
app/
├── frontend/      React + Vite (App.jsx, pairing.js + testy)
└── supabase/
    ├── schema.sql                     schemat + RLS (SQL Editor → Run)
    ├── 001_integrity.sql              opcjonalna migracja integralności (idempotentna)
    └── functions/create-user/         Edge Function do tworzenia kont
```

## Konfiguracja

1. **Supabase:** uruchom `app/supabase/schema.sql` w SQL Editor. Pierwszego superadmina utwórz ręcznie
   (Authentication → Users → Add user, potem `insert into public.profiles (id, email, role) values ('<uuid>', '<email>', 'superadmin');`).
2. **Edge Function:** `supabase functions deploy create-user` (po `supabase link`).
3. **Kontakt z developerem (opcjonalnie):** w Discordzie utwórz webhook (Ustawienia kanału → Integracje → Webhooki), potem
   `supabase secrets set DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."` i `supabase functions deploy contact-developer`.
   Formularz widzą tylko zalogowani nauczyciele i superadmini; adres webhooka nie trafia do przeglądarki ani do repo.
4. **Vercel:** Root Directory `app/frontend`, zmienne `VITE_SUPABASE_URL` i `VITE_SUPABASE_ANON_KEY`
   (Production i Preview). Zmienne są wbudowywane w czasie budowania — po zmianie zrób Redeploy.

## Lokalnie

```bash
cd app/frontend
cp .env.example .env   # uzupełnij dane z Supabase
npm ci && npm run dev
npm test && npm run build
```
