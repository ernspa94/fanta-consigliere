-- Fanta Consigliere: squadre accessibili solo tramite codice segreto, senza registrazione.
--
-- L'app usa la chiave "anon" (pubblica): le tabelle per lei sono chiuse (RLS senza policy),
-- può solo chiamare le funzioni qui sotto, che vogliono sempre il codice della squadra.
-- Il motore su GitHub usa la chiave "service_role" (segreto) e legge/scrive le tabelle direttamente.
--
-- Da eseguire una volta in Supabase → SQL Editor. Si può rieseguire: non cancella dati.

create extension if not exists pgcrypto with schema extensions;
create extension if not exists pg_net with schema extensions;

create table if not exists public.squadre (
  codice text primary key default encode(extensions.gen_random_bytes(6), 'hex'),
  nome text not null check (char_length(nome) between 1 and 60),
  lega text check (char_length(lega) <= 60),
  rosa jsonb not null default '[]'::jsonb,
  regole jsonb not null,
  notifiche_inviate jsonb not null default '{}'::jsonb,
  creata timestamptz not null default now(),
  modificata timestamptz not null default now(),
  ricalcolo_richiesto timestamptz
);

create table if not exists public.consigli (
  codice text not null references public.squadre(codice) on delete cascade,
  giornata int not null,
  dati jsonb not null,
  aggiornato timestamptz not null default now(),
  primary key (codice, giornata)
);

-- Un iPhone può seguire più squadre: una riga per (dispositivo, squadra).
create table if not exists public.iscrizioni (
  endpoint text not null,
  codice text not null references public.squadre(codice) on delete cascade,
  nome text,
  iscrizione jsonb not null,
  creata timestamptz not null default now(),
  primary key (endpoint, codice)
);

alter table public.squadre enable row level security;
alter table public.consigli enable row level security;
alter table public.iscrizioni enable row level security;
revoke all on public.squadre, public.consigli, public.iscrizioni from anon, authenticated;


-- Controlli comuni sui dati che arrivano dall'app.
create or replace function public._controlla_squadra(p_rosa jsonb, p_regole jsonb)
returns void language plpgsql as $$
begin
  if jsonb_typeof(p_rosa) <> 'array' or jsonb_array_length(p_rosa) > 40 then
    raise exception 'La rosa deve essere una lista di al massimo 40 giocatori';
  end if;
  if jsonb_typeof(p_regole) <> 'object' or pg_column_size(p_regole) > 20000 then
    raise exception 'Regolamento non valido';
  end if;
end $$;


create or replace function public.crea_squadra(p_nome text, p_lega text, p_regole jsonb)
returns text language plpgsql security definer set search_path = public as $$
declare v_codice text;
begin
  perform _controlla_squadra('[]'::jsonb, p_regole);
  insert into squadre (nome, lega, regole) values (trim(p_nome), nullif(trim(p_lega), ''), p_regole)
  returning codice into v_codice;
  return v_codice;
end $$;


create or replace function public.leggi_squadra(p_codice text)
returns jsonb language plpgsql security definer set search_path = public as $$
declare v jsonb;
begin
  select jsonb_build_object('codice', codice, 'nome', nome, 'lega', lega, 'rosa', rosa, 'regole', regole,
                            'modificata', modificata, 'ricalcolo_richiesto', ricalcolo_richiesto)
    into v from squadre where codice = p_codice;
  if v is null then raise exception 'Squadra non trovata'; end if;
  return v;
end $$;


create or replace function public.salva_squadra(p_codice text, p_nome text, p_lega text, p_rosa jsonb, p_regole jsonb)
returns void language plpgsql security definer set search_path = public as $$
begin
  perform _controlla_squadra(p_rosa, p_regole);
  update squadre set nome = trim(p_nome), lega = nullif(trim(p_lega), ''), rosa = p_rosa, regole = p_regole,
                     modificata = now()
   where codice = p_codice;
  if not found then raise exception 'Squadra non trovata'; end if;
end $$;


-- Consiglio di una giornata (o il più recente se p_giornata è null) e giornate disponibili.
create or replace function public.leggi_consiglio(p_codice text, p_giornata int default null)
returns jsonb language sql security definer set search_path = public as $$
  select jsonb_build_object(
    'consiglio', (select dati from consigli where codice = p_codice
                    and (p_giornata is null or giornata = p_giornata)
                  order by giornata desc limit 1),
    'giornate', coalesce((select jsonb_agg(giornata order by giornata desc) from consigli where codice = p_codice), '[]'::jsonb)
  );
$$;


create or replace function public.salva_iscrizione(p_codice text, p_nome text, p_iscrizione jsonb)
returns void language plpgsql security definer set search_path = public as $$
begin
  if not exists (select 1 from squadre where codice = p_codice) then raise exception 'Squadra non trovata'; end if;
  if p_iscrizione->>'endpoint' is null or pg_column_size(p_iscrizione) > 4000 then
    raise exception 'Iscrizione non valida';
  end if;
  insert into iscrizioni (endpoint, codice, nome, iscrizione)
  values (p_iscrizione->>'endpoint', p_codice, left(p_nome, 40), p_iscrizione)
  on conflict (endpoint, codice) do update set nome = excluded.nome, iscrizione = excluded.iscrizione;
end $$;


create or replace function public.rimuovi_iscrizione(p_codice text, p_endpoint text)
returns void language sql security definer set search_path = public as $$
  delete from iscrizioni where codice = p_codice and endpoint = p_endpoint;
$$;


-- Segna la squadra da ricalcolare e, se in Vault c'è il token "github_token", avvia subito il workflow.
-- Senza token ci pensa il giro programmato (entro 15 minuti).
create or replace function public.richiedi_ricalcolo(p_codice text)
returns text language plpgsql security definer set search_path = public as $$
declare
  v_ultima timestamptz;
  v_token text;
begin
  select ricalcolo_richiesto into v_ultima from squadre where codice = p_codice;
  if not found then raise exception 'Squadra non trovata'; end if;
  if v_ultima is not null and v_ultima > now() - interval '3 minutes' then
    return 'gia_richiesto';
  end if;
  update squadre set ricalcolo_richiesto = now() where codice = p_codice;

  select decrypted_secret into v_token from vault.decrypted_secrets where name = 'github_token';
  if v_token is null then
    return 'in_coda';
  end if;
  perform net.http_post(
    url := 'https://api.github.com/repos/ernspa94/fanta-consigliere/actions/workflows/consiglio.yml/dispatches',
    headers := jsonb_build_object('Authorization', 'Bearer ' || v_token, 'Accept', 'application/vnd.github+json',
                                  'User-Agent', 'fanta-consigliere', 'Content-Type', 'application/json'),
    body := jsonb_build_object('ref', 'main', 'inputs', jsonb_build_object('codice', p_codice))
  );
  return 'avviato';
end $$;


revoke all on function public._controlla_squadra(jsonb, jsonb) from public, anon, authenticated;
grant execute on function public.crea_squadra(text, text, jsonb),
                          public.leggi_squadra(text),
                          public.salva_squadra(text, text, text, jsonb, jsonb),
                          public.leggi_consiglio(text, int),
                          public.salva_iscrizione(text, text, jsonb),
                          public.rimuovi_iscrizione(text, text),
                          public.richiedi_ricalcolo(text)
  to anon, authenticated;
