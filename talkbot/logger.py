import logging
import sys

import inject

from .entities import Config

log = logging.getLogger('talkbot')
log.addHandler(logging.StreamHandler(sys.stdout))


@inject.param('config', Config)
def setup_logging(log, config=None):
    log.setLevel(logging.DEBUG)
