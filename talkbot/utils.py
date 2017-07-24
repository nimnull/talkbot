import asyncio
import os
import re
import signal

import aiohttp
import imagehash
import inject
import pandas as pd

from PIL import Image, ImageOps
from aiohttp.log import access_logger
from sklearn.ensemble import GradientBoostingClassifier


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


RESHAPE = (512, 512)


HASH_SIZE = 16
ALG = (
    ('crop', 0, 0, True),  # original fitted to RESHAPE
    ('crop', 0, 0.1, True),  # vertical 10% crop fitted to RESHAPE
    ('crop', 0.1, 0, True),  # horizontal 10% crop fitted to RESHAPE
    ('crop', 0.1, 0.1, True),  # vertical and horizontal 10% crop fitted to RESHAPE

    ('crop', 0, 0, False),  # original resized to RESHAPE
    ('crop', 0, 0.1, False),  # vertical 10% crop resized to RESHAPE
    ('crop', 0.1, 0, False),  # horizontal 10% crop resized to RESHAPE
    ('crop', 0.1, 0.1, False),  # vertical and horizontal 10% crop resized to RESHAPE
)


def prepare_image(img, crop_width_perc=0, crop_height_perc=0, fit_image=True, grayscale=True):
    # convert to grayscale
    mode = 'L' if grayscale else 'RGB'
    result = img.convert(mode)

    # crop image
    image_size = result.size
    width_crop_size = int(image_size[0] * crop_width_perc / 2) if crop_width_perc > 0 else 0
    height_crop_size = int(image_size[1] * crop_height_perc / 2) if crop_height_perc > 0 else 0
    if width_crop_size or height_crop_size:
        result = result.crop(
            (
                width_crop_size,
                height_crop_size,
                image_size[0] - width_crop_size,
                image_size[1] - height_crop_size
            )
        )

    # resize to 512x512 pixels
    resize_option = Image.ANTIALIAS
    if fit_image:
        return ImageOps.fit(result, RESHAPE, resize_option)

    return result.resize(RESHAPE, resize_option)


def calc_scores(source_image):
    scores = []
    for item in ALG:
        if item[0] == 'crop':
            v, h, fit_image = item[1:]
            name = '%s_%s_%s_%s' % item
            var_img = prepare_image(
                source_image,
                crop_width_perc=v,
                crop_height_perc=h,
                fit_image=fit_image
            )

            # val = imagehash.phash(var_img, hash_size=HASH_SIZE, highfreq_factor=HASH_SIZE)
            val = imagehash.whash(var_img, hash_size=HASH_SIZE)
            scores.append((name, val))
    return scores


def get_diff_vector(score1, score2):
    result_vec = {}
    for key, img_hash in score1.items():
        result_vec[key] = img_hash - score2[key]
    return result_vec


def fit_model(training_sample):
    df = pd.read_csv(training_sample)
    # convert values to bool
    df['d'] = df['d'].astype('bool')
    l_model = GradientBoostingClassifier()
    l_model = l_model.fit(
        df[df.columns.difference(['d'])],
        df['d']
    )
    return l_model
