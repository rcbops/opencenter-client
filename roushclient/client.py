#!/usr/bin/env python

import requests
import urlparse
import json
import sys


def pluralize(noun, irregular_nouns={'deer': 'deer'}, vowels='aeiou'):
    if not noun:
        return ''

    if noun in irregular_nouns:
        return irregular_nouns[noun]

    try:
        if noun[-1] == 'y' and noun[-2] not in vowels:
            return noun[:-1] + 'ies'
        elif noun[-1] == 'x':
            return noun + 'en'
        elif noun[-1] == 's':
            if noun[-1] in vowels:
                if noun[-3:] == 'ius':
                    return noun[:-2] + 'i'
                else:
                    return noun[:-1] + 'ses'
            else:
                return noun + 'ses'
        elif noun[-2:] in ['ch', 'sh']:
            return noun + 'es'
    finally:
        pass

    return noun + 's'


class LazyDict:
    def __init__(self, object_type, endpoint):
        self.endpoint = endpoint
        self.object_type = object_type
        self.dict = {}
        self.refreshed = False

    def __iter__(self):
        self._refresh()
        for k in self.dict.keys():
            yield k

    def items(self):
        self._refresh()
        result = []
        for k, v in self.dict.iteritems():
            result.append((k, v))
        return result

    def __str__(self):
        self._refresh()
        if len(self.dict.keys()) == 0:
            return ''
        else:
            representative_node = self.dict[self.dict.keys()[0]]
            field_list = representative_node._printable_cols()

            field_lens = {}

            for field in field_list:
                field_lens[field] = max([len(str(x._resolved_value(field))) + 1
                                            for x in self.dict.values()] +
                                           [len(field.replace('_id', '')) + 1])

            # field_lens = dict([(k,len(k) + 1) for k in field_list])
            output_str = ''
            for k in field_list:
                output_str += ("%%-%ds|" % (field_lens[k],)) % (
                    k.replace('_id', ''),)
            output_str += '\n'

            for k in field_list:
                output_str += ('-' * field_lens[k]) + '|'
            output_str += '\n'

            for k in self.dict.keys():
                output_str += self.dict[k].col_format(separator='|',
                                                      widths=field_lens) + '\n'

            return output_str

    def __getitem__(self, key):
        if not key in self.dict:
            value = roush_types[self.object_type](endpoint=self.endpoint)
            value.id = key
            if value._request_get():
                self.dict[key] = value
                print value
            else:
                value = None
            return value
        else:
            return self.dict[key]

    def __setitem__(self, key, value):
        self.dict[key] = value

    def _refresh(self, force=False):
        if (not self.refreshed) or force:
            self.dict = {}

            r = requests.get(urlparse.urljoin(self.endpoint.endpoint,
                                              pluralize(self.object_type)),
                             headers={'content-type': 'application/json'})

            # FIXME: look the class up in locals
            for item in r.json[pluralize(self.object_type)]:
                obj = roush_types[self.object_type](endpoint=self.endpoint)
                obj._set(item)
                self.dict[obj.id] = obj

            self.refreshed = True

    def keys(self):
        self._refresh()
        return self.dict.keys()

    def values(self):
        self._refresh()
        return self.dict.values()


class RoushEndpoint:
    def __init__(self, endpoint='http://localhost:8080'):
        self.endpoint = endpoint
        self.object_lists = {'nodes': LazyDict('node', self),
                             'clusters': LazyDict('cluster', self),
                             'roles': LazyDict('role', self),
                             'tasks': LazyDict('task', self)}

    def __getattr__(self, name):
        if not name in self.object_lists:
            raise AttributeError("'RoushEndpoint' has no attribute '%s'" %
                                 name)
        else:
            if not self.object_lists[name]:
                self._refresh(name)
            return self.object_lists[name]

    def _refresh(self, name):
        self.object_lists[name]._refresh()

    def Node(self):
        return RoushNode(endpoint=self)

    def Cluster(self):
        return RoushCluster(endpoint=self)

    def Role(self):
        return RoushRole(endpoint=self)

    def Task(self):
        return RoushTask(endpoint=self)


class RoushObject(object):
    def __init__(self,
                 object_type=None,
                 endpoint=RoushEndpoint('http://localhost:8080')):
        self.object_type = object_type
        self.endpoint = endpoint
        self.attributes = {}
        self.friendly_field = 'id'
        self.field_types = {}
        self.synthesized_fields = {}

    def __getattr__(self, name):
        if not name in self.__dict__['attributes']:
            if name + '_id' in self.__dict__['attributes']:
                return self._cross_object(name + '_id')
            elif name in self.synthesized_fields:
                return self.synthesized_fields[name]()
            raise AttributeError("'Roush%s' object has no attribute '%s'" % (
                self.object_type.capitalize(), name))
        return self.attributes[name]

    def __setattr__(self, name, value):
        # print "setting %s => %s" % (str(name), str(value))

        if name in self.__dict__ or name in ['attributes',
                                             'endpoint',
                                             'object_type',
                                             'friendly_field',
                                             'field_types',
                                             'synthesized_fields']:
            object.__setattr__(self, name, value)
        else:
            self.__dict__['attributes'][name] = value

    def _cross_object(self, field):
        try:
            v = self.attributes[field]
        except KeyError:
            raise AttributeError("'Roush%s' object has no attribute '%s'" % (
                self.object_type.capitalize(), field))
        if field.endswith('_id') and v:
            cross_table = field.replace('_id', '')
            cross_object = self.endpoint.object_lists[pluralize(cross_table)][
                int(v)]
            return cross_object
        return None

    def row_format(self):
        if self.attributes:
            max_len = max(map(lambda x: len(x), self.attributes.keys()))
            out_fmt = "%%-%ds: %%s" % max_len
            out_str = ""
            for k in self.attributes:
                v = self._resolved_value(k)

                out_str += out_fmt % (k.replace('_id', ''), v) + '\n'

            return out_str
        else:
            return ''

    def _printable_cols(self):
        types = self._field_types()
        if types:
            field_list = [x for x in self.attributes.keys()
                           if not x in types or types[x] != 'json']
        else:
            field_list = self.attributes.keys()

        if 'id' in field_list:
            field_list.remove('id')
            field_list.insert(0, 'id')

        return field_list

    def col_format(self, widths=None, separator=' '):
        types = self._field_types()
        out_str = ''
        printable_cols = self._printable_cols()

        if self.attributes:
            for k in printable_cols:
                v = self._resolved_value(k)

                format_str = "%s"
                if widths and k in widths:
                    format_str = "%%-%ds" % widths[k]
                out_str += (format_str + '%c') % (str(v), separator)
        return out_str

    def _resolved_value(self, key):
        if key.endswith('_id') and self.attributes[key]:
            v = self.attributes[key]
            cross_object = self._cross_object(key)
            if cross_object:
                cross_lookup = 'unknown (%d)' % v
                try:
                    cross_lookup = cross_object.__getattr__(
                        cross_object._friendly_field())
                except:
                    pass
                return cross_lookup

        return self.attributes[key]

    def __str__(self):
        return self.row_format()

    def _friendly_field(self):
        return self.friendly_field

    def _field_types(self):
        return self.field_types

    def _url_for(self):
        url = urlparse.urljoin(self.endpoint.endpoint,
                               pluralize(self.object_type) + '/')
        if 'id' in self.attributes:
            url = urlparse.urljoin(url, str(self.attributes['id']))
        return url

    def _set(self, attributes):
        # set base attributes
        self.attributes = attributes

    def as_hash(self):
        return self.attributes

    def save(self):
        # post or put, based on whether or not we have an ID field
        if not 'id' in self.attributes:
            self._request_post()
        else:
            self._request_put()

        self.endpoint._refresh(pluralize(self.object_type))

    def delete(self):
        # -XDELETE, raises if no id
        if not 'id' in self.attributes:
            raise ValueError

        self._request_delete()

    def _request(self, request_type, **kwargs):
        r = self._raw_request(request_type, **kwargs)

        try:
            if self.object_type in r.json:
                self._set(r.json[self.object_type])
        finally:
            pass

        if r.status_code < 300 and r.status_code > 199:
            return True
        else:
            return False

    def _raw_request(self,
                     request_type,
                     payload=None,
                     headers={'content-type': 'application/json'},
                     url=None):
        if not url:
            url = self._url_for()

        fn = getattr(requests, request_type)

        if payload:
            payload = json.dumps(payload)

        r = fn(url, data=payload, headers=headers)
        return r

    def _request_put(self):
        return self._request('put', payload=self.attributes)

    def _request_post(self):
        return self._request('post', payload=self.attributes)

    def _request_get(self):
        return self._request('get', payload=self.attributes)

    def _request_delete(self):
        return self._request('delete')


class RoushCluster(RoushObject):
    def __init__(self, **kwargs):
        super(RoushCluster, self).__init__('cluster', **kwargs)
        self.friendly_field = 'name'
        self.fields_types = {'config': 'json'}
        self.synthesized_fields = {'nodes': lambda: self._nodes()}

    def _nodes(self):
        url = urlparse.urljoin(self._url_for() + '/', 'nodes')
        r = self._raw_request('get', url=url)
        if r.status_code < 300 and r.status_code > 199:
            return [self.endpoint.object_lists['nodes'][x['id']]
                    for x in r.json['nodes']]
        else:
            return []


class RoushRole(RoushObject):
    def __init__(self, **kwargs):
        super(RoushRole, self).__init__('role', **kwargs)
        self.friendly_field = 'name'


class RoushNode(RoushObject):
    def __init__(self, **kwargs):
        super(RoushNode, self).__init__('node', **kwargs)
        self.friendly_field = 'hostname'
        self.field_types = {'config': 'json'}


class RoushTask(RoushObject):
    def __init__(self, **kwargs):
        super(RoushTask, self).__init__('task', **kwargs)
        self.field_types = {'payload': 'json'}


roush_types = {'node': RoushNode,
               'role': RoushRole,
               'cluster': RoushCluster,
               'task': RoushTask}


if __name__ == '__main__':
    ep = RoushEndpoint('http://localhost:8080')
    for d in ep.nodes:
        print d