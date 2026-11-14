
import hashlib
import hmac
import json


def sign_message(message, secret, purpose):
    if not isinstance(message, dict):
        raise ValueError("Message must be a dictionary.")

    if not isinstance(secret, str) or not secret:
        raise ValueError("Server credential is missing.")

    if purpose not in ("broker-request", "exchange-response"):
        raise ValueError("Invalid authentication purpose.")

    content = {
        key: value
        for key, value in message.items()
        if key != "signature"
    }

    payload = json.dumps(
        {"purpose": purpose, "message": content},
        sort_keys=True,
        separators=(",", ":")
    ).encode("utf-8")

    return hmac.new(
        secret.encode("utf-8"),
        payload,
        hashlib.sha256
    ).hexdigest()


def verify_message(message, secret, purpose):
    if not isinstance(message, dict):
        return False

    received_signature = message.get("signature")

    if not isinstance(received_signature, str):
        return False

    expected_signature = sign_message(
        message,
        secret,
        purpose
    )

    return hmac.compare_digest(
        received_signature,
        expected_signature
    )
