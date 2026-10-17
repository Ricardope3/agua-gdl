-- Who a queued reply goes to, so BAJA can cancel it, and when a delivery claimed it,
-- so a reply the provider accepted is never sent again.
alter table pending_reply
  add column channel    text not null default '',
  add column user_id    text not null default '',
  add column phone      text,
  add column claimed_at timestamptz;
create index pending_reply_recipient on pending_reply (channel, user_id);
