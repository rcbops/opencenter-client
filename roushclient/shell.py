import argparse
import logging
import os
import sys
import httplib2
import json

from client import RoushEndpoint


class RoushShell(object):
    def get_base_parser(self):
        parser = argparse.ArgumentParser(
            prog='Roush',
            description=__doc__,
            epilog='See "r3 help COMMAND" '
                   'for help on a specific command.',
            add_help=False,
            formatter_class=HelpFormatter
        )

        # Global Arguments
        parser.add_argument('-h', '--help',
                            action='store_true',
                            help=argparse.SUPPRESS,
                            )

        parser.add_argument('-v', '--verbose',
                            action='store_true',
                            help='Print more verbose output'
                            )

        return parser

    def get_subcommand_parser(self, commands):
        parser = self.get_base_parser()

        for command in commands:
            print command

        self.subcommands = commands
        subparsers = parser.add_subparsers(metavar='<subcommand>')

        return parser


    def get_schema(self, endpoint):
        url = ("%s/schema" % endpoint)
        req = httplib2.Http()
        resp, content = req.request(url, "GET")
        data = json.loads(content)

        commands = []
        for k in data['schema']['objects']:
            commands.append(k)

        return commands

    def main(self, argv):
        try:
            ep = RoushEndpoint(None)
        except:
            print >> sys.stderr, e
            sys.exit(1)

        # Get the Roush Server schema
        available_commands = self.get_schema(ep.endpoint)

        # parse args
        parser = self.get_base_parser()
        (options, args) = parser.parse_known_args(argv)

        # build available commands
        subcommand_parser = self.get_subcommand_parser(available_commands)

        # Handle toplevel --help/-h before attempting to parse
        # a command from the command line
        if options.help or not argv:
            self.do_help(parser, options)
            return 0

    def do_help(self, parser, args):
        if getattr(args, 'command', None):
            if args.command in self.subcommands:
                self.subcommands[args.command].print_help()
            else:
                raise "'%s' is not a valid subcommand" % args.command
        else:
            parser.print_help()


class HelpFormatter(argparse.HelpFormatter):
    def start_section(self, heading):
        heading = '%s%s' % (heading[0].upper(), heading[1:])
        super(HelpFormatter, self).start_section(heading)


def main():
    try:
        RoushShell().main(sys.argv[1:])
    except Exception, e:
        print >> sys.stderr, e
        sys.exit(1)


if __name__ == '__main__':
        main()
