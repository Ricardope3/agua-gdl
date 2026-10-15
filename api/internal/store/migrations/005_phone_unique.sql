delete from subscriber s using subscriber newer
where s.phone = newer.phone and s.id < newer.id;
create unique index subscriber_phone_key on subscriber (phone) where phone is not null;
