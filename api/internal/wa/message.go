// Package wa talks to the WhatsApp Cloud API: outgoing messages, webhook payloads and signatures.
package wa

// Recipient prefers the business-scoped user ID (BSUID) and falls back to the phone number.
type Recipient struct {
	UserID string
	Phone  string
}

type Message struct {
	MessagingProduct string       `json:"messaging_product"`
	RecipientType    string       `json:"recipient_type"`
	Recipient        string       `json:"recipient,omitempty"`
	To               string       `json:"to,omitempty"`
	Type             string       `json:"type"`
	Text             *Text        `json:"text,omitempty"`
	Template         *Template    `json:"template,omitempty"`
	Interactive      *Interactive `json:"interactive,omitempty"`
}

type Text struct {
	Body       string `json:"body"`
	PreviewURL bool   `json:"preview_url"`
}

type Template struct {
	Name       string      `json:"name"`
	Language   Language    `json:"language"`
	Components []Component `json:"components,omitempty"`
}

type Language struct {
	Code string `json:"code"`
}

type Component struct {
	Type       string      `json:"type"`
	SubType    string      `json:"sub_type,omitempty"`
	Index      string      `json:"index,omitempty"`
	Parameters []Parameter `json:"parameters"`
}

type Parameter struct {
	Type    string `json:"type"`
	Text    string `json:"text,omitempty"`
	Payload string `json:"payload,omitempty"`
}

type Interactive struct {
	Type   string     `json:"type"`
	Body   Body       `json:"body"`
	Action ListAction `json:"action"`
}

type Body struct {
	Text string `json:"text"`
}

type ListAction struct {
	Button   string    `json:"button"`
	Sections []Section `json:"sections"`
}

type Section struct {
	Title string `json:"title,omitempty"`
	Rows  []Row  `json:"rows"`
}

type Row struct {
	ID          string `json:"id"`
	Title       string `json:"title"`
	Description string `json:"description,omitempty"`
}

func newMessage(r Recipient, typ string) Message {
	m := Message{MessagingProduct: "whatsapp", RecipientType: "individual", Type: typ}
	if r.UserID != "" {
		m.Recipient = r.UserID
	} else {
		m.To = r.Phone
	}
	return m
}

func NewText(r Recipient, body string) Message {
	m := newMessage(r, "text")
	m.Text = &Text{Body: body}
	return m
}

// NewList builds a list message, trimming fields to WhatsApp's limits.
func NewList(r Recipient, body, button string, rows []Row) Message {
	if len(rows) > 10 {
		rows = rows[:10]
	}
	for i := range rows {
		rows[i].Title = truncate(rows[i].Title, 24)
		rows[i].Description = truncate(rows[i].Description, 72)
	}
	m := newMessage(r, "interactive")
	m.Interactive = &Interactive{
		Type:   "list",
		Body:   Body{Text: body},
		Action: ListAction{Button: truncate(button, 20), Sections: []Section{{Rows: rows}}},
	}
	return m
}

func NewTemplate(r Recipient, name, lang string, comps ...Component) Message {
	m := newMessage(r, "template")
	m.Template = &Template{Name: name, Language: Language{Code: lang}, Components: comps}
	return m
}

func BodyParams(texts ...string) Component {
	c := Component{Type: "body"}
	for _, t := range texts {
		c.Parameters = append(c.Parameters, Parameter{Type: "text", Text: t})
	}
	return c
}

func QuickReply(index int, payload string) Component {
	return Component{
		Type: "button", SubType: "quick_reply", Index: string(rune('0' + index)),
		Parameters: []Parameter{{Type: "payload", Payload: payload}},
	}
}

func truncate(s string, n int) string {
	r := []rune(s)
	if len(r) <= n {
		return s
	}
	return string(r[:n-1]) + "…"
}
