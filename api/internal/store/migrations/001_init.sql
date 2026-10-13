create table subscriber (
  id         bigserial primary key,
  wa_user_id text not null unique,
  zone       smallint not null check (zone between 1 and 7),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index subscriber_zone on subscriber (zone);

create table reminder (
  id            bigserial primary key,
  subscriber_id bigint references subscriber (id) on delete set null,
  zone          smallint not null,
  cut_date      date not null,
  wamid         text unique,
  status        text not null default 'sent',
  sent_at       timestamptz not null default now(),
  unique (subscriber_id, cut_date)
);
create index reminder_sent_at on reminder (sent_at);

create table cut_report (
  id            bigserial primary key,
  subscriber_id bigint references subscriber (id) on delete set null,
  zone          smallint not null,
  cut_date      date not null,
  answer        text not null check (answer in ('normal', 'baja', 'no_regreso', 'turbia')),
  created_at    timestamptz not null default now(),
  unique (subscriber_id, cut_date)
);

create table inbound_seen (
  wamid   text primary key,
  seen_at timestamptz not null default now()
);
