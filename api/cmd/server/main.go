package main

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"strconv"
	"strings"
	"syscall"
	"time"
	_ "time/tzdata"

	"aguagdl/api/data"
	"aguagdl/api/internal/bot"
	"aguagdl/api/internal/colonias"
	"aguagdl/api/internal/geo"
	"aguagdl/api/internal/reminders"
	"aguagdl/api/internal/rotation"
	"aguagdl/api/internal/store"
	"aguagdl/api/internal/wa"
)

type config struct {
	Port, DatabaseURL, BaseURL, HeartbeatURL                   string
	WAToken, WAPhoneNumberID, WAAppSecret, WAVerifyToken       string
	WAGraphVersion, WATemplate, WALanguage                     string
	RemindersEnabled                                           bool
	ReminderHour, CatchUpUntil, DailyCap, MonthlyCap, MinShown int
}

func loadConfig() (config, error) {
	c := config{
		Port:           env("PORT", "8080"),
		WAGraphVersion: env("WA_GRAPH_VERSION", "v24.0"),
		WATemplate:     env("WA_TEMPLATE", "aviso_corte"),
		WALanguage:     env("WA_LANGUAGE", "es_MX"),
		HeartbeatURL:   os.Getenv("HEARTBEAT_URL"),
	}
	var missing []string
	for name, dst := range map[string]*string{
		"DATABASE_URL": &c.DatabaseURL, "PUBLIC_BASE_URL": &c.BaseURL,
		"WA_TOKEN": &c.WAToken, "WA_PHONE_NUMBER_ID": &c.WAPhoneNumberID,
		"WA_APP_SECRET": &c.WAAppSecret, "WA_VERIFY_TOKEN": &c.WAVerifyToken,
	} {
		if *dst = os.Getenv(name); *dst == "" {
			missing = append(missing, name)
		}
	}
	if len(missing) > 0 {
		return c, fmt.Errorf("missing env vars: %v", missing)
	}
	c.RemindersEnabled = os.Getenv("REMINDERS_ENABLED") == "true"
	var err error
	for name, dst := range map[string]struct {
		v   *int
		def int
	}{
		"REMINDER_HOUR": {&c.ReminderHour, 20}, "CATCH_UP_UNTIL_HOUR": {&c.CatchUpUntil, 22},
		"DAILY_CAP": {&c.DailyCap, 250}, "MONTHLY_CAP": {&c.MonthlyCap, 5000}, "MIN_REPORTS_SHOWN": {&c.MinShown, 10},
	} {
		*dst.v = dst.def
		if v := os.Getenv(name); v != "" {
			if *dst.v, err = strconv.Atoi(v); err != nil {
				return c, fmt.Errorf("%s: %w", name, err)
			}
		}
	}
	return c, nil
}

func env(name, def string) string {
	if v := os.Getenv(name); v != "" {
		return v
	}
	return def
}

func main() {
	log := slog.New(slog.NewJSONHandler(os.Stdout, nil))
	if err := run(log); err != nil {
		log.Error("fatal", "err", err)
		os.Exit(1)
	}
}

func run(log *slog.Logger) error {
	cfg, err := loadConfig()
	if err != nil {
		return err
	}
	loc, err := time.LoadLocation("America/Mexico_City")
	if err != nil {
		return err
	}
	sched, err := rotation.Load(data.Rotation, loc)
	if err != nil {
		return err
	}
	zones, err := geo.Load(data.Zonas)
	if err != nil {
		return err
	}
	cols, err := colonias.Load(data.Colonias)
	if err != nil {
		return err
	}

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	db, err := store.Open(ctx, cfg.DatabaseURL)
	if err != nil {
		return fmt.Errorf("database: %w", err)
	}
	defer db.Close()
	if err := db.Migrate(ctx); err != nil {
		return err
	}

	client := &wa.Client{
		BaseURL:       "https://graph.facebook.com/" + cfg.WAGraphVersion,
		PhoneNumberID: cfg.WAPhoneNumberID,
		Token:         cfg.WAToken,
		HTTP:          &http.Client{Timeout: 15 * time.Second},
	}
	b := &bot.Bot{Store: db, Sender: client, Schedule: sched, Zones: zones, Colonias: cols,
		BaseURL: cfg.BaseURL, PhoneNumberID: cfg.WAPhoneNumberID, ReminderHour: cfg.ReminderHour,
		RemindersOn: cfg.RemindersEnabled, Now: time.Now, Log: log}
	var beat func(context.Context, bool, string)
	if cfg.HeartbeatURL != "" {
		beat = heartbeat(cfg.HeartbeatURL, log)
		b.Alert = func(ctx context.Context, msg string) { beat(ctx, false, msg) }
	}
	go purgeSeen(ctx, db, log)

	if cfg.RemindersEnabled {
		r := &reminders.Runner{Store: db, Sender: client, Schedule: sched,
			Template: cfg.WATemplate, Language: cfg.WALanguage,
			Hour: cfg.ReminderHour, CatchUpUntil: cfg.CatchUpUntil,
			DailyCap: cfg.DailyCap, MonthlyCap: cfg.MonthlyCap,
			Interval: 100 * time.Millisecond, Heartbeat: beat, Now: time.Now, Log: log}
		go r.Run(ctx)
	} else {
		log.Warn("reminders disabled; set REMINDERS_ENABLED=true to send them")
	}

	a := &api{bot: b, db: db, sched: sched, zones: zones, cols: cols,
		appSecret: []byte(cfg.WAAppSecret), verifyToken: cfg.WAVerifyToken, minShown: cfg.MinShown, log: log}
	srv := &http.Server{Addr: ":" + cfg.Port, Handler: a.routes(), ReadHeaderTimeout: 10 * time.Second}
	go func() {
		<-ctx.Done()
		shutdown, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		srv.Shutdown(shutdown)
	}()
	log.Info("listening", "port", cfg.Port, "reminders", cfg.RemindersEnabled)
	if err := srv.ListenAndServe(); !errors.Is(err, http.ErrServerClosed) {
		return err
	}
	return nil
}

// purgeSeen forgets inbound message IDs after a week, whether or not reminders are on.
func purgeSeen(ctx context.Context, db *store.DB, log *slog.Logger) {
	for {
		if err := db.PurgeSeen(ctx, time.Now().Add(-7*24*time.Hour)); err != nil {
			log.Warn("purge seen messages", "err", err)
		}
		select {
		case <-ctx.Done():
			return
		case <-time.After(24 * time.Hour):
		}
	}
}

// heartbeat pings a dead-man's-switch URL (e.g. healthchecks.io) after each nightly run,
// using its "/fail" endpoint when the run failed, hit a cap, or a reminder later went undelivered.
func heartbeat(url string, log *slog.Logger) func(context.Context, bool, string) {
	client := &http.Client{Timeout: 10 * time.Second}
	return func(ctx context.Context, ok bool, msg string) {
		target := url
		if !ok {
			target += "/fail"
		}
		req, err := http.NewRequestWithContext(ctx, http.MethodPost, target, strings.NewReader(msg))
		if err != nil {
			log.Error("heartbeat", "err", err)
			return
		}
		resp, err := client.Do(req)
		if err != nil {
			log.Error("heartbeat", "err", err)
			return
		}
		resp.Body.Close()
	}
}
