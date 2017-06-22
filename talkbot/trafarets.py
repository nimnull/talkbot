import os

import trafaret as t


class FilePath(t.String):

    def __init__(self):
        super().__init__(regex=r'^(/)?([^/\0]+(/)?)+$', min_length=1)

    def __repr__(self):
        return '<File>'

    def check_value(self, value):
        val = super().check_and_return(value)

        if not os.path.exists(val):
            self._failure("Specified path '%s' does not exists" % val, value=val)

        return val
