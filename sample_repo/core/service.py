from auth.service import validate_token

class CoreProcessor:
    def process_request(self, token: str, payload: dict) -> dict:
        """Processes core request payload after verifying token validation."""
        if not validate_token(token):
            raise PermissionError("Invalid token supplied to process_request")
        return {"result": "success", "processed": payload}
