package bot

import (
	"context"
	"errors"
	"fmt"
	"regexp"
	"strconv"
	"strings"
	"time"

	"aguagdl/api/internal/rotation"
	"aguagdl/api/internal/store"
	"aguagdl/api/internal/tg"
)

// HandleTelegram processes one webhook update. Returning an error makes Telegram retry it.
func (b *Bot) HandleTelegram(ctx context.Context, u tg.Update) error {
	id := "tg:" + strconv.FormatInt(u.UpdateID, 10)
	switch {
	case u.MyChatMember != nil && u.MyChatMember.Chat.Type == "private":
		if u.MyChatMember.NewChatMember.Status != "kicked" {
			return nil
		}
		// Blocking the bot is an opt-out: forget the subscription, as BAJA does.
		r := telegramUser(u.MyChatMember.Chat.ID)
		return b.process(ctx, id, func(w *Bot) error {
			_, err := w.Store.Unsubscribe(ctx, r.Channel, r.ID, "")
			return err
		})
	case u.CallbackQuery != nil:
		q := u.CallbackQuery
		if q.Message != nil && q.Message.Chat.Type != "private" {
			return nil
		}
		r := telegramUser(q.From.ID)
		if err := b.process(ctx, id, func(w *Bot) error { return w.onPayload(ctx, r, q.Data) }); err != nil {
			return err
		}
		if err := b.Telegram.AnswerCallback(ctx, q.ID); err != nil {
			b.Log.Warn("callback not answered", "err", err)
		}
		return nil
	case u.Message != nil && u.Message.Chat.Type == "private":
		m := u.Message
		r := telegramUser(m.Chat.ID)
		return b.process(ctx, id, func(w *Bot) error {
			switch {
			case m.Location != nil:
				return w.onLocation(ctx, r, m.Location.Latitude, m.Location.Longitude)
			case strings.HasPrefix(m.Text, "/"):
				return w.onCommand(ctx, r, m.Text)
			case m.Text != "":
				return w.onText(ctx, r, m.Text)
			}
			return w.text(ctx, r, msgUnsupported)
		})
	}
	return nil
}

func telegramUser(chatID int64) User {
	return User{Channel: store.Telegram, ID: strconv.FormatInt(chatID, 10)}
}

var startZoneRe = regexp.MustCompile(`^z([1-7])$`)

// onCommand handles the bot's menu: /start (with an optional deep-link zone, e.g. /start z6),
// /zona, /reportar, /pipa, /baja and /ayuda.
func (b *Bot) onCommand(ctx context.Context, r User, text string) error {
	cmd, arg, _ := strings.Cut(strings.TrimPrefix(text, "/"), " ")
	cmd, _, _ = strings.Cut(strings.ToLower(cmd), "@")
	arg = strings.TrimSpace(arg)
	switch cmd {
	case "start":
		if m := startZoneRe.FindStringSubmatch(arg); m != nil {
			zone, _ := strconv.Atoi(m[1])
			return b.subscribe(ctx, r, zone)
		}
		return b.greet(ctx, r)
	case "zona":
		if _, err := strconv.Atoi(arg); err == nil {
			return b.onText(ctx, r, "ZONA "+arg)
		}
		if arg != "" {
			return b.onText(ctx, r, arg)
		}
		return b.reply(ctx, r, Reply{Text: msgAskPlace, AskLocation: true})
	case "reportar":
		return b.reportLastCut(ctx, r)
	case "pipa":
		return b.text(ctx, r, msgPipa)
	case "escribe":
		return b.text(ctx, r, msgWrite(b.BaseURL))
	case "baja":
		return b.unsubscribe(ctx, r)
	}
	return b.text(ctx, r, msgHelp(b.BaseURL, r.Channel))
}

// TelegramMessage renders a reply for a Telegram chat: WhatsApp-style *bold* and _italic_
// become HTML, and choices become one button per row.
func TelegramMessage(chatID string, r Reply) (tg.Message, error) {
	id, err := strconv.ParseInt(chatID, 10, 64)
	if err != nil {
		return tg.Message{}, fmt.Errorf("telegram chat ID %q: %w", chatID, err)
	}
	m := tg.NewHTML(id, telegramHTML(r.Text))
	switch {
	case len(r.Choices) > 0:
		rows := make([][]tg.InlineButton, len(r.Choices))
		for i, c := range r.Choices {
			label := c.Title
			if c.Description != "" {
				label += " · " + c.Description
			}
			rows[i] = []tg.InlineButton{{Text: truncate(label, 60), CallbackData: c.ID}}
		}
		m.ReplyMarkup = tg.InlineKeyboard{InlineKeyboard: rows}
	case r.AskLocation:
		m.ReplyMarkup = tg.ReplyKeyboard{Keyboard: [][]tg.KeyboardButton{{{Text: "📍 Mandar mi ubicación", RequestLocation: true}}},
			ResizeKeyboard: true, OneTimeKeyboard: true}
	case r.CloseKeyboard:
		m.ReplyMarkup = tg.RemoveKeyboard{RemoveKeyboard: true}
	}
	return m, nil
}

var (
	htmlEscaper = strings.NewReplacer("&", "&amp;", "<", "&lt;", ">", "&gt;")
	boldRe      = regexp.MustCompile(`\*([^*\n]+)\*`)
	italicRe    = regexp.MustCompile(`(^|[\s(«])_([^_\n]+)_`)
)

func telegramHTML(s string) string {
	s = htmlEscaper.Replace(s)
	s = boldRe.ReplaceAllString(s, "<b>$1</b>")
	return italicRe.ReplaceAllString(s, "$1<i>$2</i>")
}

func truncate(s string, n int) string {
	r := []rune(s)
	if len(r) <= n {
		return s
	}
	return string(r[:n-1]) + "…"
}

// TelegramReminder is a Telegram chat's reminder for the block of cuts that starts tomorrow,
// with buttons to say whether the water is still on, for SIAPA's map and for BAJA.
func TelegramReminder(chatID string, zone int, days []time.Time) (tg.Message, error) {
	if len(days) == 0 {
		return tg.Message{}, errors.New("reminder without cut days")
	}
	return withWaterButtons(chatID, msgTelegramReminder(days, zone), zone, days[0])
}

// TelegramNotice is the notice two days before a block of cuts, with the reminder's buttons.
func TelegramNotice(chatID string, zone int, days []time.Time) (tg.Message, error) {
	if len(days) == 0 {
		return tg.Message{}, errors.New("notice without cut days")
	}
	return withWaterButtons(chatID, msgNotice(days, zone), zone, days[0])
}

func withWaterButtons(chatID, text string, zone int, start time.Time) (tg.Message, error) {
	m, err := TelegramMessage(chatID, Reply{Text: text})
	answers := make([]tg.InlineButton, len(waterAnswers))
	for i, a := range waterAnswers {
		date := start.Format(rotation.DateLayout)
		answers[i] = tg.InlineButton{Text: a.title, CallbackData: signed(fmt.Sprintf("A:%d:%s:%s", zone, date, a.key), chatID, "A", zone, date)}
	}
	m.ReplyMarkup = tg.InlineKeyboard{InlineKeyboard: [][]tg.InlineButton{
		answers,
		{{Text: "🗺️ Mapa del SIAPA", URL: MapURL}},
		{{Text: "Dejar de recibir avisos", CallbackData: "BAJA"}},
	}}
	return m, err
}

// TelegramFollowUp asks, after a block, how the water came back, with REPORTAR's answers for
// its last day.
func TelegramFollowUp(chatID string, zone int, days []time.Time) (tg.Message, error) {
	if len(days) == 0 {
		return tg.Message{}, errors.New("follow-up without cut days")
	}
	last := days[len(days)-1].Format(rotation.DateLayout)
	choices := make([]Choice, len(reportAnswers))
	for i, a := range reportAnswers {
		choices[i] = Choice{ID: signed(fmt.Sprintf("R:%d:%s:%s", zone, last, a.key), chatID, "R", zone, last), Title: a.title}
	}
	return TelegramMessage(chatID, Reply{Text: msgFollowUp(days, zone), Choices: choices})
}
