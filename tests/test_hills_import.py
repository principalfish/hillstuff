"""Tests for hill ascent CSV importer."""
import pytest
from flask import Flask
from flask.testing import FlaskClient

from hills.ascent_import import parse_ascent_csv, ParsedAscent, ImportResult
from hills.models import Hill, HillAscent
from walks.db import db as _db


# ---------------------------------------------------------------------------
# Unit tests — parse_ascent_csv (no DB)
# ---------------------------------------------------------------------------

HILLS: dict[str, int] = {
    'ben nevis': 1,
    'cairn gorm': 2,
    'buachaille etive mòr': 3,
}


class TestParsing:
    def test_single_ascent(self) -> None:
        result = parse_ascent_csv('Ben Nevis,2023-07-15', HILLS)
        assert result.ok
        assert result.ascents == [ParsedAscent('Ben Nevis', 1, '2023-07-15')]

    def test_multiple_ascents_same_hill(self) -> None:
        result = parse_ascent_csv('Ben Nevis,2023-07-15;2024-08-20', HILLS)
        assert result.ok
        assert len(result.ascents) == 2
        assert result.ascents[0].date == '2023-07-15'
        assert result.ascents[1].date == '2024-08-20'

    def test_header_row_skipped(self) -> None:
        csv = 'hill_name,ascent_dates\nBen Nevis,2023-07-15'
        result = parse_ascent_csv(csv, HILLS)
        assert result.ok
        assert len(result.ascents) == 1

    def test_multiple_hills(self) -> None:
        csv = 'Ben Nevis,2023-07-15\nCairn Gorm,2022-09-03'
        result = parse_ascent_csv(csv, HILLS)
        assert result.ok
        assert len(result.ascents) == 2

    def test_case_insensitive_name(self) -> None:
        result = parse_ascent_csv('ben nevis,2023-07-15', HILLS)
        assert result.ok
        assert result.ascents[0].hill_id == 1

    def test_ddmmyyyy_date_format(self) -> None:
        result = parse_ascent_csv('Ben Nevis,15/07/2023', HILLS)
        assert result.ok
        assert result.ascents[0].date == '2023-07-15'

    def test_mixed_date_formats(self) -> None:
        result = parse_ascent_csv('Ben Nevis,2023-07-15;15/08/2024', HILLS)
        assert result.ok
        assert result.ascents[0].date == '2023-07-15'
        assert result.ascents[1].date == '2024-08-15'

    def test_blank_lines_ignored(self) -> None:
        csv = 'Ben Nevis,2023-07-15\n\n\nCairn Gorm,2022-09-03'
        result = parse_ascent_csv(csv, HILLS)
        assert result.ok
        assert len(result.ascents) == 2

    def test_accented_name(self) -> None:
        result = parse_ascent_csv('Buachaille Etive Mòr,2021-06-01', HILLS)
        assert result.ok
        assert result.ascents[0].hill_id == 3


class TestErrors:
    def test_unknown_hill(self) -> None:
        result = parse_ascent_csv('Not A Hill,2023-07-15', HILLS)
        assert not result.ok
        assert any('not found' in e for e in result.errors)
        assert any('"Not A Hill"' in e for e in result.errors)

    def test_invalid_date(self) -> None:
        result = parse_ascent_csv('Ben Nevis,25-07-2023', HILLS)
        assert not result.ok
        assert any('invalid date' in e for e in result.errors)

    def test_missing_date_column(self) -> None:
        result = parse_ascent_csv('Ben Nevis', HILLS)
        assert not result.ok
        assert any('2 columns' in e for e in result.errors)

    def test_empty_dates(self) -> None:
        result = parse_ascent_csv('Ben Nevis,', HILLS)
        assert not result.ok
        assert any('no dates' in e for e in result.errors)

    def test_empty_hill_name(self) -> None:
        result = parse_ascent_csv(',2023-07-15', HILLS)
        assert not result.ok
        assert any('empty' in e for e in result.errors)

    def test_all_rows_checked_despite_errors(self) -> None:
        # Two bad rows — both should produce errors
        csv = 'Not A Hill,2023-07-15\nAlso Not A Hill,2022-01-01'
        result = parse_ascent_csv(csv, HILLS)
        assert len(result.errors) == 2

    def test_mixed_valid_and_invalid(self) -> None:
        # One valid, one bad — errors block the whole import
        csv = 'Ben Nevis,2023-07-15\nNot A Hill,2022-01-01'
        result = parse_ascent_csv(csv, HILLS)
        assert not result.ok
        assert len(result.ascents) == 1  # valid ascent still parsed
        assert len(result.errors) == 1


# ---------------------------------------------------------------------------
# Integration tests — import route
# ---------------------------------------------------------------------------

@pytest.fixture()
def hills_client(app: Flask, client: FlaskClient) -> FlaskClient:
    """Seed a few munros for route tests."""
    with app.app_context():
        for name, height in [('Ben Nevis', 1345), ('Cairn Gorm', 1245)]:
            _db.session.add(Hill(name=name, height_m=height, rank=1,
                                 region='Lochaber', hill_type='munro'))
        _db.session.commit()
    return client


class TestImportRoute:
    def test_import_page_loads(self, hills_client: FlaskClient) -> None:
        r = hills_client.get('/hills/munros/import')
        assert r.status_code == 200
        assert b'Import Ascents' in r.data
        assert b'hill_name' in r.data

    def test_successful_import(self, app: Flask, hills_client: FlaskClient) -> None:
        r = hills_client.post('/hills/munros/import', data={
            'csv_data': 'Ben Nevis,2023-07-15;2024-08-20\nCairn Gorm,2022-09-03',
        }, follow_redirects=True)
        assert r.status_code == 200
        assert b'Imported 3 ascent(s)' in r.data
        with app.app_context():
            assert HillAscent.query.count() == 3

    def test_import_resets_existing_ascents(self, app: Flask, hills_client: FlaskClient) -> None:
        # First import
        hills_client.post('/hills/munros/import', data={
            'csv_data': 'Ben Nevis,2020-01-01;2021-01-01',
        })
        # Second import for same hill — should replace
        hills_client.post('/hills/munros/import', data={
            'csv_data': 'Ben Nevis,2023-07-15',
        })
        with app.app_context():
            nevis_id = Hill.query.filter_by(name='Ben Nevis').first().id
            ascents = HillAscent.query.filter_by(hill_id=nevis_id).all()
            assert len(ascents) == 1
            assert ascents[0].date == '2023-07-15'

    def test_import_only_resets_included_hills(self, app: Flask, hills_client: FlaskClient) -> None:
        # Seed existing ascent for Cairn Gorm
        hills_client.post('/hills/munros/import', data={
            'csv_data': 'Cairn Gorm,2020-06-01',
        })
        # Import only Ben Nevis — Cairn Gorm should be untouched
        hills_client.post('/hills/munros/import', data={
            'csv_data': 'Ben Nevis,2023-07-15',
        })
        with app.app_context():
            assert HillAscent.query.count() == 2

    def test_unknown_hill_shows_error(self, hills_client: FlaskClient) -> None:
        r = hills_client.post('/hills/munros/import', data={
            'csv_data': 'Not A Munro,2023-07-15',
        })
        assert r.status_code == 200
        assert b'not found' in r.data
        assert b'Not A Munro' in r.data

    def test_invalid_date_shows_error(self, hills_client: FlaskClient) -> None:
        r = hills_client.post('/hills/munros/import', data={
            'csv_data': 'Ben Nevis,25-07-2023',
        })
        assert r.status_code == 200
        assert b'invalid date' in r.data

    def test_empty_submission(self, hills_client: FlaskClient) -> None:
        r = hills_client.post('/hills/munros/import',
                              data={'csv_data': ''},
                              follow_redirects=True)
        assert b'No data' in r.data

    def test_csv_text_repopulated_on_error(self, hills_client: FlaskClient) -> None:
        csv = 'Not A Munro,2023-07-15'
        r = hills_client.post('/hills/munros/import', data={'csv_data': csv})
        assert csv.encode() in r.data
