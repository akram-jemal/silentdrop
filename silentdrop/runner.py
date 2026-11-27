"""Run a bounded set of public service checks on the current network."""

import asyncio
from collections.abc import Callable, Sequence

from .catalog import Service
from .playback import check_playback
from .results import Result, Verdict
from .webcheck import check_page


async def check_services(
    services: Sequence[Service],
    *,
    on_result: Callable[[Result], None] | None = None,
) -> tuple[Result, ...]:
    """Run up to six page checks and one browser check at a time."""
    page_slots = asyncio.Semaphore(6)
    browser_slot = asyncio.Semaphore(1)

    async def check(service: Service) -> Result:
        async with page_slots:
            result = await check_page(service)

        if service.video_url and result.verdict is not Verdict.BLOCK_PAGE:
            async with browser_slot:
                playback = await check_playback(service)
            if playback.verdict is Verdict.PLAYED:
                result = playback
            else:
                summary = (
                    "Page loaded, playback unverified"
                    if result.verdict is Verdict.LOADED
                    else "Couldn't verify public access or playback"
                )
                result = Result(
                    service,
                    result.verdict,
                    summary,
                    (result.summary, *result.details, *playback.details),
                )

        if on_result is not None:
            on_result(result)
        return result

    tasks = [asyncio.create_task(check(service)) for service in services]
    try:
        return tuple(await asyncio.gather(*tasks))
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
