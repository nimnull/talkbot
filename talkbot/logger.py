import logging
import sys

import inject

from .entities import Config

log = logging.getLogger('talkbot')
log.addHandler(logging.StreamHandler(sys.stdout))


levels = {
    'CRITICAL': logging.CRITICAL,
    'ERROR': logging.ERROR,
    'WARNING': logging.WARNING,
    'INFO': logging.INFO,
    'DEBUG': logging.DEBUG,
    'NOTSET': logging.NOTSET
}


@inject.param('config', Config)
def setup_logging(log, config=None):
    log.setLevel(logging.DEBUG)
