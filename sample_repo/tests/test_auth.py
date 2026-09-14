from auth.service import validate_token, login_user
from core.service import CoreProcessor

def test_validate_token_success():
    assert validate_token("valid_token") is True

def test_login_user():
    res = login_user("valid_token")
    assert res["status"] == "authenticated"

def test_core_processor():
    processor = CoreProcessor()
    res = processor.process_request("valid_token", {"data": 123})
    assert res["result"] == "success"
