package tg

// Update is one webhook delivery. Only private chats are handled.
type Update struct {
	UpdateID      int64              `json:"update_id"`
	Message       *InboundMessage    `json:"message,omitempty"`
	CallbackQuery *CallbackQuery     `json:"callback_query,omitempty"`
	MyChatMember  *ChatMemberUpdated `json:"my_chat_member,omitempty"`
}

type InboundMessage struct {
	MessageID int64     `json:"message_id"`
	Chat      Chat      `json:"chat"`
	Text      string    `json:"text"`
	Location  *Location `json:"location,omitempty"`
}

type Chat struct {
	ID   int64  `json:"id"`
	Type string `json:"type"` // private, group, supergroup or channel
}

type Location struct {
	Latitude  float64 `json:"latitude"`
	Longitude float64 `json:"longitude"`
}

type User struct {
	ID int64 `json:"id"`
}

type CallbackQuery struct {
	ID      string          `json:"id"`
	From    User            `json:"from"`
	Message *InboundMessage `json:"message,omitempty"`
	Data    string          `json:"data"`
}

// ChatMemberUpdated arrives in a private chat only when the user blocks the bot
// (status "kicked") or unblocks it ("member").
type ChatMemberUpdated struct {
	Chat          Chat `json:"chat"`
	NewChatMember struct {
		Status string `json:"status"`
	} `json:"new_chat_member"`
}
