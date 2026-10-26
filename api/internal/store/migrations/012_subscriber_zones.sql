-- A person may follow several colonias or households. subscriber.zone remains the most
-- recently selected zone for compatibility; this table is the authoritative membership set.
-- Indexes and tables share a namespace; 001_init.sql used this name for an index.
alter index subscriber_zone rename to subscriber_zone_idx;
create table subscriber_zone (
  subscriber_id bigint not null references subscriber (id) on delete cascade,
  zone          smallint not null check (zone between 1 and 7),
  primary key (subscriber_id, zone)
);
create index subscriber_zone_zone on subscriber_zone (zone, subscriber_id);

insert into subscriber_zone (subscriber_id, zone)
select id, zone from subscriber
on conflict do nothing;
