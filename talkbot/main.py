import asyncio
import logging
import ssl

from ssl import SSLContext, SSLError
from urllib.parse import urljoin

import aiohttp
import datetime
import inject
import uvloop

from aiohttp import web
from motor.motor_asyncio import AsyncIOMotorDatabase

from .entities import Config
from .logger import log, setup_logging
from .reactor import MessageReactor
from .storage import init_database
from .utils import run_app


class TelegramBot:
    BASE_URI = "https://api.telegram.org/bot{0.token}/"

    def __init__(self, token, session):
        self.update_offset = 0
        self.username = "ZamzaBot"
        self.token = token
        self.session = session

    def _get_uri(self, endpoint):
        return urljoin(self.BASE_URI.format(self), endpoint)

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
            'text': '{} confirmed at {}.'.format(name, datetime.datetime.now().isoformat('T'))
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

    async def on_update(self, data):
        last_update = max(map(lambda r: r['update_id'], data))
        log.info("Got an update: %s", data)
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

        if not reactor.response:
            return

        payload = {
            'chat_id': message['chat']['id'],
        }
        payload.update(reactor.response)

        if 'photo' in payload:
            await self.send_photo(payload)
        else:
            await self.send_message(payload)

    async def set_hook(self):
        payload = {
            'url': "https://talkbot1.mediasapiens.org/updates/"
        }
        resp = await self.session.post(self._get_uri('setWebhook'), data=payload)
        await self._raise_for_response(resp)


@inject.params(bot=TelegramBot)
async def on_update(request, bot=None):
    data = await request.json()
    await bot.on_update(data)
    return web.Response()


async def test_get(request):
    data = await request.text()
    return web.Response(text='All OK')


def on_startup(app):
    connector = aiohttp.TCPConnector(limit=5, use_dns_cache=True, loop=app.loop)
    session = aiohttp.ClientSession(connector=connector, raise_for_status=True)
    bot = TelegramBot(app['config'].token, session)

    def config_injections(binder):
        # injection bindings
        binder.bind(TelegramBot, bot)
        binder.bind(Config, app['config'])
        binder.bind_to_constructor(AsyncIOMotorDatabase, init_database)

    inject.configure(config_injections)
    setup_logging(log)

    # app.loop.create_task(bot.set_hook())


def on_cleanup(app):
    pass


def create_ssl_context(config):
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    try:
        context.load_cert_chain(config.sslchain, config.sslprivkey)
    except SSLError:
        log.exception("Failed to load ssl certificates", exc_info=True)
        raise
    return context


def init(config):
    log.debug("Loglevel set to %s", logging.getLevelName(log.getEffectiveLevel()))
    asyncio.set_event_loop(None)
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    loop = uvloop.new_event_loop()
    asyncio.set_event_loop(loop)

    app = web.Application(loop=loop, debug=True)
    app['config'] = Config.load_config(config)
    ssl_context = create_ssl_context(app['config'])

    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)

    app.router.add_route('POST', '/updates/', on_update)
    app.router.add_route('GET', '/', test_get)


    run_app(app, loop, ssl_context=ssl_context)


