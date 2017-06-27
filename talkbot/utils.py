import asyncio
import os
import re
import signal

import aiohttp
import inject
from aiohttp.log import access_logger

url_regex = re.compile(
    r'^(?:http|ftp)s?://'  # http:// or https://
    r'(?:\S+(?::\S*)?@)?'  # user and password
    r'(?:(?:[A-Z0-9](?:[A-Z0-9-_]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # domain...
    r'localhost|'  # localhost...
    r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
    r'(?::\d+)?'  # optional port
    r'(?:/?|[/?]\S+)$', re.IGNORECASE)


def get_user_repr(user):
    return user.get('username', " ".join([user['first_name'], user.get('last_name','')]))


@inject.params(connector=aiohttp.TCPConnector)
async def fetch_file(url, connector=None):
    async with aiohttp.ClientSession(connector=connector) as session:
        rv = await session.get(url)
    rv.raise_for_status()
    return await rv.content.read()


def run_app(app, loop, shutdown_timeout=60.0, ssl_context=None, backlog=128):
    pid = os.getppid()

    def _sigint(signum, frame):
        os.kill(pid, signal.SIGINT)

    # send SIGINT instead of SIGTERM to unify handling
    signal.signal(signal.SIGTERM, _sigint)

    loop.run_until_complete(app.startup())

    hosts = ('0.0.0.0',)
    port = 443
    server_creations = []
    make_handler_kwargs = dict()
    # if access_log_format is not None:
    #     make_handler_kwargs['access_log_format'] = access_log_format
    handler = app.make_handler(loop=loop, access_log=access_logger,
                               **make_handler_kwargs)

    # Multiple hosts bound to same server is available in most loop
    # implementations, but only send multiple if we have multiple.
    host_binding = hosts[0] if len(hosts) == 1 else hosts
    server_creations.append(
        loop.create_server(
            handler, host_binding, port, ssl=ssl_context, backlog=backlog
        )
    )

    servers = loop.run_until_complete(
        asyncio.gather(*server_creations, loop=loop)
    )

    try:
        loop.run_forever()
    except KeyboardInterrupt:  # pragma: no cover
        pass
    finally:
        server_closures = []
        for srv in servers:
            srv.close()
            server_closures.append(srv.wait_closed())
        loop.run_until_complete(asyncio.gather(*server_closures, loop=loop))
        loop.run_until_complete(app.shutdown())
        loop.run_until_complete(handler.shutdown(shutdown_timeout))
        loop.run_until_complete(app.cleanup())

        loop.close()


def find_ngrams(input_list, n):
    return zip(*[input_list[i:] for i in range(n)])
