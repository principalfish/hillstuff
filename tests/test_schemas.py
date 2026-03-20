import pytest
from pydantic import ValidationError

from walks.schemas import (
    RouteForm, LegForm, SettingsForm, PaceTierForm, LegUpdateForm, AttemptForm,
)


# --- RouteForm ---

class TestRouteForm:
    def test_valid(self) -> None:
        form = RouteForm.model_validate({'name': 'Test', 'latitude': '56.8', 'longitude': '-5.1'})
        assert form.name == 'Test'
        assert form.latitude == 56.8

    def test_defaults(self) -> None:
        form = RouteForm(name='Test')
        assert form.latitude == 56.8
        assert form.longitude == -5.1

    def test_empty_name_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RouteForm(name='')

    def test_latitude_out_of_range(self) -> None:
        with pytest.raises(ValidationError):
            RouteForm(name='Test', latitude=999)

    def test_longitude_out_of_range(self) -> None:
        with pytest.raises(ValidationError):
            RouteForm(name='Test', longitude=200)

    def test_string_coercion(self) -> None:
        form = RouteForm.model_validate({'name': 'Test', 'latitude': '57.5', 'longitude': '-4.2'})
        assert form.latitude == 57.5
        assert form.longitude == -4.2


# --- LegForm ---

class TestLegForm:
    def test_valid(self) -> None:
        form = LegForm(leg_num=1, location='Start', distance_km=8.55, ascent_m=345.6)
        assert form.distance_km == 8.6  # rounded
        assert form.ascent_m == 346  # rounded

    def test_negative_distance_rejected(self) -> None:
        with pytest.raises(ValidationError):
            LegForm(leg_num=1, location='X', distance_km=-1)

    def test_empty_location_rejected(self) -> None:
        with pytest.raises(ValidationError):
            LegForm(leg_num=1, location='', distance_km=0, ascent_m=0)

    def test_descent_defaults_zero(self) -> None:
        form = LegForm(leg_num=1, location='X', distance_km=0, ascent_m=0)
        assert form.descent_m == 0

    def test_notes_default(self) -> None:
        form = LegForm(leg_num=1, location='X', distance_km=0, ascent_m=0)
        assert form.notes == ''


# --- SettingsForm ---

class TestSettingsForm:
    def test_empty_to_none(self) -> None:
        form = SettingsForm(start_time='', start_date='')
        assert form.start_time is None
        assert form.start_date is None

    def test_whitespace_to_none(self) -> None:
        form = SettingsForm(start_time='   ', start_date='  ')
        assert form.start_time is None
        assert form.start_date is None

    def test_valid_values(self) -> None:
        form = SettingsForm(start_time='06:00', start_date='2026-06-01')
        assert form.start_time == '06:00'
        assert form.start_date == '2026-06-01'

    def test_strips_whitespace(self) -> None:
        form = SettingsForm(start_time='  06:00  ')
        assert form.start_time == '06:00'


# --- PaceTierForm ---

class TestPaceTierForm:
    def test_valid(self) -> None:
        form = PaceTierForm.model_validate({
            'flat_pace_min_per_km': '5.0',
            'ascent_pace': '5.0',
            'descent_pace': '5.0',
        })
        assert form.flat_pace_min_per_km == 5.0
        assert form.up_to_minutes is None

    def test_zero_flat_pace_rejected(self) -> None:
        with pytest.raises(ValidationError):
            PaceTierForm(flat_pace_min_per_km=0)

    def test_negative_ascent_rejected(self) -> None:
        with pytest.raises(ValidationError):
            PaceTierForm(flat_pace_min_per_km=5, ascent_pace=-1)

    def test_with_up_to(self) -> None:
        form = PaceTierForm(flat_pace_min_per_km=5, up_to_minutes=120)
        assert form.up_to_minutes == 120


# --- LegUpdateForm ---

class TestLegUpdateForm:
    def test_valid(self) -> None:
        form = LegUpdateForm.model_validate({
            'distance_km': '8.55',
            'ascent_m': '345',
            'descent_m': '82',
            'notes': 'test',
            'override_minutes': '45.5',
        })
        assert form.distance_km == 8.6
        assert form.override_minutes == 45.5

    def test_empty_override_is_none(self) -> None:
        form = LegUpdateForm.model_validate({
            'distance_km': '8.0',
            'ascent_m': '0',
            'descent_m': '0',
            'override_minutes': '',
        })
        assert form.override_minutes is None

    def test_whitespace_override_is_none(self) -> None:
        form = LegUpdateForm.model_validate({
            'distance_km': '0',
            'ascent_m': '0',
            'descent_m': '0',
            'override_minutes': '   ',
        })
        assert form.override_minutes is None

    def test_negative_distance_rejected(self) -> None:
        with pytest.raises(ValidationError):
            LegUpdateForm(distance_km=-1, ascent_m=0, descent_m=0)


# --- AttemptForm ---

class TestAttemptForm:
    def test_valid(self) -> None:
        form = AttemptForm(name='Test Run', date='2026-06-20', notes='good')
        assert form.name == 'Test Run'
        assert form.date == '2026-06-20'

    def test_empty_name_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AttemptForm(name='')

    def test_empty_date_is_none(self) -> None:
        form = AttemptForm(name='Test', date='', notes='')
        assert form.date is None
        assert form.notes is None

    def test_strips_whitespace(self) -> None:
        form = AttemptForm(name='Test', notes='  hello  ')
        assert form.notes == 'hello'
