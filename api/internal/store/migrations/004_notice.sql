create table notice (
  id            bigserial primary key,
  subscriber_id bigint references subscriber (id) on delete set null,
  key           text not null,
  zone          smallint not null,
  wamid_hash    text unique,
  status        text not null default 'sending',
  sent_at       timestamptz not null default now(),
  unique (subscriber_id, key)
);
create index notice_sent_at on notice (sent_at);
