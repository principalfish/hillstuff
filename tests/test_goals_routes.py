import datetime

from flask.testing import FlaskClient

from walks.db import db
from goals.models import GoalYear, ActivityTotal, Goal, Milestone

# year_view auto-creates the current year, so tests operate on it directly.
YEAR = datetime.date.today().year


def _setup_year(client: FlaskClient) -> None:
    client.get(f'/goals/{YEAR}')


class TestDashboard:
    def test_index_redirects(self, client: FlaskClient) -> None:
        r = client.get('/goals/')
        assert r.status_code == 302
        assert '/goals/' in r.headers['Location']

    def test_year_autocreates_current(self, client: FlaskClient) -> None:
        r = client.get(f'/goals/{YEAR}')
        assert r.status_code == 200
        gy = GoalYear.query.filter_by(year=YEAR).first()
        assert gy is not None
        assert ActivityTotal.query.filter_by(goal_year_id=gy.id).count() == 3

    def test_past_year_not_created(self, client: FlaskClient) -> None:
        r = client.get('/goals/1990')
        assert r.status_code == 302
        assert GoalYear.query.filter_by(year=1990).first() is None


class TestTotals:
    def test_update(self, client: FlaskClient) -> None:
        _setup_year(client)
        r = client.post(f'/goals/{YEAR}/totals', data={
            'run_distance': '1325.5', 'run_ascent': '64907', 'run_time': '165',
            'walk_distance': '294.8', 'walk_ascent': '20129', 'walk_time': '73.9',
            'cycle_distance': '137.4', 'cycle_ascent': '2047', 'cycle_time': '9.25',
        })
        assert r.status_code == 302
        run = ActivityTotal.query.filter_by(activity_type='run').first()
        assert run is not None
        assert run.distance_km == 1325.5
        assert run.time_hours == 165
        assert run.ascent_m == 64907

    def test_negative_rejected(self, client: FlaskClient) -> None:
        _setup_year(client)
        client.post(f'/goals/{YEAR}/totals', data={'run_distance': '-5'})
        run = ActivityTotal.query.filter_by(activity_type='run').first()
        assert run is not None
        assert run.distance_km == 0


class TestGoals:
    def test_add_combined_goal(self, client: FlaskClient) -> None:
        _setup_year(client)
        r = client.post(f'/goals/{YEAR}/goals', data={
            'name': 'All-sport elevation', 'goal_type': 'elevation',
            'activity_types': ['run', 'walk', 'cycle'], 'target': '200000',
        })
        assert r.status_code == 302
        g = Goal.query.filter_by(name='All-sport elevation').first()
        assert g is not None
        assert g.activity_types == 'run,walk,cycle'
        assert g.target == 200000

    def test_no_activity_rejected(self, client: FlaskClient) -> None:
        _setup_year(client)
        client.post(f'/goals/{YEAR}/goals', data={
            'name': 'X', 'goal_type': 'distance', 'target': '10',
        })
        assert Goal.query.count() == 0

    def test_bad_goal_type_rejected(self, client: FlaskClient) -> None:
        _setup_year(client)
        client.post(f'/goals/{YEAR}/goals', data={
            'name': 'X', 'goal_type': 'speed', 'activity_types': ['run'], 'target': '10',
        })
        assert Goal.query.count() == 0

    def test_edit_goal(self, client: FlaskClient) -> None:
        _setup_year(client)
        client.post(f'/goals/{YEAR}/goals', data={
            'name': 'Run dist', 'goal_type': 'distance', 'activity_types': ['run'], 'target': '3000',
        })
        g = Goal.query.first()
        assert g is not None
        client.post(f'/goals/{YEAR}/goals/{g.id}/edit', data={
            'name': 'Run dist', 'goal_type': 'distance',
            'activity_types': ['run', 'walk'], 'target': '3220',
        })
        db.session.refresh(g)
        assert g.target == 3220
        assert g.activity_types == 'run,walk'

    def test_delete_goal(self, client: FlaskClient) -> None:
        _setup_year(client)
        client.post(f'/goals/{YEAR}/goals', data={
            'name': 'X', 'goal_type': 'time', 'activity_types': ['run'], 'target': '365',
        })
        g = Goal.query.first()
        assert g is not None
        client.post(f'/goals/{YEAR}/goals/{g.id}/delete')
        assert Goal.query.count() == 0

    def test_progress_renders(self, client: FlaskClient) -> None:
        _setup_year(client)
        client.post(f'/goals/{YEAR}/totals', data={
            'run_distance': '1325.5', 'run_ascent': '0', 'run_time': '0',
            'walk_distance': '0', 'walk_ascent': '0', 'walk_time': '0',
            'cycle_distance': '0', 'cycle_ascent': '0', 'cycle_time': '0',
        })
        client.post(f'/goals/{YEAR}/goals', data={
            'name': 'Run dist', 'goal_type': 'distance', 'activity_types': ['run'], 'target': '3220',
        })
        body = client.get(f'/goals/{YEAR}').data.decode('utf-8')
        assert 'Run dist' in body
        assert '1325.5' in body


class TestMilestones:
    def test_add_edit_delete(self, client: FlaskClient) -> None:
        _setup_year(client)
        client.post(f'/goals/{YEAR}/milestones', data={'name': 'Ramsay Round', 'target': '24h'})
        m = Milestone.query.first()
        assert m is not None
        assert m.achieved is False
        assert m.target == '24h'

        # One Save commits achieved + result + fields together.
        client.post(f'/goals/{YEAR}/milestones/{m.id}/edit', data={
            'name': 'Ramsay Round', 'target': '24h', 'result': '23h10', 'achieved': '1',
        })
        db.session.refresh(m)
        assert m.achieved is True
        assert m.result == '23h10'

        # Omitting the checkbox on the next Save unticks it.
        client.post(f'/goals/{YEAR}/milestones/{m.id}/edit', data={
            'name': 'Ramsay Round', 'target': '24h', 'result': '23h10',
        })
        db.session.refresh(m)
        assert m.achieved is False

        # Delete still works as its own immediate action.
        client.post(f'/goals/{YEAR}/milestones/{m.id}/delete')
        assert Milestone.query.count() == 0


class TestArchive:
    def test_archive_freezes_and_blocks_edits(self, client: FlaskClient) -> None:
        _setup_year(client)
        r = client.post(f'/goals/{YEAR}/archive')
        assert r.status_code == 302
        gy = GoalYear.query.filter_by(year=YEAR).first()
        assert gy is not None
        assert gy.archived is True
        assert gy.archived_on is not None

        r2 = client.post(f'/goals/{YEAR}/goals', data={
            'name': 'X', 'goal_type': 'distance', 'activity_types': ['run'], 'target': '10',
        }, follow_redirects=True)
        assert Goal.query.count() == 0
        assert b'archived' in r2.data

    def test_unarchive(self, client: FlaskClient) -> None:
        _setup_year(client)
        client.post(f'/goals/{YEAR}/archive')
        client.post(f'/goals/{YEAR}/unarchive')
        gy = GoalYear.query.filter_by(year=YEAR).first()
        assert gy is not None
        assert gy.archived is False
        assert gy.archived_on is None


class TestNewYear:
    def test_creates_current_then_next(self, client: FlaskClient) -> None:
        r = client.post('/goals/new-year')
        assert r.status_code == 302
        assert GoalYear.query.filter_by(year=YEAR).first() is not None
        client.post('/goals/new-year')
        assert GoalYear.query.filter_by(year=YEAR + 1).first() is not None
