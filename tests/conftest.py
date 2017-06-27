import uuid

import docker
import pytest
from aiohttp.test_utils import unused_port

from talkbot.main import create_app


@pytest.fixture(scope='session')
def session_id():
    """Unique session identifier, random string."""
    return str(uuid.uuid4())


@pytest.fixture(scope='session')
def docker_client():
    return docker.from_env(version='auto')


@pytest.yield_fixture(scope='session')
def mongo(docker_client, session_id):
    mongo_image = "mongo:3.4"
    port_bind = unused_port()
    img = docker_client.images.pull(mongo_image)

    container = docker_client.containers.run(mongo_image,
                                             detach=True,
                                             name="talkbot-test-mongo-%s" % session_id,
                                             ports={
                                                 '27017': port_bind
                                             })
    yield port_bind

    container.remove(force=True)


@pytest.fixture
def app_client(loop, test_client, mongo):
    config = {
        'mongo': {
            'uri': 'mongodb://localhost:%d' % mongo,
            'db': 'talkbot'
        },
        'sslchain': "/dev/random",
        'sslprivkey': "/dev/random"
    }

    app = create_app(loop, config)
    return loop.run_until_complete(test_client(app))
