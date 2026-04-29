create table messages (
  id uuid primary key default gen_random_uuid(),
  thread_id uuid not null references threads(id) on delete cascade,
  user_id uuid not null references auth.users(id),
  role text not null check (role in ('user', 'assistant')),
  content text not null,
  openai_message_id text,
  created_at timestamptz not null default now()
);

alter table messages enable row level security;

create policy "Users can select own messages"
  on messages for select
  using (auth.uid() = user_id);

create policy "Users can insert own messages"
  on messages for insert
  with check (auth.uid() = user_id);

create policy "Users can delete own messages"
  on messages for delete
  using (auth.uid() = user_id);
