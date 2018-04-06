#!/usr/bin/python3

import sys
import re
import argparse
from collections import defaultdict

import audit_pretty
from audit_pretty import format_utils
from audit_pretty.parser import pretty_printers, main_info_filters
from audit_pretty.parsers import *
from audit_pretty.frozendict import FrozenDict


def parse_message(line: str) -> dict:
    trimmed = line.strip()
    if len(trimmed) == 0 or 'audit' not in trimmed:
        return None
    if trimmed.startswith('['):
        # Reading from dmesg, strip timestamp and 'audit:' prefix.
        trimmed = re.sub(r'^\[\d+\.\d+\] audit: ', '', trimmed)
    match = re.fullmatch(r'(type=[0-9_A-Z]+) (?:msg=)?audit\((\d+)\.\d+:\d+\): (.+)', trimmed)
    if match is None:
        return None
    trimmed = match.group(1) + ' ' + 'time=' + match.group(2) + ' ' + match.group(3)
    # audit message is a sequence of values in form key="value" or key='value' or key=value.
    # Value can contain whitespace so we can't just line.split().split('=').
    result = {}
    for match in re.finditer(r'([a-zA-Z\-\_]+)=(?:"(.+?)"|([^ ]+))', trimmed):
        if match.group(2) is not None:
            result[match.group(1)] = match.group(2)
        if match.group(3) is not None:
            result[match.group(1)] = match.group(3)
    for k, v in result.items():
        try:
            if v.isdigit():
                result[k] = int(v)
            if v.startswith('0x'):
                result[k] = int(v, base=16)
        except ValueError:
            pass

    return result


def setup_argparse() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
            description='Linux Auditing System logs pretty printer',
            epilog='Known message types: ' +
                ','.join(filter(lambda x: type(x) == str, pretty_printers.keys())),
            add_help=False)

    dummy = parser.add_argument_group()
    dummy.add_argument('-h', '--help', help='show this text and exit', action='store_true')
    dummy.add_argument('-V', '--version', help='show version and exit', action='store_true')

    filters = parser.add_argument_group('Message filtering')
    filters.add_argument('-s', '--since', help='show only entries since this UNIX timestamp',
                         action='store', default=0, type=int)
    filters.add_argument('-u', '--until', help='show only entries until this UNIX timestamp',
                         action='store', default=2**64-1, type=int)

    group = filters.add_mutually_exclusive_group()
    group.add_argument('-e', '--exclude',
                       help='skip messages with this type; can be specified multiple times',
                       action='append', choices=pretty_printers.keys(), metavar='TYPE', default=[])
    group.add_argument('-i', '--only',
                       help='print only messages with this type; can be specified multiple times',
                       action='append', choices=pretty_printers.keys(), metavar='TYPE', default=[])

    filters.add_argument('--hide-unknown', help='hide messages with unknown type',
                         action='store_true')

    formatting = parser.add_argument_group('Output formatting')

    formatting.add_argument('-v', '--verbose', help='include fields hidden by default',
                            action='store_true')

    formatting.add_argument('-m', '--merge', help='print similar events only once',
                            action='store_true')

    formatting.add_argument('-c', '--count', help='count similar events and print them on EOF',
                            action='store_true')

    formatting.add_argument('--color', help='use ANSI escape codes to color output.',
                            action='store_true', default=sys.stdout.isatty())
    formatting.add_argument('--no-color', help='don\'t use ANSI escape codes to color output.',
                            action='store_false', dest='color')

    return parser


def should_process(args, msg) -> bool:
    # Yes, I want to write this function exactly this way because it's easier to read.
    if msg is None:
        return False

    if msg['time'] < args.since or msg['time'] > args.until:
        return False

    if len(args.exclude) != 0 and msg['type'] in args.exclude or\
       len(args.only) != 0 and msg['type'] not in args.only:
        return False

    if msg['type'] not in pretty_printers and args.hide_unknown:
        return False

    return True


def main():
    parser = setup_argparse()
    args = parser.parse_args()
    if args.help:
        parser.print_help()
        return
    if args.version:
        print('audit_pretty', audit_pretty.__version__)
        print('Copyright (c) 2018 foxcpp. Published under terms of the MIT license.')
        print()
        print('- Bugtracker: https://github.com/foxcpp/audit_pretty/issues')
        print('- Source code: https://github.com/foxcpp/audit_pretty/')
        return

    if args.count:
        args.merge = True
    if not args.color:
        format_utils.styling = defaultdict(lambda: '')
    format_utils.verbose = args.verbose

    already_seen = dict()
    for line in sys.stdin:
        msg = parse_message(line)

        if not should_process(args, msg):
            continue

        main_info = main_info_filters[msg['type']](msg)
        result = pretty_printers[msg['type']](msg)
        if args.merge or args.count:  # Count only if we need it.
            hashable_info = FrozenDict(main_info)
            if hashable_info not in already_seen.keys():
                if not args.count:  # We will print all messages later.
                    print(result)
            already_seen[hashable_info] = already_seen.get(hashable_info, 0) + 1
        else:
            print(result)
    if args.count:
        for info, count in already_seen.items():
            result = pretty_printers[info['type']](info, suffix='(' + str(count) + ')')
            print(result)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass

