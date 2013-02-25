#/usr/bin/env python
import argparse
import os
import sys
import json
import logging

from client import OpenCenterEndpoint, singularize, pluralize


class OpenCenterShell():
    def __init__(self):

        #setup root logger
        self.logger = logging.getLogger('opencenter')

        if "OPENCENTER_CLIENT_DEBUG" in os.environ:
            self.logger.setLevel(logging.DEBUG)

        if not self.logger.handlers:
            self.logger.addHandler(logging.StreamHandler(sys.stderr))

        #Warn if using default endpoint.
        default_endpoint = 'http://localhost:8080'
        if 'OPENCENTER_ENDPOINT' in os.environ:
            endpoint_url = os.environ['OPENCENTER_ENDPOINT']
        else:
            self.logger.warn("OPENCENTER_ENDPOINT not found in environment"
                             ", using %s" % default_endpoint)
            endpoint_url = default_endpoint

        self.endpoint = OpenCenterEndpoint(endpoint=endpoint_url)

    def get_base_parser(self):
        parser = argparse.ArgumentParser(description='OpenCenter CLI',
                                         prog='opencentercli',
                                         )
        parser.add_argument('-v', '--verbose',
                            action='store_true',
                            help='Print more verbose output')

        #chicken-egg issues. Parser requires schema, which reuquires endpoint..
        #parser.add_argument('--endpoint',
        #                    help="OpenCenter endpoint URL.",metavar="URL")

        return parser

    def get_subcommand_parser(self):
        parser = self.get_base_parser()
        self.subcommands = {}
        type_parsers = parser.add_subparsers(help='subcommands',
                                             dest='cli_noun')
        self._construct_parse_tree(type_parsers)
        return parser

    def _construct_parse_tree(self, type_parsers):
        """
        obj_type = object type eg Task, Adventure
        action = command eg create, delete
        argument = required, or optional argument.
        """
        obj_types = self.endpoint._object_lists.keys()

        #information about each action
        actions = {
            'list': {'description': 'list all %ss',
                     'args': [],
                     },
            'show': {'description': 'show the properties of a %s',
                     'args': ['--id']
                     },
            'delete': {'description': 'remove a %s',
                       'args': ['id']
                       },
            'create': {'description': 'create a %s',
                       'args': ['schema']
                       },
            # 'filter',
            'update': {'description': 'modify a %s',
                       'args': ['schema']
                       },
            'execute': {'description': 'execute a %s',
                        'args': ['node_id', 'adventure_id'],
                        'applies_to': ['adventure']
                        },
            'filter': {'description': ('list %ss that match filter-string. '
                                       'Example filter string: name=workspace'),
                       'args': ['filter_string']
                       }
        }

        for obj_type in obj_types:
            schema = self.endpoint.get_schema(singularize(obj_type))
            arguments = schema.field_schema
            callback = getattr(self.endpoint, obj_type)
            desc = callback.__doc__ or ''

            type_parser = type_parsers.add_parser(singularize(obj_type),
                                                  help='%s actions' %
                                                  singularize(obj_type),
                                                  description=desc,
                                                  )

            #"action" clashses with the action attribute of some object types
            #for example task.action, so the action arg is stored as cli_action
            action_parsers = type_parser.add_subparsers(dest='cli_action')
            for action in actions:

                #skip this action if it doesn't apply to this obj_type.
                if 'applies_to' in actions[action]:
                    if singularize(obj_type) not in \
                            actions[action]['applies_to']:
                        continue

                action_parser = action_parsers.add_parser(
                    action,
                    help=actions[action]['description'] % singularize(obj_type)
                )

                action_args = actions[action]['args']
                if action_args == ['schema']:
                    for arg_name, arg in arguments.items():

                        #id should be allocated rather than specified
                        if action == "create" and arg_name == 'id':
                            continue
                        opt_string = '--'
                        if arg['required']:
                            opt_string = ''
                        action_parser.add_argument('%s%s' %
                                                   (opt_string, arg_name))
                else:
                    for arg in action_args:
                        action_parser.add_argument(arg)
            self.subcommands[obj_type] = type_parser
            type_parser.set_defaults(func=callback)

    def get_field_schema(self, command):
        obj = getattr(self.endpoint, command)
        schema = self.endpoint.get_schema(singularize(command))
        fields = schema.field_schema
        return fields

    def do_show(self, args, obj):
        id = args.id
        act = getattr(self.endpoint, obj)
        print act[id]

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

    def do_delete(self, args, obj):
        try:
            id = args.id
            act = getattr(self.endpoint, obj)
            act[id].delete()
            print "%s %s has been deleted." % tuple([obj, id])
        except Exception, e:
            print "%s" % e

    def do_execute(self, args, obj):
        act = getattr(self.endpoint, obj)
        act[args.adventure_id].execute(node=args.node_id)

    def main(self, argv):
        parser = self.get_subcommand_parser()
        args = parser.parse_args(argv)

        if args.cli_action == "list":
            print getattr(self.endpoint, pluralize(args.cli_noun))

        if args.cli_action == "show":
            if args.id is not None:
                #has ID, show individual item
                self.do_show(args, pluralize(args.cli_noun))
            else:
                #no ID specified, list all.
                print getattr(self.endpoint, pluralize(args.cli_noun))

        if args.cli_action == "create":
            self.do_create(args, pluralize(args.cli_noun))

        if args.cli_action == "delete":
            self.do_delete(args, pluralize(args.cli_noun))

        if args.cli_action == "execute":
            self.do_execute(args, pluralize(args.cli_noun))

        if args.cli_action == "filter":
            self.do_filter(args, pluralize(args.cli_noun))


def main():
    if 'OPENCENTER_CLIENT_DEBUG' in os.environ:
        OpenCenterShell().main(sys.argv[1:])
    else:
        try:
            OpenCenterShell().main(sys.argv[1:])
        except Exception, e:
            print >> sys.stderr, e
            sys.exit(1)

if __name__ == '__main__':
    main()
