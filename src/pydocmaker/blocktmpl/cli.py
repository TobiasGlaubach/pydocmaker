"""Command line interface for the block templating engine (``pydocmaker-blocktmpl``).

Subcommands::

    scaffold <file> [--format auto] [--param k=v ...] [-o OUT] [--inplace]
    update <file> --params params.json [-o OUT] [--inplace]
    inspect <file>
    render <file> --body-file f [--params params.json] [-o OUT] [--format auto]

``scaffold``/``update`` write to stdout unless ``-o OUT`` or ``--inplace`` is given.
"""

import argparse
import json
import sys

try:
    from pydocmaker import blocktmpl
except Exception as err:
    from .. import blocktmpl


def _norm_format(fmt):
    return None if fmt in (None, '', 'auto') else fmt


def _read_source(path):
    with open(path, 'r', encoding='utf-8-sig') as f:
        content = f.read()
    had_bom = content.startswith('﻿')
    return content, had_bom


def _write_result(path, content, had_bom, out, inplace):
    if had_bom:
        content = '﻿' + content
    if inplace:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return
    if out:
        with open(out, 'w', encoding='utf-8') as f:
            f.write(content)
        return
    sys.stdout.write(content)


def _parse_param(text):
    try:
        return json.loads(text)
    except Exception:
        return text


def _load_params(path):
    with open(path, 'r', encoding='utf-8-sig') as f:
        return json.load(f)


def cmd_scaffold(args):
    source, had_bom = _read_source(args.file)
    params = {k: _parse_param(v) for k, v in (args.param or [])}
    result = blocktmpl.scaffold(source, tformat=_norm_format(args.format), params=params)
    _write_result(args.file, result, had_bom, args.out, args.inplace)
    return 0


def cmd_update(args):
    source, had_bom = _read_source(args.file)
    params = _load_params(args.params)
    result = blocktmpl.update_params(source, params, tformat=_norm_format(args.format))
    _write_result(args.file, result, had_bom, args.out, args.inplace)
    return 0


def cmd_inspect(args):
    source, _had_bom = _read_source(args.file)
    doc = blocktmpl.parse(source, tformat=_norm_format(args.format))
    print(f'file      : {args.file}')
    print(f'format    : {doc.tformat}')
    print(f'markers   : {"yes" if doc.had_markers else "no"}')
    for kind, attr in (('parameters', 'params_section'), ('body', 'body_section')):
        sec = getattr(doc, attr)
        if sec is None:
            print(f'{kind:<9} : -')
            continue
        rng = f'lines {sec.begin_line + 1}..{sec.end_line + 1}' if sec.end_line >= 0 else f'line {sec.begin_line + 1}..EOF'
        print(f'{kind:<9} : {rng}')
        for name, p in sec.params.items():
            value = '(unset)' if p.value is None else json.dumps(p.value, ensure_ascii=False, default=str)
            print(f'    {name:<20} [{p.kind}] {value}')
    for w in doc.warnings:
        print(f'warning   : {w}')
    return 0


def cmd_render(args):
    source, had_bom = _read_source(args.file)
    params = _load_params(args.params) if args.params else {}
    with open(args.body_file, 'r', encoding='utf-8-sig') as f:
        body = f.read()
    result = blocktmpl.render(source, body, params=params, tformat=_norm_format(args.format))
    _write_result(args.file, result, had_bom, args.out, args.inplace)
    return 0


def build_parser():
    parser = argparse.ArgumentParser(prog='pydocmaker-blocktmpl',
                                     description='Comment-delimited block templating engine for pydocmaker')
    sub = parser.add_subparsers(dest='command', required=True)

    p = sub.add_parser('scaffold', help='insert missing parameters/body blocks into a document')
    p.add_argument('file')
    p.add_argument('--format', default='auto', help="document format ('auto', 'html', 'tex', 'typ')")
    p.add_argument('--param', action='append', nargs=2, metavar=('NAME', 'VALUE'),
                   help='initial parameter value for a scaffolded block (repeatable)')
    p.add_argument('-o', '--out', default=None, help='output file (default: stdout)')
    p.add_argument('--inplace', action='store_true', help='overwrite the input file')
    p.set_defaults(func=cmd_scaffold)

    p = sub.add_parser('update', help='write parameter values back into a document (idempotent)')
    p.add_argument('file')
    p.add_argument('--params', required=True, help='JSON file with parameter values')
    p.add_argument('--format', default='auto', help="document format ('auto', 'html', 'tex', 'typ')")
    p.add_argument('-o', '--out', default=None, help='output file (default: stdout)')
    p.add_argument('--inplace', action='store_true', help='overwrite the input file')
    p.set_defaults(func=cmd_update)

    p = sub.add_parser('inspect', help='print the parsed parameter table of a document')
    p.add_argument('file')
    p.add_argument('--format', default='auto', help="document format ('auto', 'html', 'tex', 'typ')")
    p.set_defaults(func=cmd_inspect)

    p = sub.add_parser('render', help='replace the body block content and apply parameter overrides')
    p.add_argument('file')
    p.add_argument('--body-file', required=True, help='file containing the document body')
    p.add_argument('--params', default=None, help='JSON file with parameter overrides')
    p.add_argument('--format', default='auto', help="document format ('auto', 'html', 'tex', 'typ')")
    p.add_argument('-o', '--out', default=None, help='output file (default: stdout)')
    p.add_argument('--inplace', action='store_true', help='overwrite the input file')
    p.set_defaults(func=cmd_render)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except blocktmpl.BlockTemplatingError as err:
        print(f'error: {err}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
