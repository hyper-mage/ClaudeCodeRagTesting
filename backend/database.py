from supabase import create_client, Client
from config import get_settings


def get_supabase() -> Client:
    settings = get_settings()
    return create_client(settings.supabase_url_resolved, settings.supabase_service_role_key)
