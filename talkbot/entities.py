import re
from collections import namedtuple

import inject
import trafaret as t
from motor.motor_asyncio import AsyncIOMotorDatabase
from trafaret.contrib.object_id import MongoId


class Config(namedtuple('BaseConfig', 'token, mongo, loglevel')):
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
        },
        'loglevel': 'INFO'
    }

    trafaret = t.Dict({
        'token': t.String,
        'mongo': t.Dict({
            'uri': t.String(regex=mongo_uri_re),
            'db': t.String
        }),
        'loglevel': t.Enum('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
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


class User(namedtuple('BaseUser', 'id,ext_id,first_name,last_name,username')):

    trafaret = t.Dict({
        'id': t.Int,
        'first_name': t.String,
        'last_name': t.String,
        'username': t.String
    }).make_optional('username', 'last_name').ignore_extra('*')

    def to_dict(self):
        dict_repr = self._asdict()
        dict_repr['_id'] = self.id
        return dict_repr


class Reaction(namedtuple('BaseReaction', 'id,patterns,image_url,image_id,text,created_at,created_by')):
    collection = 'reactions'

    trafaret = t.Dict({
        'id': t.Or(t.String | MongoId(allow_blank=True)),
        'patterns': t.List(t.String, min_length=1),
        'image_url': t.URL(allow_blank=True),
        'image_id': t.String(allow_blank=True),
        'text': t.String(allow_blank=True),
        'created_at': t.Int,
        'created_by': User.trafaret
    }).make_optional('image_id', 'image_url', 'text')

    @classmethod
    def from_dict(cls, **kwargs):
        mutable = kwargs.copy()
        if '_id' in kwargs:
            mutable['id'] = mutable.pop('_id')
        checked = Reaction.trafaret.check(mutable)
        return cls(**checked)

    def to_dict(self):
        dict_repr = self._asdict()
        dict_repr['_id'] = self.id
        return dict_repr

    @classmethod
    @inject.params(db=AsyncIOMotorDatabase)
    async def create(cls, data_dict, db=None):
        valid_data = cls.trafaret.check(data_dict)
        res = await db[cls.collection].insert_one(valid_data)
        data_dict['id'] = res.inserted_id
        return cls.from_dict(**data_dict)

    @staticmethod
    @inject.params(db=AsyncIOMotorDatabase)
    def find_by_pattern(patterns, db=None):
        return db[Reaction.collection].find({'patterns': {'$in': patterns}})

