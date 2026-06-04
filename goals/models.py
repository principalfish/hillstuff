from walks.db import db

# The three activity types tracked in the current-state grid. One ActivityTotal
# row per type is auto-seeded for every GoalYear.
ACTIVITY_TYPES = ('run', 'walk', 'cycle')


class GoalYear(db.Model):
    __tablename__ = 'goal_years'

    id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.Integer, nullable=False, unique=True, index=True)
    archived = db.Column(db.Boolean, nullable=False, default=False)
    # ISO date (YYYY-MM-DD) frozen when the year is archived; the dashboard uses
    # this as the "as of" reference date so projections stop moving. NULL while active.
    archived_on = db.Column(db.Text, nullable=True)

    totals = db.relationship('ActivityTotal', backref='goal_year',
                             cascade='all, delete-orphan',
                             order_by='ActivityTotal.activity_type')
    goals = db.relationship('Goal', backref='goal_year',
                            cascade='all, delete-orphan',
                            order_by='Goal.sort_order, Goal.id')
    milestones = db.relationship('Milestone', backref='goal_year',
                                 cascade='all, delete-orphan',
                                 order_by='Milestone.sort_order, Milestone.id')


class ActivityTotal(db.Model):
    """Manually-maintained current-state grid: one row per activity type."""
    __tablename__ = 'goal_activity_totals'

    id = db.Column(db.Integer, primary_key=True)
    goal_year_id = db.Column(db.Integer,
                             db.ForeignKey('goal_years.id', ondelete='CASCADE'),
                             nullable=False)
    activity_type = db.Column(db.Text, nullable=False)  # 'run' | 'walk' | 'cycle'
    distance_km = db.Column(db.Float, nullable=False, default=0.0)
    ascent_m = db.Column(db.Float, nullable=False, default=0.0)
    time_hours = db.Column(db.Float, nullable=False, default=0.0)


class Goal(db.Model):
    """A numeric target for a metric, optionally combining activity types."""
    __tablename__ = 'goal_targets'

    id = db.Column(db.Integer, primary_key=True)
    goal_year_id = db.Column(db.Integer,
                             db.ForeignKey('goal_years.id', ondelete='CASCADE'),
                             nullable=False)
    name = db.Column(db.Text, nullable=False)
    goal_type = db.Column(db.Text, nullable=False)  # 'distance' | 'elevation' | 'time'
    # Comma-joined subset of ACTIVITY_TYPES, e.g. 'run' or 'run,walk' or 'run,walk,cycle'.
    activity_types = db.Column(db.Text, nullable=False)
    target = db.Column(db.Float, nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)


class Milestone(db.Model):
    """A named event / effort with a done-or-not marker."""
    __tablename__ = 'goal_milestones'

    id = db.Column(db.Integer, primary_key=True)
    goal_year_id = db.Column(db.Integer,
                             db.ForeignKey('goal_years.id', ondelete='CASCADE'),
                             nullable=False)
    name = db.Column(db.Text, nullable=False)
    target = db.Column(db.Text, nullable=True)   # e.g. target time '6h57'
    result = db.Column(db.Text, nullable=True)   # actual achieved value
    achieved = db.Column(db.Boolean, nullable=False, default=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
