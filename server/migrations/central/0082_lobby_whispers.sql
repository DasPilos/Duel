ALTER TABLE lobby_chat_messages
    ADD COLUMN recipient_user_id BIGINT REFERENCES users(id) ON DELETE CASCADE;
CREATE INDEX idx_lobby_chat_messages_recipient ON lobby_chat_messages(recipient_user_id, created_at);
