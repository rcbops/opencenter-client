#!/usr/bin/env python

import code
import copy
import json
import logging
import os
import sys
import traceback
import urlparse
import requests


class Requester(object):
    def __init__(ssl=False, cert=None, roush_ca=None):
        if not cert:
            cert = os.environ.get('ROUSH_CERT', cert)
        if not roush_ca:
            roush_ca = os.environ.get('ROUSH_CA', roush_ca)
        self.verify = not roush_ca is None
        self.requests = requests.Session(cert=cert)
        for m in ['get', 'head', 'post', 'put', 'patch', 'delete']:
            setattr(self, m, partial(self.requests, verify=self.verify))
    def __getattr__(self, attr):
        return getattr(self.requests, attr)


# monkey-patch requests
def get_json(self):
    return json.loads(self.content)

if not hasattr(requests.Response, 'json'):
    requests.Response.json = property(get_json)


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

    def is_fk(self):
        if 'fk' in self.schema_entry:
            return True
        return False

    def fk(self):
        return self.schema_entry['fk'].split('.')

    def is_unique(self):
        return self.schema_entry['unique']

    def type(self):
        if self.schema_entry['type'] == 'INTEGER':
            return 'number'
        elif self.schema_entry['type'] == 'TEXT':
            # how can we distinguish json?
            return 'text'
        elif self.schema_entry['type'] == 'JSON':
            return 'json'
        elif self.schema_entry['type'].startswith('VARCHAR'):
            return 'string'
        else:
            raise RuntimeError('unknown type "%s"' % self.schema_entry['type'])


class ObjectSchema:
    def __init__(self, endpoint, object_type):
        # we should probably pass endpoints to each object
        # type in the master schema, but we can assume they
        # are regularized.
        self.endpoint = endpoint
        self.object_type = object_type
        self.fk = {}
        self.friendly_name = 'id'

        schema_uri = "%s/%s/schema" % (endpoint.endpoint,
                                       pluralize(object_type))

        r = endpoint.requests.get(schema_uri,
                                  headers={'content-type': 'application/json'})
        # if we can't get a schema, might as well
        # just let the exception happen
        self.field_schema = r.json['schema']
        self.fields = {}
        for k, v in self.field_schema.items():
            self.fields[k] = SchemaEntry(k, v)
            if 'fk' in v:
                table, fk = v['fk'].split('.')
                if table in self.fk.keys():
                    raise RuntimeError('multiple fk for %s' % table)

                self.fk[table] = [k, fk]

        # these should really be consistent
        if 'name' in self.field_schema.keys():
            self.friendly_name = 'name'
        elif 'hostname' in self.field_schema.keys():
            self.friendly_name = 'hostname'

    def printable_cols(self):
        field_list = [x for x in self.fields.keys()
                      if self.fields[x].type() != 'json']
        # move id to the front
        if 'id' in field_list:
            field_list.remove('id')
            field_list.insert(0, 'id')

        return field_list

    def has_field(self, field_name):
        return field_name in self.fields.keys()

    def has_fk_for(self, table):
        return table in self.fk

    def fk_for(self, table):
        if table in self.fk:
            return self.fk[table]
        return None


class LazyDict:
    def __init__(self, object_type, endpoint, filter_string=None):
        self.endpoint = endpoint
        self.object_type = object_type
        self.dict = {}
        self.refreshed = False
        self.filter_string = filter_string
        self.schema = None
        self.dirty = False
        self.logger = logging.getLogger('roush.endpoint')

    def __len__(self):
        return len(self.dict)

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
        max_width = 30
        if len(self.dict.keys()) == 0:
            return ''
        else:
            self._maybe_refresh_schema()
            field_list = self.schema.printable_cols()
            field_lens = {}

            for field in field_list:
                field_lens[field] = max([len(str(x._resolved_value(field))) + 1
                                         for x in self.dict.values()] +
                                        [len(field.replace('_id', '')) + 1])
                field_lens[field] = min([field_lens[field], max_width])

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
                # make a generic
                value = RoushObject(object_type=self.object_type,
                                    endpoint=self.endpoint)
            value.id = key
            if value._request_get():
                self.dict[key] = value
            else:
                raise KeyError("Roush%s id '%s' not found" %
                               (self.object_type.capitalize(), key))
            return value
        else:
            # if the table is dirty, refresh the entry
            if self.dirty:
                self.dict[key]._request_get()
            return self.dict[key]

    def __setitem__(self, key, value):
        self.dict[key] = value

    def filter(self, filter_string):
        return LazyDict(self.object_type, self.endpoint, filter_string)

    def first(self):
        self._refresh()
        if len(self.dict) == 0:
            return None
        else:
            return self.dict[self.dict.keys().pop(0)]

    def _maybe_refresh_schema(self):
        if not self.schema:
            self.schema = self.endpoint.get_schema(self.object_type)

    def _refresh(self, force=False):
        self._maybe_refresh_schema()

        # if this table is marked as dirty, then it must refresh
        # itself.
        if (not self.refreshed) or (self.dirty) or force:
            self.dict = {}
            base_endpoint = urlparse.urljoin(self.endpoint.endpoint,
                                             pluralize(self.object_type)) + '/'

            if self.filter_string:
                r = self.endpoint.requests.post(
                    urlparse.urljoin(base_endpoint, 'filter'),
                    headers={'content-type': 'application/json'},
                    data=json.dumps({'filter': self.filter_string}))
                self.logger.debug('payload: %s' % (
                    {'filter': self.filter_string}))
            else:
                r = self.endpoint.requests.get(
                    base_endpoint,
                    headers={'content-type': 'application/json'})

            for item in r.json[pluralize(self.object_type)]:
                type_class = "Roush%s" % self.object_type.capitalize()
                if type_class in globals():
                    obj = globals()[type_class](endpoint=self.endpoint)
                else:
                    # fall back to generic
                    obj = RoushObject(endpoint=self.endpoint,
                                      object_type=self.object_type)
                obj.attributes = item
                self.dict[obj.id] = obj
            self.refreshed = True
            self.dirty = False

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
    def __init__(self, endpoint=None, cert=None, roush_ca=None):
        self.endpoint = endpoint
        if not endpoint:
            self.endpoint = os.environ.get('ROUSH_ENDPOINT',
                                           'http://localhost:8080')
        ssl = self.endpoint.find("https://") == 0
        self.requests = Requester(ssl, cert, roush_ca)

        self.logger = logging.getLogger('roush.endpoint')
        self.schemas = {}

        try:
            r = self.requests.get('%s/schema' % self.endpoint)
        except requests.exceptions.ConnectionError as e:
            self.logger.error(str(e))
            self.logger.error('Could not connect to endpoint %s/schema' % (
                self.endpoint))
            raise requests.exceptions.ConnectionError(
                'could not connect to endpoint %s/schema' % self.endpoint)

        try:
            self.master_schema = r.json['schema']
            self._object_lists = {}
            for obj_type in r.json['schema']['objects']:
                self._object_lists[obj_type] = LazyDict(
                    singularize(obj_type), self)
        except:
            raise AttributeError('Invalid endpoint - no /schema')

    def __getitem__(self, name):
        if name in self._object_lists:
            return self._object_lists[name]
        else:
            raise KeyError(name)

    def __getattr__(self, name):
        if not name in self._object_lists:
            raise AttributeError("'RoushEndpoint' has no attribute '%s'" %
                                 name)
        else:
            if not self._object_lists[name]:
                self._refresh(name, 'list')
            return self._object_lists[name]

    def _refresh(self, what, why):
        self.logger.debug('Refreshing %s for %s' % (what, why))
        self._object_lists[what].dirty = True

    def _invalidate(self, what, how):
        self.logger.debug('invalidating %s on %s' % (what, how))

    def get_schema(self, object_type):
        if not object_type in self.schemas:
            self.schemas[object_type] = ObjectSchema(self, object_type)
        return self.schemas[object_type]

    # These are all deprecated interfaces.  Should now
    # use endpoint.nodes.create(), or endpoint.cluster.create(), etc.

    def Node(self, **kwargs):
        self.logger.debug('DEPRECATED: endpoint.Node()')
        return RoushObject('node', self, **kwargs)

    def Cluster(self, **kwargs):
        self.logger.debug('DEPRECATED: endpoint.Cluster()')
        return RoushCluster(endpoint=self, **kwargs)

    def Role(self, **kwargs):
        self.logger.debug('DEPRECATED: endpoint.Role()')
        return RoushObject('role', self, **kwargs)

    def Task(self, **kwargs):
        self.logger.debug('DEPRECATED: endpoint.Task()')
        return RoushObject('task', self, **kwargs)


class RoushObject(object):
    def __init__(self,
                 object_type=None,
                 endpoint=None, **kwargs):

        # once the schema is set, we can figure out what are
        # fields and what are regular attributes
        object.__setattr__(self, 'schema', endpoint.get_schema(object_type))

        # object.__setattr__(self, 'object_type', object_type)
        # object.__setattr__(self, 'endpoint', endpoint)

        self.object_type = object_type
        self.endpoint = endpoint
        self.attributes = {}
        self.synthesized_fields = {}

        for k, v in kwargs.items():
            setattr(self, k, v)

        self.logger = logging.getLogger('roush.%s' % object_type)

    def __getattr__(self, name):
        if self.schema.has_field(name):
            if not name in self.__dict__['attributes']:
                return None   # valid, but not set
            return self.__dict__['attributes'][name]

        # try looking up along fk
        if self.schema.has_fk_for(pluralize(name)):
            return self._cross_object(pluralize(name))

        # try synthesized fields
        if name in self.synthesized_fields:
            return self.synthesized_fields[name]()

        # uh oh.
        raise AttributeError("'Roush%s' object has no attribute '%s'" % (
                self.object_type.capitalize(), name))

    def __getitem__(self, name):
        return self.__getattr__(name)

    def __setattr__(self, name, value):
        # print "setting %s => %s" % (str(name), str(value))
        if self.schema.has_field(name):
            if self.schema.fields[name].type() == 'json':
                if isinstance(value, str):   # SHOULD I BE DOING THIS?!?!?!
                    value = json.loads(value)
            self.__dict__['attributes'][name] = value
        elif name in ['attributes',
                         'endpoint',
                         'object_type',
                         'synthesized_fields',
                         'logger',
                         'schema']:
            object.__setattr__(self, name, value)
        else:
            raise AttributeError("'Roush%s' object has no attribute '%s'" % (
                    self.object_type.capitalize(), name))

    def _cross_object(self, foreign_table):
        if self.schema.has_fk_for(foreign_table):
            local_field, remote_field = self.schema.fk_for(foreign_table)

            v = getattr(self, local_field)
            if not v:
                return None

            return self.endpoint[foreign_table][int(v)]
        return None

    def to_hash(self):
        return copy.deepcopy(self.__dict__['attributes'])

    def to_dict(self):
        return self.to_hash()

    def row_format(self):
        max_len = max(map(lambda x: len(x), self.schema.fields.keys()))
        out_fmt = "%%-%ds: %%s" % max_len
        out_str = ""
        for k in self.schema.fields.keys():
            v = self._resolved_value(k)
            out_str += out_fmt % (k.replace('_id', ''), v) + '\n'

        return out_str

    def col_format(self, widths=None, separator=' '):
        out_str = ''
        printable_cols = self.schema.printable_cols()

        if self.attributes:
            for k in printable_cols:
                v = self._resolved_value(k)

                format_str = "%s"
                value = str(v).strip()

                if widths and k in widths:
                    maxlen = widths[k]
                    if len(value) > widths[k]:
                        value = value[:maxlen - 4] + '...'
                    format_str = "%%-%ds" % widths[k]

                out_str += (format_str + '%c') % (value, separator)
        return out_str

    def _resolved_value(self, key):
        if self.schema.fields[key].is_fk():
            ctable, cfield = self.schema.fields[key].fk()

            v = getattr(self, key)
            if not v:
                return None

            cross_object = self._cross_object(ctable)

            if not cross_object:
                return 'bad fk (%s)' % v

            return getattr(cross_object, cross_object.schema.friendly_name)

        if key in self.attributes:
            return self.attributes[key]
        else:
            return None

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
        action = 'none'

        if getattr(self, 'id') is None:
            action = 'post'
        else:
            action = 'put'

        getattr(self, '_request_%s' % action)()
        self.endpoint._refresh(pluralize(self.object_type), action)

    def delete(self):
        # -XDELETE, raises if no id
        if not hasattr(self, 'id'):
            raise ValueError("No id specified")
        self._request_delete()

    def _request(self, request_type, **kwargs):
        r = self._raw_request(request_type, **kwargs)

        try:
            if self.object_type in r.json:
                self.logger.debug('got result back: %s' % (
                    r.json[self.object_type]))
                self.logger.debug('got result code: %d' % r.status_code)
                self.attributes = r.json[self.object_type]
        except KeyboardInterrupt:
            raise
        except:
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
        fn = getattr(self.endpoint.requests, request_type)
        if payload:
            payload = json.dumps(payload)
            self.logger.debug('Payload: %s' % (payload))
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


class RoushNode(RoushObject):
    def __init__(self, **kwargs):
        super(RoushNode, self).__init__('node', **kwargs)
        self.synthesized_fields = {'tasks': lambda: self._tasks(),
                                   'task': lambda: self._task(),
                                   'task_blocking': lambda: self._task(True),
                                   'adventures': lambda: self._adventures()}

    # return filtered list of all tasks
    def _tasks(self):
        return self.endpoint['tasks'].filter('host_id=%d' % (
            self.attributes['id']))

    # return next available task
    def _task(self, blocking=False):
        url = urlparse.urljoin(self._url_for() + '/', 'tasks')
        if blocking:
            url += '_blocking'

        r = self._raw_request('get', url=url)
        if r.status_code < 300 and r.status_code > 199:
            return self.endpoint['tasks'][int(r.json['task']['id'])]
        return None

    # return all available adventures
    def _adventures(self):
        url = urlparse.urljoin(self._url_for() + '/', 'adventures')
        r = self._raw_request('get', url=url)
        if r.status_code < 300 and r.status_code > 199:
            adventure_list = map(lambda x: x['id'], r.json['adventures'])
            if len(adventure_list) == 0:
                return None
            return self.endpoint['adventures'].filter(' or '.join(
                map(lambda x: '(id=%d)' % x, adventure_list)))


# this only exists to provide synthesized
class RoushCluster(RoushObject):
    def __init__(self, **kwargs):
        super(RoushCluster, self).__init__('cluster', **kwargs)
        self.synthesized_fields = {'nodes': lambda: self._nodes()}

    def _nodes(self):
        return self.endpoint['nodes'].filter('cluster_id=%d' % (
            self.attributes['id']))


class ClientApp:
    def main(self, argv):
        # logging.basicConfig(level=logging.DEBUG)
        argv.pop(0)
        uopts = [x for x in argv if not x.startswith('--')]
        fopts = [x.replace('--', '') for x in argv if x not in uopts]

        if 'debug' in fopts:
            logging.basicConfig(level=logging.DEBUG)
            fopts.remove('debug')

        payload = dict([x.split('=', 1) for x in fopts])

        endpoint = None
        if 'endpoint' in payload:
            endpoint = payload['endpoint']
            del payload['endpoint']

        ep = RoushEndpoint(endpoint)

        if uopts[0] == 'shell':
            code.interact(local=locals())
            sys.exit(0)

        (node_type, op), uopts = uopts[:2], uopts[2:]

        for opt in payload:
            if payload[opt].startswith('@'):
                payload[opt] = ' '.join(open(payload[opt][1:]).read().split(
                    '\n'))

        obj = ep[pluralize(node_type)]

        # reduce(lambda x, y: x[y], [ "a", "b", "c" ],
        #     { "a": { "b": { "c": 3}}})

        {'list': lambda: sys.stdout.write(str(obj) + '\n'),
         'show': lambda: sys.stdout.write(str(reduce(lambda x, y: x[y],
                                                     uopts, obj)) + '\n'),
         'delete': lambda: obj[uopts.pop(0)].delete(),
         'create': lambda: obj.new(**payload).save(),
         'filter': lambda: sys.stdout.write(str(obj.filter(uopts.pop(0))) +
                                            '\n'),
         'schema': lambda: sys.stdout.write(
             '\n'.join(['%-15s: %s' % (x.field_name, x.type())
                        for x in ep.get_schema(node_type).fields.values()])
             + '\n'),
         'update': lambda: obj.new(id=uopts.pop(0), **payload).save()}[op]()


def main():
    app = ClientApp()
    try:
        app.main(sys.argv)
    except Exception, e:
        print '\nError: %s' % str(e)
        if logging.getLogger().isEnabledFor(logging.DEBUG):
            print ''
            traceback.print_exc()

        sys.exit(1)


if __name__ == '__main__':
    main()
