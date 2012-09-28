#!/usr/bin/env python

import requests
import urlparse
import json
import sys
import logging


# this might be a trifle naive
def singularize(noun):
    if noun[-1] == 's':
        return noun[:-1]

    return noun[:-1]

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


class SchemaEntry:
    def __init__(self, field_name, schema_entry):
        self.field_name = field_name
        self.schema_entry = schema_entry


class ObjectSchema:
    def __init__(self, endpoint, object_type):
        # we should probably pass endpoints to each object
        # type in the master schema, but we can assume they
        # are regularized.
        self.endpoint = endpoint
        self.object_type = object_type
        schema_uri = "%s/%s/schema" % (endpoint.endpoint,
                                       pluralize(object_type))

        r = requests.get(schema_uri,
                         headers={'content-type': 'application/json'})
        # if we can't get a schema, might as well
        # just let the exception happen
        self.field_schema = r.json['schema']
        self.fields = {}
        for k, v in self.field_schema.items():
            self.fields[k] = SchemaEntry(k, v)


class LazyDict:
    def __init__(self, object_type, endpoint, filter_string = None):
        self.endpoint = endpoint
        self.object_type = object_type
        self.dict = {}
        self.refreshed = False
        self.filter_string = filter_string
        self.schema = None

    def __iter__(self):
        self._refresh()
        for k, v in self.dict.iteritems():
            yield v

    def iteritems(self):
        self._refresh()
        return self.dict.iteritems()

    def create(self, **kwargs):
        return self.new(**kwargs)

    def new(self, **kwargs):
        obj = None

        self._maybe_refresh_schema()

        type_class = "Roush%s" % self.object_type.capitalize()
        if type_class in globals():
            obj = globals()[type_class](endpoint=self.endpoint, **kwargs)
        else:
            # we'll just assume it's a default type.
            # we won't be able to do anything other
            # than crud options, but that's better
            # than nothing.
            obj = RoushObject(object_type=self.object_type,
                              endpoint=self.endpoint,
                              **kwargs)
        return obj

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

            # field_lens = dict([(k, len(k) + 1) for k in field_list])
            output_str = ''
            for k in field_list:
                output_str += ("%%-%ds|" % (field_lens[k],)) % (
                    k.replace('_id', ''),)
            output_str += '\n'

            for k in field_list:
                output_str += ('-' * field_lens[k]) + '|'
            output_str += '\n'

            for k, v in self.dict.iteritems():
                output_str += v.col_format(separator='|',
                                           widths=field_lens) + '\n'

            return output_str

    def __getitem__(self, key):
        if not key in self.dict:
            type_class = "Roush%s" % self.object_type.capitalize()
            if type_class in globals():
                value = globals()[type_class](endpoint=self.endpoint)
            else:
                raise RuntimeError('Cannot find class %s' % type_class)

            value.id = key
            if value._request_get():
                self.dict[key] = value
            else:
                raise KeyError("Roush%s id '%s' not found" %
                               (self.object_type.capitalize(), key))
            return value
        else:
            return self.dict[key]

    def __setitem__(self, key, value):
        self.dict[key] = value

    def filter(self, filter_string):
        return LazyDict(self.object_type, self.endpoint, filter_string)

    def _maybe_refresh_schema(self):
        if not self.schema:
            self.schema = ObjectSchema(self.endpoint, self.object_type)

    def _refresh(self, force=False):
        self._maybe_refresh_schema()

        if (not self.refreshed) or force:
            self.dict = {}
            base_endpoint = urlparse.urljoin(self.endpoint.endpoint,
                                             pluralize(self.object_type)) + '/'

            if self.filter_string:
                r = requests.post(
                    urlparse.urljoin(base_endpoint, 'filter'),
                    headers={'content-type': 'application/json'},
                    data=json.dumps({'filter': self.filter_string}))
            else:
                r = requests.get(
                    base_endpoint,
                    headers={'content-type': 'application/json'})

            for item in r.json[pluralize(self.object_type)]:
                type_class = "Roush%s" % self.object_type.capitalize()
                if type_class in globals():
                    obj = globals()[type_class](endpoint=self.endpoint)
                else:
                    # can we synthesize this class?!?
                    raise RuntimeError('Cannot find class %s' % type_class)

                obj.attributes = item
                self.dict[obj.id] = obj
            self.refreshed = True

    def cached_keys(self):
        return self.dict.keys()

    def cached_values(self):
        return self.dict.values()

    def cached_items(self):
        return self.dict.items()

    def keys(self):
        self._refresh()
        return self.dict.keys()

    def values(self):
        self._refresh()
        return self.dict.values()


class RoushEndpoint:
    def __init__(self, endpoint='http://localhost:8080'):
        self.endpoint = endpoint
        self.logger = logging.getLogger('roush.endpoint')

        r = requests.get('%s/schema' % endpoint)
        try:
            self.master_schema = r.json['schema']
            self.object_lists = {}
            for obj_type in r.json['schema']['objects']:
                self.object_lists[obj_type] = LazyDict(
                    singularize(obj_type), self)
        except:
            raise AttributeError('Invalid endpoint - no /schema')

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

    def _invalidate(self, what, how):
        self.logger.debug('invalidating %s on %s' % (what, how))

    def Node(self, **kwargs):
        return RoushNode(endpoint=self, **kwargs)

    def Cluster(self, **kwargs):
        return RoushCluster(endpoint=self, **kwargs)

    def Role(self, **kwargs):
        return RoushRole(endpoint=self, **kwargs)

    def Task(self, **kwargs):
        return RoushTask(endpoint=self, **kwargs)


class RoushObject(object):
    def __init__(self,
                 object_type=None,
                 endpoint=RoushEndpoint('http://localhost:8080'), **kwargs):
        self.object_type = object_type
        self.endpoint = endpoint
        self.attributes = {}
        self._friendly_field = 'id'
        self._field_types = {}
        self.synthesized_fields = {}
        self.attributes.update(kwargs)
        self.logger = logging.getLogger('roush.%s' % object_type)

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
                                             '_friendly_field',
                                             '_field_types',
                                             'synthesized_fields',
                                             'logger']:
            object.__setattr__(self, name, value)
        else:
            self.__dict__['attributes'][name] = value

    def _cross_object(self, field):
        try:
            v = getattr(self, field)
        except AttributeError:
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
        types = self._field_types
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
        types = self._field_types
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
        if key.endswith('_id') and hasattr(self, key):
            v = getattr(self, key)
            cross_lookup = 'unknown (%s)' % v

            try:
                cross_object = self._cross_object(key)
            except KeyError:
                return cross_lookup

            if cross_object:
                try:
                    cross_lookup = getattr(cross_object,
                                           cross_object._friendly_field)
                except KeyError:
                    pass
                return cross_lookup
        return self.attributes[key]

    def __str__(self):
        return self.row_format()

    def _url_for(self):
        url = urlparse.urljoin(self.endpoint.endpoint + '/',
                               pluralize(self.object_type) + '/')
        if 'id' in self.attributes:
            url = urlparse.urljoin(url, str(self.attributes['id']))
        return url

    def save(self):
        # post or put, based on whether or not we have an ID field
        if not hasattr(self, 'id'):
            self._request_post()
        else:
            self._request_put()
        self.endpoint._refresh(pluralize(self.object_type))

    def delete(self):
        # -XDELETE, raises if no id
        if not hasattr(self, 'id'):
            raise ValueError("No id specified")
        self._request_delete()

    def _request(self, request_type, **kwargs):
        r = self._raw_request(request_type, **kwargs)

        try:
            if self.object_type in r.json:
                self.attributes = r.json[self.object_type]
        except:
            pass
        finally:
            pass

        if r.status_code < 300 and r.status_code > 199:
            self.endpoint._invalidate(self.object_type,
                                      request_type)
            return True
        else:
            self.logger.warn('status code %s on %s' % (
                    r.status_code, request_type))
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
        return self._request('get')

    def _request_delete(self):
        return self._request('delete')


class RoushCluster(RoushObject):
    def __init__(self, **kwargs):
        super(RoushCluster, self).__init__('cluster', **kwargs)
        self._friendly_field = 'name'
        self._field_types = {'config': 'json'}
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
        self._friendly_field = 'name'


class RoushNode(RoushObject):
    def __init__(self, **kwargs):
        super(RoushNode, self).__init__('node', **kwargs)
        self._friendly_field = 'hostname'
        self._field_types = {'config': 'json'}


class RoushTask(RoushObject):
    def __init__(self, **kwargs):
        super(RoushTask, self).__init__('task', **kwargs)
        self._field_types = {'payload': 'json'}


class ClientApp:
    def main(self, argv):
        argv.pop(0)
        uopts = [x for x in argv if not x.startswith('--')]
        fopts = [x.replace('--','') for x in argv if x not in uopts]

        payload=dict([x.split('=') for x in fopts])

        (node_type, op), uopts = uopts[:2], uopts[2:]

        ep = RoushEndpoint()

        obj = ep.object_lists[pluralize(node_type)]

        {'list': lambda: sys.stdout.write(str(obj) + '\n'),
         'show': lambda: sys.stdout.write(str(obj[uopts.pop(0)]) + '\n'),
         'delete': lambda: obj[uopts.pop(0)].delete(),
         'create': lambda: getattr(ep,node_type.capitalize())(**payload).save(),
         'update': lambda: getattr(ep,node_type.capitalize())(id=uopts.pop(0),**payload).save()}[op]()

def main():
    app = ClientApp()
    app.main(sys.argv)

if __name__ == '__main__':
    main()
