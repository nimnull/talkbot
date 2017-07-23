import re
import time
from collections import namedtuple

import inject
import trafaret as t

from motor.motor_asyncio import AsyncIOMotorDatabase
from trafaret.contrib.object_id import MongoId

from .trafarets import FilePath


class Config(namedtuple('BaseConfig', 'token, mongo, loglevel, sslchain, sslprivkey,reaction_threshold,sample_df')):
    __slots__ = ()
    mongo_uri_re = re.compile(
        r'^(?:mongodb)://'  # mongodb://
        r'(?:\S+(?::\S*)?@)?'  # user and password
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-_]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # domain...
        r'localhost|mongodb|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)

    default = {
        'token': 'randomtoken',
        'mongo': {
            'uri': 'mongodb://mongodb',
            'db': 'talkbot'
        },
        'loglevel': 'DEBUG',
        'reaction_threshold': 4,
        'sample_df': "sample.csv",
    }

    trafaret = t.Dict({
        'token': t.String,
        'mongo': t.Dict({
            'uri': t.String(regex=mongo_uri_re),
            'db': t.String
        }),
        'loglevel': t.Enum('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'),
        'sslchain': FilePath(),
        'sslprivkey': FilePath(),
        'sample_df': FilePath(),
        'reaction_threshold': t.Int
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


class StorableMix:

    collection = None

    @classmethod
    def from_dict(cls, **kwargs):
        mutable = kwargs.copy()
        if '_id' in kwargs:
            mutable['id'] = mutable.pop('_id')
        checked = cls.trafaret.check(mutable)
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

    @classmethod
    @inject.params(db=AsyncIOMotorDatabase)
    def find(cls, query=None, limit=0, skip=0, db=None):
        return db[cls.collection].find(query).skip(skip).limit(limit)

    @classmethod
    @inject.params(db=AsyncIOMotorDatabase)
    def find_one(cls, query=None, db=None):
        return db[cls.collection].find_one(query)


class Reaction(namedtuple('BaseReaction', 'id,patterns,image_url,image_id,text,created_at,created_by,last_used'),
               StorableMix):
    collection = 'reactions'

    trafaret = t.Dict({
        'id': t.Or(t.String | MongoId(allow_blank=True)),
        'patterns': t.List(t.String, min_length=1),
        'image_url': t.URL(allow_blank=True),
        'image_id': t.String(allow_blank=True),
        'text': t.String(allow_blank=True),
        'created_at': t.Int,
        'created_by': User.trafaret,
        t.Key('last_used', default=0): t.Int,
    }).make_optional('image_id', 'image_url', 'text', 'last_used')

    @classmethod
    @inject.params(db=AsyncIOMotorDatabase)
    def find_by_pattern(cls, patterns, db=None):
        return db[cls.collection].find({'patterns': {'$in': patterns}})

    @inject.params(db=AsyncIOMotorDatabase)
    def update_usage(self, db=None):
        epoch_now = int(time.time())
        return db[self.collection].update({'_id': self.id}, {'$set': {'last_used': epoch_now}})

    @property
    @inject.params(config=Config)
    def on_hold(self, config=None):
        epoch_now = int(time.time())
        return self.last_used >= (epoch_now - config.reaction_threshold * 60)


class ImageFinger(namedtuple('ImageFinger', 'id,vectors,message,file_id,chat_id'),
                  StorableMix):
    collection = 'images'
    trafaret = t.Dict({
        'id': t.Or(t.String | MongoId(allow_blank=True)),
        'vectors': t.List(t.List(t.String, min_length=2, max_length=2)),
        'message': t.Dict().allow_extra('*'),
        'file_id': t.String,
        'chat_id': t.Int
    })
