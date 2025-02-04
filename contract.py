# -*- coding: utf-8 -*-

import functools
import inspect
import re
from dateutil.parser import parse as dateutil_parse

"""
Contract is tiny library for data validation
It provides several primitives to validate complex data structures
Look at doctests for usage examples
"""

__all__ = ("ContractValidationError", "Contract", "AnyC", "IntC", "StringC",
           "ListC", "DictC", "OrC", "NullC", "FloatC", "EnumC", "CallableC",
           "CallC", "ForwardC", "BoolC", "TypeC", "MappingC", "guard",
           "EmailC")


class ContractValidationError(TypeError):

    """
    Basic contract validation error
    """

    def __init__(self, msg, name=None):
        message = msg if not name else "%s: %s" % (name, msg)
        super(ContractValidationError, self).__init__(message)
        self.msg = msg
        self.name = name


class ContractMeta(type):

    """
    Metaclass for contracts to make using "|" operator possible not only
    on instances but on classes

    >>> IntC | StringC
    Integer or String
    >>> IntC | StringC | NullC
    Integer or String or Null
    """

    def __or__(cls, other):
        return cls() | other


class Contract(object):

    """
    Base class for contracts, provides only one method for
    contract validation failure reporting
    """

    __metaclass__ = ContractMeta

    def check(self, value):
        """
        Implement this method in Contract subclasses
        """
        cls = "%s.%s" % (type(self).__module__, type(self).__name__)
        raise NotImplementedError("method check is not implemented in"
                                  " '%s'" % cls)

    def _failure(self, message):
        """
        Shortcut method for raising validation error
        """
        raise ContractValidationError(message)

    def _contract(self, contract):
        """
        Helper for complex contracts, takes contract instance or class
        and returns contract instance
        """
        if isinstance(contract, Contract):
            return contract
        elif issubclass(contract, Contract):
            return contract()
        elif isinstance(contract, type):
            return TypeC(contract)
        else:
            raise RuntimeError("%r should be instance or subclass"
                               " of Contract" % contract)

    def __or__(self, other):
        return OrC(self, other)

    def get_full_condition_name(self, condition):
        conditions = {"gt": "greater than",
                      "lt": "less than",
                      "gte": "greater or equal than",
                      "lte": "less or equal than"}
        return conditions.get(condition)


class TypeC(Contract):

    """
    >>> TypeC(int)
    <type(int)>
    >>> TypeC[int]
    <type(int)>
    >>> c = TypeC[int]
    >>> c.check(1)
    >>> c.check("foo")
    Traceback (most recent call last):
    ...
    ContractValidationError: value is not int
    """

    class __metaclass__(ContractMeta):

        def __getitem__(self, type_):
            return self(type_)

    def __init__(self, type_):
        self.type_ = type_

    def check(self, value):
        if not isinstance(value, self.type_):
            self._failure("value is not %s" % self.type_.__name__)

    def __repr__(self):
        return "<type(%s)>" % self.type_.__name__


class AnyC(Contract):

    """
    >>> AnyC()
    Any
    >>> AnyC().check(object())
    """

    def check(self, value):
        pass

    def __repr__(self):
        return "Any"


class OrCMeta(ContractMeta):

    """
    Allows to use "<<" operator on OrC class

    >>> OrC << IntC << StringC
    Integer or String
    """

    def __lshift__(cls, other):
        return cls() << other


class OrC(Contract):

    """
    >>> nullString = OrC(StringC, NullC)
    >>> nullString
    String or Null
    >>> nullString.check(None)
    >>> nullString.check("test")
    >>> nullString.check(1)
    Traceback (most recent call last):
    ...
    ContractValidationError: no one contract matches
    """

    __metaclass__ = OrCMeta

    def __init__(self, *contracts):
        self.contracts = map(self._contract, contracts)

    def check(self, value):
        for contract in self.contracts:
            try:
                contract.check(value)
            except ContractValidationError:
                pass
            else:
                return
        self._failure("no one contract matches")

    def __lshift__(self, contract):
        self.contracts.append(self._contract(contract))
        return self

    def __or__(self, contract):
        self << contract
        return self

    def __repr__(self):
        #return "\n\n\t- %s\n" % ("\n\t- ".join(map(repr, self.contracts)))
        return "%s" % (" or ".join(map(repr, self.contracts)))


class NullC(Contract):

    """
    >>> NullC()
    Null
    >>> NullC().check(None)
    >>> NullC().check(1)
    Traceback (most recent call last):
    ...
    ContractValidationError: value should be None
    """

    def check(self, value):
        if value is not None:
            self._failure("value should be None")

    def __repr__(self):
        return "Null"


class BoolC(Contract):

    """
    >>> BoolC()
    Boolean
    >>> BoolC().check(True)
    >>> BoolC().check(False)
    >>> BoolC().check(1)
    Traceback (most recent call last):
    ...
    ContractValidationError: value should be True or False
    """

    def check(self, value):
        if not isinstance(value, bool):
            self._failure("value should be True or False")

    def __repr__(self):
        return "Boolean"


class NumberCMeta(ContractMeta):

    """
    Allows slicing syntax for min and max arguments for
    number contracts

    >>> IntC[1:]
    Integer (greater or equal than 1)
    >>> IntC[1:10]
    Integer (greater or equal than 1, less or equal than 10)
    >>> IntC[:10]
    Integer (less or equal than 10)
    >>> FloatC[1:]
    Float (greater or equal than 1)
    >>> IntC > 3
    Integer (greater than 3)
    >>> 1 < (FloatC < 10)
    Float (greater than 1, less than 10)
    >>> (IntC > 5).check(10)
    >>> (IntC > 5).check(1)
    Traceback (most recent call last):
    ...
    ContractValidationError: value should be greater than 5
    >>> (IntC < 3).check(1)
    >>> (IntC < 3).check(3)
    Traceback (most recent call last):
    ...
    ContractValidationError: value should be less than 3
    """

    def __getitem__(self, slice_):
        return self(gte=slice_.start, lte=slice_.stop)

    def __lt__(self, lt):
        return self(lt=lt)

    def __gt__(self, gt):
        return self(gt=gt)


class FloatC(Contract):

    """
    >>> FloatC()
    Float
    >>> FloatC(gte=1)
    Float (greater or equal than 1)
    >>> FloatC(lte=10)
    Float (less or equal than 10)
    >>> FloatC(gte=1, lte=10)
    Float (greater or equal than 1, less or equal than 10)
    >>> FloatC().check(1.0)
    >>> FloatC().check(1)
    Traceback (most recent call last):
    ...
    ContractValidationError: value is not float
    >>> FloatC(gte=2).check(3.0)
    >>> FloatC(gte=2).check(1.0)
    Traceback (most recent call last):
    ...
    ContractValidationError: value is less than 2
    >>> FloatC(lte=10).check(5.0)
    >>> FloatC(lte=3).check(5.0)
    Traceback (most recent call last):
    ...
    ContractValidationError: value is greater than 3
    """

    __metaclass__ = NumberCMeta

    value_type = float

    def __init__(self, gte=None, lte=None, gt=None, lt=None):
        self.gte = gte
        self.lte = lte
        self.gt = gt
        self.lt = lt

    def check(self, value):
        if not isinstance(value, self.value_type):
            self._failure("value is not %s" % self.value_type.__name__)
        if self.gte is not None and value < self.gte:
            self._failure("value is less than %s" % self.gte)
        if self.lte is not None and value > self.lte:
            self._failure("value is greater than %s" % self.lte)
        if self.lt is not None and value >= self.lt:
            self._failure("value should be less than %s" % self.lt)
        if self.gt is not None and value <= self.gt:
            self._failure("value should be greater than %s" % self.gt)

    def __lt__(self, lt):
        return type(self)(gte=self.gte, lte=self.lte, gt=self.gt, lt=lt)

    def __gt__(self, gt):
        return type(self)(gte=self.gte, lte=self.lte, gt=gt, lt=self.lt)

    def __reprname__(self):
        return type(self).__name__.lower()[:-1]

    def __repr__(self):
        if type(self) is IntC:
            r = "Integer"
        else:
            r = "Float"
        options = []
        for param in ("gte", "lte", "gt", "lt"):
            if getattr(self, param) is not None:
                condition = self.get_full_condition_name(param)
                options.append("%s %s" % (condition, getattr(self, param)))
        if options:
            r += " (%s)" % (", ".join(options))
        return r


class IntC(FloatC):

    """
    >>> IntC()
    Integer
    >>> IntC().check(5)
    >>> IntC().check(1.1)
    Traceback (most recent call last):
    ...
    ContractValidationError: value is not int
    """

    value_type = int


class StringC(Contract):

    """
    >>> StringC()
    String
    >>> StringC(allow_blank=True)
    String (could be blank)
    >>> StringC().check("foo")
    >>> StringC().check("")
    Traceback (most recent call last):
    ...
    ContractValidationError: blank value is not allowed
    >>> StringC(allow_blank=True).check("")
    >>> StringC().check(1)
    Traceback (most recent call last):
    ...
    ContractValidationError: value is not string
    """

    def __init__(self, allow_blank=False):
        self.allow_blank = allow_blank

    def check(self, value):
        if not isinstance(value, basestring):
            self._failure("value is not string")
        if not self.allow_blank and len(value) is 0:
            self._failure("blank value is not allowed")

    def __repr__(self):
        return "String (could be blank)" if self.allow_blank else "String"


class EmailC(Contract):

    """
    >>> EmailC()
    String with email format
    >>> EmailC().check('alex.gonzalez@paylogic.eu')
    >>> EmailC().check(1)
    Traceback (most recent call last):
    ...
    ContractValidationError: value is not email
    >>> EmailC().check('alex')
    Traceback (most recent call last):
    ...
    ContractValidationError: value is not email
    """

    email_re = re.compile(
        r"(^[-!#$%&'*+/=?^_`{}|~0-9A-Z]+(\.[-!#$%&'*+/=?^_`{}|~0-9A-Z]+)*"  # dot-atom
        r'|^"([\001-\010\013\014\016-\037!#-\[\]-\177]|\\[\001-011\013\014\016-\177])*"'  # quoted-string
        r')@((?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?$)'  # domain
        r'|\[(25[0-5]|2[0-4]\d|[0-1]?\d?\d)(\.(25[0-5]|2[0-4]\d|[0-1]?\d?\d)){3}\]$', re.IGNORECASE)  # literal form, ipv4 address (SMTP 4.1.3)

    def __init__(self):
        pass

    def check(self, value):
        if not value or not isinstance(value, basestring):
            self._failure("value is not email")
        if self.email_re.search(value):
            return
        # Trivial case failed. Try for possible IDN domain-part
        if value and u'@' in value:
            parts = value.split(u'@')
            try:
                parts[-1] = parts[-1].encode('idna')
            except UnicodeError:
                pass
            else:
                if self.email_re.search(u'@'.join(parts)):
                    return
        self._failure('value is not email')

    def __repr__(self):
        return "String with email format"

class IsoDateC(Contract):
    def _rant(self, value):
        self._failure("value is not an iso formatted date: %r" % value)

    def check(self, value):
        if not value:
            self._rant(value)
        try:
            dateutil_parse(value)
        except:
            self._rant(value)

    def __repr__(self):
        return "ISO formatted date"


class SquareBracketsMeta(ContractMeta):

    """
    Allows usage of square brackets for ListC initialization

    >>> ListC[IntC]
    List of Integer
    >>> ListC[IntC, 1:]
    List of Integer (minimum length of 1)
    >>> ListC[:10, IntC]
    List of Integer (maximum length of 10)
    >>> ListC[1:10]
    Traceback (most recent call last):
    ...
    RuntimeError: Contract is required for ListC initialization
    """

    def __getitem__(self, args):
        slice_ = None
        contract = None
        if not isinstance(args, tuple):
            args = (args, )
        for arg in args:
            if isinstance(arg, slice):
                slice_ = arg
            elif isinstance(arg, Contract) or issubclass(arg, Contract) \
                 or isinstance(arg, type):
                contract = arg
        if not contract:
            raise RuntimeError("Contract is required for ListC initialization")
        if slice_:
            return self(contract, min_length=slice_.start or 0,
                                  max_length=slice_.stop)
        return self(contract)


class ListC(Contract):

    """
    >>> ListC(IntC)
    List of Integer
    >>> ListC(IntC, min_length=1)
    List of Integer (minimum length of 1)
    >>> ListC(IntC, min_length=1, max_length=10)
    List of Integer (minimum length of 1, maximum length of 10)
    >>> ListC(IntC).check(1)
    Traceback (most recent call last):
    ...
    ContractValidationError: value is not list
    >>> ListC(IntC).check([1, 2, 3])
    >>> ListC(StringC).check(["foo", "bar", "spam"])
    >>> ListC(IntC).check([1, 2, 3.0])
    Traceback (most recent call last):
    ...
    ContractValidationError: 2: value is not int
    >>> ListC(IntC, min_length=1).check([1, 2, 3])
    >>> ListC(IntC, min_length=1).check([])
    Traceback (most recent call last):
    ...
    ContractValidationError: list length is less than 1
    >>> ListC(IntC, max_length=2).check([1, 2])
    >>> ListC(IntC, max_length=2).check([1, 2, 3])
    Traceback (most recent call last):
    ...
    ContractValidationError: list length is greater than 2
    """

    __metaclass__ = SquareBracketsMeta

    def __init__(self, contract, min_length=0, max_length=None):
        self.contract = self._contract(contract)
        self.min_length = min_length
        self.max_length = max_length

    def check(self, value):
        if not isinstance(value, list):
            self._failure("value is not list")
        if len(value) < self.min_length:
            self._failure("list length is less than %s" % self.min_length)
        if self.max_length is not None and len(value) > self.max_length:
            self._failure("list length is greater than %s" % self.max_length)
        for index, item in enumerate(value):
            try:
                self.contract.check(item)
            except ContractValidationError as err:
                name = "%i.%s" % (index, err.name) if err.name else str(index)
                raise ContractValidationError(err.msg, name)

    def __repr__(self):
        r = "List of %s" % self.contract
        options = []
        if self.min_length:
            options.append("minimum length of %s" % self.min_length)
        if self.max_length:
            options.append("maximum length of %s" % self.max_length)
        if options:
            r = "%s (%s)" % (r, ', '.join(options))
        return r


class DictC(Contract):

    """
    >>> contract = DictC(foo=IntC, bar=StringC)
    >>> contract.check({"foo": 1, "bar": "spam"})
    >>> contract.check({"foo": 1, "bar": 2})
    Traceback (most recent call last):
    ...
    ContractValidationError: bar: value is not string
    >>> contract.check({"foo": 1})
    Traceback (most recent call last):
    ...
    ContractValidationError: bar is required
    >>> contract.check({"foo": 1, "bar": "spam", "eggs": None})
    Traceback (most recent call last):
    ...
    ContractValidationError: eggs is not allowed key
    >>> contract.allow_extra("eggs")
    <DictC(extras=(eggs) | bar=String, foo=Integer)>
    >>> contract.check({"foo": 1, "bar": "spam", "eggs": None})
    >>> contract.check({"foo": 1, "bar": "spam"})
    >>> contract.check({"foo": 1, "bar": "spam", "ham": 100})
    Traceback (most recent call last):
    ...
    ContractValidationError: ham is not allowed key
    >>> contract.allow_extra("*")
    <DictC(any, extras=(eggs) | bar=String, foo=Integer)>
    >>> contract.check({"foo": 1, "bar": "spam", "ham": 100})
    >>> contract.check({"foo": 1, "bar": "spam", "ham": 100, "baz": None})
    >>> contract.check({"foo": 1, "ham": 100, "baz": None})
    Traceback (most recent call last):
    ...
    ContractValidationError: bar is required
    >>> contract.allow_optionals("bar")
    <DictC(any, extras=(eggs), optionals=(bar) | bar=String, foo=Integer)>
    >>> contract.check({"foo": 1, "ham": 100, "baz": None})
    >>> contract.check({"bar": 1, "ham": 100, "baz": None})
    Traceback (most recent call last):
    ...
    ContractValidationError: foo is required
    >>> contract.check({"foo": 1, "bar": 1, "ham": 100, "baz": None})
    Traceback (most recent call last):
    ...
    ContractValidationError: bar: value is not string
    """

    def __init__(self, **contracts):
        self.optionals = []
        self.extras = []
        self.allow_any = False
        self.contracts = {}
        for key, contract in contracts.items():
            self.contracts[key] = self._contract(contract)

    def allow_extra(self, *names):
        for name in names:
            if name == "*":
                self.allow_any = True
            else:
                self.extras.append(name)
        return self

    def allow_optionals(self, *names):
        for name in names:
            if name == "*":
                self.optionals = self.contracts.keys()
            else:
                self.optionals.append(name)
        return self

    def check(self, value):
        if not isinstance(value, dict):
            self._failure("value is not dict")
        self.check_presence(value)
        map(self.check_item, value.items())

    def check_presence(self, value):
        for key in self.contracts:
            if key not in self.optionals and key not in value:
                self._failure("%s is required" % key)

    def check_item(self, item):
        key, value = item
        if key in self.contracts:
            try:
                self.contracts[key].check(value)
            except ContractValidationError as err:
                name = "%s.%s" % (key, err.name) if err.name else key
                raise ContractValidationError(err.msg, name)
        elif not self.allow_any and key not in self.extras:
            self._failure("%s is not allowed key" % key)

    def __repr__(self):
        r = "<DictC("
        options = []
        if self.allow_any:
            options.append("any")
        if self.extras:
            options.append("extras=(%s)" % (", ".join(self.extras)))
        if self.optionals:
            options.append("optionals=(%s)" % (", ".join(self.optionals)))
        r += ", ".join(options)
        if options:
            r += " | "
        options = []
        for key in sorted(self.contracts.keys()):
            options.append("%s=%r" % (key, self.contracts[key]))
        r += ", ".join(options)
        r += ")>"
        return r


class MappingC(Contract):

    """
    >>> contract = MappingC(StringC, IntC)
    >>> contract
    <String => Integer>
    >>> contract.check({"foo": 1, "bar": 2})
    >>> contract.check({"foo": 1, "bar": None})
    Traceback (most recent call last):
    ...
    ContractValidationError: (value for key 'bar'): value is not int
    >>> contract.check({"foo": 1, 2: "bar"})
    Traceback (most recent call last):
    ...
    ContractValidationError: (key 2): value is not string
    """

    def __init__(self, keyC, valueC):
        self.keyC = self._contract(keyC)
        self.valueC = self._contract(valueC)

    def check(self, mapping):
        for key in mapping:
            value = mapping[key]
            try:
                self.keyC.check(key)
            except ContractValidationError as err:
                raise ContractValidationError(err.msg, "(key %r)" % key)
            try:
                self.valueC.check(value)
            except ContractValidationError as err:
                raise ContractValidationError(err.msg, "(value for key %r)" % key)

    def __repr__(self):
        return "<%r => %r>" % (self.keyC, self.valueC)


class EnumC(Contract):

    """
    >>> contract = EnumC("foo", "bar", 1)
    >>> contract
    'foo' or 'bar' or 1
    >>> contract.check("foo")
    >>> contract.check(1)
    >>> contract.check(2)
    Traceback (most recent call last):
    ...
    ContractValidationError: value doesn't match any variant
    """

    def __init__(self, *variants):
        self.variants = variants[:]

    def check(self, value):
        if value not in self.variants:
            self._failure("value doesn't match any variant")

    def __repr__(self):
        return "%s" % (" or ".join(map(repr, self.variants)))


class CallableC(Contract):

    """
    >>> CallableC().check(lambda: 1)
    >>> CallableC().check(1)
    Traceback (most recent call last):
    ...
    ContractValidationError: value is not callable
    """

    def check(self, value):
        if not callable(value):
            self._failure("value is not callable")

    def __repr__(self):
        return "<callable>"


class CallC(Contract):

    """
    >>> def validator(value):
    ...     if value != "foo":
    ...         return "I want only foo!"
    ...
    >>> contract = CallC(validator)
    >>> contract
    <CallC(validator)>
    >>> contract.check("foo")
    >>> contract.check("bar")
    Traceback (most recent call last):
    ...
    ContractValidationError: I want only foo!
    """

    def __init__(self, fn):
        if not callable(fn):
            raise RuntimeError("CallC argument should be callable")
        argspec = inspect.getargspec(fn)
        if len(argspec.args) - len(argspec.defaults or []) > 1:
            raise RuntimeError("CallC argument should be"
                               " one argument function")
        self.fn = fn

    def check(self, value):
        error = self.fn(value)
        if error is not None:
            self._failure(error)

    def __repr__(self):
        return "<CallC(%s)>" % self.fn.__name__


class ForwardC(Contract):

    """
    >>> nodeC = ForwardC()
    >>> nodeC << DictC(name=StringC, children=ListC[nodeC])
    >>> nodeC
    <ForwardC(<DictC(children=List of <recur>, name=String)>)>
    >>> nodeC.check({"name": "foo", "children": []})
    >>> nodeC.check({"name": "foo", "children": [1]})
    Traceback (most recent call last):
    ...
    ContractValidationError: children.0: value is not dict
    >>> nodeC.check({"name": "foo", "children": [ \
                        {"name": "bar", "children": []} \
                     ]})
    """

    def __init__(self):
        self.contract = None
        self._recur_repr = False

    def __lshift__(self, contract):
        if self.contract:
            raise RuntimeError("contract for ForwardC is already specified")
        self.contract = self._contract(contract)

    def check(self, value):
        self.contract.check(value)

    def __repr__(self):
        # XXX not threadsafe
        if self._recur_repr:
            return "<recur>"
        self._recur_repr = True
        r = "<ForwardC(%r)>" % self.contract
        self._recur_repr = False
        return r


class GuardValidationError(ContractValidationError):

    """
    Raised when guarded function gets invalid arguments,
    inherits error message from corresponding ContractValidationError
    """

    pass


def get_array_from_contract(doc_contract):
    contracts = {}
    for attribute in doc_contract.split(','):
        (key, value) = attribute.split('=')
        key = key.strip()
        contracts.update({key: value})
    return contracts


def guard(contract=None, **kwargs):
    """
    Decorator for protecting function with contracts

    >>> @guard(a=StringC, b=IntC, c=StringC)
    ... def fn(a, b, c="default"):
    ...     '''docstring'''
    ...     return (a, b, c)
    ...
    >>> fn.__module__ = None
    >>> help(fn)
    Help on function fn:
    <BLANKLINE>
    fn(*args, **kwargs)
        Guarded with:
    <BLANKLINE>
        - ``a``: String
        - ``c``: String
        - ``b``: Integer
    <BLANKLINE>
        docstring
    <BLANKLINE>
    >>> fn("foo", 1)
    ('foo', 1, 'default')
    >>> fn("foo", 1, 2)
    Traceback (most recent call last):
    ...
    GuardValidationError: c: value is not string
    >>> fn("foo")
    Traceback (most recent call last):
    ...
    GuardValidationError: b is required
    >>> g = guard(DictC())
    >>> c = ForwardC()
    >>> c << DictC(name=basestring, children=ListC[c])
    >>> g = guard(c)
    >>> g = guard(IntC())
    Traceback (most recent call last):
    ...
    RuntimeError: contract should be instance of DictC or ForwardC
    """
    if contract and not isinstance(contract, DictC) and \
                    not isinstance(contract, ForwardC):
        raise RuntimeError("contract should be instance of DictC or ForwardC")
    elif contract and kwargs:
        raise RuntimeError("choose one way of initialization,"
                           " contract or kwargs")
    if not contract:
        contract = DictC(**kwargs)

    def wrapper(fn):
        argspec = inspect.getargspec(fn)

        @functools.wraps(fn)
        def decor(*args, **kwargs):
            fnargs = argspec.args
            if fnargs[0] == 'self':
                fnargs = fnargs[1:]
                checkargs = args[1:]
            else:
                checkargs = args

            try:
                call_args = dict(zip(fnargs, checkargs) + kwargs.items())
                for name, default in zip(reversed(fnargs),
                                          argspec.defaults or ()):
                    if name not in call_args:
                        call_args[name] = default
                contract.check(call_args)
            except ContractValidationError as err:
                raise GuardValidationError(unicode(err))
            return fn(*args, **kwargs)

        doc_contract = repr(contract)

        # find the first ( and strip anything around it
        min_garbage_index = doc_contract.index("(") + 1
        max_garbage_index = doc_contract.index(")")
        doc_contract = doc_contract[min_garbage_index:max_garbage_index]
        guarded_with = get_array_from_contract(doc_contract)

        try:
            pattern = re.compile('^( ){8}', flags=re.MULTILINE)
            old_documentation = pattern.sub('', decor.__doc__)
        except TypeError:
            old_documentation = ''
        decor.__doc__ = "Guarded with:\n\n"
        for param in guarded_with:
            decor.__doc__ += '- ``%s``: %s\n' % (param, guarded_with[param])
        if len(guarded_with) > 0:
            decor.__doc__ += '\n'
        decor.__doc__ += old_documentation

        return decor
    return wrapper


class NumberC(StringC):
    """
    >>> NumberC()
    Digit
    >>> NumberC().check(5)
    >>> NumberC().check('alex')
    Traceback (most recent call last):
    ...
    ContractValidationError: value is not a number
    """
    def __init__(self):
        super(NumberC, self).__init__(allow_blank=False)

    def check(self, value):
        if value == None:
            self._failure("value is None")
        try:
            super(NumberC, self).check(value)
        except ContractValidationError as e:
            try:
                float(value)
                return
            except ValueError:
                raise e
        if not value.isdigit():
            self._failure("value is not a number")

    def __repr__(self):
        return 'Digit'


if __name__ == "__main__":
    import doctest
    doctest.testmod()
