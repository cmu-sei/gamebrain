# Copyright 2023 Carnegie Mellon University. All Rights Reserved.
# Released under a MIT (SEI)-style license. See LICENSE.md in the project root for license information.

import asyncio

import pytest
import pytest_asyncio

from gamebrain.pubsub import Subscriber, PubSub


@pytest.fixture(scope='module')
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def fixture_init_pubsub():
    yield await PubSub.init({})
    PubSub._pubsub_task.cancel("Test cleanup")


@pytest.mark.asyncio
async def test_publish_no_subs(event_loop, fixture_init_pubsub):
    await PubSub.publish("test message")


@pytest.mark.asyncio
async def test_publish_late_sub(event_loop, fixture_init_pubsub):
    subscriber = Subscriber()

    await PubSub.publish("test message")

    await asyncio.sleep(0.1)

    await subscriber.subscribe()

    result = await subscriber.get(0.5)
    assert result is None


@pytest.mark.asyncio
async def test_publish_after_sub(event_loop, fixture_init_pubsub):
    subscriber = Subscriber()
    await subscriber.subscribe()

    await asyncio.sleep(0.1)

    message = "test message"

    await PubSub.publish(message)

    result = await subscriber.get(0.5)
    assert result == message


@pytest.mark.asyncio
async def test_multiple_subscribers(event_loop, fixture_init_pubsub):
    subscriber_1 = Subscriber()
    subscriber_2 = Subscriber()
    await subscriber_1.subscribe()
    await subscriber_2.subscribe()

    await asyncio.sleep(0.1)

    message = "test message"

    await PubSub.publish(message)

    result_1 = await subscriber_1.get(0.5)
    result_2 = await subscriber_2.get(0.5)

    assert message == result_1 == result_2


@pytest.mark.asyncio
async def test_multiple_subscribers_interleaved(event_loop, fixture_init_pubsub):
    subscriber_1 = Subscriber()
    subscriber_2 = Subscriber()
    await subscriber_1.subscribe()

    await asyncio.sleep(0.1)

    message_1 = "test message 1"

    await PubSub.publish(message_1)

    result_1_1 = await subscriber_1.get(0.5)

    assert message_1 == result_1_1

    message_2 = "test message 2"

    await subscriber_2.subscribe()
    await asyncio.sleep(0.1)

    await PubSub.publish(message_2)

    result_2_1 = await subscriber_1.get(0.5)
    result_2_2 = await subscriber_2.get(0.5)

    assert message_2 == result_2_1
    assert message_2 == result_2_2
