import asyncio as aio
import logging
import time
from types import TracebackType
from typing import Any, NoReturn, Self, Type

import atask
import httpx

from .cards import error_card_factory
from .signer import Signer

__all__ = [
    "Bot",
    "ABot",
    "QBot",
]


_logger = logging.getLogger(__name__)
_logger.addHandler(logging.NullHandler())


class Bot:
    def __init__(
        self,
        url: str,
        *,
        secret: str | None = None,
        delay: float = 1.0,
        max_tries: int = 3,
    ) -> None:
        self._url = url
        self._signer = Signer(secret) if secret else None
        self._delay = max(0.0, delay)
        self._max_tries = max(1, max_tries)
        self._client = httpx.Client()

    def __enter__(
        self,
    ) -> Self:
        self.start()
        return self

    def __exit__(
        self,
        exc_type: Type[BaseException] | None,
        exc_value: BaseException | None,
        exc_traceback: TracebackType | None,
    ) -> None:
        self.stop(exc_type, exc_value, exc_traceback)

    @property
    def closed(
        self,
    ) -> bool:
        return self._client.is_closed

    def start(
        self,
    ) -> None:
        self._client.__enter__()

    def stop(
        self,
        exc_type: Type[BaseException] | None = None,
        exc_value: BaseException | None = None,
        exc_traceback: TracebackType | None = None,
    ) -> None:
        self._client.__exit__(exc_type, exc_value, exc_traceback)

    def send(
        self,
        payload: dict,
    ) -> httpx.Response:
        for i in range(self._max_tries):
            if 0 < i:
                time.sleep(self._delay)
            if self._signer:
                self._signer.sign(payload)
            resp = self._client.post(self._url, json=payload)
            status = resp.status_code
            reason = resp.reason_phrase
            headers = resp.headers
            text = resp.text
            if resp.is_error:
                _logger.warning(f"{status} {reason} {text}")
                continue
            data = resp.json()
            if not (isinstance(data, dict) and 0 == data.get("code")):
                _logger.warning(f"{status} {reason} {text}")
                continue
            _logger.info(f"{status} {reason} {text}")
            break
        else:
            message = f"{status} {reason} {text}\n{headers}"
            _logger.error(message)
            error_card = error_card_factory()
            error_card["body"]["elements"][1]["text"]["content"] = message
            payload = {"msg_type": "interactive", "card": error_card}
            if self._signer:
                self._signer.sign(payload)
            _resp = self._client.post(self._url, json=payload)
        return resp

    def send_text(
        self,
        text: str,
    ) -> httpx.Response:
        payload = {
            "msg_type": "text",
            "content": {"text": text},
        }
        return self.send(payload)

    def send_post(
        self,
        post: dict,
    ) -> httpx.Response:
        payload = {
            "msg_type": "post",
            "content": {"post": post},
        }
        return self.send(payload)

    def send_share_chat(
        self,
        share_chat_id: str,
    ) -> httpx.Response:
        payload = {
            "msg_type": "share_chat",
            "content": {"share_chat_id": share_chat_id},
        }
        return self.send(payload)

    def send_image(
        self,
        image_key: str,
    ) -> httpx.Response:
        payload = {
            "msg_type": "image",
            "content": {"image_key": image_key},
        }
        return self.send(payload)

    def send_interactive(
        self,
        card: dict,
    ) -> httpx.Response:
        payload = {
            "msg_type": "interactive",
            "card": card,
        }
        return self.send(payload)


class ABot:
    def __init__(
        self,
        url: str,
        *,
        secret: str | None = None,
        delay: float = 1.0,
        max_tries: int = 3,
    ) -> None:
        self._url = url
        self._signer = Signer(secret) if secret else None
        self._delay = max(0.0, delay)
        self._max_tries = max(1, max_tries)
        self._aclient = httpx.AsyncClient()

    async def __aenter__(
        self,
    ) -> Self:
        await self.astart()
        return self

    async def __aexit__(
        self,
        exc_type: Type[BaseException] | None,
        exc_value: BaseException | None,
        exc_traceback: TracebackType | None,
    ) -> None:
        await self.astop(exc_type, exc_value, exc_traceback)

    @property
    def closed(
        self,
    ) -> bool:
        return self._aclient.is_closed

    async def astart(
        self,
    ) -> None:
        await self._aclient.__aenter__()

    async def astop(
        self,
        exc_type: Type[BaseException] | None = None,
        exc_value: BaseException | None = None,
        exc_traceback: TracebackType | None = None,
    ) -> None:
        await self._aclient.__aexit__(exc_type, exc_value, exc_traceback)

    async def asend(
        self,
        payload: dict,
    ) -> httpx.Response:
        for i in range(self._max_tries):
            if 0 < i:
                await aio.sleep(self._delay)
            if self._signer:
                self._signer.sign(payload)
            resp = await self._aclient.post(self._url, json=payload)
            status = resp.status_code
            reason = resp.reason_phrase
            headers = resp.headers
            text = resp.text
            if resp.is_error:
                _logger.warning(f"{status} {reason} {text}")
                continue
            data = resp.json()
            if not (isinstance(data, dict) and 0 == data.get("code")):
                _logger.warning(f"{status} {reason} {text}")
                continue
            _logger.info(f"{status} {reason} {text}")
            break
        else:
            message = f"{status} {reason} {text}\n{headers}"
            _logger.error(message)
            error_card = error_card_factory()
            error_card["body"]["elements"][1]["text"]["content"] = message
            payload = {"msg_type": "interactive", "card": error_card}
            if self._signer:
                self._signer.sign(payload)
            _resp = await self._aclient.post(self._url, json=payload)
        return resp

    async def asend_text(
        self,
        text: str,
    ) -> httpx.Response:
        payload = {
            "msg_type": "text",
            "content": {"text": text},
        }
        return await self.asend(payload)

    async def asend_post(
        self,
        post: dict,
    ) -> httpx.Response:
        payload = {
            "msg_type": "post",
            "content": {"post": post},
        }
        return await self.asend(payload)

    async def asend_share_chat(
        self,
        share_chat_id: str,
    ) -> httpx.Response:
        payload = {
            "msg_type": "share_chat",
            "content": {"share_chat_id": share_chat_id},
        }
        return await self.asend(payload)

    async def asend_image(
        self,
        image_key: str,
    ) -> httpx.Response:
        payload = {
            "msg_type": "image",
            "content": {"image_key": image_key},
        }
        return await self.asend(payload)

    async def asend_interactive(
        self,
        card: dict,
    ) -> httpx.Response:
        payload = {
            "msg_type": "interactive",
            "card": card,
        }
        return await self.asend(payload)


class QBot(atask.AsyncTask[NoReturn]):
    def __init__(
        self,
        url: str,
        *,
        secret: str | None = None,
        delay: float = 1.0,
        max_tries: int = 3,
    ) -> None:
        super().__init__()
        self._url = url
        self._signer = Signer(secret) if secret else None
        self._delay = max(0.0, delay)
        self._max_tries = max(1, max_tries)
        self._aclient = httpx.AsyncClient()
        self._aque = aio.Queue()

    @property
    def closed(
        self,
    ) -> bool:
        return self._aclient.is_closed

    async def astart(
        self,
    ) -> None:
        _logger.info(f"{self} starting")
        if self.started:
            _logger.info(f"{self} has started")
            return
        await self._aclient.__aenter__()
        await super().astart()
        _logger.info(f"{self} started")

    async def acancel(
        self,
        msg: Any | None = None,
    ) -> None:
        _logger.info(f"{self} canceling")
        if not self.started:
            _logger.info(f"{self} has canceled")
            return
        await self._aque.join()
        await super().acancel(msg)
        _logger.info(f"{self} canceled")

    async def astop(
        self,
        exc_type: Type[BaseException] | None = None,
        exc_value: BaseException | None = None,
        exc_traceback: TracebackType | None = None,
    ) -> None:
        _logger.info(f"{self} stopping")
        if not self.started:
            _logger.info(f"{self} has stopped")
            return
        await super().astop(exc_type, exc_value, exc_traceback)
        await self._aclient.__aexit__(exc_type, exc_value, exc_traceback)
        _logger.info(f"{self} stopped")

    async def _atask(
        self,
    ) -> NoReturn:
        while True:
            payload, fut = await self._aque.get()
            for i in range(self._max_tries):
                if 0 < i:
                    await aio.sleep(self._delay)
                if self._signer:
                    self._signer.sign(payload)
                resp = await self._aclient.post(self._url, json=payload)
                status = resp.status_code
                reason = resp.reason_phrase
                headers = resp.headers
                text = resp.text
                if resp.is_error:
                    _logger.warning(f"{status} {reason} {text}")
                    continue
                data = resp.json()
                if not (isinstance(data, dict) and 0 == data.get("code")):
                    _logger.warning(f"{status} {reason} {text}")
                    continue
                _logger.info(f"{status} {reason} {text}")
                break
            else:
                message = f"{status} {reason} {text}\n{headers}"
                _logger.error(message)
                error_card = error_card_factory()
                error_card["body"]["elements"][1]["text"]["content"] = message
                payload = {"msg_type": "interactive", "card": error_card}
                if self._signer:
                    self._signer.sign(payload)
                _resp = await self._aclient.post(self._url, json=payload)
            fut.set_result(resp)
            self._aque.task_done()

    def send(
        self,
        payload: dict,
    ) -> aio.Future[httpx.Response]:
        fut = aio.Future()
        self._aque.put_nowait((payload, fut))
        return fut

    def send_text(
        self,
        text: str,
    ) -> aio.Future[httpx.Response]:
        payload = {
            "msg_type": "text",
            "content": {"text": text},
        }
        return self.send(payload)

    def send_post(
        self,
        post: dict,
    ) -> aio.Future[httpx.Response]:
        payload = {
            "msg_type": "post",
            "content": {"post": post},
        }
        return self.send(payload)

    def send_share_chat(
        self,
        share_chat_id: str,
    ) -> aio.Future[httpx.Response]:
        payload = {
            "msg_type": "share_chat",
            "content": {"share_chat_id": share_chat_id},
        }
        return self.send(payload)

    def send_image(
        self,
        image_key: str,
    ) -> aio.Future[httpx.Response]:
        payload = {
            "msg_type": "image",
            "content": {"image_key": image_key},
        }
        return self.send(payload)

    def send_interactive(
        self,
        card: dict,
    ) -> aio.Future[httpx.Response]:
        payload = {
            "msg_type": "interactive",
            "card": card,
        }
        return self.send(payload)

    async def asend(
        self,
        payload: dict,
    ) -> aio.Future[httpx.Response]:
        fut = aio.Future()
        await self._aque.put((payload, fut))
        return fut

    async def asend_text(
        self,
        text: str,
    ) -> aio.Future[httpx.Response]:
        payload = {
            "msg_type": "text",
            "content": {"text": text},
        }
        return await self.asend(payload)

    async def asend_post(
        self,
        post: dict,
    ) -> aio.Future[httpx.Response]:
        payload = {
            "msg_type": "post",
            "content": {"post": post},
        }
        return await self.asend(payload)

    async def asend_share_chat(
        self,
        share_chat_id: str,
    ) -> aio.Future[httpx.Response]:
        payload = {
            "msg_type": "share_chat",
            "content": {"share_chat_id": share_chat_id},
        }
        return await self.asend(payload)

    async def asend_image(
        self,
        image_key: str,
    ) -> aio.Future[httpx.Response]:
        payload = {
            "msg_type": "image",
            "content": {"image_key": image_key},
        }
        return await self.asend(payload)

    async def asend_interactive(
        self,
        card: dict,
    ) -> aio.Future[httpx.Response]:
        payload = {
            "msg_type": "interactive",
            "card": card,
        }
        return await self.asend(payload)
