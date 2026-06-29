import datetime

from flask import render_template, request, redirect, url_for, flash
from pydantic import ValidationError
from werkzeug.wrappers import Response as WerkzeugResponse

from goals import bp, calc
from goals.models import GoalYear, ActivityTotal, Goal, GoalPeriod, Milestone, ACTIVITY_TYPES
from goals.schemas import GoalCreate, GoalPeriodForm, MilestoneCreate, ActivityTotalUpdate
from walks.db import db

# (key, label) pairs in display order for the grid rows and projection rows.
ACTIVITY_ROWS = [('run', 'Run'), ('walk', 'Walk'), ('cycle', 'Cycle')]
# (metric, column label, unit, form-field suffix) in display order — matches the
# source spreadsheet. The suffix is the totals-form input name, e.g. 'run_ascent'.
METRIC_COLS = [('time', 'Hours', 'h', 'time'),
               ('distance', 'Distance', 'km', 'distance'),
               ('elevation', 'Ascent', 'm', 'ascent')]
METRICS = ('distance', 'elevation', 'time')


def _current_year() -> int:
    return datetime.date.today().year


def _ensure_year(year: int) -> GoalYear:
    """Fetch a GoalYear, creating it (with the 3 activity rows) if absent."""
    gy = GoalYear.query.filter_by(year=year).first()
    if gy is None:
        gy = GoalYear(year=year)
        db.session.add(gy)
        db.session.flush()
        for at in ACTIVITY_TYPES:
            db.session.add(ActivityTotal(goal_year_id=gy.id, activity_type=at))
        db.session.commit()
    return gy


def _reference_date(gy: GoalYear) -> datetime.date:
    """The 'as of' date: frozen archive date for archived years, else today."""
    if gy.archived and gy.archived_on:
        try:
            return datetime.date.fromisoformat(gy.archived_on)
        except ValueError:
            pass
    return datetime.date.today()


def _flash_errors(e: ValidationError) -> None:
    for err in e.errors():
        loc = err["loc"]
        field = loc[-1] if loc else 'value'  # model-level errors have an empty loc
        flash(f'{field}: {err["msg"]}', 'error')


def _load_active(year: int) -> GoalYear | WerkzeugResponse:
    """Load a year for a write action, or a redirect if missing/archived."""
    gy = GoalYear.query.filter_by(year=year).first()
    if gy is None:
        flash('That year is not set up yet.', 'error')
        return redirect(url_for('goals.index'))
    if gy.archived:
        flash('This year is archived. Unarchive it to make changes.', 'error')
        return redirect(url_for('goals.year_view', year=year))
    return gy


@bp.route('/')
def index() -> WerkzeugResponse:
    gy = (GoalYear.query.filter_by(archived=False).order_by(GoalYear.year.desc()).first()
          or GoalYear.query.order_by(GoalYear.year.desc()).first())
    if gy is None:
        gy = _ensure_year(_current_year())
    return redirect(url_for('goals.year_view', year=gy.year))


@bp.route('/<int:year>')
def year_view(year: int) -> WerkzeugResponse | str:
    gy = GoalYear.query.filter_by(year=year).first()
    if gy is None:
        if year == _current_year():
            gy = _ensure_year(year)
        else:
            flash('That year is not set up yet. Start it from the Goals page.', 'error')
            return redirect(url_for('goals.index'))

    totals_by_type = {t.activity_type: t for t in gy.totals}

    def _cell(at: str, metric: str) -> float:
        row = totals_by_type.get(at)
        if row is None:
            return 0.0
        return {'distance': row.distance_km,
                'elevation': row.ascent_m,
                'time': row.time_hours}[metric]

    grid: dict[str, dict[str, float]] = {
        at: {m: _cell(at, m) for m in METRICS} for at in ACTIVITY_TYPES
    }
    totals_sum = {m: sum(grid[at][m] for at in ACTIVITY_TYPES) for m in METRICS}

    ref = _reference_date(gy)
    yp = calc.year_progress(year, ref)

    # Goals with computed status.
    goal_rows = []
    for g in gy.goals:
        ats = g.activity_types.split(',') if g.activity_types else []
        progress = calc.goal_progress(g.goal_type, ats, grid)
        period_pairs = [(p.start_date, p.end_date) for p in g.periods]
        total = elapsed = None
        if period_pairs:
            total, elapsed = calc.active_day_counts(year, period_pairs, ref)
        goal_rows.append({
            'goal': g,
            'activity_types': ats,
            'type_label': calc.GOAL_TYPE_LABELS.get(g.goal_type, g.goal_type),
            'unit': calc.GOAL_TYPE_UNITS.get(g.goal_type, ''),
            'periods': period_pairs,
            'active_days': total,
            'status': calc.goal_status(g.target, progress, yp, total, elapsed),
        })

    # Day / week / year-end projections per activity (+ total).
    projections: dict[str, dict[str, dict[str, float | None]]] = {
        'day': {}, 'week': {}, 'year': {},
    }
    for key in [at for at, _ in ACTIVITY_ROWS] + ['total']:
        vals = totals_sum if key == 'total' else grid[key]
        for m in METRICS:
            per_day, per_week, per_year = calc.extrapolate(vals[m], yp)
            projections['day'].setdefault(key, {})[m] = per_day
            projections['week'].setdefault(key, {})[m] = per_week
            projections['year'].setdefault(key, {})[m] = per_year

    years = GoalYear.query.order_by(GoalYear.year.desc()).all()

    return render_template(
        'goals/year.html',
        gy=gy,
        year=year,
        years=years,
        current_year=_current_year(),
        yp=yp,
        grid=grid,
        totals_by_type=totals_by_type,
        totals_sum=totals_sum,
        goal_rows=goal_rows,
        projections=projections,
        milestones=gy.milestones,
        activity_rows=ACTIVITY_ROWS,
        metric_cols=METRIC_COLS,
        goal_type_options=[(t, calc.GOAL_TYPE_LABELS[t]) for t in calc.GOAL_TYPES],
    )


@bp.route('/<int:year>/totals', methods=['POST'])
def totals_update(year: int) -> WerkzeugResponse:
    gy = _load_active(year)
    if isinstance(gy, WerkzeugResponse):
        return gy

    totals_by_type = {t.activity_type: t for t in gy.totals}  # type: ignore[attr-defined]
    parsed = {}
    for at in ACTIVITY_TYPES:
        try:
            parsed[at] = ActivityTotalUpdate.model_validate({
                'distance_km': request.form.get(f'{at}_distance') or '0',
                'ascent_m': request.form.get(f'{at}_ascent') or '0',
                'time_hours': request.form.get(f'{at}_time') or '0',
            })
        except ValidationError as e:
            _flash_errors(e)
            return redirect(url_for('goals.year_view', year=year))

    for at, form in parsed.items():
        row = totals_by_type.get(at)
        if row is None:
            row = ActivityTotal(goal_year_id=gy.id, activity_type=at)
            db.session.add(row)
        row.distance_km = form.distance_km
        row.ascent_m = form.ascent_m
        row.time_hours = form.time_hours
    db.session.commit()
    flash('Totals updated.', 'success')
    return redirect(url_for('goals.year_view', year=year))


def _goal_form() -> GoalCreate:
    return GoalCreate.model_validate({
        'name': request.form.get('name', ''),
        'goal_type': request.form.get('goal_type', ''),
        'activity_types': request.form.getlist('activity_types'),
        'target': request.form.get('target') or '0',
    })


def _goal_periods() -> list[GoalPeriodForm]:
    """Parse the repeatable date-range rows into validated periods.

    Fully-blank rows are skipped; a half-filled or malformed row raises
    ValidationError so it surfaces to the user.
    """
    starts = request.form.getlist('period_start')
    ends = request.form.getlist('period_end')
    periods = []
    for start, end in zip(starts, ends):
        start, end = start.strip(), end.strip()
        if not start and not end:
            continue
        periods.append(GoalPeriodForm.model_validate({'start': start, 'end': end}))
    return periods


def _period_rows(periods: list[GoalPeriodForm]) -> list[GoalPeriod]:
    return [GoalPeriod(start_date=p.start.isoformat(), end_date=p.end.isoformat())
            for p in periods]


@bp.route('/<int:year>/goals', methods=['POST'])
def goal_new(year: int) -> WerkzeugResponse:
    gy = _load_active(year)
    if isinstance(gy, WerkzeugResponse):
        return gy
    try:
        form = _goal_form()
        periods = _goal_periods()
    except ValidationError as e:
        _flash_errors(e)
        return redirect(url_for('goals.year_view', year=year))

    next_order = max((g.sort_order for g in gy.goals), default=-1) + 1  # type: ignore[attr-defined]
    db.session.add(Goal(
        goal_year_id=gy.id,
        name=form.name,
        goal_type=form.goal_type,
        activity_types=','.join(form.activity_types),
        target=form.target,
        sort_order=next_order,
        periods=_period_rows(periods),
    ))
    db.session.commit()
    flash('Goal added.', 'success')
    return redirect(url_for('goals.year_view', year=year))


@bp.route('/<int:year>/goals/<int:goal_id>/edit', methods=['POST'])
def goal_edit(year: int, goal_id: int) -> WerkzeugResponse:
    gy = _load_active(year)
    if isinstance(gy, WerkzeugResponse):
        return gy
    goal = db.session.get(Goal, goal_id)
    if goal is None or goal.goal_year_id != gy.id:
        flash('Goal not found.', 'error')
        return redirect(url_for('goals.year_view', year=year))
    try:
        form = _goal_form()
        periods = _goal_periods()
    except ValidationError as e:
        _flash_errors(e)
        return redirect(url_for('goals.year_view', year=year))

    goal.name = form.name
    goal.goal_type = form.goal_type
    goal.activity_types = ','.join(form.activity_types)
    goal.target = form.target
    goal.periods = _period_rows(periods)  # type: ignore[assignment]  # replaces rows (delete-orphan)
    db.session.commit()
    flash('Goal updated.', 'success')
    return redirect(url_for('goals.year_view', year=year))


@bp.route('/<int:year>/goals/<int:goal_id>/delete', methods=['POST'])
def goal_delete(year: int, goal_id: int) -> WerkzeugResponse:
    gy = _load_active(year)
    if isinstance(gy, WerkzeugResponse):
        return gy
    goal = db.session.get(Goal, goal_id)
    if goal is None or goal.goal_year_id != gy.id:
        flash('Goal not found.', 'error')
        return redirect(url_for('goals.year_view', year=year))
    db.session.delete(goal)
    db.session.commit()
    flash('Goal deleted.', 'success')
    return redirect(url_for('goals.year_view', year=year))


@bp.route('/<int:year>/milestones', methods=['POST'])
def milestone_new(year: int) -> WerkzeugResponse:
    gy = _load_active(year)
    if isinstance(gy, WerkzeugResponse):
        return gy
    try:
        form = MilestoneCreate.model_validate({
            'name': request.form.get('name', ''),
            'target': request.form.get('target', ''),
            'result': request.form.get('result', ''),
            'achieved': bool(request.form.get('achieved')),
        })
    except ValidationError as e:
        _flash_errors(e)
        return redirect(url_for('goals.year_view', year=year))

    next_order = max((m.sort_order for m in gy.milestones), default=-1) + 1  # type: ignore[attr-defined]
    db.session.add(Milestone(
        goal_year_id=gy.id,
        name=form.name,
        target=form.target,
        result=form.result,
        achieved=form.achieved,
        sort_order=next_order,
    ))
    db.session.commit()
    flash('Milestone added.', 'success')
    return redirect(url_for('goals.year_view', year=year))


def _load_milestone(gy: GoalYear, milestone_id: int) -> Milestone | None:
    m = db.session.get(Milestone, milestone_id)
    if m is None or m.goal_year_id != gy.id:
        return None
    return m


@bp.route('/<int:year>/milestones/<int:milestone_id>/edit', methods=['POST'])
def milestone_edit(year: int, milestone_id: int) -> WerkzeugResponse:
    gy = _load_active(year)
    if isinstance(gy, WerkzeugResponse):
        return gy
    m = _load_milestone(gy, milestone_id)
    if m is None:
        flash('Milestone not found.', 'error')
        return redirect(url_for('goals.year_view', year=year))
    try:
        form = MilestoneCreate.model_validate({
            'name': request.form.get('name', ''),
            'target': request.form.get('target', ''),
            'result': request.form.get('result', ''),
            'achieved': bool(request.form.get('achieved')),
        })
    except ValidationError as e:
        _flash_errors(e)
        return redirect(url_for('goals.year_view', year=year))
    m.name = form.name
    m.target = form.target
    m.result = form.result
    m.achieved = form.achieved
    db.session.commit()
    flash('Milestone saved.', 'success')
    return redirect(url_for('goals.year_view', year=year))


@bp.route('/<int:year>/milestones/<int:milestone_id>/delete', methods=['POST'])
def milestone_delete(year: int, milestone_id: int) -> WerkzeugResponse:
    gy = _load_active(year)
    if isinstance(gy, WerkzeugResponse):
        return gy
    m = _load_milestone(gy, milestone_id)
    if m is None:
        flash('Milestone not found.', 'error')
        return redirect(url_for('goals.year_view', year=year))
    db.session.delete(m)
    db.session.commit()
    flash('Milestone deleted.', 'success')
    return redirect(url_for('goals.year_view', year=year))


@bp.route('/<int:year>/archive', methods=['POST'])
def archive(year: int) -> WerkzeugResponse:
    gy = GoalYear.query.filter_by(year=year).first()
    if gy is None:
        flash('That year is not set up yet.', 'error')
        return redirect(url_for('goals.index'))
    gy.archived = True
    gy.archived_on = datetime.date.today().isoformat()
    db.session.commit()
    flash(f'{year} archived.', 'success')
    return redirect(url_for('goals.year_view', year=year))


@bp.route('/<int:year>/unarchive', methods=['POST'])
def unarchive(year: int) -> WerkzeugResponse:
    gy = GoalYear.query.filter_by(year=year).first()
    if gy is None:
        flash('That year is not set up yet.', 'error')
        return redirect(url_for('goals.index'))
    gy.archived = False
    gy.archived_on = None
    db.session.commit()
    flash(f'{year} reopened.', 'success')
    return redirect(url_for('goals.year_view', year=year))


@bp.route('/new-year', methods=['POST'])
def new_year() -> WerkzeugResponse:
    today_year = _current_year()
    if GoalYear.query.filter_by(year=today_year).first() is None:
        candidate = today_year
    else:
        max_year = db.session.query(db.func.max(GoalYear.year)).scalar()
        candidate = (max_year or today_year) + 1
    _ensure_year(candidate)
    flash(f'{candidate} started.', 'success')
    return redirect(url_for('goals.year_view', year=candidate))
