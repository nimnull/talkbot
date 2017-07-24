import io
import time

from datetime import datetime
from http import HTTPStatus
from urllib.parse import urljoin

import aiohttp

from talkbot.reactor import MessageReactor
from .logger import log


class TelegramBot:
    BASE_URI = "https://api.telegram.org/bot{0.token}/"
    FILE_URI = "https://api.telegram.org/file/bot{0.token}/"

    def __init__(self, token, session):
        self.update_offset = 0
        self.username = "ZamzaBot"
        self.token = token
        self.session = session

    def _get_uri(self, endpoint):
        return urljoin(self.BASE_URI.format(self), endpoint)

    def _get_file_path(self, file_path):
        return urljoin(self.FILE_URI.format(self), file_path)

    async def _raise_for_response(self, response):
        r_data = await response.json()
        if r_data['ok']:
            return r_data['result']
        else:
            msg = "{error_code} | {description} ".format(**r_data)
            log.error(msg)

    async def pong(self, chat, sender=None):
        name = sender['first_name']
        payload = {
            'chat_id': chat['id'],
            'text': '{} confirmed at {}.'.format(name, datetime.now().isoformat('T'))
        }
        return await self.send_message(payload)

    async def send_message(self, payload):
        payload['disable_notification'] = True

        try:
            resp = await self.session.post(self._get_uri('sendMessage'), data=payload)
            result = await self._raise_for_response(resp)
            log.info("sent: %s", result)
        except aiohttp.ClientResponseError as ex:
            log.error("Message send failed %s", ex, exc_info=True)

    async def send_photo(self, payload):
        payload['disable_notification'] = True
        try:
            resp = await self.session.post(self._get_uri('sendPhoto'), data=payload)
            result = await self._raise_for_response(resp)
            log.info("sent: %s", result)
        except aiohttp.ClientResponseError as ex:
                log.error("Message send failed %s", ex, exc_info=True)

    async def get_file(self, file_id):
        try:
            resp = await self.session.get(self._get_uri('getFile'), params={'file_id': file_id})
            result = await self._raise_for_response(resp)
            log.info("File: %s", result)
        except aiohttp.ClientResponseError as ex:
            log.error("Failed to retreive file: %s", ex, exc_info=True)
            return None

        return result

    async def on_update(self, update):
        message = update.get('message') or update.get('channel_post')
        if message and (time.time() - message['date']) < 180:
            log.info("Got update: %s", update)
            await self.on_message(message)

    async def on_message(self, message):
        reactor = MessageReactor(message, self)

        async for rv in reactor:
            log.debug("RV '%s'" % rv)

        if not reactor.response:
            return

        payload = {
            'chat_id': message['chat']['id'],
        }
        payload.update(reactor.response)

        if 'photo' in payload:
            await self.send_photo(payload)
        elif 'text' in payload:
            await self.send_message(payload)

    async def set_hook(self):
        payload = {
            'url': "https://talkbot1.mediasapiens.org/updates/"
        }
        resp = await self.session.post(self._get_uri('setWebhook'), data=payload)
        await self._raise_for_response(resp)

    async def download_file(self, path):
        resp = await self.session.get(self._get_file_path(path))
        assert resp.status == HTTPStatus.OK, resp.status
        content = await resp.content.read()
        return io.BytesIO(content)
