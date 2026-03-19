from flask.testing import FlaskClient
from walks.db import db
from walks.models import Route, Leg, PaceTier, TimeOverride, Attempt, AttemptLeg


# --- Home & List ---

class TestHome:
    def test_home(self, client: FlaskClient) -> None:
        r = client.get('/')
        assert r.status_code == 200
        assert b'Hills & Runs' in r.data

    def test_list_empty(self, client: FlaskClient) -> None:
        r = client.get('/walks/')
        assert r.status_code == 200
        assert b'No routes yet' in r.data

    def test_list_with_route(self, client: FlaskClient, sample_route: int) -> None:
        r = client.get('/walks/')
        assert r.status_code == 200
        assert b'Mamores' in r.data


# --- Create Route ---

class TestCreateRoute:
    def test_new_form(self, client: FlaskClient) -> None:
        r = client.get('/walks/new')
        assert r.status_code == 200

    def test_create_valid(self, client: FlaskClient) -> None:
        r = client.post('/walks/new', data={
            'name': 'Ben Nevis',
            'latitude': '56.79',
            'longitude': '-5.0',
            'leg_location_0': 'Car Park',
            'leg_distance_0': '0',
            'leg_ascent_0': '0',
            'leg_descent_0': '0',
            'leg_notes_0': '',
        })
        assert r.status_code == 302
        assert '/walks/' in r.headers['Location']

    def test_create_empty_name(self, client: FlaskClient) -> None:
        r = client.post('/walks/new', data={
            'name': '',
            'latitude': '56.8',
            'longitude': '-5.1',
            'leg_location_0': 'Start',
            'leg_distance_0': '0',
            'leg_ascent_0': '0',
            'leg_descent_0': '0',
            'leg_notes_0': '',
        }, follow_redirects=True)
        assert b'name' in r.data.lower()

    def test_create_invalid_latitude(self, client: FlaskClient) -> None:
        r = client.post('/walks/new', data={
            'name': 'Test',
            'latitude': '999',
            'longitude': '-5.1',
            'leg_location_0': 'Start',
            'leg_distance_0': '0',
            'leg_ascent_0': '0',
            'leg_descent_0': '0',
            'leg_notes_0': '',
        }, follow_redirects=True)
        assert b'latitude' in r.data.lower()

    def test_create_no_legs(self, client: FlaskClient) -> None:
        r = client.post('/walks/new', data={
            'name': 'Empty',
            'latitude': '56.8',
            'longitude': '-5.1',
        }, follow_redirects=True)
        assert b'No legs provided' in r.data

    def test_creates_default_pace_tiers(self, client: FlaskClient, sample_route: int) -> None:
        tiers = PaceTier.query.filter_by(route_id=sample_route).all()
        assert len(tiers) == 3


# --- Detail View ---

class TestDetail:
    def test_detail_exists(self, client: FlaskClient, sample_route: int) -> None:
        r = client.get(f'/walks/{sample_route}')
        assert r.status_code == 200
        assert b'Mamores' in r.data
        assert b'Lower Falls' in r.data
        assert b'Binnein Beag' in r.data

    def test_detail_not_found(self, client: FlaskClient) -> None:
        r = client.get('/walks/9999')
        assert r.status_code == 302  # redirects with flash


# --- Edit Route ---

class TestEditRoute:
    def test_edit_form(self, client: FlaskClient, sample_route: int) -> None:
        r = client.get(f'/walks/{sample_route}/edit')
        assert r.status_code == 200
        assert b'Mamores' in r.data

    def test_edit_save(self, client: FlaskClient, sample_route: int) -> None:
        r = client.post(f'/walks/{sample_route}/edit', data={
            'name': 'Mamores Renamed',
            'latitude': '56.8',
            'longitude': '-5.1',
            'leg_location_0': 'New Start',
            'leg_distance_0': '0',
            'leg_ascent_0': '0',
            'leg_descent_0': '0',
            'leg_notes_0': '',
        })
        assert r.status_code == 302
        route = db.session.get(Route, sample_route)
        assert route is not None
        assert route.name == 'Mamores Renamed'

    def test_edit_not_found(self, client: FlaskClient) -> None:
        r = client.get('/walks/9999/edit')
        assert r.status_code == 302


# --- Delete Route ---

class TestDeleteRoute:
    def test_delete(self, client: FlaskClient, sample_route: int) -> None:
        r = client.post(f'/walks/{sample_route}/delete')
        assert r.status_code == 302
        assert db.session.get(Route, sample_route) is None

    def test_delete_cascades_legs(self, client: FlaskClient, sample_route: int) -> None:
        legs_before = Leg.query.filter_by(route_id=sample_route).count()
        assert legs_before > 0
        client.post(f'/walks/{sample_route}/delete')
        assert Leg.query.filter_by(route_id=sample_route).count() == 0

    def test_delete_cascades_pace_tiers(self, client: FlaskClient, sample_route: int) -> None:
        client.post(f'/walks/{sample_route}/delete')
        assert PaceTier.query.filter_by(route_id=sample_route).count() == 0


# --- Settings ---

class TestSettings:
    def test_save_settings(self, client: FlaskClient, sample_route: int) -> None:
        r = client.post(f'/walks/{sample_route}/settings', data={
            'start_time': '05:30',
            'start_date': '2026-06-15',
        })
        assert r.status_code == 302
        route = db.session.get(Route, sample_route)
        assert route is not None
        assert route.start_time == '05:30'
        assert route.start_date == '2026-06-15'

    def test_empty_settings_become_none(self, client: FlaskClient, sample_route: int) -> None:
        client.post(f'/walks/{sample_route}/settings', data={
            'start_time': '',
            'start_date': '',
        })
        route = db.session.get(Route, sample_route)
        assert route is not None
        assert route.start_time is None
        assert route.start_date is None


# --- Pace Tiers ---

class TestPaces:
    def test_save_paces(self, client: FlaskClient, sample_route: int) -> None:
        r = client.post(f'/walks/{sample_route}/paces', data={
            'up_to_0': '60',
            'flat_pace_0': '4.5',
            'ascent_pace_0': '4.5',
            'descent_pace_0': '4.5',
            'up_to_1': '',
            'flat_pace_1': '6.0',
            'ascent_pace_1': '6.0',
            'descent_pace_1': '6.0',
        })
        assert r.status_code == 302
        tiers = PaceTier.query.filter_by(route_id=sample_route).all()
        assert len(tiers) == 2
        bounded = [t for t in tiers if t.up_to_minutes is not None]
        unbounded = [t for t in tiers if t.up_to_minutes is None]
        assert len(bounded) == 1
        assert bounded[0].up_to_minutes == 60
        assert bounded[0].flat_pace_min_per_km == 4.5
        assert len(unbounded) == 1

    def test_save_paces_invalid(self, client: FlaskClient, sample_route: int) -> None:
        r = client.post(f'/walks/{sample_route}/paces', data={
            'up_to_0': '',
            'flat_pace_0': 'not_a_number',
            'ascent_pace_0': '0',
            'descent_pace_0': '0',
        }, follow_redirects=True)
        assert r.status_code == 200  # redirected back with error


# --- Legs (inline edit) ---

class TestLegs:
    def test_save_legs(self, client: FlaskClient, sample_route: int) -> None:
        legs = Leg.query.filter_by(route_id=sample_route).all()
        leg = legs[1]  # second leg (River)
        r = client.post(f'/walks/{sample_route}/legs', data={
            f'distance_{leg.id}': '9.0',
            f'ascent_{leg.id}': '400',
            f'descent_{leg.id}': '100',
            f'notes_{leg.id}': 'updated',
            f'override_{leg.id}': '',
        })
        assert r.status_code == 302
        db.session.refresh(leg)
        assert leg.distance_km == 9.0
        assert leg.ascent_m == 400
        assert leg.notes == 'updated'

    def test_save_leg_with_override(self, client: FlaskClient, sample_route: int) -> None:
        legs = Leg.query.filter_by(route_id=sample_route).all()
        leg = legs[1]
        client.post(f'/walks/{sample_route}/legs', data={
            f'distance_{leg.id}': '8.0',
            f'ascent_{leg.id}': '346',
            f'descent_{leg.id}': '82',
            f'notes_{leg.id}': '',
            f'override_{leg.id}': '55.0',
        })
        override = TimeOverride.query.filter_by(leg_id=leg.id).first()
        assert override is not None
        assert override.override_minutes == 55.0

    def test_clear_override(self, client: FlaskClient, sample_route: int) -> None:
        legs = Leg.query.filter_by(route_id=sample_route).all()
        leg = legs[1]
        # Set override
        client.post(f'/walks/{sample_route}/legs', data={
            f'distance_{leg.id}': '8.0',
            f'ascent_{leg.id}': '346',
            f'descent_{leg.id}': '82',
            f'notes_{leg.id}': '',
            f'override_{leg.id}': '55.0',
        })
        assert TimeOverride.query.filter_by(leg_id=leg.id).count() == 1
        # Clear it
        client.post(f'/walks/{sample_route}/legs', data={
            f'distance_{leg.id}': '8.0',
            f'ascent_{leg.id}': '346',
            f'descent_{leg.id}': '82',
            f'notes_{leg.id}': '',
            f'override_{leg.id}': '',
        })
        assert TimeOverride.query.filter_by(leg_id=leg.id).count() == 0


# --- Attempts ---

class TestAttempts:
    def test_create_attempt(self, client: FlaskClient, sample_route: int) -> None:
        r = client.post(f'/walks/{sample_route}/attempts', data={
            'attempt_name': 'First Go',
            'attempt_date': '2026-06-20',
            'attempt_notes': 'sunny',
        })
        assert r.status_code == 302
        attempt = Attempt.query.filter_by(route_id=sample_route).first()
        assert attempt is not None
        assert attempt.name == 'First Go'
        assert attempt.date == '2026-06-20'

    def test_create_attempt_empty_name(self, client: FlaskClient, sample_route: int) -> None:
        r = client.post(f'/walks/{sample_route}/attempts', data={
            'attempt_name': '',
            'attempt_date': '',
            'attempt_notes': '',
        }, follow_redirects=True)
        assert b'name' in r.data.lower()

    def test_create_attempt_with_leg_times(self, client: FlaskClient, sample_route: int) -> None:
        legs = Leg.query.filter_by(route_id=sample_route).order_by(Leg.leg_num).all()
        data = {
            'attempt_name': 'Timed Run',
            'attempt_date': '2026-06-20',
            'attempt_notes': '',
        }
        for leg in legs:
            data[f'attempt_time_{leg.id}'] = '30.0'
        client.post(f'/walks/{sample_route}/attempts', data=data)
        attempt = Attempt.query.filter_by(route_id=sample_route).first()
        assert attempt is not None
        a_legs = AttemptLeg.query.filter_by(attempt_id=attempt.id).all()
        assert len(a_legs) == len(legs)
        assert all(al.actual_time_minutes == 30.0 for al in a_legs)

    def test_delete_attempt(self, client: FlaskClient, sample_route: int) -> None:
        client.post(f'/walks/{sample_route}/attempts', data={
            'attempt_name': 'To Delete',
            'attempt_date': '',
            'attempt_notes': '',
        })
        attempt = Attempt.query.filter_by(route_id=sample_route).first()
        assert attempt is not None
        r = client.post(f'/walks/{sample_route}/attempts/{attempt.id}/delete')
        assert r.status_code == 302
        assert Attempt.query.filter_by(id=attempt.id).first() is None

    def test_delete_attempt_cascades_legs(self, client: FlaskClient, sample_route: int) -> None:
        legs = Leg.query.filter_by(route_id=sample_route).all()
        data = {
            'attempt_name': 'Cascade Test',
            'attempt_date': '',
            'attempt_notes': '',
        }
        for leg in legs:
            data[f'attempt_time_{leg.id}'] = '25'
        client.post(f'/walks/{sample_route}/attempts', data=data)
        attempt = Attempt.query.filter_by(route_id=sample_route).first()
        assert attempt is not None
        assert AttemptLeg.query.filter_by(attempt_id=attempt.id).count() > 0
        client.post(f'/walks/{sample_route}/attempts/{attempt.id}/delete')
        assert AttemptLeg.query.filter_by(attempt_id=attempt.id).count() == 0
