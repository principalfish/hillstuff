import os
import pytest
from flask import Flask
from flask.testing import FlaskClient

# Use test database
os.environ['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///walks_test.db'

from app import create_app
from walks.db import db as _db
from walks.models import Route, Leg, PaceTier


@pytest.fixture()
def app() -> Flask:
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite://'  # in-memory
    with app.app_context():
        _db.drop_all()
        _db.create_all()
        yield app
        _db.session.rollback()


@pytest.fixture()
def client(app: Flask) -> FlaskClient:
    return app.test_client()


@pytest.fixture()
def db_session(app: Flask):  # type: ignore[no-untyped-def]
    with app.app_context():
        yield _db.session


@pytest.fixture()
def sample_route(client: FlaskClient) -> int:
    """Create a route with 3 legs and return its ID."""
    r = client.post('/walks/new', data={
        'name': 'Mamores',
        'latitude': '56.8',
        'longitude': '-5.1',
        'leg_location_0': 'Lower Falls',
        'leg_distance_0': '0',
        'leg_ascent_0': '0',
        'leg_descent_0': '0',
        'leg_notes_0': '',
        'leg_location_1': 'River',
        'leg_distance_1': '8.0',
        'leg_ascent_1': '346',
        'leg_descent_1': '82',
        'leg_notes_1': '',
        'leg_location_2': 'Binnein Beag',
        'leg_distance_2': '2.1',
        'leg_ascent_2': '637',
        'leg_descent_2': '3',
        'leg_notes_2': 'steep',
    })
    # Extract route_id from redirect location
    loc = r.headers['Location']
    return int(loc.split('/')[-1])
