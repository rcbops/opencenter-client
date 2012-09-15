#!/usr/bin/env python

import requests
import urlparse
import json
import sys

class RoushEndpoint:
    def __init__(self, endpoint):
        self.endpoint = endpoint
        self.object_lists = {'nodes': None,
                             'clusters': None,
                             'roles': None,
                             'tasks': None}

    def __getattr__(self, name):
        if not name in self.object_lists:
            raise AttributeError
        else:
            if not self.object_lists[name]:
                self._refresh(name)
            return self.object_lists[name]

    def _refresh(self, name):
        self.object_lists[name] = []
        r = requests.get(urlparse.urljoin(self.endpoint, name), headers={'content-type': 'application/json'})
        for item in r.json[name]:
            obj = {'nodes': RoushNode,
                   'roles': RoushRole,
                   'clusters': RoushCluster,
                   'tasks': RoushTask}[name](endpoint=self.endpoint)
            obj._set(item)
            self.object_lists[name].append(obj)


class RoushObject(object):
    def __init__(self, object_type=None, endpoint='http://localhost:8080/'):
        self.object_type = object_type
        self.endpoint = endpoint
        self.attributes = {}

    def __getattr__(self, name):
        if not name in self.attributes.keys():
            raise AttributeError
        return self.attributes[name]

    def __setattr__(self, name, value):
        # print "setting %s => %s" % (str(name), str(value))

        if name in self.__dict__ or name in ['attributes', 'endpoint', 'object_type']:
            object.__setattr__(self, name, value)
        else:
            self.__dict__['attributes'][name] = value

    def __str__(self):
        if self.attributes:
            return '\n'.join([ "%s => %s" % (x, self.attributes[x]) for x in self.attributes ])

    def _pluralize(self, noun):
        # in case we don't use regular nouns!
        vowels = 'aeiou'
        irregular_nouns = {'deer': 'deer'}

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

    def _url_for(self):
        url = urlparse.urljoin(self.endpoint, self._pluralize(self.object_type) + '/')
        if 'id' in self.attributes:
            url = urlparse.urljoin(url, str(self.attributes['id']))
        return url

    def _set(self, attributes):
        # set base attributes
        self.attributes = attributes

    def save(self):
        # post or put, based on whether or not we have an ID field
        print " *** trying to save"
        if not 'id' in self.attributes:
            print "posting"
            self._request_post()
        else:
            print "putting"
            self._request_put()

    def delete(self):
        # -XDELETE, raises if no id
        if not 'id' in self.attributes:
            raise ValueError

        self._request_delete()

    def _request(self, request_type, payload=None, headers={'content-type': 'application/json'}):
        fn = getattr(requests, request_type)

        if payload:
            payload = json.dumps(payload)

        print self._url_for()
        print payload

        r = fn(self._url_for(), data=payload, headers=headers)
        print r.status_code
        print r.content

    def _request_put(self):
        r = self._request('put', self.attributes)

    def _request_post(self):
        r = self._request('post', self.attributes)

    def _request_get(self):
        pass

    def _request_delete(self):
        self._request('delete')



class RoushCluster(RoushObject):
    def __init__(self, **kwargs):
        super(RoushCluster, self).__init__('cluster', **kwargs)


class RoushRole(RoushObject):
    def __init__(self, **kwargs):
        super(RoushRole, self).__init__('role', **kwargs)


class RoushNode(RoushObject):
    def __init__(self, **kwargs):
        super(RoushNode, self).__init__('node', **kwargs)


class RoushTask(RoushObject):
    def __init__(self, **kwargs):
        super(RoushTask, self).__init__('task', **kwargs)

if __name__ == '__main__':
    { 'nodes': { 'list':,
                 'delete',
                 'update',
                 'create'
