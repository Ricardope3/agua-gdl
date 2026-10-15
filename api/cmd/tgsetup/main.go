// Command tgsetup points the Telegram bot at the server and sets its Spanish profile:
// name, descriptions and command menu. Run it once after creating the bot in @BotFather
// and deploying with TG_TOKEN and TG_WEBHOOK_SECRET, and again after changing this file.
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
	shortDescription = "Aviso gratis la noche antes de cada corte de agua del SIAPA en tu zona. Ciudadano, no oficial, sin partido."
	description      = `Te aviso gratis la noche antes de cada corte de agua de la rotación del SIAPA en tu zona (zona metropolitana de Guadalajara).

Iniciativa ciudadana: no es del SIAPA ni del gobierno y no tiene partido.

Toca «Iniciar» y mándame tu ubicación, tu colonia o tu zona.
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
	flag.Parse()
	if err := run(*url); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

func run(url string) error {
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
			"allowed_updates": []string{"message", "callback_query", "my_chat_member"}, "drop_pending_updates": true}},
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
