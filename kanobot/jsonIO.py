import os
import json
from functools import wraps
from random import randint


class InvalidJsonFile(Exception):
    pass


class InvalidPath(Exception):
    pass


class JsonIO(dict):

    def save(self, filename, data):
        """
        Save json in file
        @param {String} filename - The filename.
        @param {Dict like} data
        """
        return self.save_json(filename, data)

    # pylint: disable=E0213
    # pylint: disable=E1102
    def _save(func):
        """ wrapper function """

        @wraps(func)
        def wrapper(self, *args, **kwargs):
            filename, data = func(self, *args, **kwargs)
            self.save_json(filename, data)
            return data

        return wrapper

    def get(self, filename):
        """
        get json from file
        @param {String} filename - The filename.
        """
        if not os.path.isfile(filename):
            self.save(filename, {})

        if self.is_valid_json(filename):
            data = self.load_json(filename)
        else:
            raise InvalidJsonFile()
        return data

    @_save
    def set_values(self, filename, items):
        """
        Set values using dict {}
        @param {String} filename - The filename.
        @param {Dict} items - The dictionary {}.
        """
        data = self.load_json(filename)
        for key, value in items.items():
            data[key] = value
        return filename, data

    @_save
    def set_value(self, filename, key, value):
        """
        Set single key, value
        @param {String} filename - The filename.
        @param {String} key
        @param {Any} value
        """
        data = self.load_json(filename)
        data[key] = value
        return filename, data

    def save_json(self, filename, data):
        """
        Save json in file
        @param {String} filename - The filename.
        @param {Dict like} data
        """
        rnd = randint(1000, 9999)
        path, _ = os.path.splitext(filename)
        tmp_file = "{}-{}".format(path, rnd)
        self._save_json(tmp_file, data)
        try:
            self._read_json(tmp_file)
        except json.decoder.JSONDecodeError:
            return False

        os.replace(tmp_file, filename)

    def load_json(self, filename):
        """Loads json file"""
        return self._read_json(filename)

    def is_valid_json(self, filename):
        """Verifies if json file exists / is readable"""
        try:
            self._read_json(filename)
            return True
        except FileNotFoundError:
            return False
        except json.decoder.JSONDecodeError:
            return False

    def _save_json(self, filename, data):
        if not os.path.exists(os.path.dirname(filename)):
            try:
                os.makedirs(os.path.dirname(filename))
            except Exception:
                raise InvalidPath()
        with open(filename, encoding='utf-8', mode="w") as f:
            json.dump(data, f, indent=4, sort_keys=True, separators=(',', ' : '))
        return data

    def _read_json(self, filename):
        with open(filename, encoding='utf-8', mode="r") as f:
            data = json.load(f)
        return data
