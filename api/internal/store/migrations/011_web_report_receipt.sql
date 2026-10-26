-- A random receipt lets the server's local write-ahead log replay a report after a crash
-- without duplicating it. Existing anonymous reports have no receipt and stay unchanged.
alter table web_report add column request_id text;
create unique index web_report_request_id on web_report (request_id) where request_id is not null;
