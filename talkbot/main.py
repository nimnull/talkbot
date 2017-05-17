import asyncio
import logging
import os
import signal

from http import HTTPStatus
from urllib.parse import urljoin

import aiohttp
import datetime
import inject
import uvloop

from motor.motor_asyncio import AsyncIOMotorDatabase

from talkbot.entities import Config
from talkbot.logger import log, setup_logging
from talkbot.reactor import MessageReactor
from talkbot.storage import init_database


class TelegramBot:
    BASE_URI = "https://api.telegram.org/bot{0.token}/"

    def __init__(self, token):
        self.update_offset = 0
        self.username = "ZamzaBot"
        self.token = token
        self.connector = inject.instance(aiohttp.TCPConnector)
        self.session = aiohttp.ClientSession(connector=self.connector)

    def _get_uri(self, endpoint):
        return urljoin(self.BASE_URI.format(self), endpoint)

    async def _raise_for_status(self, resp):
        if resp.status == HTTPStatus.OK:
            rv = await resp.json()
            resp.release()
            return rv
        else:
            rv = await resp.text()
            resp.close()
            raise ValueError("Status: %s\n%s", resp.status, rv)

    def _raise_for_response(self, response):
        if response['ok']:
            return response['result']
        else:
            msg = "{error_code} | {description} ".format(**response)
            log.error(msg)

    async def pong(self, chat, sender=None):
        name = sender['first_name']
        payload = {
            'chat_id': chat['id'],
            'text': '{} confirmed at {}.'.format(name, datetime.datetime.now().isoformat('T'))
        }
        return await self.send_message(payload)

    async def send_message(self, payload):
        payload['disable_notification'] = True

        resp = await self.session.post(self._get_uri('sendMessage'), data=payload)
        r_data = await self._raise_for_status(resp)

        try:
            result = self._raise_for_response(r_data)
            log.info("sent: %s", result)
        except ValueError as ex:
                log.error("Message send failed %s", ex)

    async def get_updates(self):
        uri = self._get_uri('getUpdates')
        params = self.update_offset and {'offset': self.update_offset} or None

        resp = await self.session.get(uri, params=params)
        r_data = await self._raise_for_status(resp)

        try:
            result = self._raise_for_response(r_data)
            if len(result):
                await self.on_update(result)
        except ValueError as ex:
            log.error("Failed to retrieve updates: %s", ex)

    async def on_update(self, data):
        last_update = max(map(lambda r: r['update_id'], data))
        log.info("Got update: %s", data)
        for update in data:
            message = update.get('message')
            if message:
                log.info("message: %s", message)
                await self.on_message(message)

        self.update_offset = last_update + 1

    async def on_message(self, message):
        reactor = MessageReactor(message)

        async for rv in reactor:
            log.debug("RV '%s'" % rv)

        if reactor.response is None:
            return

        payload = {
            'chat_id': message['chat']['id'],
        }
        payload.update(reactor.response)
        await self.send_message(payload)


@inject.params(config=Config)
async def main(config=None):
    bot = TelegramBot(config.token)

    while True:
        await bot.get_updates()
        await asyncio.sleep(3)


def init(config):
    asyncio.set_event_loop(None)

    pid = os.getppid()

    def _sigint(signum, frame):
        os.kill(pid, signal.SIGINT)

    # send SIGINT instead of SIGTERM to unify handling
    signal.signal(signal.SIGTERM, _sigint)

    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    loop = uvloop.new_event_loop()
    asyncio.set_event_loop(loop)

    connector = aiohttp.TCPConnector(limit=5, use_dns_cache=True, loop=loop)
    # session = aiohttp.ClientSession(connector=connector, loop=loop, conn_timeout=5)

    def config_injections(binder):
        binder.bind(aiohttp.TCPConnector, connector)
        binder.bind(Config, Config.load_config(config))
        binder.bind_to_constructor(AsyncIOMotorDatabase, init_database)

    inject.configure(config_injections)

    setup_logging(log)
    log.debug("Loglevel set to %s", logging.getLevelName(log.getEffectiveLevel()))

    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        log.info('Interrupted by user')
    finally:
        connector.close()
        loop.close()

