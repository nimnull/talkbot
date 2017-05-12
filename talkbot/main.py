import asyncio

from http import HTTPStatus
from urllib.parse import urljoin

import aiohttp
import datetime

from talkbot.logger import log
from talkbot.reactions import process_chat_left, process_chat_joined, process_entities

BOT_TOKEN = "<your token here>"


class TelegramBot:
    BASE_URI = "https://api.telegram.org/bot{0.token}/"

    def __init__(self, session, token):
        self.session = session
        self.token = token
        self.update_offset = 0
        self.username = "ZamzaBot"

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
        payload = {
            'chat_id': chat['id'],
            'text': '@{} confirmed at {}'.format(sender['username'], datetime.datetime.now().isoformat('T'))
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
        log.info("Message: %s", message_text)

        if message_text:
            await self.reply(message['chat'], message.get('from'))
        if left_chat_member:
            process_chat_left(self, left_chat_member, message['chat'])
        if new_chat_member:
            process_chat_joined(self, new_chat_member, message['chat'])

        [process_entities(self, entry, message) for entry in entities]


async def main(loop, connector):
    session = aiohttp.ClientSession(connector=connector, loop=loop, conn_timeout=5)
    bot = TelegramBot(session, BOT_TOKEN)

    while True:
        await bot.get_updates()
        await asyncio.sleep(3)

if __name__ =='__main__':
    loop = asyncio.get_event_loop()
    try:
        conn = aiohttp.TCPConnector(limit=5, use_dns_cache=True, loop=loop)
        loop.run_until_complete(main(loop, conn))
    except KeyboardInterrupt:
        log.info('Interrupted by user')
    finally:
        loop.close()
