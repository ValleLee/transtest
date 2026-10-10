import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from qutebrowser.config import qtargs
from qutebrowser.utils import utils

class FakeLibraryInfo:
    TranslationsPath = 1
    root = None

    @classmethod
    def location(cls, _kind):
        return cls.root

class FakeLocale:
    def bcp47Name(self):
        return 'POSIX.UTF-8'

with TemporaryDirectory() as tmp:
    FakeLibraryInfo.root = tmp
    packs = Path(tmp) / 'qtwebengine_locales'
    packs.mkdir()
    (packs / 'en-US.pak').touch()
    val = SimpleNamespace(qt=SimpleNamespace(workarounds=SimpleNamespace(locale=True)))
    fake_version = SimpleNamespace(webengine=utils.VersionNumber(5, 15, 3))
    with patch.object(qtargs.config, 'val', val), \
         patch.object(qtargs.utils, 'is_linux', True), \
         patch.object(qtargs.version, 'qtwebengine_versions', return_value=fake_version), \
         patch.object(qtargs, 'QLibraryInfo', FakeLibraryInfo), \
         patch.object(qtargs, 'QLocale', FakeLocale), \
         patch.dict(os.environ, {'QTWEBENGINE_CHROMIUM_FLAGS': '--disable-gpu'}):
        qtargs._init_locale_workaround()
        flags = os.environ['QTWEBENGINE_CHROMIUM_FLAGS']
        assert flags == '--disable-gpu --lang=en-US', flags
        print('PASS: startup hook appends --lang=en-US and preserves existing flags')
