create table threads (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id),
  title text,
  openai_thread_id text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table threads enable row level security;

create policy "Users can select own threads"
  on threads for select
  using (auth.uid() = user_id);

create policy "Users can insert own threads"
  on threads for insert
  with check (auth.uid() = user_id);

create policy "Users can update own threads"
  on threads for update
  using (auth.uid() = user_id);

create policy "Users can delete own threads"
  on threads for delete
  using (auth.uid() = user_id);
