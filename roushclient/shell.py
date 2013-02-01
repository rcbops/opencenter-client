#/usr/bin/env python
import argparse
import os
import sys
import json

from client import RoushEndpoint


class RoushShell():
    endpoint = RoushEndpoint(None)

    def get_base_parser(self):
        parser = argparse.ArgumentParser(description='Roush CLI',
                                         prog='roushcli',
                                         )
        parser.add_argument('-v', '--verbose',
                            action='store_true',
                            help='Print more verbose output'
                            )

        return parser

    def get_subcommand_parser(self):
        parser = self.get_base_parser()
        self.subcommands = {}
        subparsers = parser.add_subparsers(help='subcommands')
        self._get_actions(subparsers)
        return parser

    def _get_actions(self, subparsers):
        commands = self.endpoint._object_lists.keys()

        for command in commands:
            schema = self.endpoint.get_schema(command[:-1])
            arguments = schema.field_schema
            callback = getattr(self.endpoint, command)
            desc = callback.__doc__ or ''
            help = desc.strip().split('\n')[0]

            subparser = subparsers.add_parser(command[:-1],
                                              help='%s actions' % command[:-1]
                                              )

            subparser.add_argument(command,
                                   choices=['list',
                                   'show',
                                   'delete',
                                   'create',
                                   # 'filter',
                                   'update'],
                                   help='available commands'
                                   )

            for arg in arguments:
                # print arguments[arg]['type']
                subparser.add_argument('--%s' % arg)
            self.subcommands[command] = subparser
            subparser.set_defaults(func=callback)

    def get_field_schema(self, command):
        obj = getattr(self.endpoint, command)
        schema = self.endpoint.get_schema(command[:-1])
        fields = schema.field_schema
        return fields

    def do_show(self, args, obj):
        if not args.id:
            print ("--id <integer> is required for the show command")
            return 0
        try:
            id = args.id
        except Exception, e:
            print "%s" % e

        act = getattr(self.endpoint, obj)
        print act[id]

    def do_create(self, args, obj):
        if not args.name:
            print ("--name <string> is required for the create command")
            return 0
        field_schema = self.get_field_schema(obj)
        arguments = []
        for field in field_schema:
            arguments.append(field)

        ver = dict([(k, v) for k, v in args._get_kwargs()
                   if k in arguments and v is not None])
        act = getattr(self.endpoint, obj)
        try:
            new_node = act.create(**ver)
            new_node.save()
        except Exception, e:
            print "%s" % e

    def do_delete(self, args, obj):
        if not args.id:
            print ("--id <integer is required for the delete command")
            return 0
        try:
            id = args.id
        except Exception, e:
            print "%s" % e

        act = getattr(self.endpoint, obj)
        try:
            act[id].delete()
        except Exception, e:
            print "%s" % e

        print "%s %s has been deleted." % tuple([obj, id])

    def main(self, argv):
        # setup
        parser = self.get_subcommand_parser()
        args = parser.parse_args(argv)

        for command in self.subcommands:
            try:
                action = getattr(args, command)
                obj = command
            except:
                continue

        if action == "list":
            print getattr(self.endpoint, obj)

        if action == "show":
            self.do_show(args, obj)

        if action == "create":
            self.do_create(args, obj)

        if action == "delete":
            self.do_delete(args, obj)


def main():
    try:
        RoushShell().main(sys.argv[1:])
    except Exception, e:
        print >> sys.stderr, e
        sys.exit(1)

if __name__ == '__main__':
    main()
