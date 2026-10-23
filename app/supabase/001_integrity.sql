-- OPCJONALNA migracja integralności danych dla Supabase (SQL Editor → Run). Idempotentna.
-- Uwaga: indeksy unikalne się nie utworzą, jeśli w istniejących danych są duplikaty
-- (ten sam zawodnik dwa razy w jednej rundzie) — usuń je wcześniej.
create unique index if not exists uq_pairs_round_white on public.pairs(round_number, white_id);
create unique index if not exists uq_pairs_round_black on public.pairs(round_number, black_id) where black_id is not null;
do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'pairs_distinct_players') then
    alter table public.pairs add constraint pairs_distinct_players check (black_id is null or black_id <> white_id);
  end if;
  if not exists (select 1 from pg_constraint where conname = 'pairs_result_valid') then
    alter table public.pairs add constraint pairs_result_valid check (result in ('', '1-0', '0-1', '0.5-0.5', 'wolny los'));
  end if;
end $$;
