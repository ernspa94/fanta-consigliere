-- Giro ogni 15 minuti mandato da Supabase (il cron di GitHub salta molti giri: a volte 3-4 al giorno).
-- Prima, una volta sola, nel SQL Editor di Supabase (sostituisci il token, non salvarlo altrove):
--   select vault.create_secret('github_pat_...', 'github_token');
-- Lo stesso token fa partire subito anche il pulsante "Ricalcola" (richiedi_ricalcolo in schema.sql).
-- Poi esegui questo file. Si può rieseguire: sostituisce il giro esistente.

create extension if not exists pg_cron;
create extension if not exists pg_net;

create or replace function public._giro_programmato()
returns void language plpgsql security definer set search_path = public as $$
declare
  v_token text;
begin
  select decrypted_secret into v_token from vault.decrypted_secrets where name = 'github_token';
  if v_token is null then return; end if;
  perform net.http_post(
    url := 'https://api.github.com/repos/ernspa94/fanta-consigliere/actions/workflows/consiglio.yml/dispatches',
    headers := jsonb_build_object('Authorization', 'Bearer ' || v_token, 'Accept', 'application/vnd.github+json',
                                  'User-Agent', 'fanta-consigliere', 'Content-Type', 'application/json'),
    body := jsonb_build_object('ref', 'main', 'inputs', jsonb_build_object('programmato', 'true'))
  );
end $$;

revoke all on function public._giro_programmato() from public, anon, authenticated;

select cron.schedule('giro-consiglio', '*/15 * * * *', 'select public._giro_programmato()');

-- Controllo: le ultime risposte di GitHub (204 = giro avviato; 401 = token sbagliato o scaduto;
-- 403/404 = al token manca il permesso "Actions: Read and write" sul repository).
--   select created, status_code, left(content::text, 200) from net._http_response order by created desc limit 5;
