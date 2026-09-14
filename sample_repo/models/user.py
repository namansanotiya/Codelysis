class User:
    def __init__(self, user_id: str, role: str):
        self.user_id = user_id
        self.role = role

def get_user_profile(user_id: str) -> User:
    """Fetch user profile model."""
    return User(user_id=user_id, role="user")
