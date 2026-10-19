-- Answers to the reminder's «¿Ahorita tienes agua?»: whether the water was already gone
-- before the cut SIAPA announced. One per subscription and cut (the run's first day);
-- the latest answer wins, with its time. BAJA unlinks them, as it does reports.
create table water_report (
  id            bigserial primary key,
  subscriber_id bigint references subscriber (id) on delete set null,
  zone          smallint not null,
  cut_date      date not null,
  answer        text not null check (answer in ('si', 'poca', 'no')),
  created_at    timestamptz not null default now(),
  unique (subscriber_id, cut_date)
);
