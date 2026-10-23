-- ♟ Turniej Szachowy — schemat dla SUPABASE
-- Wklej całość do: Supabase Dashboard → SQL Editor → New query → Run

-- ─── ROZSZERZENIA ────────────────────────────────────────────────────────────
create extension if not exists "uuid-ossp";

-- ─── PROFILE (role użytkowników, powiązane z auth.users) ────────────────────
-- Supabase sam zarządza auth.users (hasła, sesje, JWT).
-- My trzymamy tylko rolę w osobnej tabeli.
create table if not exists public.profiles (
    id         uuid primary key references auth.users(id) on delete cascade,
    email      text not null,
    role       text not null default 'teacher' check (role in ('teacher', 'superadmin')),
    created_at timestamptz default now()
);

-- ─── UCZESTNICY ──────────────────────────────────────────────────────────────
create table if not exists public.participants (
    id         bigint generated always as identity primary key,
    imie       varchar(100) not null,
    klasa      varchar(20)  not null,
    created_at timestamptz default now()
);

-- ─── PARY ────────────────────────────────────────────────────────────────────
create table if not exists public.pairs (
    id           bigint generated always as identity primary key,
    round_number integer      not null,
    white_id     bigint       not null references public.participants(id) on delete cascade,
    black_id     bigint                references public.participants(id) on delete cascade,
    result       varchar(20)  not null default '',
    created_at   timestamptz  default now()
);

create index if not exists idx_pairs_round on public.pairs(round_number);
create index if not exists idx_pairs_white on public.pairs(white_id);
create index if not exists idx_pairs_black on public.pairs(black_id);

-- ─── FUNKCJA POMOCNICZA: rola aktualnie zalogowanego użytkownika ─────────────
create or replace function public.current_role_name()
returns text
language sql
stable
security definer
set search_path = public
as $$
    select role from public.profiles where id = auth.uid();
$$;

-- ─── RLS: włącz na wszystkich tabelach ───────────────────────────────────────
alter table public.profiles     enable row level security;
alter table public.participants enable row level security;
alter table public.pairs        enable row level security;

-- ─── POLITYKI: profiles ───────────────────────────────────────────────────────
-- każdy zalogowany widzi swój profil; superadmin widzi wszystkie (lista kont)
drop policy if exists "profiles_select_own_or_admin" on public.profiles;
create policy "profiles_select_own_or_admin"
    on public.profiles for select
    using ( auth.uid() = id or public.current_role_name() = 'superadmin' );

-- brak insert/update/delete z poziomu klienta — to robi wyłącznie
-- Edge Function (create-user) kluczem service_role, który omija RLS.

-- ─── POLITYKI: participants ───────────────────────────────────────────────────
-- podgląd: wszyscy, łącznie z gośćmi (klucz anon, niezalogowani)
drop policy if exists "participants_select_all" on public.participants;
create policy "participants_select_all"
    on public.participants for select
    using ( true );

drop policy if exists "participants_insert_teacher" on public.participants;
create policy "participants_insert_teacher"
    on public.participants for insert
    to authenticated
    with check ( public.current_role_name() in ('teacher','superadmin') );

drop policy if exists "participants_delete_superadmin" on public.participants;
create policy "participants_delete_superadmin"
    on public.participants for delete
    to authenticated
    using ( public.current_role_name() = 'superadmin' );

-- ─── POLITYKI: pairs ──────────────────────────────────────────────────────────
drop policy if exists "pairs_select_all" on public.pairs;
create policy "pairs_select_all"
    on public.pairs for select
    using ( true );

drop policy if exists "pairs_insert_teacher" on public.pairs;
create policy "pairs_insert_teacher"
    on public.pairs for insert
    to authenticated
    with check ( public.current_role_name() in ('teacher','superadmin') );

drop policy if exists "pairs_update_teacher" on public.pairs;
create policy "pairs_update_teacher"
    on public.pairs for update
    to authenticated
    using ( public.current_role_name() in ('teacher','superadmin') )
    with check ( public.current_role_name() in ('teacher','superadmin') );

drop policy if exists "pairs_delete_superadmin" on public.pairs;
create policy "pairs_delete_superadmin"
    on public.pairs for delete
    to authenticated
    using ( public.current_role_name() = 'superadmin' );

-- ─── PIERWSZY SUPERADMIN (ręcznie, jednorazowo) ──────────────────────────────
-- 1. Supabase Dashboard → Authentication → Users → "Add user" (email + hasło)
-- 2. Skopiuj jego UUID (widoczny na liście userów)
-- 3. Uruchom poniżej, podmieniając wartości:
--
-- insert into public.profiles (id, email, role)
-- values ('WKLEJ-TU-UUID-UŻYTKOWNIKA', 'superadmin@szkola.pl', 'superadmin');