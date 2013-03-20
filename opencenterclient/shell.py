#/usr/bin/env python
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
import argparse
import os
import sys
import json
import logging
import re
import copy

from client import OpenCenterEndpoint, singularize, pluralize


def deep_update(base, updates):
    """
    Update one recursive dict with values from another.
    Modified from:
    http://www.xormedia.com/recursively-merge-dictionaries-in-python/

    Special case: If an updated value is None,
    then the whole subtree is removed from the original dict.
    """
    if not isinstance(updates, dict):
        return updates
    retdict = copy.deepcopy(base)
    for k, v in updates.items():
        if v is None and k in retdict:
            del retdict[k]
            continue
        if k in retdict and isinstance(retdict[k], dict):
            retdict[k] = deep_update(retdict[k], v)
        else:
            retdict[k] = copy.deepcopy(v)
    return retdict


class OpenCenterShell():

    def set_endpoint(self, endpoint_url):
        self.endpoint = OpenCenterEndpoint(endpoint=endpoint_url,
                                           interactive=True)

    def set_log_level(self, level):
        self.logger = logging.getLogger('opencenter')
        self.logger.setLevel(level)
        streamHandler = logging.StreamHandler()
        streamFormat = logging.Formatter('%(asctime)s - %(name)s - '
                                         '%(levelname)s - %(message)s')
        streamHandler.setFormatter(streamFormat)
        self.logger.addHandler(streamHandler)

    def parse_args(self, argv):
        """Parse arguments using Argparse.

        Approach: arg_tree is a multi level dictionary that contains all the
        arguments. This is tree is walked in order to build a
        corresponding tree of ArgumentParsers.

        There is a default set of actions in the actions dictionary that can
        be grafted into the arg_tree to avoid repeating common subcommands.
        This is achieved via the deep_update function.

        """

        if 'OPENCENTER_CLIENT_ARGPARSE_DEBUG' in os.environ:
            arg_debug = True
            self.set_log_level(logging.DEBUG)
        else:
            arg_debug = False

        # Base list of actions. this can be included in the arg_tree as a
        # default set of actions for a noun (eg node, task).

        # help strings will be formated with .format . The argument will be
        # a list representing the path in the tree, eg:
        #       node > list
        #       0      1
        # so {0} will usually refer to the type of object specified.

        # In the help output, Subcommands are listed alphabetically.
        # Argument order can be influenced with an 'order' key under an
        # argument. The default order is 0 and negative numbers sort first.

        # Read Only Actions:
        ro_actions = {
            'list': {
                'help': 'List all {0}s',
                'args': {}
            },
            'show': {
                'help': 'Show the properties of a {0}',
                'args': {
                    'id_or_name': {
                        'help': 'name or id of the {0} to show'
                    },
                    '--property': {
                        'help': 'Only print one property of this '
                                '{0}. Example: --property id. If the '
                                'property is a nested structure, '
                                'then dotted paths can be specified. Example:'
                                ' --property attrs.opencenter_agent_actions.'
                                'upgrade_agent.timeout Lookup tries object'
                                ' attributes, dictionary keys and list '
                                'indices. '
                    }
                }
            },
            'filter': {
                'help': ('list {0}s that match filter-string. '
                         'Example: id=4 or name="workspace"'),
                'args': {
                    'filter_string': {
                        'help': 'filter string, '
                                'Example: id=4 or name="workspace"'
                    }
                }
            }
        }

        #ReadWrite actions = RO actions plus the following:
        rw_actions = deep_update(ro_actions, {
            'delete': {
                'help': 'Delete a {0}',
                'args': {
                    'id_or_name': {
                        'help': 'ID or name of {0} to delete.'
                    }
                }
            },
            'create': {
                'help': 'Create a {0}',
                'args': {
                    'name': {
                        'help': 'Name of the new {0}'
                    }
                }
            },
            'update': {
                'help': 'Modify a {0}',
                'args': {
                    'id_or_name': {
                        'help': 'name or id of {0} to update'
                    }
                }
            },

        })

        # Commands are nodes, args are leaves.
        # When there is a choice of subcommand, the chosen command is stored
        # in the namespace object under the key 'dest'. (The namespace
        # object is the thing returned by ArgumentParser.parse_args())
        arg_tree = {
            'node': {
                'help': 'An opencenter object, may represent a server'
                        ' or a container for other nodes. ',
                'dest': 'cli_action',
                'subcommands': deep_update(rw_actions, {
                    'adventure': {
                        'help': 'Adventure related commands for a node.',
                        'dest': 'node_adventure_subcommand',
                        'subcommands': {
                            'execute': {
                                'help': 'Execute an adventure against this '
                                'node.',
                                'args': {
                                    'node_id_or_name': {
                                        'help': 'Name or ID of node to '
                                                'execute adventure against.',
                                        'order': -1
                                    },
                                    'adventure_id_or_name': {
                                        'help': 'Name or ID of adventure to '
                                                'execute.'
                                    }
                                }
                            },
                            'list': {
                                'help': 'List adventures that can be executed '
                                        'against this node.',
                                'args': {
                                    'node_id_or_name': {}
                                }
                            }
                        }
                    },
                    'update': {
                        'args': {
                            'newname': {
                                'help': 'Specify the new name for an '
                                        'node'
                            }
                        }
                    },
                    'move': {
                        'help': 'Move a node to a different container. This '
                                'is an alias for "fact create node parent_id '
                                'new_parent". This operation is not available'
                                ' if either the node to be moved or '
                                'current/destination container has the '
                                'locked attribute set. ',
                        'args': {
                            'node_id_or_name': {
                                'help': 'id or name of node to move',
                                'order': -1
                            },
                            'new_parent_id_or_name': {
                                'help': 'id or name of container node to '
                                        'move into'
                            }
                        }
                    },
                    'file': {
                        'help': 'list or retrieve files from a node that is '
                                'running the opencenter agent',
                        'args': {
                            'node_id_or_name': {
                                'help': 'Name or ID of the node to list or '
                                        'retrieve files from.',
                                'order': -1
                            },
                            'action': {
                                'choices': ['list', 'get'],
                                'help': 'Retrieve a list of files at a path, '
                                        'or retrieve an individual file',
                                'order': -2
                            },
                            'path': {
                                'help': 'Path to directory to list or file to '
                                        'retrieve. This is a local filesystem '
                                        'path on the system that is running '
                                        'the OpenCenter agent.'
                            }
                        }
                    }

                })
            },
            'task': {
                'help': 'An action that runs against a node',
                'dest': 'cli_action',
                'subcommands': deep_update(rw_actions, {
                    'update': None,
                    'delete': None,
                    'create': {
                        'args': {
                            'name': None,
                            'action': {
                                'help': 'Action for this task to execute. '
                                        'Valid actions are listed in each '
                                        'node\'s opencenter_agent_actions'
                                        'attribute'
                            },
                            'node_id_or_name': {
                                'help': 'Node to execute this action on.',
                                'order': -1
                            },
                            'payload': {
                                'help': 'JSON string containing inputs for '
                                        'the task.',
                                'order': 1
                            }
                        }
                    },
                    'logs': {
                        'help': 'Retrieve task logs',
                        'args': {
                            'task_id': {
                                'help': 'ID of the task to retrieve logs for'
                            },
                            '--offset': {
                                'help': 'Log offset, '
                                        'usage: Display last n bites '
                                        'of'
                                        ' log: --offset -n. Skip first n '
                                        'bites of log: -offset +n. Retrieve '
                                        'whole log: --offset +0'
                                        '  '
                            }
                        }
                    }
                })
            },
            'fact': {
                'help': 'An inheritable property of a node',
                'dest': 'cli_action',
                'subcommands': deep_update(rw_actions, {
                    'create': {
                        'args': {
                            'key': {
                                'help': 'The name of the fact to create'
                            },
                            'value': {
                                'help': 'The value to store against the key'
                            },
                            'node_id_or_name': {
                                'help': 'The node to set this fact against',
                                'order': -1
                            },
                            'name': None
                        }
                    },
                    'update': {
                        'args': {
                            'fact_id': {
                                'help': 'ID of fact to update',
                                'order': -1
                            },
                            'value': {
                                'help': 'new value',
                                'order': 2
                            },
                            'id_or_name': None
                        }
                    }
                })
            },
            'attr': {
                'help': 'A non-inherritable attribute of a node',
                'dest': 'cli_action',
                'subcommands': deep_update(rw_actions, {
                    'create': {
                        'args': {
                            'node_id_or_name': {
                                'help': 'The node to set this attribute on',
                                'order': -1
                            },
                            'key': {
                                'help': 'new key',
                                'order': 1
                            },
                            'value': {
                                'help': 'new value',
                                'order': 2
                            },
                            'name': None
                        }
                    },
                    'update': {
                        'args': {
                            'value': {
                                'help': 'new value',
                                'order': 2
                            }
                        }
                    }
                })
            },
            'adventure': {
                'help': 'A predefined set of tasks for achieving a goal.',
                'dest': 'cli_action',
                'subcommands': deep_update(rw_actions, {
                    'execute': {
                        'help': 'Execute an adventure',
                        'args': {
                            'adventure_id_or_name': {
                                'order': +1
                            },
                            'node_id_or_name': {}
                        }
                    },
                    'create': {
                        'args': {
                            'name': {
                                'help': 'Name of the new Adventure.',
                                'order': -1
                            },
                            'arguments': {
                                'help': 'Arguments for this Adventure, '
                                        'JSON string.',
                                'order': 1
                            },
                            'dsl': {
                                'help': 'Domain Specific Languague for '
                                        'defining adventures. For example: '
                                        '[ {{ "ns": {{}}, "primitive": '
                                        '"download_cookbooks" }} ]',
                                'order': 2
                            },
                            'criteria': {
                                'help': 'Filter string written in the '
                                        'opencenter filter languague.',
                                'order': 3
                            }
                        }
                    },
                    'update': {
                        'args': {
                            'id_or_name': {
                                'help': 'name or id of adventure to update',
                                'order': -1
                            },
                            '--name': {
                                'help': 'New name for this adventure.'
                            },
                            '--arguments': {
                                'help': 'Arguments for this Adventure, '
                                        'JSON string.',
                                'order': 1
                            },
                            '--dsl': {
                                'help': 'Domain Specific Languague for '
                                        'defining adventures. For example: '
                                        '[ {{ "ns": {{}}, "primitive": '
                                        '"download_cookbooks" }} ]',
                                'order': 2
                            },
                            '--criteria': {
                                'help': 'Filter string written in the '
                                        'opencenter filter languague.',
                                'order': 3
                            }
                        }
                    }
                })
            },
            'primitive': {
                'help': 'A low level action that can be executed as part of '
                        'an OpenCenter adventure.',
                'dest': 'cli_action',
                'subcommands': ro_actions
            }
        }

        if arg_debug:
            self.logger.debug(json.dumps(arg_tree, sort_keys=True, indent=2,
                              separators=(',', ':')))

        def _traverse_arg_tree(tree, parser, parents=None, dest="", help="",
                               path=None):
            """Recursive function for walking the arg_tree and building a
            corresponding tree of ArgumentParsers"""

            if len(tree) == 0:
                return

            sub_parsers = None
            for command_name, command_dict in sorted(tree.items(),
                                                     key=lambda x: x[0]):
                _path = copy.deepcopy(path)
                _path.append(command_name)
                if arg_debug:
                    self.logger.debug(_path)
                if 'subcommands' in command_dict:

                    if sub_parsers is None:
                        sub_parsers = parser.add_subparsers(dest=dest,
                                                            help=help)
                    command_parser = sub_parsers.add_parser(
                        command_name,
                        help=command_dict['help'] if
                        'help' in command_dict else "",
                        parents=parents
                    )

                    _traverse_arg_tree(tree=command_dict['subcommands'],
                                       parser=command_parser,
                                       parents=parents,
                                       dest=command_dict['dest'],
                                       help="Commands relating to %s" %
                                            command_name,
                                       path=_path)

                elif 'args' in command_dict:
                    if sub_parsers is None:
                        sub_parsers = parser.add_subparsers(dest=dest,
                                                            help=help)
                    command_parser = sub_parsers.add_parser(
                        command_name,
                        help=command_dict['help'].format(*_path) if
                        'help'in command_dict else '',
                        parents=parents
                    )

                    # parents and dest are not needed as there will be no
                    # more sub levels - the next recusive call will be
                    # adding args, which are the leaves of this tree.
                    _traverse_arg_tree(tree={'args': command_dict['args']},
                                       parser=command_parser,
                                       help="Commands relating to %s" % (
                                           command_name),
                                       path=_path)

                elif command_name == 'args':
                    for arg_name, arg_dict in command_dict.items():
                        if arg_debug:
                            self.logger.debug('%s, %s' % (arg_name,
                                                          str(arg_dict)))
                        if 'order' not in arg_dict:
                            arg_dict['order'] = 0

                    for arg_name, arg_dict in sorted(command_dict.items(),
                                                     key=lambda x: x[1][
                                                         'order']):
                        if 'help' in arg_dict:
                            arg_dict['help'] = arg_dict['help'].format(*_path)
                        del arg_dict['order']
                        parser.add_argument(arg_name, **arg_dict)

        # The global_options parser will be added to all other parsers as a
        # parent. This ensures that these options are available at every
        # level of command.
        global_options = argparse.ArgumentParser(add_help=False)
        global_options.add_argument(
            "--debug",
            help="Print debug information such as API requests",
            action='store_true'
        )

        # Precedence for endpoint URL:
        #      command line option > environment variable > default
        global_options.add_argument(
            '--endpoint',
            default=os.environ['OPENCENTER_ENDPOINT'] if
            'OPENCENTER_ENDPOINT' in os.environ else "http://localhost:8080",
            help="URL to opencenter endpoint. Should be of the form "
                 "http://host:8080 or https://user:pass@host:8443"
        )

        #Root parser - all other commands will be added as sub parsers.
        parser = argparse.ArgumentParser(description='OpenCenter CLI',
                                         prog='opencentercli',
                                         parents=[global_options]
                                         )

        #kick off arg_tree traversal
        _traverse_arg_tree(tree=arg_tree,
                           parser=parser,
                           parents=[global_options],
                           dest="cli_noun",
                           help="subcommands",
                           path=[])

        #parse args and return a namespace object
        return parser.parse_args(argv)

    def get_field_schema(self, command):
        obj = getattr(self.endpoint, command)
        schema = self.endpoint.get_schema(singularize(command))
        fields = schema.field_schema
        return fields

    def do_show(self, args, obj):
        """Print a whole object, or a specific property following a dotted
        path.

        When a dotted path is specified (eg:
        attrs.opencenter_agent_actions.upgrade_agent.timeout),
        lookup is done in three ways:
            1) Object Attribute: getattr
            2) Dictionary key:  []
            3) List Key: convert to int, then []

        """
        id = args.id
        act = getattr(self.endpoint, obj)
        if args.property is None:
            #No property specified, print whole item.
            print act[id]
        else:
            item = act[id]
            for path_section in args.property.split('.'):

                # Lookup by object attribute
                if hasattr(item, path_section):
                    item = getattr(item, path_section)
                    continue
                else:
                    try:
                        # Lookup by dictionary key
                        item = item[path_section]
                        continue
                    except:
                        try:
                            # Lookup by list index
                            item = item[int(path_section)]
                            continue
                        except:
                            pass

                # None of the lookup methods succeeded, so property path must
                # be invalid.
                raise ValueError(
                    'Cannot resolve "%s" from property string "%s" for'
                    ' %s %s' % (
                        path_section,
                        args.property,
                        singularize(obj),
                        act[id].name
                    )
                )

            # Assume the property is JSON and try to pretty-print. If that
            # fails, print the item normally
            try:
                print json.dumps(item, sort_keys=True, indent=2,
                                 separators=(',', ':'))
            except:
                print item

    def do_logs(self, args):
        id = args.task_id
        task = self.endpoint.tasks[id]
        print "=== Logs for task %s: %s > %s ===" % (id, task.node.name,
                                                     task.action)
        print task._logtail(offset=args.offset)
        print "=== End of Logs ==="

    def do_filter(self, args, obj):
        act = getattr(self.endpoint, obj)
        print act.filter(args.filter_string)

    def do_create(self, args, obj):
        field_schema = self.get_field_schema(obj)
        arguments = []
        for field in field_schema:
            arguments.append(field)

        ver = dict([(k, v) for k, v in args._get_kwargs()
                   if k in arguments and v is not None])
        act = getattr(self.endpoint, obj)
        new_node = act.create(**ver)
        new_node.save()
        return new_node

    def do_delete(self, args, obj):
        try:
            id = args.id
            act = getattr(self.endpoint, obj)
            act[id].delete()
            print "%s %s has been deleted." % tuple([obj, id])
        except Exception, e:
            print "%s" % e

    def do_adventure_execute(self, args):
        print "Executing Adventure %s, %s on Node %s, %s" % (
            args.adventure_id,
            self.endpoint.adventures[args.adventure_id].name,
            args.node_id,
            self.endpoint.nodes[args.node_id].name
        )
        self.endpoint.adventures[args.adventure_id].execute(node=args.node_id)

    def do_node_adventure_list(self, args):
        print "Adventures that may be executed against node %s, %s:" % (
            args.node_id, self.endpoint.nodes[args.node_id].name)
        print self.endpoint.nodes[args.node_id]._adventures()

    def do_file(self, args):
        """  List or retrieve files from a node, by creating tasks for the
        files plugin.
        """

        verb = args.action
        if args.action == 'list':
            action = 'files_list'
            args.payload = json.dumps({
                'path': args.path
            })
        if args.action == 'get':
            action = 'files_get'
            args.payload = json.dumps({
                'file': args.path
            })

        args.action = action

        task = self.do_create(args, 'tasks')
        task.wait_for_complete()
        if task._success():
            result = task.result['result_data']

            if args.action == 'files_list':
                for file in sorted(result):
                    print file
            else:
                print result
        else:
            print "Failed to %s %s: %s" % (verb, args.path,
                                           task.result['result_str'])

    def validate_id_or_name(self, obj_type, id_or_name):
        """Get object ID from type and name, or validate that the specified
        ID is valid.

        Returns the ID as an int, not an OpenCenter object.
        """

        obj = getattr(self.endpoint, pluralize(obj_type))

        try:
            id = int(id_or_name)
            return obj[id].id

        except ValueError:
            # can't convert string to int, try lookup by name
            matches = [x[1] for x in obj.filter(
                "name='%s'" % id_or_name).items()]
            if len(matches) == 1:
                return matches[0].id
            elif len(matches) == 0:
                raise ValueError('No %s found for id or name %s' %
                                 (obj_type, id_or_name))
            elif len(matches) > 1:

                match_string = "\n".join(map(str, matches))
                raise ValueError("Multiple %ss matched name %s, "
                                 "please specify an ID "
                                 "instead.\n\nMatches:\n%s" %
                                 (obj_type, id_or_name, match_string))

        except KeyError:
            #obj[id] lookup failed, so ID is an int but not a valid ID.
            raise ValueError('No %s found for ID %s' % (obj_type, id_or_name))

    def main(self, argv):
        args = self.parse_args(argv)

        if args.debug:
            self.set_log_level(logging.DEBUG)
            self.logger.debug("CLI arguments: %s" % str(args))
        else:
            self.set_log_level(logging.WARNING)

        try:
            self.set_endpoint(args.endpoint)
        except Exception, e:
            print "'%s' is not a valid endpoint. Please specify a valid " \
                  "endpoint in environment variable OPENCENTER_ENDPOINT" \
                  " or using the command line option --endpoint. The " \
                  "endpoint string should follow one of these forms: " \
                  "http://host:8080 or " \
                  "https://user:pass@host:8443" % args.endpoint
            self.logger.debug(e)
            return

        #Resolve name or id fields into valid IDs.
        id_or_name_re = re.compile(
            '((?P<obj_type>[a-zA-Z0-9]*)_)?id(_or_name)?')
        for arg, value in args.__dict__.items():
            match = id_or_name_re.match(arg)
            if match:
                groups = match.groupdict()
                try:
                    if 'obj_type' in groups and groups['obj_type'] is not \
                            None:
                        attr_name = '%s_id' % groups['obj_type']
                        obj_type = groups['obj_type']
                    else:
                        attr_name = 'id'
                        obj_type = args.cli_noun

                    setattr(
                        args,
                        attr_name,
                        self.validate_id_or_name(obj_type, value)
                    )

                except ValueError, e:
                    print e
                    return

        #Adventure has an arg called args, this conflicts with the arg_tree
        # structure, so I called the args arg arguments. At this point it
        # can be renamed back to args.
        if hasattr(args, 'arguments'):
            args.args = args.arguments
            del args.arguments

        if args.cli_action == "list":
            print getattr(self.endpoint, pluralize(args.cli_noun))

        if args.cli_action == "show":
            #has ID, show individual item
            self.do_show(args, pluralize(args.cli_noun))

        if args.cli_action == "create":
            self.do_create(args, pluralize(args.cli_noun))

        if args.cli_action == "delete":
            self.do_delete(args, pluralize(args.cli_noun))

        if args.cli_action == "update":
            self.do_create(args, pluralize(args.cli_noun))

        if args.cli_action == "adventure":
            if args.node_adventure_subcommand == 'execute':
                self.do_adventure_execute(args)
            elif args.node_adventure_subcommand == 'list':
                self.do_node_adventure_list(args)

        #adventure execute is an alias for node adventure execute
        if args.cli_noun == "adventure" and args.cli_action == "execute":
            self.do_adventure_execute(args)

        if args.cli_action == "filter":
            self.do_filter(args, pluralize(args.cli_noun))

        if args.cli_action == "adventures":
            self.do_adventures(args, pluralize(args.cli_noun))

        if args.cli_action == "logs":
            self.do_logs(args)

        # node move is an alias for fact create parent_id
        if args.cli_noun == "node" and args.cli_action == "move":
            args.key = "parent_id"
            args.value = self.validate_id_or_name(
                'node', args.new_parent_id_or_name)
            self.do_create(args, 'facts')

        if args.cli_noun == "node" and args.cli_action == "file":
            self.do_file(args)


def main():
    print "test patch"
    if 'OPENCENTER_CLIENT_DEBUG' in os.environ:
        OpenCenterShell().main(sys.argv[1:])
        return
    else:
        try:
            OpenCenterShell().main(sys.argv[1:])
        except Exception, e:
            print >> sys.stderr, e

            sys.exit(1)

if __name__ == '__main__':
    main()
