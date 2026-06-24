"""Unit tests for libtmg.py

Run with:
    python -m pytest tests/
or:
    python -m unittest discover -s tests

Gramps must be installed.  The DBF-dependent import functions are tested by
patching the module-level table globals so no real .dbf files are needed.
"""

import sys
import os
import unittest

# Make sure libtmg is importable from the parent directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import libtmg

from gramps.gen.lib import Date

# ---------------------------------------------------------------------------
# Pure function: _strip_tmg_codes
# ---------------------------------------------------------------------------

class TestStripTmgCodes(unittest.TestCase):

    def test_none_returns_none(self):
        self.assertIsNone(libtmg._strip_tmg_codes(None))

    def test_empty_string_returns_empty(self):
        self.assertEqual(libtmg._strip_tmg_codes(''), '')

    def test_plain_text_unchanged(self):
        self.assertEqual(libtmg._strip_tmg_codes('Hello World'), 'Hello World')

    def test_italic_codes_removed(self):
        self.assertEqual(libtmg._strip_tmg_codes('[:ITAL:]text[:ITAL:]'), 'text')

    def test_cr_code_removed(self):
        self.assertEqual(libtmg._strip_tmg_codes('line1[:CR:]line2'), 'line1line2')

    def test_bold_codes_removed(self):
        self.assertEqual(libtmg._strip_tmg_codes('[BOLD:]text[BOLD:]'), 'text')

    def test_mixed_codes_all_removed(self):
        result = libtmg._strip_tmg_codes('[BOLD:][:ITAL:]hello[:ITAL:][BOLD:]')
        self.assertEqual(result, 'hello')

    def test_whitespace_stripped(self):
        self.assertEqual(libtmg._strip_tmg_codes('  hello  '), 'hello')


# ---------------------------------------------------------------------------
# Pure function: tmg_date_to_gramps_date
# ---------------------------------------------------------------------------

def _raw(date1='19000615', mod='3', date2='00000000', uncertain='0'):
    """Build a 21-char TMG date string.

    Layout:  [0] type-flag  [1:9] date1  [9] old-style  [10] modifier
             [11:19] date2  [19] old-style2  [20] uncertain
    """
    return '1' + date1 + '0' + mod + date2 + '0' + uncertain


class TestTmgDateToGrampsDate(unittest.TestCase):

    def test_none_returns_none(self):
        self.assertIsNone(libtmg.tmg_date_to_gramps_date(None))

    def test_empty_string_returns_none(self):
        self.assertIsNone(libtmg.tmg_date_to_gramps_date(''))

    def test_type_flag_zero_returns_none(self):
        # datefieldtype '0' means no date
        self.assertIsNone(libtmg.tmg_date_to_gramps_date('0' + '0' * 20))

    def test_all_zero_date_returns_none(self):
        # type=1 but all date digits zero → effectively empty
        self.assertIsNone(libtmg.tmg_date_to_gramps_date(_raw(date1='00000000')))

    def test_exact_date_fields(self):
        d = libtmg.tmg_date_to_gramps_date(_raw())
        self.assertEqual(d.get_year(),  1900)
        self.assertEqual(d.get_month(), 6)
        self.assertEqual(d.get_day(),   15)

    def test_before_modifier(self):
        d = libtmg.tmg_date_to_gramps_date(_raw(mod='0'))
        self.assertEqual(d.get_modifier(), Date.MOD_BEFORE)

    def test_say_modifier_maps_to_about(self):
        d = libtmg.tmg_date_to_gramps_date(_raw(mod='1'))
        self.assertEqual(d.get_modifier(), Date.MOD_ABOUT)

    def test_circa_modifier_maps_to_about(self):
        d = libtmg.tmg_date_to_gramps_date(_raw(mod='2'))
        self.assertEqual(d.get_modifier(), Date.MOD_ABOUT)

    def test_exact_modifier(self):
        d = libtmg.tmg_date_to_gramps_date(_raw(mod='3'))
        self.assertEqual(d.get_modifier(), Date.MOD_NONE)

    def test_after_modifier(self):
        d = libtmg.tmg_date_to_gramps_date(_raw(mod='4'))
        self.assertEqual(d.get_modifier(), Date.MOD_AFTER)

    def test_range_modifier(self):
        d = libtmg.tmg_date_to_gramps_date(_raw(mod='5', date2='19501231'))
        self.assertEqual(d.get_modifier(), Date.MOD_RANGE)
        self.assertEqual(d.get_year(),      1900)
        self.assertEqual(d.get_stop_year(), 1950)

    def test_or_modifier_maps_to_range(self):
        d = libtmg.tmg_date_to_gramps_date(_raw(mod='6', date2='19501231'))
        self.assertEqual(d.get_modifier(), Date.MOD_RANGE)

    def test_span_modifier(self):
        d = libtmg.tmg_date_to_gramps_date(_raw(mod='7', date2='19501231'))
        self.assertEqual(d.get_modifier(), Date.MOD_SPAN)

    def test_uncertain_sets_estimated_quality(self):
        d = libtmg.tmg_date_to_gramps_date(_raw(uncertain='1'))
        self.assertEqual(d.get_quality(), Date.QUAL_ESTIMATED)

    def test_say_sets_estimated_quality(self):
        # "Say" (mod=1) also triggers QUAL_ESTIMATED regardless of uncertain flag
        d = libtmg.tmg_date_to_gramps_date(_raw(mod='1'))
        self.assertEqual(d.get_quality(), Date.QUAL_ESTIMATED)

    def test_exact_certain_has_no_quality(self):
        d = libtmg.tmg_date_to_gramps_date(_raw(mod='3', uncertain='0'))
        self.assertEqual(d.get_quality(), Date.QUAL_NONE)


# ---------------------------------------------------------------------------
# Pure functions: num_to_month, num_to_date, parse_date
# ---------------------------------------------------------------------------

class TestNumToMonth(unittest.TestCase):

    def test_january(self):
        self.assertEqual(libtmg.num_to_month('01'), 'Jan')

    def test_september(self):
        self.assertEqual(libtmg.num_to_month('09'), 'Sep')

    def test_december(self):
        self.assertEqual(libtmg.num_to_month('12'), 'Dec')

    def test_integer_input(self):
        self.assertEqual(libtmg.num_to_month(6), 'Jun')


class TestNumToDate(unittest.TestCase):

    def test_full_date(self):
        self.assertEqual(libtmg.num_to_date('20130920'), '20 Sep 2013')

    def test_year_only(self):
        self.assertEqual(libtmg.num_to_date('20130000'), '2013')

    def test_month_year_only(self):
        self.assertEqual(libtmg.num_to_date('20130900'), 'Sep 2013')

    def test_all_zeros_returns_none(self):
        self.assertIsNone(libtmg.num_to_date('00000000'))

    def test_day_month_only(self):
        # YYYY=0000 MM=09 DD=20 → "20 Sep"
        self.assertEqual(libtmg.num_to_date('00000920'), '20 Sep')

    def test_day_only(self):
        self.assertEqual(libtmg.num_to_date('00000020'), '20')

    def test_month_only(self):
        self.assertEqual(libtmg.num_to_date('00000900'), 'Sep')


class TestParseDate(unittest.TestCase):

    def _d(self, date1='19000615', mod='3', date2='00000000', uncertain='0'):
        """Build a TMG date string (same layout as the _raw helper above)."""
        return '1' + date1 + '0' + mod + date2 + '0' + uncertain

    def test_exact_date(self):
        self.assertEqual(libtmg.parse_date(self._d()), '15 Jun 1900')

    def test_before_modifier(self):
        result = libtmg.parse_date(self._d(mod='0'))
        self.assertTrue(result.startswith('Before '))

    def test_say_modifier(self):
        result = libtmg.parse_date(self._d(mod='1'))
        self.assertTrue(result.startswith('Say '))

    def test_circa_modifier(self):
        result = libtmg.parse_date(self._d(mod='2'))
        self.assertTrue(result.startswith('Circa '))

    def test_after_modifier(self):
        result = libtmg.parse_date(self._d(mod='4'))
        self.assertTrue(result.startswith('After '))

    def test_between_modifier(self):
        result = libtmg.parse_date(self._d(mod='5', date2='19501231'))
        self.assertIn('Between', result)
        self.assertIn('1900', result)
        self.assertIn('1950', result)

    def test_or_modifier(self):
        result = libtmg.parse_date(self._d(mod='6', date2='19501231'))
        self.assertIn(' or ', result)

    def test_from_to_modifier(self):
        result = libtmg.parse_date(self._d(mod='7', date2='19501231'))
        self.assertTrue(result.startswith('From '))
        self.assertIn(' to ', result)

    def test_uncertain_flag_adds_question_mark(self):
        result = libtmg.parse_date(self._d(uncertain='1'))
        self.assertTrue(result.endswith('?'))

    def test_certain_flag_no_question_mark(self):
        result = libtmg.parse_date(self._d(uncertain='0'))
        self.assertFalse(result.endswith('?'))

    def test_irregular_date_code_returns_raw(self):
        # type '0' → return the 28-char raw value after the type flag
        raw = '0' + 'about 1900' + ' ' * 18
        result = libtmg.parse_date(raw[:29])
        self.assertEqual(result, raw[1:29])


# ---------------------------------------------------------------------------
# Pure functions: _repo_type_from_name, _url_from_name
# ---------------------------------------------------------------------------

class TestRepoTypeFromName(unittest.TestCase):

    def _t(self, name):
        return libtmg._repo_type_from_name(name)

    def test_website_by_domain(self):
        from gramps.gen.lib import RepositoryType
        self.assertEqual(self._t('ancestry.com'), RepositoryType.WEBSITE)

    def test_website_by_keyword(self):
        from gramps.gen.lib import RepositoryType
        self.assertEqual(self._t('My Online Genealogy Website'), RepositoryType.WEBSITE)

    def test_archive(self):
        from gramps.gen.lib import RepositoryType
        self.assertEqual(self._t('National Archives'), RepositoryType.ARCHIVE)

    def test_library(self):
        from gramps.gen.lib import RepositoryType
        self.assertEqual(self._t('City Library'), RepositoryType.LIBRARY)

    def test_cemetery(self):
        from gramps.gen.lib import RepositoryType
        self.assertEqual(self._t('St John Cemetery'), RepositoryType.CEMETERY)

    def test_church(self):
        from gramps.gen.lib import RepositoryType
        self.assertEqual(self._t('St Mary Parish Church'), RepositoryType.CHURCH)

    def test_default_is_library(self):
        from gramps.gen.lib import RepositoryType
        self.assertEqual(self._t('Unknown Place Name'), RepositoryType.LIBRARY)


class TestUrlFromName(unittest.TestCase):

    def test_bare_domain(self):
        self.assertEqual(libtmg._url_from_name('ancestry.com'),
                         'https://www.ancestry.com')

    def test_www_prefix_preserved(self):
        self.assertEqual(libtmg._url_from_name('www.familysearch.org'),
                         'https://www.familysearch.org')

    def test_no_domain_returns_none(self):
        self.assertIsNone(libtmg._url_from_name('Some Local Library'))

    def test_gov_domain(self):
        url = libtmg._url_from_name('records.gov')
        self.assertEqual(url, 'https://www.records.gov')

    def test_domain_embedded_in_name(self):
        url = libtmg._url_from_name('Ancestry (ancestry.com) family trees')
        self.assertEqual(url, 'https://www.ancestry.com')


if __name__ == '__main__':
    unittest.main()
