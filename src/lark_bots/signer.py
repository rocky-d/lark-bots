import base64
import hashlib
import hmac
import time

__all__ = [
    "Signer",
]


class Signer:
    def __init__(
        self,
        secret: str,
    ) -> None:
        self._secret = secret

    @property
    def secret(
        self,
    ) -> str:
        return self._secret

    def gen_sign(
        self,
        timestamp: str | int,
    ) -> str:
        return base64.b64encode(
            hmac.digest(
                f"{timestamp}\n{self._secret}".encode(),
                b"",
                hashlib.sha256,
            ),
        ).decode()

    def sign(
        self,
        payload: dict,
    ) -> None:
        payload["timestamp"] = timestamp = int(time.time())
        payload["sign"] = self.gen_sign(timestamp)
