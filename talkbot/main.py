import asyncio

from http import HTTPStatus
from urllib.parse import urljoin

import aiohttp
import datetime

import inject
from motor.motor_asyncio import AsyncIOMotorDatabase

from talkbot.entities import Config
from talkbot.logger import log
from talkbot.reactions import process_chat_left, process_chat_joined, process_entities
from talkbot.storage import init_database

BOT_TOKEN = "<your token here>"


class TelegramBot:
    BASE_URI = "https://api.telegram.org/bot{0.token}/"
    known_commands = {

    }

    def __init__(self, session, token):
        self.session = session
        self.update_offset = 0
        self.username = "ZamzaBot"
        self.token = token

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

    async def reply(self, chat, sender=None):
        name = sender['first_name']
        payload = {
            'chat_id': chat['id'],
            'text': 'confirmed at {} from {}'.format(datetime.datetime.now().isoformat('T'), name)
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
        message_text = message.get('text')
        left_chat_member = message.get('left_chat_member')
        new_chat_member = message.get('new_chat_member')

        entities = message.get('entities', [])
        command_ents = filter(lambda e: e['type'] == 'bot_command', entities)
        for marker in command_ents:
            cmd = message_text[marker['offset']:marker['length']].strip('/')
            await self.on_command(cmd)


        log.info("Message: %s", message_text)

        if message_text:
            await self.reply(message['chat'], message.get('from'))
        if left_chat_member:
            process_chat_left(self, left_chat_member, message['chat'])
        if new_chat_member:
            process_chat_joined(self, new_chat_member, message['chat'])

        [process_entities(self, entry, message) for entry in entities]

    async def on_command(self, cmd):
        pass


async def main(loop, connector):
    session = aiohttp.ClientSession(connector=connector, loop=loop, conn_timeout=5)
    token = inject.instance(Config).token
    bot = TelegramBot(session, token)

    while True:
        await bot.get_updates()
        await asyncio.sleep(3)


def init(config):

    def config_injections(binder):
        binder.bind(Config, Config.load_config(config))
        binder.bind_to_provider(AsyncIOMotorDatabase, init_database)

    inject.configure(config_injections)

    loop = asyncio.get_event_loop()
    conn = aiohttp.TCPConnector(limit=5, use_dns_cache=True, loop=loop)
    try:
        loop.run_until_complete(main(loop, conn))
    except KeyboardInterrupt:
        log.info('Interrupted by user')
    finally:
        conn.close()
        loop.close()

