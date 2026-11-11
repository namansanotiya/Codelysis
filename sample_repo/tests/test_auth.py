import sys
import os

# Ensure sample_repo root is in sys.path for standalone or suite test discovery
_sample_repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _sample_repo_root not in sys.path:
    sys.path.insert(0, _sample_repo_root)

# If 'core' was previously imported by the outer test runner pointing to Codelysis/core,
# add sample_repo/core to core.__path__ so both namespaces are resolved cleanly without conflict.
try:
    import core
    sample_core_dir = os.path.join(_sample_repo_root, "core")
    if hasattr(core, "__path__") and sample_core_dir not in core.__path__:
        core.__path__.insert(0, sample_core_dir)
except ImportError:
    pass

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
