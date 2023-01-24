
class GetWrappedJson:
    def __init__(self, data):
        self._data = data
    
    def __getattr__(self, name):
        # print(f"Getting attribute {name} {type(self._data)}")

        if isinstance(self._data, dict) and name in self._data:
            value = self._data[name]
            if isinstance(value, (dict, list)):
                return GetWrappedJson(value)
            return value
        elif isinstance(self._data, dict):
            if name in dir(dict):
                return getattr(self._data, name)
            return None
        elif isinstance(self._data, list):
            if name == "append":
                def wrapped_append(kw):
                    if isinstance(kw, GetWrappedJson):
                        self._data.append(kw._data)
                    else:
                        self._data.append(kw)
                return wrapped_append
            if name in dir(list):
                return getattr(self._data, name)
            return None
        return None

    def __getitem__(self, name):
        # print(f"Getting item {name} {type(self._data)}")
        if isinstance(self._data, list) and isinstance(name, int) and 0 <= name < len(self._data):
            value = self._data[name]
            if isinstance(value, (dict, list)):
                return GetWrappedJson(value)
            return value
        elif isinstance(self._data, dict) and name in self._data:
            value = self._data[name]
            if isinstance(value, (dict, list)):
                return GetWrappedJson(value)
            return value
        return None

    def __setattr__(self, name, value):
        if name != "_data":
            if isinstance(self._data, dict):
                if isinstance(value, GetWrappedJson):
                    self._data[name] = value._data
                else:
                    self._data[name] = value
        else:
            super().__setattr__(name, value)

    def __setitem__(self, key, value):
        if isinstance(self._data, list) and isinstance(key, int) and 0 <= key < len(self._data):
            if isinstance(value, GetWrappedJson):
                self._data[key] = value._data
            else:
                self._data[key] = value
        elif isinstance(self._data, dict):
            if isinstance(value, GetWrappedJson):
                self._data[key] = value._data
            else:
                self._data[key] = value

    def __len__(self):
        return len(self._data)

    def __iter__(self):
        for value in self._data:
            if isinstance(value, (dict, list)):
                yield GetWrappedJson(value)
            else:
                yield value


    def __str__(self):
        return str(self._data)

    def __repr__(self):
        return repr(self._data)


    def __bool__(self):
        return bool(self._data)
