import time

from lark_bots.signer import Signer

# ===========================================================================
# Signer
# ===========================================================================


class TestSigner:
    def test_secret_property(self) -> None:
        signer = Signer("abc")
        assert "abc" == signer.secret

    def test_gen_sign_deterministic(self) -> None:
        signer = Signer("s")
        a = signer.gen_sign(1000)
        b = signer.gen_sign(1000)
        assert a == b

    def test_gen_sign_differs_by_timestamp(self) -> None:
        signer = Signer("s")
        assert signer.gen_sign(1) != signer.gen_sign(2)

    def test_gen_sign_differs_by_secret(self) -> None:
        a = Signer("a").gen_sign(1)
        b = Signer("b").gen_sign(1)
        assert a != b

    def test_gen_sign_accepts_str_timestamp(self) -> None:
        signer = Signer("s")
        result = signer.gen_sign("12345")
        assert isinstance(result, str)
        assert 0 < len(result)

    def test_sign_mutates_payload(self) -> None:
        signer = Signer("s")
        payload: dict = {}
        signer.sign(payload)
        assert "timestamp" in payload
        assert "sign" in payload
        assert isinstance(payload["timestamp"], int)
        assert isinstance(payload["sign"], str)

    def test_sign_timestamp_is_current(self) -> None:
        signer = Signer("s")
        payload: dict = {}
        before = int(time.time())
        signer.sign(payload)
        after = int(time.time())
        assert before <= payload["timestamp"] <= after

    def test_sign_consistency(self) -> None:
        signer = Signer("s")
        payload: dict = {}
        signer.sign(payload)
        expected = signer.gen_sign(payload["timestamp"])
        assert expected == payload["sign"]
