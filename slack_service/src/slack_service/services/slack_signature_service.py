import hashlib
import hmac
import time

from slack_service.core.config import settings


class SlackSignatureService:
    def is_valid_request(self, timestamp: str, signature: str, body: bytes) -> bool:
        if not timestamp or not signature:
            return False

        try:
            request_time = int(timestamp)
        except ValueError:
            return False

        current_time = int(time.time())

        if abs(current_time - request_time) > 60 * 5:
            return False

        basestring = f"v0:{timestamp}:{body.decode('utf-8')}"
        expected_signature = "v0=" + hmac.new(
            settings.slack_signing_secret.encode("utf-8"),
            basestring.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(expected_signature, signature)


slack_signature_service = SlackSignatureService()