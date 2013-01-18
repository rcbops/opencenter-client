#/usr/bin/env python
import argparse
import os
import sys
import httplib2
import json

from client import RoushEndpoint


class RoushShell():
    endpoint = RoushEndpoint(None)

    def get_base_parser(self):
        parser = argparse.ArgumentParser(description='Roush CLI',
                                         prog='r2',
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
                                   'filter',
                                   'update'],
                                   help='available commands'
                                   )

            for arg in arguments:
                subparser.add_argument('--%s' % arg)
            self.subcommands[command] = subparser
            subparser.set_defaults(func=callback)

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



def main():
    try:
        RoushShell().main(sys.argv[1:])
    except Exception, e:
        print >> sys.stderr, e
        sys.exit(1)

if __name__ == '__main__':
    main()
