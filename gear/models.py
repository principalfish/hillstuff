from walks.db import db


class Loadout(db.Model):
    __tablename__ = 'gear_loadouts'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, nullable=False, unique=True)

    items = db.relationship('LoadoutItem', backref='loadout',
                            cascade='all, delete-orphan',
                            order_by='LoadoutItem.category, LoadoutItem.name')


class LoadoutItem(db.Model):
    __tablename__ = 'gear_loadout_items'

    id = db.Column(db.Integer, primary_key=True)
    loadout_id = db.Column(db.Integer,
                           db.ForeignKey('gear_loadouts.id', ondelete='CASCADE'),
                           nullable=False)
    category = db.Column(db.Text, nullable=False)
    name = db.Column(db.Text, nullable=False)
    weight_g = db.Column(db.Integer, nullable=False)
    owned = db.Column(db.Boolean, nullable=False, default=False)
    worn = db.Column(db.Boolean, nullable=False, default=False)
