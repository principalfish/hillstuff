from walks.db import db
from sqlalchemy import func


class Route(db.Model):
    __tablename__ = 'routes'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, nullable=False)
    latitude = db.Column(db.Float, default=56.8)
    longitude = db.Column(db.Float, default=-5.1)
    start_time = db.Column(db.Text, default='06:00')
    start_date = db.Column(db.Text, default='2026-06-01')
    created_at = db.Column(db.DateTime, server_default=func.now())

    legs = db.relationship('Leg', backref='route', cascade='all, delete-orphan',
                           order_by='Leg.leg_num')
    pace_tiers = db.relationship('PaceTier', backref='route', cascade='all, delete-orphan')
    time_overrides = db.relationship('TimeOverride', backref='route', cascade='all, delete-orphan')
    attempts = db.relationship('Attempt', backref='route', cascade='all, delete-orphan',
                               order_by='Attempt.date.desc()')


class Leg(db.Model):
    __tablename__ = 'legs'

    id = db.Column(db.Integer, primary_key=True)
    route_id = db.Column(db.Integer, db.ForeignKey('routes.id', ondelete='CASCADE'), nullable=False)
    leg_num = db.Column(db.Integer, nullable=False)
    location = db.Column(db.Text, nullable=False)
    distance_km = db.Column(db.Float, nullable=False, default=0)
    ascent_m = db.Column(db.Float, nullable=False, default=0)
    descent_m = db.Column(db.Float, nullable=False, default=0)
    notes = db.Column(db.Text, default='')


class PaceTier(db.Model):
    __tablename__ = 'pace_tiers'

    id = db.Column(db.Integer, primary_key=True)
    route_id = db.Column(db.Integer, db.ForeignKey('routes.id', ondelete='CASCADE'), nullable=False)
    up_to_minutes = db.Column(db.Float, nullable=True)
    flat_pace_min_per_km = db.Column(db.Float, nullable=False)
    ascent_pace_min_per_125m = db.Column(db.Float, nullable=False, default=0)
    descent_pace_min_per_375m = db.Column(db.Float, nullable=False, default=0)


class TimeOverride(db.Model):
    __tablename__ = 'time_overrides'

    id = db.Column(db.Integer, primary_key=True)
    route_id = db.Column(db.Integer, db.ForeignKey('routes.id', ondelete='CASCADE'), nullable=False)
    leg_id = db.Column(db.Integer, db.ForeignKey('legs.id', ondelete='CASCADE'), nullable=False, unique=True)
    override_minutes = db.Column(db.Float, nullable=False)


class Attempt(db.Model):
    __tablename__ = 'attempts'

    id = db.Column(db.Integer, primary_key=True)
    route_id = db.Column(db.Integer, db.ForeignKey('routes.id', ondelete='CASCADE'), nullable=False)
    name = db.Column(db.Text, nullable=False)
    date = db.Column(db.Text)
    notes = db.Column(db.Text)

    attempt_legs = db.relationship('AttemptLeg', backref='attempt', cascade='all, delete-orphan')


class AttemptLeg(db.Model):
    __tablename__ = 'attempt_legs'

    id = db.Column(db.Integer, primary_key=True)
    attempt_id = db.Column(db.Integer, db.ForeignKey('attempts.id', ondelete='CASCADE'), nullable=False)
    leg_id = db.Column(db.Integer, db.ForeignKey('legs.id', ondelete='CASCADE'), nullable=False)
    actual_time_minutes = db.Column(db.Float)
