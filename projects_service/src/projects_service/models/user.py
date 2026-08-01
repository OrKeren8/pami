from datetime import datetime
from typing import Optional

from beanie import Document
from pydantic import Field
from pymongo import ASCENDING, IndexModel


class User(Document):
    """A local mirror of the Cognito users who have signed in.

    Two reasons this exists rather than calling Cognito.

    Sharing resolves an email address to an account. Doing that against Cognito needs
    ListUsers, an IAM permission a restricted lab account may not grant - and the whole
    feature would then be unavailable for a reason unrelated to the code. Against this
    collection it needs nothing.

    The admin dashboard needs a user list with per-user project counts. Cognito cannot join
    against Mongo, so the counts come from here anyway; keeping the roster here too means one
    query instead of a paginated API call plus a join.

    Written on every sign-in, so it is at most one login stale. `sub` is the Cognito subject
    and the only durable identifier - an email can be changed.
    """

    sub: str
    email: str
    name: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_seen_at: datetime = Field(default_factory=datetime.utcnow)
    # Cognito exposes no last-sign-in time (UserLastModifiedDate is not one), so the admin
    # page shows this instead of implying data AWS does not give us.
    sign_in_count: int = 0

    class Settings:
        name = "users"
        indexes = [
            IndexModel([("sub", ASCENDING)], unique=True, name="sub_unique"),
            # Sharing looks users up by email on every invite, and it must be unique or an
            # invite could resolve to two accounts.
            IndexModel([("email", ASCENDING)], unique=True, name="email_unique"),
        ]
