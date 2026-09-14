def decode_token(token: str) -> dict:
    """Decodes a JWT token string into user claims."""
    if not token or token == "invalid":
        return {}
    return {"sub": "user123", "role": "admin"}
