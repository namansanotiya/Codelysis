from auth.token import decode_token

def validate_token(token: str, require_admin: bool = False) -> bool:
    """Validates security token and checks authorization level."""
    claims = decode_token(token)
    if not claims:
        return False
    if require_admin and claims.get("role") != "admin":
        return False
    return True

def login_user(token: str) -> dict:
    """Logs in user given a valid token."""
    if validate_token(token):
        return {"status": "authenticated", "token": token}
    return {"status": "unauthorized"}
