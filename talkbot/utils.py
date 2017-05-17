import re

import aiohttp
import inject


url_regex = re.compile(
    r'^(?:http|ftp)s?://'  # http:// or https://
    r'(?:\S+(?::\S*)?@)?'  # user and password
    r'(?:(?:[A-Z0-9](?:[A-Z0-9-_]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # domain...
    r'localhost|'  # localhost...
    r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
    r'(?::\d+)?'  # optional port
    r'(?:/?|[/?]\S+)$', re.IGNORECASE)


def get_user_repr(user):
    return user.get('username', " ".join([user['first_name'], user.get('last_name')]))


@inject.params(connector=aiohttp.TCPConnector)
async def fetch_file(url, connector=None):
    async with aiohttp.ClientSession(connector=connector) as session:
        rv = await session.get(url)
    rv.raise_for_status()
    return await rv.content.read()

