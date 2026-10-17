create table pending_reply (
  id           bigserial primary key,
  inbound_hash text not null references inbound_seen (wamid_hash) on delete cascade,
  body         jsonb not null,
  created_at   timestamptz not null default now()
);
create index pending_reply_inbound on pending_reply (inbound_hash);
