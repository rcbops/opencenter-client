#!/usr/bin/env python

import cliapp
import json
import logging
import requests
import sys
import time
from pprint import pprint


class RoushCLI(cliapp.Application):
    def add_settings(self):
        self.settings.string(['api_endpoint'], 'URI for Roush Endpoint',
                             default='http://0.0.0.0:8080')
        self.settings.boolean(['poll'], 'Polls a task after it has been' \
                              'created until it has been completed',
                              default=False)
        self.settings.load_configs()
        self.urls = {"node": self.settings['api_endpoint'] + '/nodes/',
                     "role": self.settings['api_endpoint'] + '/roles/',
                     "cluster": self.settings['api_endpoint'] + '/clusters/',
                     "task": self.settings['api_endpoint'] + '/tasks/'}
        self.headers = {'content-type': 'application/json'}
        self.node_cols = ['id', 'hostname', 'cluster_id', 'role_id', 'config']
        self.cluster_cols = ['id', 'name', 'description', 'config']
        self.task_cols = ['id', 'node_id', 'action', 'payload', 'state', 'result',
                          'submitted', 'expires', 'completed']

    def _list_obj(self, obj):
        r = requests.get(self.urls[obj])
        for item in r.json[obj + 's']:
            print "\n".join("%s: %s" % (i, item[i])
                            for i in self.__getattribute__('%s_cols' % obj)
                            ) + "\n"

    def _delete_obj(self, obj_id, obj):
        r = requests.delete(self.urls[obj] + obj_id,
                            headers=self.headers)
        if r.status_code == 200:
            print "%s %s deleted" % (obj.title(), obj_id)
        else:
            print "Unable to delete %s: %s" % (obj.title(), obj_id)

    def _get_obj(self, obj_id, obj):
        r = requests.get(self.urls[obj] + obj_id,
                         headers=self.headers)
        if r.status_code == 200:
            print "\n".join("%s: %s" % (i, r.json[i])
                            for i in self.__getattribute__('%s_cols' % obj))
        else:
            print "%s %s does not exist" % (obj.title(), obj_id)

    def _update_obj(self, obj_id, obj, payload):
        r = requests.put(self.urls[obj] + obj_id,
                         data=json.dumps(payload),
                         headers=self.headers)
        if r.status_code == 200:
            print "\n".join("%s: %s" % (i, r.json[i])
                            for i in self.__getattribute__('%s_cols' % obj))
        else:
            print "Unable to update %s %s" % (obj.title(), obj_id)

    def _create_obj(self, obj, payload):
        r = requests.post(self.urls[obj],
                          data=json.dumps(payload),
                          headers=self.headers)
        if r.status_code == 201:
            print "\n".join("%s: %s" % (i, r.json[obj][i])
                            for i in self.__getattribute__('%s_cols' % obj))
            return r.json[obj]['id']
        else:
            print "Unable to create %s: %s" % (obj.title(), r.json['message'])

    def cmd_node_list(self, args):
        """List all nodes.
        Positional Arguments: NONE
        """
        self._list_obj('node')

    def cmd_node_get(self, args):
        """Get the details for a node.
        Positional Arguments: <node_id>
        """
        node_id = args[0]
        self._get_obj(node_id, 'node')

    def cmd_node_create(self, args):
        """Create a Node entry.
        Positional Arguments: <hostname> <config>
        """
        config = None if (len(args) < 2) else args[1]
        data = {'hostname': args[0], 'config': config}
        self._create_obj('node', data)

    def cmd_node_delete(self, args):
        """Delete a node.
        Positional Arguments: <node_id>
        """
        node_id = args[0]
        self._delete_obj(node_id, 'node')

    def cmd_node_update(self, args):
        """Create a Node entry.
        Positional Arguments: <node_id> <config>
        """
        node_id = args[0]
        config = None if (len(args) < 2) else args[1]
        data = {'config': config}
        self._update_obj(node_id, 'node', data)

    def cmd_node_update_role(self, args):
        """Assign a node to a role.
        Positional Arguments: <node_id> <role_id>
        """
        node_id = args[0]
        role_id = args[1]
        data = {'role_id': role_id}
        self._update_obj(node_id, 'node', data)

    def cmd_node_update_cluster(self, args):
        """Assign a node to a cluster.
        Positional Arguments: <node_id> <cluster_id>
        """
        node_id = args[0]
        cluster_id = args[1]
        data = {'cluster_id': cluster_id}
        self._update_obj(node_id, 'node', data)

    def cmd_node_task_list(self, args):
        """List the tasks for a node.
        Positional Arguments: <node_id>
        """
        node_id = args[0]
        r = requests.get(self.urls['node'] + node_id + '/tasks/',
                         headers=self.headers)
        if r.status_code == 200:
            #TODO(shep): .doit
            pprint(r)
        else:
            print "No tasks assigned to node %s" % (node_id)
        pass

    def cmd_role_list(self, args):
        """List all roles.
        Positional Arguments: NONE
        """
        self._list_obj('role')

    def cmd_role_get(self, args):
        """Get the details for a role.
        Positional Arguments: <role_id>
        """
        role_id = args[0]
        self._get_obj(role_id, 'role')

#    def cmd_role_create(self, args):
#        """Not Implemented: WONT FIX"""
#        pass
#
#    def cmd_role_delete(self, args):
#        """Not Implemented: WONT FIX"""
#        pass
#
#    def cmd_role_update(self, args):
#        """Not Implemented: WONT FIX"""
#        pass

    def cmd_cluster_list(self, args):
        """List all clusters.
        Positional Arguments: NONE
        """
        self._list_obj('cluster')

    def cmd_cluster_get(self, args):
        """Get the details for a cluster.
        Positional Arguments: <cluster_id>
        """
        cluster_id = args[0]
        self._get_obj(cluster_id, 'cluster')

    def cmd_cluster_create(self, args):
        """Create a Node entry.
        Positional Arguments: <name> <description> <config>
        """
        config = None if (len(args) < 3) else args[2]
        data = {'name': args[0], "description": args[1], 'config': config}
        self._create_obj('cluster', data)

    def cmd_cluster_delete(self, args):
        """Delete a cluster.
        Positional Arguments: <cluster_id>
        """
        cluster_id = args[0]
        self._delete_obj(cluster_id, 'cluster')

    def cmd_cluster_update(self, args):
        """Update a clusters attributes.
        Positional Arguments: <cluster_id> <description> <config>
        """
        #FIXME(shep): This needs validation badly
        cluster_id = args[0]
        desc = args[1]
        config = None if (len(args) < 3) else args[2]
        data = {'description': desc, 'config': config}
        self._update_obj(cluster_id, 'cluster', data)

    def cmd_task_list(self, args):
        """List all tasks.
        Positional Arguments: NONE
        """
        self._list_obj('task')

    def cmd_task_get(self, args):
        """Get the details for a task.
        Positional Arguments: <task_id>
        """
        task_id = args[0]
        self._get_obj(task_id, 'task')

    def cmd_task_create(self, args):
        """Create a task.
           Positional Arguments: <node_id> <action> <payload> <state>
        """
        if len(args) < 4:
            print "Not enough arguments. Required arguments are " \
                  "<node_id> <action> <payload> <state>"
        else:
            node_id = args[0]
            action = args[1]
            payload = args[2]
            state = args[3]
            data = {'node_id': node_id, 'action': action, 'payload': payload,
                    'state': state}
            task_id = str(self._create_obj('task', data))
        if self.settings['poll']:
            # keep checking on the status of the created task until it 
            # is complete
            print "\n--waiting for task to complete--"
            complete = False
            count = 0
            while not complete:
                count += 1
                # do something
                r = requests.get(self.urls['task'] + task_id)
                if r.json['state'] == 'done':
                    complete = True
                    sys.stdout.write('\n--task completed--\n\n')
                    sys.stdout.flush()
                    self.cmd_task_get([task_id])
                else:
                    sys.stdout.write('\r8%sD' % ('=' * count,))
                    sys.stdout.flush()
                    time.sleep(3)
            

#    def cmd_task_delete(self, args):
#        """Not Implemented: WONT FIX"""
#        pass

    def cmd_task_update_state(self, args):
        """Update the state of a task.
           Positional Arguments: <task_id> <state>
        """
        task_id = args[0]
        state = args[1]
        data = {'state': state}
        self._update_obj(task_id, 'task', data)

    def cmd_task_update_result(self, args):
        """Update the state of a task.
           Positional Arguments: <task_id> <result>
        """
        task_id = args[0]
        result = args[1]
        data = {'result': result}
        self._update_obj(task_id, 'task', data)

#    def cmd_task_update(self, args):
#        """Not Implemented: WONT FIX"""
#        pass

    # Convience functions for ron
    def cmd_cluster(self, args):
        """Provides shortcuts to long-name commands:
           .... create -> cluster-create

           .... list -> cluster-list

           .... get -> cluster-get

           .... delete -> cluster-delete

           .... update -> cluster-update
        """
        options = {'create': self.cmd_cluster_create,
                   'list': self.cmd_cluster_list,
                   'get': self.cmd_cluster_get,
                   'delete': self.cmd_cluster_delete,
                   'update': self.cmd_cluster_update}
        cmd = args.pop(0)
        options[cmd](args)

    # Convience functions for ron
    def cmd_node(self, args):
        """Provides shortcuts to long-name commands:
           .... create -> node-create

           .... list -> node-list

           .... get -> node-get

           .... delete -> node-delete

           .... update -> node-update
        """
        options = {'create': self.cmd_node_create,
                   'list': self.cmd_node_list,
                   'get': self.cmd_node_get,
                   'delete': self.cmd_node_delete,
                   'update': self.cmd_node_update}
        cmd = args.pop(0)
        options[cmd](args)

    # Convience functions for ron
    def cmd_task(self, args):
        """Provides shortcuts to long-name commands:
           .... create -> task-create

           .... list -> task-list

           .... get -> task-get
        """
        options = {'create': self.cmd_task_create,
                   'list': self.cmd_task_list,
                   'get': self.cmd_task_get}
        cmd = args.pop(0)
        options[cmd](args)

def main():
    app = RoushCLI(version='1.0.0')
    app.settings.config_files = ['/etc/roush/client_settings.conf',
                                 '~/.roush_clientrc']
    app.run()
