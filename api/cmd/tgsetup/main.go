// Command tgsetup points the Telegram bot at the server and sets its Spanish profile:
// name, descriptions and command menu. Run it once after creating the bot in @BotFather
// and deploying with TG_TOKEN and TG_WEBHOOK_SECRET, and again after changing this file.
// A re-run keeps the updates Telegram holds for the webhook: messages people sent meanwhile,
// and those whose replies were refused and wait for redelivery. -drop-pending discards them.
//
//	cd api
//	TG_TOKEN='…' TG_WEBHOOK_SECRET='…' go run ./cmd/tgsetup
package main

import (
	"context"
	"errors"
	"flag"
	"fmt"
	"net/http"
	"os"
	"time"

	"aguagdl/api/internal/tg"
)

const (
	name             = "Agua GDL"
	shortDescription = "El agua es un derecho. Exígelo. Reporta tu colonia, pide una pipa y recibe avisos de los cortes del SIAPA. Sin partido."
	description      = `El agua es un derecho. Exígelo.

Reporta cómo está el agua en tu colonia: cada reporte es una prueba de dónde falla el gobierno. Exígele a quien le toca que lo arregle: https://aguagdl.com/exige. ¿Sin agua? Te digo cómo pedir una pipa. Y te aviso gratis dos días antes de los cortes de tu zona y la noche antes.

Iniciativa ciudadana: no es del SIAPA ni del gobierno y no tiene partido. Toca «Iniciar».

Más en https://aguagdl.com
Aviso de privacidad: https://aguagdl.com/privacidad`
)

type command struct {
	Command     string `json:"command"`
	Description string `json:"description"`
}

var commands = []command{
	{"zona", "Elegir o cambiar tu zona"},
	{"reportar", "Contar cómo regresó el agua"},
	{"pipa", "Cómo pedir una pipa al SIAPA"},
	{"escribe", "Escribirle al Congreso sobre el contrato del agua"},
	{"baja", "Dejar de recibir avisos y borrar tus datos"},
	{"ayuda", "Ver lo que puedo hacer"},
}

func main() {
	url := flag.String("url", "https://api.aguagdl.com/tg/webhook", "webhook URL")
	dropPending := flag.Bool("drop-pending", false, "discard the updates Telegram holds for the webhook")
	flag.Parse()
	if err := run(*url, *dropPending); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

func run(url string, dropPending bool) error {
	token, secret := os.Getenv("TG_TOKEN"), os.Getenv("TG_WEBHOOK_SECRET")
	if token == "" || secret == "" {
		return errors.New("set TG_TOKEN and TG_WEBHOOK_SECRET (the same values as in Fly)")
	}
	c := &tg.Client{BaseURL: "https://api.telegram.org", Token: token, HTTP: &http.Client{Timeout: 15 * time.Second}}
	ctx := context.Background()
	steps := []struct {
		method string
		params any
	}{
		{"setMyName", map[string]string{"name": name}},
		{"setMyShortDescription", map[string]string{"short_description": shortDescription}},
		{"setMyDescription", map[string]string{"description": description}},
		{"setMyCommands", map[string]any{"commands": commands}},
		{"setWebhook", map[string]any{"url": url, "secret_token": secret, "max_connections": 10,
			"allowed_updates": []string{"message", "callback_query", "my_chat_member"}, "drop_pending_updates": dropPending}},
	}
	for _, s := range steps {
		if err := c.Call(ctx, s.method, s.params, nil); err != nil {
			return fmt.Errorf("%s: %w", s.method, err)
		}
		fmt.Println("ok", s.method)
	}
	var info struct {
		URL                string `json:"url"`
		PendingUpdateCount int    `json:"pending_update_count"`
		LastErrorMessage   string `json:"last_error_message"`
	}
	if err := c.Call(ctx, "getWebhookInfo", struct{}{}, &info); err != nil {
		return fmt.Errorf("getWebhookInfo: %w", err)
	}
	fmt.Printf("webhook %s, %d pending, last error %q\n", info.URL, info.PendingUpdateCount, info.LastErrorMessage)
	return nil
}
