// Command notify sends the cambio_rotacion template to one zone's subscribers after
// SIAPA changes that zone's days. Update api/data/rotation.json and deploy first, so
// the reminders follow the new days; the days in the message come from that file.
// Telegram is the default channel; WhatsApp ran until 15 Oct 2026 and needs -channel wa.
//
// It only reports what it would send, without changing the database, unless -send is
// given. Re-running with the same -zone and -from reaches only the subscribers who
// haven't received it, so it's safe to run again after the daily or monthly cap stops it.
//
//	cd api
//	DATABASE_URL='…' go run ./cmd/notify -zone 4 -from 2026-11-02
//	DATABASE_URL='…' TG_TOKEN='…' go run ./cmd/notify -zone 4 -from 2026-11-02 -send
//
// With -tomorrow it instead sends tomorrow's reminder for the zone as a normal text, for
// nights the aviso_corte template can't be used. It always uses WhatsApp (ignores
// -channel): WhatsApp delivers normal texts only to people who wrote in the last 24
// hours, so it reaches subscribers whose last change is under 23 hours old, and the
// nightly run won't send them that cut's reminder again:
//
//	DATABASE_URL='…' go run ./cmd/notify -zone 6 -tomorrow
//	DATABASE_URL='…' WA_TOKEN='…' WA_PHONE_NUMBER_ID=… go run ./cmd/notify -zone 6 -tomorrow -send
//
// With -channel wa the schedule change goes to the WhatsApp subscribers instead
// (Telegram is the default; it has no templates, no 24-hour window and no daily cap):
//
//	DATABASE_URL='…' WA_TOKEN='…' WA_PHONE_NUMBER_ID=… go run ./cmd/notify -channel wa -zone 4 -from 2026-11-02 -send
//
// With -avisos it tells every Telegram subscriber, once, that the reminders now also come two
// days before each block of cuts, with their zone's cuts for the coming week (bot.AvisosChange).
// Run it right after deploying that change and before that evening's 8 p.m. run: a block already
// under way got the old reminder, and the new run sends nothing for the block's later days.
// -key sets the idempotency key; change it when the message changes, so subscribers get it again.
//
//	DATABASE_URL='…' TG_TOKEN='…' go run ./cmd/notify -avisos -send
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

// now is the clock for tomorrow's date and the caps; tests set it.
var now = time.Now

func main() {
	zone := flag.Int("zone", 0, "zone (1-7)")
	from := flag.String("from", "", "cambio_rotacion: first day of the new schedule, YYYY-MM-DD")
	tomorrow := flag.Bool("tomorrow", false, "send tomorrow's reminder for -zone as a normal text instead of cambio_rotacion")
	send := flag.Bool("send", false, "send the messages; without it, only report")
	channel := flag.String("channel", store.Telegram, "wa (WhatsApp) or tg (Telegram); default tg")
	avisos := flag.Bool("avisos", false, "tell every Telegram subscriber, once, about the notice two days before each cut")
	key := flag.String("key", avisosKey, "avisos: idempotency key; change it when the message changes, so subscribers get it again")
	flag.Parse()
	var err error
	switch {
	case *avisos:
		err = runAvisos(*key, *send)
	case *tomorrow:
		// -tomorrow always uses WhatsApp, whatever -channel says.
		err = runTomorrow(*zone, *send)
	case *channel != store.WhatsApp && *channel != store.Telegram:
		err = fmt.Errorf("-channel must be %s or %s", store.WhatsApp, store.Telegram)
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
	if !sched.IsCut(zone, start) {
		return fmt.Errorf("-from %s is not a cut day for zone %d in rotation.json", from, zone)
	}
	if start.Before(sched.Day(now())) {
		fmt.Fprintf(os.Stderr, "WARNING: -from %s is in the past; the notice still reaches whoever hasn't received it (expected when re-running after a cap stopped it).\n", from)
	}
	n := notices.Notice{
		Zone: zone, Key: fmt.Sprintf("cambio_rotacion/%d/%s", zone, from),
		Template: "cambio_rotacion", Language: env("WA_LANGUAGE", "es_MX"),
		Params: []string{strconv.Itoa(zone), rotation.DaysES(sched.Weekdays(zone)), rotation.DateES(start)},
	}
	ctx := context.Background()
	db, err := connect(ctx, send)
	if err != nil {
		return err
	}
	defer db.Close()
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
		return errors.Join(err, reportUnresolved(ctx, db, channel, n.Key))
	}
	if !send {
		fmt.Println("Dry run. Check the days against SIAPA's calendar, then add -send.")
		return nil
	}
	token, phoneID := os.Getenv("WA_TOKEN"), os.Getenv("WA_PHONE_NUMBER_ID")
	if token == "" || phoneID == "" {
		return errors.New("set WA_TOKEN and WA_PHONE_NUMBER_ID to send")
	}
	caps := map[string]int{"DAILY_CAP": 250, "MONTHLY_CAP": 5000}
	for name := range caps {
		if caps[name], err = strconv.Atoi(env(name, strconv.Itoa(caps[name]))); err != nil {
			return fmt.Errorf("%s: %w", name, err)
		}
	}
	client := &wa.Client{BaseURL: "https://graph.facebook.com/" + env("WA_GRAPH_VERSION", "v24.0"),
		PhoneNumberID: phoneID, Token: token, HTTP: &http.Client{Timeout: 15 * time.Second}}
	log := slog.New(slog.NewTextHandler(os.Stderr, nil))
	local := func() time.Time { return now().In(loc) }
	sent, err := notices.Send(ctx, db, client, n, caps["DAILY_CAP"], caps["MONTHLY_CAP"], 100*time.Millisecond, local, log)
	fmt.Printf("sent %d\n", sent)
	if errors.Is(err, notices.ErrCapped) {
		fmt.Println("A send cap stopped the run; run the same command again later for the rest.")
	}
	return errors.Join(err, reportUnresolved(ctx, db, channel, n.Key))
}

// reportUnresolved warns about notices whose delivery is still open (stuck sending,
// uncertain, rejected or failed), so a re-run doesn't paper over a message that needs
// a decision. It returns the count query's error, never hides it.
func reportUnresolved(ctx context.Context, db *store.DB, channel, key string) error {
	n, err := db.UnresolvedNotices(ctx, channel, key)
	if err != nil {
		return err
	}
	if n > 0 {
		fmt.Printf("WARNING: %d notices for %s are unresolved (sending, uncertain, rejected or failed); check them before re-running.\n", n, key)
	}
	return nil
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
	ctx := context.Background()
	db, err := connect(ctx, send)
	if err != nil {
		return err
	}
	defer db.Close()
	at := now()
	r := &reminders.Runner{Store: db, Schedule: sched, DailyCap: caps["DAILY_CAP"], MonthlyCap: caps["MONTHLY_CAP"],
		Interval: 100 * time.Millisecond, Now: now, Log: slog.New(slog.NewTextHandler(os.Stderr, nil))}
	m := reminders.Manual{Zone: zone, ActiveSince: at.Add(-23 * time.Hour),
		Text: bot.ManualReminder(rotation.DateES(sched.Day(at).AddDate(0, 0, 1)), zone)}
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

// avisosKey is the default -key: it makes the change message idempotent, so a re-run
// reaches only whoever hasn't got it.
const avisosKey = "avisos/2026-10"

// runAvisos sends bot.AvisosChange to every Telegram subscriber who hasn't received it
// under key; a new key reaches everyone again.
func runAvisos(key string, send bool) error {
	loc, err := time.LoadLocation("America/Mexico_City")
	if err != nil {
		return err
	}
	sched, err := rotation.Load(data.Rotation, loc)
	if err != nil {
		return err
	}
	ctx := context.Background()
	db, err := connect(ctx, send)
	if err != nil {
		return err
	}
	defer db.Close()
	// Each zone's message lists its cuts from tomorrow through the next week.
	tomorrow := sched.Day(now()).AddDate(0, 0, 1)
	texts := map[int]string{}
	due := 0
	for _, zone := range sched.Zones() {
		var next []time.Time
		for _, d := range sched.NextCuts(zone, tomorrow, 7) {
			if d.Before(tomorrow.AddDate(0, 0, 7)) {
				next = append(next, d)
			}
		}
		texts[zone] = bot.AvisosChange(env("PUBLIC_BASE_URL", "https://aguagdl.com"), zone, next)
		subs, err := db.NoticeRecipients(ctx, store.Telegram, zone, key)
		if err != nil {
			return err
		}
		due += len(subs)
		fmt.Printf("Zone %d: %d Telegram subscribers; next cuts: %s\n", zone, len(subs), rotation.DatesES(next))
	}
	fmt.Printf("\nTo %d Telegram subscribers in all. Zone 1's message:\n\n%s\n\n", due, texts[1])
	if !send {
		fmt.Println("Dry run. Add -send to send it.")
		return nil
	}
	token := os.Getenv("TG_TOKEN")
	if token == "" {
		return errors.New("set TG_TOKEN to send")
	}
	client := &tg.Client{BaseURL: "https://api.telegram.org", Token: token, HTTP: &http.Client{Timeout: 15 * time.Second}}
	log := slog.New(slog.NewTextHandler(os.Stderr, nil))
	total := 0
	for _, zone := range sched.Zones() {
		sent, sendErr := notices.SendTelegram(ctx, db, client, notices.Notice{Zone: zone, Key: key}, texts[zone], 100*time.Millisecond, log)
		total += sent
		err = errors.Join(err, sendErr)
	}
	fmt.Printf("sent %d\n", total)
	return errors.Join(err, reportUnresolved(ctx, db, store.Telegram, key))
}

// connect opens DATABASE_URL. Only a run that sends migrates it: a dry run, perhaps from a
// checkout with a newer migration, must not change the database under the running server.
func connect(ctx context.Context, send bool) (*store.DB, error) {
	url := os.Getenv("DATABASE_URL")
	if url == "" {
		return nil, errors.New("set DATABASE_URL")
	}
	db, err := store.Open(ctx, url)
	if err != nil {
		return nil, err
	}
	if send {
		if err := db.Migrate(ctx); err != nil {
			db.Close()
			return nil, err
		}
	}
	return db, nil
}

func env(name, def string) string {
	if v := os.Getenv(name); v != "" {
		return v
	}
	return def
}
