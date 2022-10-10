import asyncio
import logging


class Timer:
    def __init__(self, callback, timeout):
        logging.info("Created a schedule interval as " + str(timeout) + " seconds.")
        loop = asyncio.get_event_loop()
        self.callback = callback
        self.timeout = timeout
        self.task = loop.create_task(self.wait())

    def __str__(self):
        return "timeout: " + str(self.timeout)

    async def wait(self):
        await asyncio.sleep(self.timeout)
        logging.info("Successfully executed a timer schedule.")
        await self.callback

    def stop(self):
        try:
            self.task.cancel()
            self.callback.close()
        except asyncio.CancelledError:
            pass
