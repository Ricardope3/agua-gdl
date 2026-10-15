// Command notify sends the cambio_rotacion template to one zone's subscribers after
// SIAPA changes that zone's days. Update api/data/rotation.json and deploy first, so
// the reminders follow the new days; the days in the message come from that file.
//
// It only reports what it would send unless -send is given. Re-running with the same
// -zone and -from reaches only the subscribers who haven't received it, so it's safe
// to run again after the daily cap stops it.
//
//	cd api
//	DATABASE_URL='…' go run ./cmd/notify -zone 4 -from 2026-11-02
//	DATABASE_URL='…' WA_TOKEN='…' WA_PHONE_NUMBER_ID=… go run ./cmd/notify -zone 4 -from 2026-11-02 -send
//
// With -tomorrow it instead sends tomorrow's reminder for the zone as a normal text, for
// nights the aviso_corte template can't be used. WhatsApp delivers normal texts only to
// people who wrote in the last 24 hours, so it reaches subscribers whose last change is
// under 23 hours old, and the nightly run won't send them that cut's reminder again:
//
//	DATABASE_URL='…' go run ./cmd/notify -zone 6 -tomorrow
//	DATABASE_URL='…' WA_TOKEN='…' WA_PHONE_NUMBER_ID=… go run ./cmd/notify -zone 6 -tomorrow -send
//
// With -channel tg the schedule change goes to Telegram subscribers as a normal message
// (Telegram has no templates, no 24-hour window and no daily cap):
//
//	DATABASE_URL='…' TG_TOKEN='…' go run ./cmd/notify -channel tg -zone 4 -from 2026-11-02 -send
package main

import (
	"context"
	"errors"
	"flag"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"strconv"
	"time"
	_ "time/tzdata"

	"aguagdl/api/data"
	"aguagdl/api/internal/bot"
	"aguagdl/api/internal/notices"
	"aguagdl/api/internal/reminders"
	"aguagdl/api/internal/rotation"
	"aguagdl/api/internal/store"
	"aguagdl/api/internal/tg"
	"aguagdl/api/internal/wa"
)

func main() {
	zone := flag.Int("zone", 0, "zone (1-7)")
	from := flag.String("from", "", "cambio_rotacion: first day of the new schedule, YYYY-MM-DD")
	tomorrow := flag.Bool("tomorrow", false, "send tomorrow's reminder for -zone as a normal text instead of cambio_rotacion")
	send := flag.Bool("send", false, "send the messages; without it, only report")
	channel := flag.String("channel", store.WhatsApp, "wa (WhatsApp) or tg (Telegram)")
	flag.Parse()
	var err error
	switch {
	case *channel != store.WhatsApp && *channel != store.Telegram:
		err = fmt.Errorf("-channel must be %s or %s", store.WhatsApp, store.Telegram)
	case *tomorrow && *channel == store.Telegram:
		err = errors.New("-tomorrow is for WhatsApp only: Telegram reminders need no fallback")
	case *tomorrow:
		err = runTomorrow(*zone, *send)
	default:
		err = run(*channel, *zone, *from, *send)
	}
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

func run(channel string, zone int, from string, send bool) error {
	loc, err := time.LoadLocation("America/Mexico_City")
	if err != nil {
		return err
	}
	sched, err := rotation.Load(data.Rotation, loc)
	if err != nil {
		return err
	}
	if !sched.HasZone(zone) {
		return fmt.Errorf("-zone %d is not in rotation.json", zone)
	}
	start, err := sched.ParseDate(from)
	if err != nil {
		return fmt.Errorf("-from: %w", err)
	}
	n := notices.Notice{
		Zone: zone, Key: fmt.Sprintf("cambio_rotacion/%d/%s", zone, from),
		Template: "cambio_rotacion", Language: env("WA_LANGUAGE", "es_MX"),
		Params: []string{strconv.Itoa(zone), rotation.DaysES(sched.Weekdays(zone)), rotation.DateES(start)},
	}
	url := os.Getenv("DATABASE_URL")
	if url == "" {
		return errors.New("set DATABASE_URL")
	}
	ctx := context.Background()
	db, err := store.Open(ctx, url)
	if err != nil {
		return err
	}
	defer db.Close()
	if err := db.Migrate(ctx); err != nil {
		return err
	}
	due, err := db.NoticeRecipients(ctx, channel, zone, n.Key)
	if err != nil {
		return err
	}
	fmt.Printf("%s to %d %s subscribers of zone %d: {{1}}=%s {{2}}=%s {{3}}=%s\n", n.Template, len(due), channel, zone, n.Params[0], n.Params[1], n.Params[2])
	if channel == store.Telegram {
		text := bot.ScheduleChange(zone, n.Params[1], n.Params[2])
		fmt.Printf("\n%s\n\n", text)
		if !send {
			fmt.Println("Dry run. Check the days against SIAPA's calendar, then add -send.")
			return nil
		}
		token := os.Getenv("TG_TOKEN")
		if token == "" {
			return errors.New("set TG_TOKEN to send")
		}
		client := &tg.Client{BaseURL: "https://api.telegram.org", Token: token, HTTP: &http.Client{Timeout: 15 * time.Second}}
		sent, err := notices.SendTelegram(ctx, db, client, n, text, 100*time.Millisecond, slog.New(slog.NewTextHandler(os.Stderr, nil)))
		fmt.Printf("sent %d\n", sent)
		return err
	}
	if !send {
		fmt.Println("Dry run. Check the days against SIAPA's calendar, then add -send.")
		return nil
	}
	token, phoneID := os.Getenv("WA_TOKEN"), os.Getenv("WA_PHONE_NUMBER_ID")
	if token == "" || phoneID == "" {
		return errors.New("set WA_TOKEN and WA_PHONE_NUMBER_ID to send")
	}
	dailyCap, err := strconv.Atoi(env("DAILY_CAP", "250"))
	if err != nil {
		return fmt.Errorf("DAILY_CAP: %w", err)
	}
	client := &wa.Client{BaseURL: "https://graph.facebook.com/" + env("WA_GRAPH_VERSION", "v24.0"),
		PhoneNumberID: phoneID, Token: token, HTTP: &http.Client{Timeout: 15 * time.Second}}
	log := slog.New(slog.NewTextHandler(os.Stderr, nil))
	sent, err := notices.Send(ctx, db, client, n, dailyCap, 100*time.Millisecond, time.Now, log)
	fmt.Printf("sent %d\n", sent)
	if errors.Is(err, notices.ErrCapped) {
		fmt.Println("The daily cap stopped the run; run the same command again later for the rest.")
	}
	return err
}

// runTomorrow sends tomorrow's reminder to zone's subscribers inside WhatsApp's 24-hour
// window as a normal text.
func runTomorrow(zone int, send bool) error {
	loc, err := time.LoadLocation("America/Mexico_City")
	if err != nil {
		return err
	}
	sched, err := rotation.Load(data.Rotation, loc)
	if err != nil {
		return err
	}
	if !sched.HasZone(zone) {
		return fmt.Errorf("-zone %d is not in rotation.json", zone)
	}
	caps := map[string]int{"DAILY_CAP": 250, "MONTHLY_CAP": 5000}
	for name := range caps {
		if caps[name], err = strconv.Atoi(env(name, strconv.Itoa(caps[name]))); err != nil {
			return fmt.Errorf("%s: %w", name, err)
		}
	}
	url := os.Getenv("DATABASE_URL")
	if url == "" {
		return errors.New("set DATABASE_URL")
	}
	ctx := context.Background()
	db, err := store.Open(ctx, url)
	if err != nil {
		return err
	}
	defer db.Close()
	if err := db.Migrate(ctx); err != nil {
		return err
	}
	now := time.Now()
	r := &reminders.Runner{Store: db, Schedule: sched, DailyCap: caps["DAILY_CAP"], MonthlyCap: caps["MONTHLY_CAP"],
		Interval: 100 * time.Millisecond, Now: time.Now, Log: slog.New(slog.NewTextHandler(os.Stderr, nil))}
	m := reminders.Manual{Zone: zone, ActiveSince: now.Add(-23 * time.Hour),
		Text: bot.ManualReminder(rotation.DateES(sched.Day(now).AddDate(0, 0, 1)), zone)}
	in, due, err := r.ManualRecipients(ctx, m)
	if err != nil {
		return err
	}
	fmt.Printf("Zone %d: %d of the %d subscribers still due for tomorrow wrote in the last 23 hours and would get:\n\n%s\n\n", zone, len(in), due, m.Text)
	if !send {
		fmt.Println("Dry run. Add -send to send it.")
		return nil
	}
	token, phoneID := os.Getenv("WA_TOKEN"), os.Getenv("WA_PHONE_NUMBER_ID")
	if token == "" || phoneID == "" {
		return errors.New("set WA_TOKEN and WA_PHONE_NUMBER_ID to send")
	}
	r.Sender = &wa.Client{BaseURL: "https://graph.facebook.com/" + env("WA_GRAPH_VERSION", "v24.0"),
		PhoneNumberID: phoneID, Token: token, HTTP: &http.Client{Timeout: 15 * time.Second}}
	sent, err := r.SendManual(ctx, m)
	fmt.Printf("sent %d\n", sent)
	if errors.Is(err, reminders.ErrCapped) {
		fmt.Println("A send cap stopped the run; run the same command again later for the rest.")
	}
	return err
}

func env(name, def string) string {
	if v := os.Getenv(name); v != "" {
		return v
	}
	return def
}
