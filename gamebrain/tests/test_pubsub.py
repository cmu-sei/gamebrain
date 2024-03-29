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

import pytest
import pytest_asyncio

from gamebrain.pubsub import Subscriber, PubSub


@pytest.fixture(scope="module")
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
