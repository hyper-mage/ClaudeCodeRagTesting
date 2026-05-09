import jwt
from jwt import PyJWKClient
from fastapi import Depends, HTTPException, Request
from config import Settings, get_settings

_jwk_client: PyJWKClient | None = None


def _get_jwk_client(settings: Settings) -> PyJWKClient:
    global _jwk_client
    if _jwk_client is None:
        jwks_url = f"{settings.supabase_url_resolved}/auth/v1/.well-known/jwks.json"
        _jwk_client = PyJWKClient(jwks_url)
    return _jwk_client


def get_user_id(
    request: Request, settings: Settings = Depends(get_settings)
) -> str:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing authorization token")

    token = auth_header.split(" ", 1)[1]
    try:
        # Detect algorithm from token header
        header = jwt.get_unverified_header(token)
        alg = header.get("alg", "HS256")

        if alg == "HS256":
            # Legacy Supabase projects use symmetric signing
            signing_key = settings.supabase_jwt_secret
        else:
            # Newer projects use asymmetric (ES256) with JWKS
            jwk_client = _get_jwk_client(settings)
            signing_key = jwk_client.get_signing_key_from_jwt(token).key

        payload = jwt.decode(
            token,
            signing_key,
            algorithms=[alg],
            audience="authenticated",
            leeway=30,
        )
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token: no sub claim")
        request.state.user_id = user_id   # SEC-04: bridge for slowapi key_func (Phase 6 D-04)
        return user_id
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
