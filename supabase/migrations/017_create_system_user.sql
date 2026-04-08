-- System user for default knowledge base ownership.
-- This user owns all pre-seeded default KB content (e.g., Board Games folder and documents).
-- It should NEVER log in via the frontend -- the password is random and unguessable.
-- The fixed UUID '00000000-0000-0000-0000-000000000000' allows other migrations to
-- reference this user without needing a lookup query.

DO $$
DECLARE
  system_user_id UUID := '00000000-0000-0000-0000-000000000000';
BEGIN
  -- Only insert if not exists (idempotent)
  IF NOT EXISTS (SELECT 1 FROM auth.users WHERE id = system_user_id) THEN
    INSERT INTO auth.users (
      instance_id, id, aud, role, email,
      encrypted_password, email_confirmed_at,
      created_at, updated_at, confirmation_token,
      raw_app_meta_data, raw_user_meta_data
    ) VALUES (
      '00000000-0000-0000-0000-000000000000',
      system_user_id,
      'authenticated',
      'authenticated',
      'default-kb@system.internal',
      crypt('SYSTEM_USER_NO_LOGIN_' || gen_random_uuid()::text, gen_salt('bf')),
      now(),
      now(),
      now(),
      '',
      '{"provider": "email", "providers": ["email"]}'::jsonb,
      '{"is_system_user": true}'::jsonb
    );

    INSERT INTO auth.identities (
      id, user_id, identity_data, provider, provider_id,
      last_sign_in_at, created_at, updated_at
    ) VALUES (
      gen_random_uuid(),
      system_user_id,
      jsonb_build_object('sub', system_user_id::text, 'email', 'default-kb@system.internal'),
      'email',
      system_user_id::text,
      now(),
      now(),
      now()
    );
  END IF;
END $$;
