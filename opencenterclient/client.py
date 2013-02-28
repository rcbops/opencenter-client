#!/usr/bin/env python
#               OpenCenter(TM) is Copyright 2013 by Rackspace US, Inc.
##############################################################################
#
# OpenCenter is licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.  This
# version of OpenCenter includes Rackspace trademarks and logos, and in
# accordance with Section 6 of the License, the provision of commercial
# support services in conjunction with a version of OpenCenter which includes
# Rackspace trademarks and logos is prohibited.  OpenCenter source code and
# details are available at: # https://github.com/rcbops/opencenter or upon
# written request.
#
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0 and a copy, including this
# notice, is available in the LICENSE file accompanying this software.
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the # specific language governing permissions and limitations
# under the License.
#
##############################################################################

import code
import copy
import json
import logging
import os
import sys
import traceback
import urlparse
import requests
from functools import partial


def ensure_json(f):
    def wrap(*args, **kwargs):
        r = f(*args, **kwargs)
        if not hasattr(r, 'json'):
            r.__dict__['json'] = json.loads(r.content)
        if callable(r.json):
            r.json = r.json()
        return r
    return wrap


class Requester(object):
    def __init__(self, cert=None, opencenter_ca=None,
                 user=None, password=None):
        if not cert:
            cert = os.environ.get('OPENCENTER_CERT', cert)
        if not opencenter_ca:
            opencenter_ca = os.environ.get('OPENCENTER_CA', opencenter_ca)
        self.verify = not opencenter_ca is None
        self.cert = cert
        self.requests = requests
        if user is not None and password is not None:
            auth = (user, password)
        else:
            auth = None
        old = False
        try:
            requests.get("", verify=False)
        except TypeError:
            #old version of requests
            old = True
        except requests.exceptions.URLRequired:
            #newer version
            pass
        except requests.exceptions.MissingSchema:
            #requests 1.1
            pass
        for m in ['get', 'head', 'post', 'put', 'patch', 'delete']:
            if old:
                f = partial(getattr(self.requests, m),
                            auth=auth)
            else:
                f = partial(getattr(self.requests, m),
                            cert=self.cert,
                            verify=self.verify,
                            auth=auth)
            setattr(self, m, ensure_json(f))

    def __getattr__(self, attr):
        return getattr(self.requests, attr)


# this might be a trifle naive
def singularize(noun):
    if noun[-1] == 's':
        return noun[:-1]

    return noun[:-1]


# oddly, this is not a direct inversion of the
# sophisticated "singularize" function
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
        elif self.schema_entry['type'] == 'JSON_ENTRY':
            return 'json_entry'
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


class RequestResult(object):
    def __init__(self, endpoint, response):
        self.response = response
        self.execution_plan = None
        self.endpoint = endpoint

        if self.response.status_code == 409:
            self.execution_plan = ExecutionPlan(self.response.json['plan'])

    def __nonzero__(self):
        if self.response.status_code < 200 or \
                self.response.status_code > 299:
            return False
        return True

    @property
    def requires_input(self):
        if self.response.status_code == 409:
            return True
        return False

    @property
    def deferred_task(self):
        if self.response.status_code == 202:
            return True
        return False

    @property
    def task(self):
        if self.response.status_code != 202:
            return None

        # otherwise, get the task from the reponse
        json_data = self.response.json
        if not 'task' in json_data or \
                not 'id' in json_data['task']:
            return None

        task_id = self.response.json['task']['id']
        return self.endpoint.tasks[task_id]

    @property
    def status_code(self):
        return self.response.status_code

    @property
    def json(self):
        return self.response.json


class ExecutionPlan(object):
    def __init__(self, plan):
        self.raw_plan = plan

    def can_naively_solve(self, value_hash):
        all_args = {}

        for plan_entry in self.raw_plan:
            if 'args' in plan_entry:
                args = plan_entry['args']
                for arg in args:
                    if args[arg].get('required', True):
                        if not arg in value_hash:
                            return False

                        if arg in all_args:
                            return False

                        all_args[arg] = True
        return True

    def naively_solve(self, value_hash):
        if not self.can_naively_solve(value_hash):
            return False

        for plan_entry in self.raw_plan:
            if 'args' in plan_entry:
                args = plan_entry['args']
                for arg in args:
                    if arg in value_hash:
                        args[arg]['value'] = value_hash[arg]

        return True

    def interactively_solve(self):
        for plan_entry in self.raw_plan:
            if 'args' in plan_entry:
                args = plan_entry['args']
                for arg in args:
                    arg_type = args[arg]['type']
                    arg_required = args[arg]['required']
                    arg_choices = args[arg].get('choices', None)
                    arg_default = args[arg].get('default', None)

                    if 'friendly' in args[arg]:
                        print '%s: %s' % (arg, args[arg]['friendly'])

                    if arg_default is not None:
                        prompt = "%s (%s) %s %s" % (
                            arg, arg_type,
                            'REQUIRED' if arg_required else 'OPTIONAL',
                            ' [%s]' % arg_default)
                    else:
                        prompt = '%s (%s) %s' % (
                            arg, arg_type,
                            'REQUIRED' if arg_required else 'OPTIONAL')

                    if arg_choices:
                        prompt += '[Choices: %s]' % ','.join(arg_choices)

                    value = raw_input('%s > ' % prompt)

                    if value == '':
                        value = arg_default

                    if arg_type == 'int':
                        value = int(value)

                    if arg_type == 'interface':
                        value = int(value)

                    plan_entry['args'][arg]['value'] = value

        return self.raw_plan


class LazyDict:
    def __init__(self, object_type, endpoint, filter_string=None):
        self.endpoint = endpoint
        self.object_type = object_type
        self.dict = {}
        self.refreshed = False
        self.filter_string = filter_string
        self.schema = None
        self.dirty = False
        self.logger = logging.getLogger('opencenter.endpoint')

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

        type_class = "OpenCenter%s" % self.object_type.capitalize()
        if type_class in globals():
            obj = globals()[type_class](endpoint=self.endpoint, **kwargs)
        else:
            # we'll just assume it's a default type.
            # we won't be able to do anything other
            # than crud options, but that's better
            # than nothing.
            obj = OpenCenterObject(object_type=self.object_type,
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
            type_class = "OpenCenter%s" % self.object_type.capitalize()
            if type_class in globals():
                value = globals()[type_class](endpoint=self.endpoint)
            else:
                # make a generic
                value = OpenCenterObject(object_type=self.object_type,
                                         endpoint=self.endpoint)
            value.id = key
            if value._request_get():
                self.dict[key] = value
            else:
                raise KeyError("OpenCenter%s id '%s' not found" %
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
                type_class = "OpenCenter%s" % self.object_type.capitalize()
                if type_class in globals():
                    obj = globals()[type_class](endpoint=self.endpoint)
                else:
                    # fall back to generic
                    obj = OpenCenterObject(endpoint=self.endpoint,
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


class OpenCenterEndpoint:
    def __init__(self, endpoint=None, cert=None, opencenter_ca=None,
                 user=None,
                 password=None,
                 interactive=False):
        self.endpoint = endpoint
        self.interactive = interactive
        if endpoint is None:
            self.endpoint = os.environ.get('OPENCENTER_ENDPOINT',
                                           'http://localhost:8080')
        if user is None and password is None:
            user, password, endpoint = get_auth_from_uri(self.endpoint)
            # some versions of requests don't like user:pass in uris
            self.endpoint = endpoint

        self.requests = Requester(cert, opencenter_ca, user, password)

        self.logger = logging.getLogger('opencenter.endpoint')
        self.schemas = {}

        try:
            r = self.requests.get('%s/schema' % self.endpoint)
        except requests.exceptions.ConnectionError as e:
            self.logger.error(str(e))
            self.logger.error('Could not connect to endpoint %s/schema' % (
                self.endpoint))
            raise requests.exceptions.ConnectionError(
                'could not connect to endpoint %s/schema' % self.endpoint)

        if r.status_code == 401:
            r.raise_for_status()

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
            raise AttributeError("'OpenCenterEndpoint' has no attribute '%s'" %
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

    def get_objectlist(self):
        return self._object_lists.keys()

    def get_schema(self, object_type):
        if not object_type in self.schemas:
            self.schemas[object_type] = ObjectSchema(self, object_type)
        return self.schemas[object_type]


class OpenCenterObject(object):
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

        self.logger = logging.getLogger('opencenter.%s' % object_type)

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
        raise AttributeError("'OpenCenter%s' object has no attribute '%s'" %
                             (self.object_type.capitalize(), name))

    def __getitem__(self, name):
        return self.__getattr__(name)

    def __setattr__(self, name, value):
        # print "setting %s => %s" % (str(name), str(value))
        if self.schema.has_field(name):
            field_type = self.schema.fields[name].type()

            if field_type == 'json' or field_type == 'json_entry':
                if isinstance(value, str):   # SHOULD I BE DOING THIS?!?!?!
                    try:
                        value = json.loads(value)
                    except ValueError:
                        # no json... make it a string
                        pass

            self.__dict__['attributes'][name] = value

        elif name in ['attributes',
                      'endpoint',
                      'object_type',
                      'synthesized_fields',
                      'logger',
                      'schema']:
            object.__setattr__(self, name, value)
        else:
            raise AttributeError("'OpenCenter%s' object has no attribute '%s'"
                                 % (self.object_type.capitalize(), name))

    def _cross_object(self, foreign_table):
        if self.schema.has_fk_for(foreign_table):
            local_field, remote_field = self.schema.fk_for(foreign_table)

            v = getattr(self, local_field)
            if not v:
                return None

            try:
                return self.endpoint[foreign_table][int(v)]
            except KeyError:
                # orphaned fk relationship
                return None

        return None

    def to_hash(self):
        return copy.deepcopy(self.__dict__['attributes'])

    def to_dict(self):
        return self.to_hash()

    def row_format(self):
        max_len = max(map(lambda x: len(x), self.schema.fields.keys()))
        out_fmt = "%%-%ds: %%s" % max_len
        pad = '  '.join(('\n', ' ' * max_len))
        out_str = ""
        for k in self.schema.fields.keys():
            v = self._resolved_value(k)
            v = json.dumps(v, sort_keys=True, indent=4)
            v = v.replace('\n', pad)
            str_bits = (out_str, out_fmt % (k.replace('_id', ''), v), '\n')
            out_str = ''.join(str_bits)
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
                return '%s [orphaned]' % v

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

        ret = getattr(self, '_request_%s' % action)()
        self.endpoint._refresh(pluralize(self.object_type), action)
        return ret

    def delete(self):
        # -XDELETE, raises if no id
        if not hasattr(self, 'id'):
            raise ValueError("No id specified")
        self._request_delete()

    def _request(self, request_type, polling=False, **kwargs):
        plan_args = None
        if 'plan_args' in kwargs:
            plan_args = kwargs.pop('plan_args')

        r = RequestResult(self.endpoint,
                          self._raw_request(request_type, **kwargs))
        try:
            self.logger.debug('got result back: %s' % r.json)
            self.logger.debug('got result code: %d' % r.status_code)

            if self.object_type in r.json:
                self.attributes = r.json[self.object_type]
        except KeyboardInterrupt:
            raise
        except:
            pass

        if not r:
            if r.requires_input:
                payload = kwargs.get('payload', {})
                solved = False

                if self.endpoint.interactive:
                    solved = True
                    new_plan = r.execution_plan.interactively_solve()
                elif plan_args is not None:
                    solved = r.execution_plan.naively_solve(plan_args)
                    new_plan = r.execution_plan.raw_plan

                if solved:
                    payload.update({'plan': new_plan})
                    # really, node_id should be the arg for /plan
                    if 'node_id' in payload:
                        payload['node'] = payload['node_id']

                    return self._request(
                        'post', url=self.endpoint.endpoint + '/plan/',
                        payload=payload)

            self.logger.warn('status code %s on %s' %
                             (r.status_code, request_type))
        else:
            self.endpoint._invalidate(self.object_type,
                                      request_type)
        return r

    def _raw_request(self,
                     request_type,
                     payload=None,
                     poll=False,
                     headers={'content-type': 'application/json'},
                     url=None):
        if not url:
            url = "%s%s" % (self._url_for(),
                            '?poll' if poll else '')

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


class OpenCenterTask(OpenCenterObject):
    def __init__(self, **kwargs):
        super(OpenCenterTask, self).__init__('task', **kwargs)
        self.synthesized_fields = {'success': lambda: self._success(),
                                   'running': lambda: self._running(),
                                   'complete': lambda: self._complete(),
                                   'logtail': lambda: self._logtail()}

    def _complete(self):
        return self.state in ['done', 'timeout', 'cancelled']

    def _running(self):
        return self.state in ['running', 'delivered']

    def _success(self):
        return self._complete() and self.state == 'done' and \
            'result_code' in self.result and self.result['result_code'] == 0

    def wait_for_complete(self):
        self._request_get()

        while self.state not in ['done', 'timeout', 'cancelled']:
            self._request('get', poll=True)

    def _logtail(self):
        url = urlparse.urljoin(self._url_for() + '/', 'logs')
        return self._request('get', url=url).json['log']


class OpenCenterAdventure(OpenCenterObject):
    def __init__(self, **kwargs):
        super(OpenCenterAdventure, self).__init__('adventure', **kwargs)

    def execute(self, plan_args=None, **kwargs):
        url = urlparse.urljoin(self._url_for() + '/', 'execute')
        return self._request('post', url=url, plan_args=plan_args,
                             payload=kwargs)


class OpenCenterNode(OpenCenterObject):
    def __init__(self, **kwargs):
        super(OpenCenterNode, self).__init__('node', **kwargs)
        self.synthesized_fields = {'tasks': lambda: self._tasks(),
                                   'task': lambda: self._task(),
                                   'task_blocking': lambda: self._task(True),
                                   'adventures': lambda: self._adventures()}

    # return filtered list of all tasks
    def _tasks(self):
        return self.endpoint['tasks'].filter('node_id=%d' % (
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

    def whoami(self, name):
        url = urlparse.urljoin(self._url_for(), 'whoami')
        return self._request('post', url=url, payload={"hostname": name})


class ClientApp:
    def main(self, argv):
        argv.pop(0)
        uopts = [x for x in argv if not x.startswith('--')]
        fopts = [x.replace('--', '') for x in argv if x not in uopts]

        if 'debug' in fopts:
            logging.basicConfig(level=logging.DEBUG)
            fopts.remove('debug')
        else:
            logging.basicConfig(level=logging.WARN)

        payload = dict([x.split('=', 1) for x in fopts])

        endpoint = None
        if 'endpoint' in payload:
            endpoint = payload['endpoint']
            del payload['endpoint']

        ep = OpenCenterEndpoint(endpoint, interactive=True)

        if uopts[0] == 'shell':
            code.interact(local=locals())
            sys.exit(0)

        (node_type, op), uopts = uopts[:2], uopts[2:]

        for opt in payload:
            if payload[opt].startswith('@'):
                payload[opt] = ' '.join(open(payload[opt][1:]).read().split(
                    '\n'))

        obj = ep[pluralize(node_type)]
        # TODO: if there is no object number on the 'op' call, it
        # should call the class method.
        cmds = {'list': lambda: sys.stdout.write(str(obj) + '\n'),
                'show': lambda: sys.stdout.write(str(
                    reduce(lambda x, y: x[y], uopts, obj)) + '\n'),
                'delete': lambda: obj[uopts.pop(0)].delete(),
                'create': lambda: obj.new(**payload).save(),
                'filter': lambda: sys.stdout.write(str(
                    obj.filter(uopts.pop(0))) + '\n'),
                'schema': lambda: sys.stdout.write(
                '\n'.join(['%-15s: %s' % (x.field_name, x.type())
                           for x in ep.get_schema(node_type).fields.values()])
                + '\n'),
                'update': lambda: obj.new(id=uopts.pop(0), **payload).save()}

        #if the command is in the cmds list, use it, otherwise call
        #the object or class method as appropriate
        cmds.get(op, op_helper(obj, op, uopts, **payload))()


def op_helper(obj, op, uopts, **payload):
    if len(uopts) > 0:
        # this must be an object method
        return lambda: getattr(obj[uopts.pop()], op)(**payload)
    else:
        # this must be a class method
        type_class = "OpenCenter%s" % obj.object_type.capitalize()
        if type_class in globals():
            o = globals()[type_class](endpoint=obj.endpoint, **payload)
        else:
            o = OpenCenterObject
        return lambda: getattr(o, op)(**payload)


def get_auth_from_uri(s):
    try:
        netloc_idx = s.find("://") + 3
        at_idx = s.find("@")
        split_idx = s[netloc_idx:].find(":") + netloc_idx
        if -1 in (netloc_idx, at_idx, split_idx) or not (
                netloc_idx < split_idx
                and split_idx < at_idx):
            return (None, None, s)
        else:
            return (s[netloc_idx:split_idx],
                    s[split_idx + 1: at_idx],
                    s[:netloc_idx] + s[at_idx + 1:])
    except Exception:
        return (None, None, s)


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
