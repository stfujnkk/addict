import copy
import weakref


class Dict(dict):

    def __init__(__self, *args, **kwargs):
        _set_state(__self, kwargs)
        for arg in args:
            if not arg:
                continue
            elif isinstance(arg, dict):
                for key, val in arg.items():
                    __self[key] = __self._hook(val)
            elif isinstance(arg, tuple) and (not isinstance(arg[0], tuple)):
                __self[arg[0]] = __self._hook(arg[1])
            else:
                for key, val in iter(arg):
                    __self[key] = __self._hook(val)

        for key, val in kwargs.items():
            __self[key] = __self._hook(val)

    def __setattr__(self, name, value):
        if hasattr(self.__class__, name):
            raise AttributeError("'Dict' object attribute "
                                 "'{0}' is read-only".format(name))
        else:
            try:
                self[name] = value
            except KeyError:
                self_type = type(self).__name__
                raise AttributeError(
                    "'{}' object has no attribute '{}'".format(
                        self_type, name))

    def __setitem__(self, name, value):
        if name in _STATE_KEYS:
            return
        """Make sure all values are wrapped by `Dict`

If you remove this code, the value will not be wrapped in the following cases
>>> d = Dict()
>>> d.a = {'b': 1}
>>> print(type(d.a))
<class 'dict'>
        """
        if not isinstance(value, Dict):
            value = type(self)._hook(value)
        isFrozen = (hasattr(self, '__frozen') and
                    object.__getattribute__(self, '__frozen'))
        if isFrozen and name not in super(Dict, self).keys():
                raise KeyError(name)
        super(Dict, self).__setitem__(name, value)
        try:
            p = object.__getattribute__(self, '__parent')
            key = object.__getattribute__(self, '__key')
        except AttributeError:
            p = None
            key = None
        if p is not None:
            p[key] = self
            object.__delattr__(self, '__parent')
            object.__delattr__(self, '__key')

    def __add__(self, other):
        if not self.keys():
            return other
        else:
            self_type = type(self).__name__
            other_type = type(other).__name__
            msg = "unsupported operand type(s) for +: '{}' and '{}'"
            raise TypeError(msg.format(self_type, other_type))

    @classmethod
    def _hook(cls, item):
        if isinstance(item, dict):
            return cls(item)
        elif isinstance(item, (list, tuple)):
            return type(item)(cls._hook(elem) for elem in item)
        return item

    def __getattr__(self, item):
        try:
            return self.__getitem__(item)
        except KeyError:
            self_type = type(self).__name__
            raise AttributeError("'{}' object has no attribute '{}'".format(
                self_type, item))

    def __missing__(self, name):
        if object.__getattribute__(self, '__frozen'):
            raise KeyError(name)
        st: dict = _get_state(self, ['__other_state'])['__other_state']
        missing_ref = st.get('missing_ref')
        if missing_ref is None:
            missing_ref = weakref.WeakValueDictionary()
            st['missing_ref'] = missing_ref

        if name in missing_ref:
            return missing_ref[name]
        ref = self.__class__(__parent=self, __key=name)
        missing_ref[name] = ref
        return ref

    def __delattr__(self, name):
        del self[name]

    def to_dict(self):
        base = {}
        for key, value in self.items():
            base[key] = unwrap(value)
        return base

    def copy(self):
        return copy.copy(self)

    def deepcopy(self):
        return copy.deepcopy(self)

    def __deepcopy__(self, memo):
        other = self.__class__()
        memo[id(self)] = other
        for key, value in self.items():
            other[copy.deepcopy(key, memo)] = copy.deepcopy(value, memo)
        return other

    def update(self, *args, **kwargs):
        other = {}
        if args:
            if len(args) > 1:
                raise TypeError()
            other.update(args[0])
        other.update(kwargs)
        for k, v in other.items():
            if ((k not in self) or
                (not isinstance(self[k], dict)) or
                (not isinstance(v, dict))):
                self[k] = v
            else:
                self[k].update(v)

    def __getnewargs__(self):
        return tuple(self.items())

    def __getstate__(self):
        return self.to_dict(), _get_state(self, ['__frozen'])

    def __setstate__(self, state):
        kv, st = state
        self.update(kv)
        _set_state(self, st)

    def __or__(self, other):
        if not isinstance(other, (Dict, dict)):
            return NotImplemented
        new = type(self)(self)
        new.update(other)
        return new

    def __ror__(self, other):
        if not isinstance(other, (Dict, dict)):
            return NotImplemented
        new = type(self)(other)
        new.update(self)
        return new

    def __ior__(self, other):
        self.update(other)
        return self

    def setdefault(self, key, default=None):
        if key in self:
            return self[key]
        else:
            self[key] = default
            return self[key]

    def freeze(self, shouldFreeze=True):
        object.__setattr__(self, '__frozen', shouldFreeze)
        for _, val in self.items():
            if isinstance(val, Dict):
                val.freeze(shouldFreeze)

    def unfreeze(self):
        self.freeze(False)


def unwrap(value):
    to_dict = getattr(value, 'to_dict', None)
    if callable(to_dict):
        return to_dict()
    elif isinstance(value, (list, tuple)):
        return type(value)(unwrap(item) for item in value)
    elif isinstance(value, dict):
        return {k: unwrap(v) for k, v in value.items()}
    return value


_STATE_KEYS = ['__parent', '__key', '__frozen', '__other_state']


def _get_state(d: Dict, ks=None):
    state = {}
    for k in _STATE_KEYS:
        if k not in ks:
            continue
        if not hasattr(d, k):
            state[k] = None
            continue
        state[k] = object.__getattribute__(d, k)
    return state


def _set_state(d: Dict, state: dict):
    for k in _STATE_KEYS:
        if k not in state:
            if k == '__other_state':
                object.__setattr__(d, k, {})
            else:
                object.__setattr__(d, k, None)
            continue
        object.__setattr__(d, k, state[k])
