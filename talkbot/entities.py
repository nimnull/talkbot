import re
from collections import namedtuple
import trafaret as t


class Config(namedtuple('BaseConfig', 'token, mongo')):
    __slots__ = ()
    mongo_uri_re = re.compile(
        r'^(?:mongodb)://'  # mongodb://
        r'(?:\S+(?::\S*)?@)?'  # user and password
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-_]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)

    default = {
        'token': 'randomtoken',
        'mongo': {
            'uri': 'mongodb://localhost',
            'db': 'talkbot'
        }
    }

    trafaret = t.Dict({
        'token': t.String,
        'mongo': t.Dict({
            'uri': t.String(regex=mongo_uri_re),
            'db': t.String
        })
    })

    @classmethod
    def load_config(cls, dict_object):
        default = cls.default.copy()
        default.update(dict_object)

        valid_conf = cls.trafaret.check(default)

        Mongo = namedtuple('BaseMongoConfig', 'uri, db')
        valid_conf['mongo'] = Mongo(**valid_conf['mongo'])
        return cls(**valid_conf)

    def to_dict(self):
        return self._asdict()
