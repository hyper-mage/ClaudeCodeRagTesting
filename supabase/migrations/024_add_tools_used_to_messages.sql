-- Add tools_used JSONB column to messages table for persisting tool call card data.
-- Stores array of tool events (tool name, args, output, call_id, status) so the
-- frontend can render tool call cards on message reload, not just during streaming.

ALTER TABLE messages ADD COLUMN tools_used JSONB DEFAULT NULL;
