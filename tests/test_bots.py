import asyncio as aio
import random
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from lark_bots import ABot, Bot, QBot
from lark_bots.bots import _Signer

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_URL = "https://open.feishu.cn/open-apis/bot/v2/hook/test"
_SECRET = "test-secret"


def _ok_response() -> httpx.Response:
    return httpx.Response(200, json={"code": 0})


def _bad_code_response() -> httpx.Response:
    return httpx.Response(200, json={"code": 1, "msg": "bad"})


def _server_error_response() -> httpx.Response:
    return httpx.Response(500, text="Internal Server Error")


@asynccontextmanager
async def _qbot_ctx(qbot: QBot) -> AsyncGenerator[QBot, None]:
    await qbot.astart()
    try:
        yield qbot
    finally:
        await qbot.acancel()
        await qbot.astop()


# ===========================================================================
# _Signer
# ===========================================================================


class TestSigner:
    def test_secret_property(self) -> None:
        signer = _Signer("abc")
        assert "abc" == signer.secret

    def test_gen_sign_deterministic(self) -> None:
        signer = _Signer("s")
        a = signer.gen_sign(1000)
        b = signer.gen_sign(1000)
        assert a == b

    def test_gen_sign_differs_by_timestamp(self) -> None:
        signer = _Signer("s")
        assert signer.gen_sign(1) != signer.gen_sign(2)

    def test_gen_sign_differs_by_secret(self) -> None:
        a = _Signer("a").gen_sign(1)
        b = _Signer("b").gen_sign(1)
        assert a != b

    def test_gen_sign_accepts_str_timestamp(self) -> None:
        signer = _Signer("s")
        result = signer.gen_sign("12345")
        assert isinstance(result, str)
        assert 0 < len(result)

    def test_sign_mutates_payload(self) -> None:
        signer = _Signer("s")
        payload: dict = {}
        signer.sign(payload)
        assert "timestamp" in payload
        assert "sign" in payload
        assert isinstance(payload["timestamp"], int)
        assert isinstance(payload["sign"], str)

    def test_sign_timestamp_is_current(self) -> None:
        signer = _Signer("s")
        payload: dict = {}
        before = int(time.time())
        signer.sign(payload)
        after = int(time.time())
        assert before <= payload["timestamp"] <= after

    def test_sign_consistency(self) -> None:
        signer = _Signer("s")
        payload: dict = {}
        signer.sign(payload)
        expected = signer.gen_sign(payload["timestamp"])
        assert expected == payload["sign"]


# ===========================================================================
# Bot
# ===========================================================================


class TestBotInit:
    def test_defaults(self) -> None:
        bot = Bot(_URL)
        assert False is bot.closed
        assert bot._signer is None
        assert 1.0 == bot._delay
        assert 3 == bot._max_tries

    def test_with_secret(self) -> None:
        bot = Bot(_URL, secret=_SECRET)
        assert bot._signer is not None
        assert _SECRET == bot._signer.secret

    def test_delay_clamp(self) -> None:
        bot = Bot(_URL, delay=-5.0)
        assert 0.0 == bot._delay

    def test_max_tries_clamp(self) -> None:
        bot = Bot(_URL, max_tries=-1)
        assert 1 == bot._max_tries


class TestBotLifecycle:
    def test_context_manager(self) -> None:
        with Bot(_URL) as bot:
            assert False is bot.closed
        assert True is bot.closed

    def test_start_stop(self) -> None:
        bot = Bot(_URL)
        bot.start()
        assert False is bot.closed
        bot.stop()
        assert True is bot.closed


class TestBotSend:
    @patch("httpx.Client.post")
    def test_success_first_try(self, mock_post: MagicMock) -> None:
        mock_post.return_value = _ok_response()
        with Bot(_URL) as bot:
            resp = bot.send({"msg_type": "text", "content": {"text": "hi"}})
        assert 200 == resp.status_code

    @patch("httpx.Client.post")
    def test_with_signer(self, mock_post: MagicMock) -> None:
        mock_post.return_value = _ok_response()
        with Bot(_URL, secret=_SECRET) as bot:
            payload: dict = {"msg_type": "text"}
            bot.send(payload)
        assert "timestamp" in payload
        assert "sign" in payload

    @patch("time.sleep")
    @patch("httpx.Client.post")
    def test_retry_on_http_error(
        self,
        mock_post: MagicMock,
        mock_sleep: MagicMock,
    ) -> None:
        mock_post.side_effect = [_server_error_response(), _ok_response()]
        with Bot(_URL, max_tries=3) as bot:
            resp = bot.send({"msg_type": "text"})
        assert 200 == resp.status_code
        assert 2 == mock_post.call_count
        mock_sleep.assert_called_once_with(1.0)

    @patch("time.sleep")
    @patch("httpx.Client.post")
    def test_retry_on_bad_code(
        self,
        mock_post: MagicMock,
        mock_sleep: MagicMock,
    ) -> None:
        mock_post.side_effect = [_bad_code_response(), _ok_response()]
        with Bot(_URL, max_tries=3) as bot:
            resp = bot.send({"msg_type": "text"})
        assert 200 == resp.status_code
        assert 2 == mock_post.call_count

    @patch("httpx.Client.post")
    def test_retry_on_non_dict_json(self, mock_post: MagicMock) -> None:
        mock_post.side_effect = [
            httpx.Response(200, json=[1, 2, 3]),
            _ok_response(),
        ]
        with Bot(_URL, max_tries=2) as bot:
            resp = bot.send({"msg_type": "text"})
        assert {"code": 0} == resp.json()

    @patch("time.sleep")
    @patch("httpx.Client.post")
    def test_exhausted_retries_sends_error_card(
        self,
        mock_post: MagicMock,
        mock_sleep: MagicMock,
    ) -> None:
        err = _server_error_response()
        mock_post.side_effect = [err, err, err, _ok_response()]
        with Bot(_URL, max_tries=3) as bot:
            resp = bot.send({"msg_type": "text"})
        assert 500 == resp.status_code
        assert 4 == mock_post.call_count
        error_payload = mock_post.call_args_list[3][1]["json"]
        assert "interactive" == error_payload["msg_type"]

    @patch("time.sleep")
    @patch("httpx.Client.post")
    def test_exhausted_retries_with_signer(
        self,
        mock_post: MagicMock,
        mock_sleep: MagicMock,
    ) -> None:
        mock_post.side_effect = [_server_error_response(), _ok_response()]
        with Bot(_URL, secret=_SECRET, max_tries=1) as bot:
            bot.send({"msg_type": "text"})
        assert 2 == mock_post.call_count
        error_payload = mock_post.call_args_list[1][1]["json"]
        assert "sign" in error_payload

    @patch("time.sleep")
    @patch("httpx.Client.post")
    def test_no_sleep_on_first_try(
        self,
        mock_post: MagicMock,
        mock_sleep: MagicMock,
    ) -> None:
        mock_post.return_value = _ok_response()
        with Bot(_URL) as bot:
            bot.send({"msg_type": "text"})
        mock_sleep.assert_not_called()

    @patch("time.sleep")
    @patch("httpx.Client.post")
    def test_custom_delay(
        self,
        mock_post: MagicMock,
        mock_sleep: MagicMock,
    ) -> None:
        mock_post.side_effect = [_server_error_response(), _ok_response()]
        with Bot(_URL, delay=2.5, max_tries=2) as bot:
            bot.send({"msg_type": "text"})
        mock_sleep.assert_called_once_with(2.5)


class TestBotSendHelpers:
    @patch("httpx.Client.post")
    def test_send_text(self, mock_post: MagicMock) -> None:
        mock_post.return_value = _ok_response()
        with Bot(_URL) as bot:
            bot.send_text("hello")
        payload = mock_post.call_args[1]["json"]
        assert "text" == payload["msg_type"]
        assert "hello" == payload["content"]["text"]

    @patch("httpx.Client.post")
    def test_send_post(self, mock_post: MagicMock) -> None:
        mock_post.return_value = _ok_response()
        with Bot(_URL) as bot:
            bot.send_post({"en_us": {"title": "t"}})
        payload = mock_post.call_args[1]["json"]
        assert "post" == payload["msg_type"]

    @patch("httpx.Client.post")
    def test_send_share_chat(self, mock_post: MagicMock) -> None:
        mock_post.return_value = _ok_response()
        with Bot(_URL) as bot:
            bot.send_share_chat("oc_xxx")
        payload = mock_post.call_args[1]["json"]
        assert "share_chat" == payload["msg_type"]
        assert "oc_xxx" == payload["content"]["share_chat_id"]

    @patch("httpx.Client.post")
    def test_send_image(self, mock_post: MagicMock) -> None:
        mock_post.return_value = _ok_response()
        with Bot(_URL) as bot:
            bot.send_image("img_xxx")
        payload = mock_post.call_args[1]["json"]
        assert "image" == payload["msg_type"]
        assert "img_xxx" == payload["content"]["image_key"]

    @patch("httpx.Client.post")
    def test_send_interactive(self, mock_post: MagicMock) -> None:
        mock_post.return_value = _ok_response()
        card = {"schema": "2.0"}
        with Bot(_URL) as bot:
            bot.send_interactive(card)
        payload = mock_post.call_args[1]["json"]
        assert "interactive" == payload["msg_type"]
        assert card == payload["card"]


# ===========================================================================
# ABot
# ===========================================================================


class TestABotInit:
    def test_defaults(self) -> None:
        abot = ABot(_URL)
        assert False is abot.closed
        assert abot._signer is None
        assert 1.0 == abot._delay
        assert 3 == abot._max_tries

    def test_with_secret(self) -> None:
        abot = ABot(_URL, secret=_SECRET)
        assert abot._signer is not None

    def test_delay_clamp(self) -> None:
        abot = ABot(_URL, delay=-1.0)
        assert 0.0 == abot._delay

    def test_max_tries_clamp(self) -> None:
        abot = ABot(_URL, max_tries=0)
        assert 1 == abot._max_tries


class TestABotLifecycle:
    @pytest.mark.asyncio
    async def test_async_context_manager(self) -> None:
        async with ABot(_URL) as abot:
            assert False is abot.closed
        assert True is abot.closed

    @pytest.mark.asyncio
    async def test_astart_astop(self) -> None:
        abot = ABot(_URL)
        await abot.astart()
        assert False is abot.closed
        await abot.astop()
        assert True is abot.closed


class TestABotSend:
    @pytest.mark.asyncio
    @patch("httpx.AsyncClient.post", new_callable=AsyncMock)
    async def test_success_first_try(self, mock_post: AsyncMock) -> None:
        mock_post.return_value = _ok_response()
        async with ABot(_URL) as abot:
            resp = await abot.asend({"msg_type": "text"})
        assert 200 == resp.status_code

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient.post", new_callable=AsyncMock)
    async def test_with_signer(self, mock_post: AsyncMock) -> None:
        mock_post.return_value = _ok_response()
        async with ABot(_URL, secret=_SECRET) as abot:
            payload: dict = {"msg_type": "text"}
            await abot.asend(payload)
        assert "sign" in payload

    @pytest.mark.asyncio
    @patch("asyncio.sleep", new_callable=AsyncMock)
    @patch("httpx.AsyncClient.post", new_callable=AsyncMock)
    async def test_retry_on_http_error(
        self,
        mock_post: AsyncMock,
        mock_sleep: AsyncMock,
    ) -> None:
        mock_post.side_effect = [_server_error_response(), _ok_response()]
        async with ABot(_URL, max_tries=3) as abot:
            resp = await abot.asend({"msg_type": "text"})
        assert 200 == resp.status_code
        assert 2 == mock_post.call_count

    @pytest.mark.asyncio
    @patch("asyncio.sleep", new_callable=AsyncMock)
    @patch("httpx.AsyncClient.post", new_callable=AsyncMock)
    async def test_exhausted_retries_sends_error_card(
        self,
        mock_post: AsyncMock,
        mock_sleep: AsyncMock,
    ) -> None:
        err = _server_error_response()
        mock_post.side_effect = [err, err, err, _ok_response()]
        async with ABot(_URL, max_tries=3) as abot:
            resp = await abot.asend({"msg_type": "text"})
        assert 500 == resp.status_code
        assert 4 == mock_post.call_count
        error_payload = mock_post.call_args_list[3][1]["json"]
        assert "interactive" == error_payload["msg_type"]

    @pytest.mark.asyncio
    @patch("asyncio.sleep", new_callable=AsyncMock)
    @patch("httpx.AsyncClient.post", new_callable=AsyncMock)
    async def test_exhausted_retries_with_signer(
        self,
        mock_post: AsyncMock,
        mock_sleep: AsyncMock,
    ) -> None:
        mock_post.side_effect = [_server_error_response(), _ok_response()]
        async with ABot(_URL, secret=_SECRET, max_tries=1) as abot:
            await abot.asend({"msg_type": "text"})
        error_payload = mock_post.call_args_list[1][1]["json"]
        assert "sign" in error_payload

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient.post", new_callable=AsyncMock)
    async def test_retry_on_non_dict_json(self, mock_post: AsyncMock) -> None:
        mock_post.side_effect = [
            httpx.Response(200, json="not a dict"),
            _ok_response(),
        ]
        async with ABot(_URL, max_tries=2) as abot:
            resp = await abot.asend({"msg_type": "text"})
        assert {"code": 0} == resp.json()


class TestABotSendHelpers:
    @pytest.mark.asyncio
    @patch("httpx.AsyncClient.post", new_callable=AsyncMock)
    async def test_asend_text(self, mock_post: AsyncMock) -> None:
        mock_post.return_value = _ok_response()
        async with ABot(_URL) as abot:
            await abot.asend_text("hello")
        payload = mock_post.call_args[1]["json"]
        assert "text" == payload["msg_type"]
        assert "hello" == payload["content"]["text"]

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient.post", new_callable=AsyncMock)
    async def test_asend_post(self, mock_post: AsyncMock) -> None:
        mock_post.return_value = _ok_response()
        async with ABot(_URL) as abot:
            await abot.asend_post({"en_us": {"title": "t"}})
        payload = mock_post.call_args[1]["json"]
        assert "post" == payload["msg_type"]

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient.post", new_callable=AsyncMock)
    async def test_asend_share_chat(self, mock_post: AsyncMock) -> None:
        mock_post.return_value = _ok_response()
        async with ABot(_URL) as abot:
            await abot.asend_share_chat("oc_xxx")
        payload = mock_post.call_args[1]["json"]
        assert "share_chat" == payload["msg_type"]

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient.post", new_callable=AsyncMock)
    async def test_asend_image(self, mock_post: AsyncMock) -> None:
        mock_post.return_value = _ok_response()
        async with ABot(_URL) as abot:
            await abot.asend_image("img_xxx")
        payload = mock_post.call_args[1]["json"]
        assert "image" == payload["msg_type"]

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient.post", new_callable=AsyncMock)
    async def test_asend_interactive(self, mock_post: AsyncMock) -> None:
        mock_post.return_value = _ok_response()
        card = {"schema": "2.0"}
        async with ABot(_URL) as abot:
            await abot.asend_interactive(card)
        payload = mock_post.call_args[1]["json"]
        assert "interactive" == payload["msg_type"]


# ===========================================================================
# QBot
# ===========================================================================


class TestQBotInit:
    @pytest.mark.asyncio
    async def test_defaults(self) -> None:
        qbot = QBot(_URL)
        assert False is qbot.closed
        assert qbot._signer is None
        assert 1.0 == qbot._delay
        assert 3 == qbot._max_tries

    @pytest.mark.asyncio
    async def test_with_secret(self) -> None:
        qbot = QBot(_URL, secret=_SECRET)
        assert qbot._signer is not None

    @pytest.mark.asyncio
    async def test_delay_clamp(self) -> None:
        qbot = QBot(_URL, delay=-2.0)
        assert 0.0 == qbot._delay

    @pytest.mark.asyncio
    async def test_max_tries_clamp(self) -> None:
        qbot = QBot(_URL, max_tries=0)
        assert 1 == qbot._max_tries


class TestQBotLifecycle:
    @pytest.mark.asyncio
    async def test_astart_acancel_astop(self) -> None:
        qbot = QBot(_URL)
        await qbot.astart()
        assert False is qbot.closed
        assert True is qbot.started
        await qbot.acancel()
        await qbot.astop()
        assert True is qbot.closed
        assert False is qbot.started

    @pytest.mark.asyncio
    async def test_astart_idempotent(self) -> None:
        async with _qbot_ctx(QBot(_URL)) as qbot:
            await qbot.astart()
            assert True is qbot.started

    @pytest.mark.asyncio
    async def test_acancel_not_started(self) -> None:
        qbot = QBot(_URL)
        await qbot.acancel()
        assert False is qbot.started

    @pytest.mark.asyncio
    async def test_astop_not_started(self) -> None:
        qbot = QBot(_URL)
        await qbot.astop()
        assert False is qbot.started


class TestQBotSend:
    @pytest.mark.asyncio
    @patch("httpx.AsyncClient.post", new_callable=AsyncMock)
    async def test_send_returns_future(self, mock_post: AsyncMock) -> None:
        mock_post.return_value = _ok_response()
        async with _qbot_ctx(QBot(_URL)) as qbot:
            fut = qbot.send({"msg_type": "text", "content": {"text": "hi"}})
            assert isinstance(fut, aio.Future)
            resp = await fut
        assert 200 == resp.status_code

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient.post", new_callable=AsyncMock)
    async def test_asend_returns_future(self, mock_post: AsyncMock) -> None:
        mock_post.return_value = _ok_response()
        async with _qbot_ctx(QBot(_URL)) as qbot:
            fut = await qbot.asend({"msg_type": "text"})
            assert isinstance(fut, aio.Future)
            resp = await fut
        assert 200 == resp.status_code

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient.post", new_callable=AsyncMock)
    async def test_send_with_signer(self, mock_post: AsyncMock) -> None:
        mock_post.return_value = _ok_response()
        async with _qbot_ctx(QBot(_URL, secret=_SECRET)) as qbot:
            fut = qbot.send({"msg_type": "text"})
            await fut
        call_payload = mock_post.call_args[1]["json"]
        assert "sign" in call_payload

    @pytest.mark.asyncio
    @patch("asyncio.sleep", new_callable=AsyncMock)
    @patch("httpx.AsyncClient.post", new_callable=AsyncMock)
    async def test_retry_then_success(
        self,
        mock_post: AsyncMock,
        mock_sleep: AsyncMock,
    ) -> None:
        mock_post.side_effect = [_server_error_response(), _ok_response()]
        async with _qbot_ctx(QBot(_URL, max_tries=3)) as qbot:
            resp = await qbot.send({"msg_type": "text"})
        assert 200 == resp.status_code

    @pytest.mark.asyncio
    @patch("asyncio.sleep", new_callable=AsyncMock)
    @patch("httpx.AsyncClient.post", new_callable=AsyncMock)
    async def test_retry_on_bad_code(
        self,
        mock_post: AsyncMock,
        mock_sleep: AsyncMock,
    ) -> None:
        mock_post.side_effect = [_bad_code_response(), _ok_response()]
        async with _qbot_ctx(QBot(_URL, max_tries=2)) as qbot:
            resp = await qbot.send({"msg_type": "text"})
        assert 200 == resp.status_code
        assert 2 == mock_post.call_count

    @pytest.mark.asyncio
    @patch("asyncio.sleep", new_callable=AsyncMock)
    @patch("httpx.AsyncClient.post", new_callable=AsyncMock)
    async def test_exhausted_retries_sends_error_card(
        self,
        mock_post: AsyncMock,
        mock_sleep: AsyncMock,
    ) -> None:
        err = _server_error_response()
        mock_post.side_effect = [err, err, _ok_response()]
        async with _qbot_ctx(QBot(_URL, max_tries=2)) as qbot:
            resp = await qbot.send({"msg_type": "text"})
        assert 500 == resp.status_code
        assert 3 == mock_post.call_count

    @pytest.mark.asyncio
    @patch("asyncio.sleep", new_callable=AsyncMock)
    @patch("httpx.AsyncClient.post", new_callable=AsyncMock)
    async def test_exhausted_retries_with_signer(
        self,
        mock_post: AsyncMock,
        mock_sleep: AsyncMock,
    ) -> None:
        mock_post.side_effect = [_server_error_response(), _ok_response()]
        async with _qbot_ctx(QBot(_URL, secret=_SECRET, max_tries=1)) as qbot:
            resp = await qbot.send({"msg_type": "text"})
        assert 500 == resp.status_code
        assert 2 == mock_post.call_count
        error_payload = mock_post.call_args_list[1][1]["json"]
        assert "sign" in error_payload

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient.post", new_callable=AsyncMock)
    async def test_multiple_sends_processed_in_order(
        self,
        mock_post: AsyncMock,
    ) -> None:
        mock_post.return_value = _ok_response()
        async with _qbot_ctx(QBot(_URL)) as qbot:
            fut1 = qbot.send({"msg_type": "text", "content": {"text": "a"}})
            fut2 = qbot.send({"msg_type": "text", "content": {"text": "b"}})
            r1 = await fut1
            r2 = await fut2
        assert 200 == r1.status_code
        assert 200 == r2.status_code
        assert 2 == mock_post.call_count

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient.post", new_callable=AsyncMock)
    async def test_mixed_send_and_asend(self, mock_post: AsyncMock) -> None:
        mock_post.return_value = _ok_response()
        sync_ops = [
            lambda q: q.send_text("s1"),
            lambda q: q.send_post({"en_us": {}}),
            lambda q: q.send_share_chat("oc_x"),
            lambda q: q.send_image("img_k"),
            lambda q: q.send_interactive({"schema": "2.0"}),
        ]
        async_ops = [
            lambda q: q.asend_text("a1"),
            lambda q: q.asend_post({"en_us": {}}),
            lambda q: q.asend_share_chat("oc_y"),
            lambda q: q.asend_image("img_j"),
            lambda q: q.asend_interactive({"schema": "2.0"}),
        ]
        ops = [(False, op) for op in sync_ops] + [(True, op) for op in async_ops]
        random.shuffle(ops)
        async with _qbot_ctx(QBot(_URL)) as qbot:
            futs = []
            for is_async, op in ops:
                if is_async:
                    futs.append(await op(qbot))
                else:
                    futs.append(op(qbot))
            results = [await f for f in futs]
        for r in results:
            assert 200 == r.status_code
        assert 10 == mock_post.call_count


class TestQBotSendHelpers:
    @pytest.mark.asyncio
    @patch("httpx.AsyncClient.post", new_callable=AsyncMock)
    async def test_send_text(self, mock_post: AsyncMock) -> None:
        mock_post.return_value = _ok_response()
        async with _qbot_ctx(QBot(_URL)) as qbot:
            resp = await qbot.send_text("hello")
        assert 200 == resp.status_code
        payload = mock_post.call_args[1]["json"]
        assert "text" == payload["msg_type"]

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient.post", new_callable=AsyncMock)
    async def test_send_post(self, mock_post: AsyncMock) -> None:
        mock_post.return_value = _ok_response()
        async with _qbot_ctx(QBot(_URL)) as qbot:
            resp = await qbot.send_post({"en_us": {}})
        assert 200 == resp.status_code
        payload = mock_post.call_args[1]["json"]
        assert "post" == payload["msg_type"]

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient.post", new_callable=AsyncMock)
    async def test_send_share_chat(self, mock_post: AsyncMock) -> None:
        mock_post.return_value = _ok_response()
        async with _qbot_ctx(QBot(_URL)) as qbot:
            resp = await qbot.send_share_chat("oc_xxx")
        assert 200 == resp.status_code
        payload = mock_post.call_args[1]["json"]
        assert "share_chat" == payload["msg_type"]

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient.post", new_callable=AsyncMock)
    async def test_send_image(self, mock_post: AsyncMock) -> None:
        mock_post.return_value = _ok_response()
        async with _qbot_ctx(QBot(_URL)) as qbot:
            resp = await qbot.send_image("img_xxx")
        assert 200 == resp.status_code
        payload = mock_post.call_args[1]["json"]
        assert "image" == payload["msg_type"]

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient.post", new_callable=AsyncMock)
    async def test_send_interactive(self, mock_post: AsyncMock) -> None:
        mock_post.return_value = _ok_response()
        card = {"schema": "2.0"}
        async with _qbot_ctx(QBot(_URL)) as qbot:
            resp = await qbot.send_interactive(card)
        assert 200 == resp.status_code
        payload = mock_post.call_args[1]["json"]
        assert "interactive" == payload["msg_type"]

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient.post", new_callable=AsyncMock)
    async def test_asend_text(self, mock_post: AsyncMock) -> None:
        mock_post.return_value = _ok_response()
        async with _qbot_ctx(QBot(_URL)) as qbot:
            fut = await qbot.asend_text("hello")
            resp = await fut
        assert 200 == resp.status_code

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient.post", new_callable=AsyncMock)
    async def test_asend_post(self, mock_post: AsyncMock) -> None:
        mock_post.return_value = _ok_response()
        async with _qbot_ctx(QBot(_URL)) as qbot:
            fut = await qbot.asend_post({"en_us": {}})
            resp = await fut
        assert 200 == resp.status_code

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient.post", new_callable=AsyncMock)
    async def test_asend_share_chat(self, mock_post: AsyncMock) -> None:
        mock_post.return_value = _ok_response()
        async with _qbot_ctx(QBot(_URL)) as qbot:
            fut = await qbot.asend_share_chat("oc_xxx")
            resp = await fut
        assert 200 == resp.status_code

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient.post", new_callable=AsyncMock)
    async def test_asend_image(self, mock_post: AsyncMock) -> None:
        mock_post.return_value = _ok_response()
        async with _qbot_ctx(QBot(_URL)) as qbot:
            fut = await qbot.asend_image("img_xxx")
            resp = await fut
        assert 200 == resp.status_code

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient.post", new_callable=AsyncMock)
    async def test_asend_interactive(self, mock_post: AsyncMock) -> None:
        mock_post.return_value = _ok_response()
        card = {"schema": "2.0"}
        async with _qbot_ctx(QBot(_URL)) as qbot:
            fut = await qbot.asend_interactive(card)
            resp = await fut
        assert 200 == resp.status_code
