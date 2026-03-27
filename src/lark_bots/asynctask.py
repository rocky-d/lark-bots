import asyncio as aio
from contextvars import Context
from types import TracebackType
from typing import Any, Awaitable, Generator, Iterable, Self, Type

__all__ = [
    "AsyncTask",
    "AsyncTaskGroup",
]


class AsyncTask[T](Awaitable[T]):
    """
    Usage:

    >>> # Define a subclass of AsyncTask
    >>> class Example(AsyncTask[int]):
    ...     async def _run(self) -> int:
    ...         await aio.sleep(3)
    ...         return 2025
    ...
    >>> # Manually
    >>> x = Example()
    >>> await x.start()
    >>> await x.join()
    >>> result = x.result
    >>> await x.stop()
    >>> print(result)
    2025
    >>> # With async context manager
    >>> async with Example() as x:
    ...     print("Started")
    ...     result = await x
    ...     print("Result:", result)
    ...
    Started
    Result: 2025
    """

    def __init__(
        self,
        *,
        name: str | None = None,
        context: Context | None = None,
    ) -> None:
        self._name = name
        self._context = context
        self._fut = aio.Future()
        self._fut.set_result(None)
        self._started = False

    def __await__(
        self,
    ) -> Generator[Any, None, T]:
        yield from self.join().__await__()
        return self.result

    async def __aenter__(
        self,
    ) -> Self:
        await self.start()
        return self

    async def __aexit__(
        self,
        exc_type: Type[BaseException] | None,
        exc_value: BaseException | None,
        exc_traceback: TracebackType | None,
    ) -> None:
        await self.stop(exc_type, exc_value, exc_traceback)

    @property
    def name(
        self,
    ) -> str | None:
        return self._name

    @property
    def context(
        self,
    ) -> Context | None:
        return self._context

    @property
    def started(
        self,
    ) -> bool:
        return self._started

    @property
    def done(
        self,
    ) -> bool:
        return self._fut.done()

    @property
    def cancelled(
        self,
    ) -> bool:
        return self._fut.cancelled()

    @property
    def running(
        self,
    ) -> bool:
        return self.started and not self.done

    @property
    def result(
        self,
    ) -> T:
        return self._fut.result()

    @property
    def exception(
        self,
    ) -> BaseException | None:
        return self._fut.exception()

    async def _run(
        self,
    ) -> T:
        raise NotImplementedError

    async def start(
        self,
    ) -> None:
        if self.started:
            return
        self._started = True
        self._fut = aio.create_task(self._run(), name=self._name, context=self._context)

    async def join(
        self,
    ) -> None:
        if not self.started:
            return
        await self._fut

    async def cancel(
        self,
        msg: Any | None = None,
    ) -> None:
        if not self.started:
            return
        self._fut.cancel(msg=msg)
        try:
            await self._fut
        except aio.CancelledError:
            pass

    async def stop(
        self,
        exc_type: Type[BaseException] | None = None,
        exc_value: BaseException | None = None,
        exc_traceback: TracebackType | None = None,
    ) -> None:
        if not self.started:
            return
        if self.running:
            raise aio.InvalidStateError
        self._started = False


class AsyncTaskGroup[T](AsyncTask[list[T]]):
    def __init__(
        self,
        atasks: Iterable[AsyncTask[T]],
        *,
        name: str | None = None,
        context: Context | None = None,
    ) -> None:
        super().__init__(name=name, context=context)
        self._atasks = list(atasks)

    async def _run(
        self,
    ) -> list[T]:
        async with aio.TaskGroup() as tg:
            for atask in self._atasks:
                tg.create_task(atask.join())
        return [atask.result for atask in self._atasks]

    async def start(
        self,
    ) -> None:
        if self.started:
            return
        async with aio.TaskGroup() as tg:
            for atask in self._atasks:
                tg.create_task(atask.start())
        await super().start()

    async def stop(
        self,
        exc_type: Type[BaseException] | None = None,
        exc_value: BaseException | None = None,
        exc_traceback: TracebackType | None = None,
    ) -> None:
        if not self.started:
            return
        if self.running:
            raise aio.InvalidStateError
        await super().stop(exc_type, exc_value, exc_traceback)
        async with aio.TaskGroup() as tg:
            for atask in self._atasks:
                tg.create_task(atask.stop(exc_type, exc_value, exc_traceback))


if __name__ == "__main__":

    class Example(AsyncTask[int]):
        async def _run(
            self,
        ) -> int:
            await aio.sleep(3)
            return 2025

    async def main() -> None:
        async with Example() as x:
            print("Started")
            result = await x
            print("Result:", result)

        x = Example()
        await x.start()
        await x.join()
        result = x.result
        await x.stop()
        print(result)

    aio.run(main())
