import asyncio
import logging
import ssl

import aiohttp
import inject
import uvloop

from aiohttp import web
from motor.motor_asyncio import AsyncIOMotorDatabase
from sklearn.ensemble import GradientBoostingClassifier

from .api_client import TelegramBot
from .entities import Config
from .logger import log, setup_logging
from .storage import init_database
from .utils import run_app, fit_model


@inject.params(bot=TelegramBot)
async def on_update(request, bot=None):
    data = await request.json()
    await bot.on_update(data)
    return web.Response()


async def on_ping(request):
    data = await request.text()
    return web.Response(text='All OK')


def on_startup(app):
    connector = aiohttp.TCPConnector(limit=5, use_dns_cache=True, loop=app.loop)
    session = aiohttp.ClientSession(connector=connector, raise_for_status=True)
    bot = TelegramBot(app['config'].token, session)
    image_model = fit_model(app['config'].sample_df)

    def config_injections(binder):
        # injection bindings
        binder.bind(Config, app['config'])
        binder.bind(TelegramBot, bot)
        binder.bind(GradientBoostingClassifier, image_model)
        binder.bind_to_constructor(AsyncIOMotorDatabase, init_database)


    try:
        inject.configure(config_injections)
    except inject.InjectorException:
        log.error("Injector already configured", exc_info=True)

    setup_logging(log)

    app.loop.create_task(bot.set_hook())


def on_cleanup(app):
    pass


def create_ssl_context(config):
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    try:
        context.load_cert_chain(config.sslchain, config.sslprivkey)
    except ssl.SSLError:
        log.exception("Failed to load ssl certificates", exc_info=True)
        raise
    return context


def create_app(loop, config):
    app = web.Application(loop=loop, debug=True)
    app['config'] = Config.load_config(config)

    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)

    app.router.add_route('POST', '/updates/', on_update)
    app.router.add_route('GET', '/ping', on_ping)

    return app


def init(config):
    log.debug("Loglevel set to %s", logging.getLevelName(log.getEffectiveLevel()))
    asyncio.set_event_loop(None)
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    loop = uvloop.new_event_loop()
    asyncio.set_event_loop(loop)

    app = create_app(loop, config)
    ssl_context = create_ssl_context(app['config'])
    run_app(app, loop, ssl_context=ssl_context)


