from walks.db import db


class LogEntry(db.Model):
    __tablename__ = 'log_entries'

    id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.Integer, nullable=False, index=True)
    date = db.Column(db.Text, nullable=False)           # YYYY-MM-DD (start date, for sorting)
    date_display = db.Column(db.Text, nullable=False)   # original text, e.g. "17th - 18th Aug"
    distance_km = db.Column(db.Float, nullable=True)
    ascent_m = db.Column(db.Integer, nullable=True)
    activity_type = db.Column(db.Text, nullable=True)   # 'walk', 'run', 'cycle'
    with_whom = db.Column(db.Text, nullable=True)
    region = db.Column(db.Text, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    hills_text = db.Column(db.Text, nullable=True)
    corbetts_count = db.Column(db.Integer, nullable=False, default=0)
    munros_count = db.Column(db.Integer, nullable=False, default=0)
    wainwrights_count = db.Column(db.Integer, nullable=False, default=0)
    rating = db.Column(db.Integer, nullable=True)

    linked_hills = db.relationship('LogEntryHill', backref='entry',
                                   cascade='all, delete-orphan')


class LogEntryHill(db.Model):
    __tablename__ = 'log_entry_hills'

    id = db.Column(db.Integer, primary_key=True)
    log_entry_id = db.Column(db.Integer,
                             db.ForeignKey('log_entries.id', ondelete='CASCADE'),
                             nullable=False)
    hill_id = db.Column(db.Integer,
                        db.ForeignKey('hills.id', ondelete='CASCADE'),
                        nullable=False)

    hill = db.relationship('Hill')


