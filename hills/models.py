from walks.db import db


class Hill(db.Model):
    __tablename__ = 'hills'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, nullable=False)
    height_m = db.Column(db.Integer, nullable=False)
    rank = db.Column(db.Integer, nullable=True)
    region = db.Column(db.Text, nullable=False, default='')
    hill_type = db.Column(db.Text, nullable=False)  # 'munro', 'corbett', 'wainwright'

    ascents = db.relationship('HillAscent', backref='hill', cascade='all, delete-orphan',
                              order_by='HillAscent.date')


class HillAscent(db.Model):
    __tablename__ = 'hill_ascents'

    id = db.Column(db.Integer, primary_key=True)
    hill_id = db.Column(db.Integer, db.ForeignKey('hills.id', ondelete='CASCADE'), nullable=False)
    date = db.Column(db.Text, nullable=False)  # YYYY-MM-DD
