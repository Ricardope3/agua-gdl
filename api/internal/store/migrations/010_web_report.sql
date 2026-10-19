-- Reports made on aguagdl.com/reportes: what the water is like in a colonia right now.
-- Anonymous: the colonia (name|municipio|postal code, as in api/data/colonias_mapa.json),
-- the answer and the time; no IP, location or subscriber.
create table web_report (
  id         bigserial primary key,
  colonia    text not null,
  status     text not null check (status in ('sin_agua', 'baja', 'con_agua')),
  turbia     boolean not null default false,
  olor       boolean not null default false,
  sedimento  boolean not null default false,
  created_at timestamptz not null default now()
);
create index web_report_created_at on web_report (created_at);
