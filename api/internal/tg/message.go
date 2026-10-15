package tg

type Message struct {
	ChatID             int64               `json:"chat_id"`
	Text               string              `json:"text"`
	ParseMode          string              `json:"parse_mode,omitempty"`
	LinkPreviewOptions *LinkPreviewOptions `json:"link_preview_options,omitempty"`
	ReplyMarkup        any                 `json:"reply_markup,omitempty"`
}

type LinkPreviewOptions struct {
	IsDisabled bool `json:"is_disabled"`
}

type InlineKeyboard struct {
	InlineKeyboard [][]InlineButton `json:"inline_keyboard"`
}

type InlineButton struct {
	Text         string `json:"text"`
	CallbackData string `json:"callback_data,omitempty"`
	URL          string `json:"url,omitempty"`
}

type ReplyKeyboard struct {
	Keyboard        [][]KeyboardButton `json:"keyboard"`
	ResizeKeyboard  bool               `json:"resize_keyboard"`
	OneTimeKeyboard bool               `json:"one_time_keyboard"`
}

type KeyboardButton struct {
	Text            string `json:"text"`
	RequestLocation bool   `json:"request_location,omitempty"`
}

type RemoveKeyboard struct {
	RemoveKeyboard bool `json:"remove_keyboard"`
}

// NewHTML is a message in Telegram's HTML mode without link previews.
func NewHTML(chatID int64, html string) Message {
	return Message{ChatID: chatID, Text: html, ParseMode: "HTML", LinkPreviewOptions: &LinkPreviewOptions{IsDisabled: true}}
}
