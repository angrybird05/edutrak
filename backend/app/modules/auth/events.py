"""
Auth module events — Event definitions and subscribers.
"""
import logging
from app.core.event_bus import event_bus

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Event names (constants for type safety)
# ---------------------------------------------------------------------------
AUTH_LOGIN_SUCCESS = "auth.login_success"
AUTH_LOGIN_FAILED = "auth.login_failed"
AUTH_TOKEN_REVOKED = "auth.token_revoked"
AUTH_OTP_REQUESTED = "auth.otp_requested"


# ---------------------------------------------------------------------------
# Subscribers for auth events (other modules register their own handlers)
# ---------------------------------------------------------------------------
# Auth module itself has no event subscribers — it only publishes.
# The platform module subscribes to auth events for audit logging.
# The notification module subscribes for security alerts.
