-- Uruchom w Supabase: SQL Editor -> New query -> wklej i Run.
-- Tabela pamieta, ktore alerty zostaly oznaczone jako prawidlowe - wspoldzielona
-- miedzy komputerami (kazdy zalogowany user widzi te same wiersze).

create table if not exists oznaczone_prawidlowe (
    klucz text primary key,
    rodzaj text not null,
    obiekt_wiersz integer not null,
    obiekt_nazwa text not null,
    opis text not null,
    oznaczono_przez uuid references auth.users(id) default auth.uid(),
    oznaczono_dnia timestamptz not null default now()
);

alter table oznaczone_prawidlowe enable row level security;

create policy "zalogowani czytaja" on oznaczone_prawidlowe
    for select using (auth.role() = 'authenticated');

create policy "zalogowani dodaja" on oznaczone_prawidlowe
    for insert with check (auth.role() = 'authenticated');

create policy "zalogowani usuwaja" on oznaczone_prawidlowe
    for delete using (auth.role() = 'authenticated');
