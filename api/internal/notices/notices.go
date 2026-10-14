// Package notices sends one-off templates to a zone's subscribers, such as cambio_rotacion
// when SIAPA changes a zone's days.
package notices

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"time"

	"aguagdl/api/internal/store"
	"aguagdl/api/internal/wa"
)

type Store interface {
	NoticeRecipients(ctx context.Context, zone int, key string) ([]store.Subscriber, error)
	SendNotice(ctx context.Context, s store.Subscriber, key string, send func(store.Subscriber) (string, error)) (bool, error)
	RecipientsSince(ctx context.Context, since time.Time) (int, error)
}

type Sender interface {
	Send(ctx context.Context, m wa.Message) (string, error)
}

// Notice is one template for one zone. Key makes it idempotent: a re-run with the
// same key only reaches the subscribers who haven't received it yet.
type Notice struct {
	Zone     int
	Key      string
	Template string
	Language string
	Params   []string
}

// ErrCapped means the daily cap stopped the run; run it again later to reach the rest.
var ErrCapped = errors.New("daily cap reached")

const maxConsecutiveFailures = 5

// Send reaches every pending subscriber of n.Zone and returns how many were sent.
func Send(ctx context.Context, st Store, snd Sender, n Notice, dailyCap int, interval time.Duration, now func() time.Time, log *slog.Logger) (sent int, err error) {
	subs, err := st.NoticeRecipients(ctx, n.Zone, n.Key)
	if err != nil {
		return 0, err
	}
	failures := 0
	for i, s := range subs {
		if i > 0 {
			select {
			case <-ctx.Done():
				return sent, errors.Join(err, ctx.Err())
			case <-time.After(interval):
			}
		}
		day, capErr := st.RecipientsSince(ctx, now().Add(-24*time.Hour))
		if capErr != nil {
			return sent, errors.Join(err, capErr)
		}
		if day >= dailyCap {
			log.Warn("daily cap reached; run again later for the rest", "pending", len(subs)-i)
			return sent, errors.Join(err, ErrCapped)
		}
		attempted, sendErr := st.SendNotice(ctx, s, n.Key, func(current store.Subscriber) (string, error) {
			return snd.Send(ctx, wa.NewTemplate(wa.Recipient{UserID: current.UserID, Phone: current.Phone}, n.Template, n.Language, wa.BodyParams(n.Params...)))
		})
		if sendErr != nil {
			err = errors.Join(err, fmt.Errorf("subscriber %d: %w", s.ID, sendErr))
			log.Error("notice attempt failed", "subscriber", s.ID, "err", sendErr)
			if failures++; failures >= maxConsecutiveFailures {
				return sent, err
			}
			continue
		}
		if attempted {
			failures = 0
			sent++
		}
	}
	return sent, err
}
