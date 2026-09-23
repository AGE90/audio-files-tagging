"""
Tests for Discogs client composer-credit extraction.

Run with: pytest tests/test_discogs_client.py -v
"""
from unittest.mock import Mock
from aft.discogs_client import _extract_composer_credit


def _credited(name: str, role: str) -> Mock:
    """Build a fake Artist-like credit as the discogs_client library shapes
    it: .name is a field, the raw API dict (with 'role') lives on .data."""
    artist = Mock()
    artist.name = name
    artist.data = {'role': role, 'name': name}
    return artist


def test_extract_composer_credit_matches_composed_by():
    credits = [_credited('Jane Doe', 'Composed By')]
    assert _extract_composer_credit(credits) == 'Jane Doe'


def test_extract_composer_credit_matches_written_by():
    credits = [_credited('John Smith', 'Written-By')]
    assert _extract_composer_credit(credits) == 'John Smith'


def test_extract_composer_credit_ignores_unrelated_roles():
    """Roles like Remix or Mixed By must not be mistaken for composer credit."""
    credits = [_credited('DJ Someone', 'Remix'), _credited('Mix Engineer', 'Mixed By')]
    assert _extract_composer_credit(credits) == ''


def test_extract_composer_credit_joins_multiple_composers():
    credits = [
        _credited('Composer One', 'Composed By'),
        _credited('Composer Two', 'Written-By'),
    ]
    assert _extract_composer_credit(credits) == 'Composer One, Composer Two'


def test_extract_composer_credit_empty_input():
    assert _extract_composer_credit([]) == ''
    assert _extract_composer_credit(None) == ''
