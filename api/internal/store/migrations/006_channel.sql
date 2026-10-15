alter table subscriber rename column wa_user_id to user_id;
alter table subscriber add column channel text not null default 'wa' check (channel in ('wa', 'tg'));
alter table subscriber drop constraint subscriber_wa_user_id_key;
alter table subscriber add constraint subscriber_channel_user_id_key unique (channel, user_id);
alter table reminder add column channel text not null default 'wa';
alter table notice add column channel text not null default 'wa';
