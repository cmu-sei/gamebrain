# Cyber Defenders Video Game

# Copyright 2023 Carnegie Mellon University.

# NO WARRANTY. THIS CARNEGIE MELLON UNIVERSITY AND SOFTWARE ENGINEERING
# INSTITUTE MATERIAL IS FURNISHED ON AN "AS-IS" BASIS. CARNEGIE MELLON
# UNIVERSITY MAKES NO WARRANTIES OF ANY KIND, EITHER EXPRESSED OR IMPLIED, AS
# TO ANY MATTER INCLUDING, BUT NOT LIMITED TO, WARRANTY OF FITNESS FOR PURPOSE
# OR MERCHANTABILITY, EXCLUSIVITY, OR RESULTS OBTAINED FROM USE OF THE
# MATERIAL. CARNEGIE MELLON UNIVERSITY DOES NOT MAKE ANY WARRANTY OF ANY KIND
# WITH RESPECT TO FREEDOM FROM PATENT, TRADEMARK, OR COPYRIGHT INFRINGEMENT.

# Released under a MIT (SEI)-style license, please see license.txt or contact
# permission@sei.cmu.edu for full terms.

# [DISTRIBUTION STATEMENT A] This material has been approved for public
# release and unlimited distribution.  Please see Copyright notice for
# non-US Government use and distribution.

# This Software includes and/or makes use of Third-Party Software each subject
# to its own license.

# DM23-0100

import asyncio


class Subscriber:
    _internal_queue: asyncio.Queue

    def __init__(self):
        self._internal_queue = asyncio.Queue()

    async def subscribe(self):
        await PubSub.register_subscriber(self)

    async def unsubscribe(self):
        await PubSub.unregister_subscriber(self)

    async def get(self, timeout: float | int = None) -> str | None:
        try:
            return await asyncio.wait_for(self._internal_queue.get(), timeout)
        except asyncio.TimeoutError:
            return None


class PubSub:
    _pubsub_task: asyncio.tasks.Task = None

    _pub_queue = asyncio.Queue()
    _subscribers: set[Subscriber] = set()
    _subscribers_lock = asyncio.Lock()

    _settings: "SettingsModel"

    @classmethod
    async def init(cls, _settings: "SettingsModel"):
        cls._settings = _settings

        cls._pubsub_task = asyncio.create_task(cls._pubsub())

    @classmethod
    async def _pubsub(cls):
        while True:
            message = await cls._pub_queue.get()

            async with cls._subscribers_lock:
                for sub in cls._subscribers:
                    await sub._internal_queue.put(message)

    @classmethod
    async def publish(cls, message: str):
        await cls._pub_queue.put(message)

    @classmethod
    async def register_subscriber(cls, subscriber: Subscriber):
        async with cls._subscribers_lock:
            cls._subscribers.add(subscriber)

    @classmethod
    async def unregister_subscriber(cls, subscriber: Subscriber):
        async with cls._subscribers_lock:
            cls._subscribers.remove(subscriber)
