from ldap3 import MODIFY_ADD, MODIFY_DELETE, MODIFY_REPLACE, MODIFY_INCREMENT
class LdapperException(Exception):
    def __init__(self, message):
        self.message = message

class LdapperInterface(object):
    @staticmethod
    def define(searchBase, primarySearch, **kwargs):
        return LdapperModelDefinition(searchBase, primarySearch, **kwargs)


class LdapperModelDefinition(object):
    def __init__(self, searchBase, primarySearch, attributes=['*'], connection=None, wrapper=True, attributeOverride=None):
        self._wrapper = wrapper
        self._searchBase = searchBase
        if "(" not in primarySearch:
            primarySearch = "(%s)" % primarySearch
        self._primarySearch = primarySearch
        self._attributes = attributes
        self._connection = connection

        if attributeOverride == None:
            attributeOverride = LdapperAttributeOverride()
        self._attributeOverride = attributeOverride

    def using(self, connection):
        return LdapperModelDefinition(self._searchBase,
                self._primarySearch,
                attributes=self._attributes,
                wrapper=self._wrapper,
                connection=connection,
                attributeOverride=self._attributeOverride)

    def get(self, primary):
        if not self._connection:
            raise LdapperException("No connection for ModelDefinition, consider chaining with using()")
        if not self._connection.search(self._searchBase, self._primarySearch % self.override().object(primary), attributes=self._attributes):
            raise LdapperException(self._connection.result)
        if len(self._connection.response) != 1:
            return None
        else:
            if self._wrapper:
                return LdapperModelWrapper(self._connection.response[0].attributes)
            else:
                return self._connection.response[0].attributes

    def find(self, **kwargs):
        search = "(&"
        for pair in kwargs.items():
            pair[1] = self.override().all(pair[0], pair[1])
            search += "(%s=%s)" % pair
        search += ")"
        return self.find_raw(search)

    def find_raw(self, search):
        if not self._connection:
            raise LdapperException("No connection for ModelDefinition, consider chaining with using()")
        if not self._connection.search(self._searchBase, search, attributes=self._attributes):
            raise LdapperException(self._connection.result)
        if self._wrapper:
            return [LdapperModelWrapper(e.attributes) for e in self._connection.response]
        else:
            return self._connection.response

    def save(self, obj):
        if not self._connection:
            raise LdapperException("No connection for ModelDefinition, consider chaining with using()")
        # empty entry assumes new object
        if obj._entry == None:
            pass
        else:
            changes = {}
            for key, value in obj._newValues.items():
                if value == None: # delete
                    changes[key] = [(MODIFY_DELETE,[])]
                elif not hasattr(obj._entry, key):
                    if isinstance(value, list):
                        changes[key] = [(MODIFY_ADD,value)]
                    else:
                        changes[key] = [(MODIFY_ADD, [value])]
                else:
                    if isinstance(value, list):
                        changes[key] = [(MODIFY_REPLACE,value)]
                    else:
                        changes[key] = [(MODIFY_REPLACE, [value])]
            if not self._connection.modify(obj._entry.entry_dn, changes):
                raise LdapperException(self._connection.result)

    def override(self):
        return self._attributeOverride

from datetime import datetime
class LdapperAttributeOverride:

    def __init__(self):
        self._attributes = {}
        self._objects = {}
        self._define_defaults()
        
    def _define_defaults(self):
        self.add_object(datetime, lambda x: x.isoformat())

    def add_object(self, obj, f):
        if not callable(f):
            raise TypeError("'{}' is not callable.".format(f.__class__.__name__))
        self._objects[obj] = f

    def add_attribute(self, attr, f):
        if not callable(f):
            raise TypeError("'{}' is not callable.".format(f.__class__.__name__))
        self._attributes[attr] = f

    def object(self, val):
        if val.__class__ in self._objects:
            overwritten = self._objects[val.__class__](val)
            if isinstance(overwritten, type("")):
                val = overwritten

        return val
    
    def attribute(self, attr, val):
        if attr in self._attributes:
            val = self.attributes[attr]
        return val

    def all(self, attr, val):
        val = self.attribute(attr, val)
        return  self.object(attr, val)


class LdapperModelWrapper:
    def __init__(self, entry):
        self._entry = entry
        self._newValues = {}

    def __getattr__(self, key):
        if key in self._newValues:
            return self._newValues[key]
        else:
            return getattr(self._entry, key).value

    def __setattr__(self, key, value):
        if not key.startswith('_'):
            self._newValues[key] = value
        else:
            self.__dict__[key] = value
