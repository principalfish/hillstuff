import csv
import io
import json

from flask import (
    render_template, request, redirect, url_for, flash, jsonify
)
from pydantic import ValidationError
from sqlalchemy import func

from walks import bp
from walks.calc import (
    calculate_leg_times, find_solar_events,
    format_time, format_time_of_day, format_diff,
)
from walks.db import db
from walks.models import Route, Leg, PaceTier, TimeOverride, Attempt, AttemptLeg
from walks.schemas import (
    RouteForm, LegForm, SettingsForm, PaceTierForm, LegUpdateForm, AttemptForm,
)
from walks.solar import solar_times


# (up_to_minutes, flat, ascent, descent) — ascent & descent default to flat
DEFAULT_PACE_TIERS = [
    (120, 5.0, 5.0, 5.0),
    (300, 6.0, 6.0, 6.0),
    (None, 7.0, 7.0, 7.0),
]


@bp.route('/')
def route_list():
    routes = (
        db.session.query(
            Route,
            func.count(Leg.id).label('leg_count'),
            func.coalesce(func.sum(Leg.distance_km), 0).label('total_distance'),
            func.coalesce(func.sum(Leg.ascent_m), 0).label('total_ascent'),
            func.coalesce(func.sum(Leg.descent_m), 0).label('total_descent'),
        )
        .outerjoin(Leg)
        .group_by(Route.id)
        .order_by(Route.created_at.desc())
        .all()
    )
    # Template expects dict-like rows with route fields + aggregates
    route_rows = []
    for route, leg_count, total_distance, total_ascent, total_descent in routes:
        route_rows.append({
            'id': route.id,
            'name': route.name,
            'latitude': route.latitude,
            'longitude': route.longitude,
            'start_time': route.start_time,
            'start_date': route.start_date,
            'created_at': route.created_at,
            'leg_count': leg_count,
            'total_distance': total_distance,
            'total_ascent': total_ascent,
            'total_descent': total_descent,
        })
    return render_template('walks/list.html', routes=route_rows)


@bp.route('/new', methods=['GET', 'POST'])
def route_new():
    if request.method == 'POST':
        return _save_route(None)
    return render_template('walks/form.html', route=None, legs=[])


@bp.route('/<int:route_id>/edit', methods=['GET', 'POST'])
def route_edit(route_id):
    route = db.session.get(Route, route_id)
    if not route:
        flash('Route not found.', 'error')
        return redirect(url_for('walks.route_list'))

    if request.method == 'POST':
        return _save_route(route_id)

    legs = Leg.query.filter_by(route_id=route_id).order_by(Leg.leg_num).all()
    return render_template('walks/form.html', route=route, legs=legs)


def _save_route(route_id):
    try:
        form = RouteForm(
            name=request.form.get('name', ''),
            latitude=request.form.get('latitude', '56.8'),
            longitude=request.form.get('longitude', '-5.1'),
        )
    except ValidationError as e:
        for err in e.errors():
            flash(f'{err["loc"][-1]}: {err["msg"]}', 'error')
        return redirect(request.url)

    # Parse legs from CSV or form
    legs = _parse_legs(request)
    if legs is None:
        return redirect(request.url)

    if route_id is None:
        route = Route(name=form.name, latitude=form.latitude, longitude=form.longitude)
        db.session.add(route)
        db.session.flush()
        route_id = route.id
        for up_to, flat, asc, desc in DEFAULT_PACE_TIERS:
            db.session.add(PaceTier(
                route_id=route_id,
                up_to_minutes=up_to,
                flat_pace_min_per_km=flat,
                ascent_pace_min_per_125m=asc,
                descent_pace_min_per_375m=desc,
            ))
    else:
        route = db.session.get(Route, route_id)
        route.name = form.name
        route.latitude = form.latitude
        route.longitude = form.longitude
        Leg.query.filter_by(route_id=route_id).delete()
        TimeOverride.query.filter_by(route_id=route_id).delete()

    for leg in legs:
        db.session.add(Leg(
            route_id=route_id,
            leg_num=leg.leg_num,
            location=leg.location,
            distance_km=leg.distance_km,
            ascent_m=leg.ascent_m,
            descent_m=leg.descent_m,
            notes=leg.notes,
        ))

    db.session.commit()
    flash('Route saved.', 'success')
    return redirect(url_for('walks.route_detail', route_id=route_id))


def _parse_legs(req) -> list[LegForm] | None:
    """Parse legs from either CSV input or form fields."""
    csv_text = req.form.get('csv_data', '').strip()
    csv_file = req.files.get('csv_file')

    if csv_file and csv_file.filename:
        csv_text = csv_file.read().decode('utf-8')

    if csv_text:
        return _parse_csv(csv_text)

    legs: list[LegForm] = []
    i = 0
    while True:
        location = req.form.get(f'leg_location_{i}')
        if location is None:
            break
        try:
            legs.append(LegForm(
                leg_num=i + 1,
                location=location,
                distance_km=float(req.form.get(f'leg_distance_{i}', '0')),
                ascent_m=float(req.form.get(f'leg_ascent_{i}', '0')),
                descent_m=float(req.form.get(f'leg_descent_{i}', '0')),
                notes=req.form.get(f'leg_notes_{i}', '').strip(),
            ))
        except (ValidationError, ValueError) as e:
            if isinstance(e, ValidationError):
                for err in e.errors():
                    flash(f'Leg {i + 1} {err["loc"][-1]}: {err["msg"]}', 'error')
            else:
                flash(f'Invalid number in leg {i + 1}.', 'error')
            return None
        i += 1

    if not legs:
        flash('No legs provided.', 'error')
        return None
    return legs


def _parse_csv(text: str) -> list[LegForm] | None:
    """Parse CSV text into legs. Expected: leg_num,location,distance_km,ascent_m,descent_m"""
    reader = csv.reader(io.StringIO(text))
    legs: list[LegForm] = []
    for i, row in enumerate(reader):
        if i == 0 and any(h in row[0].lower() for h in ['leg', 'num', 'loc', '#']):
            continue
        if len(row) < 4:
            flash(f'CSV row {i + 1}: expected at least 4 columns, got {len(row)}.', 'error')
            return None
        try:
            legs.append(LegForm(
                leg_num=int(row[0].strip()),
                location=row[1].strip(),
                distance_km=float(row[2].strip()),
                ascent_m=float(row[3].strip()),
                descent_m=float(row[4].strip()) if len(row) > 4 else 0,
                notes=row[5].strip() if len(row) > 5 else '',
            ))
        except (ValidationError, ValueError) as e:
            if isinstance(e, ValidationError):
                for err in e.errors():
                    flash(f'CSV row {i + 1} {err["loc"][-1]}: {err["msg"]}', 'error')
            else:
                flash(f'CSV row {i + 1}: invalid number.', 'error')
            return None
    if not legs:
        flash('CSV contained no data rows.', 'error')
        return None
    return legs


@bp.route('/<int:route_id>/delete', methods=['POST'])
def route_delete(route_id):
    route = db.session.get(Route, route_id)
    if route:
        db.session.delete(route)
        db.session.commit()
    flash('Route deleted.', 'success')
    return redirect(url_for('walks.route_list'))


@bp.route('/<int:route_id>')
def route_detail(route_id):
    route = db.session.get(Route, route_id)
    if not route:
        flash('Route not found.', 'error')
        return redirect(url_for('walks.route_list'))

    legs = Leg.query.filter_by(route_id=route_id).order_by(Leg.leg_num).all()

    pace_tiers = (
        PaceTier.query
        .filter_by(route_id=route_id)
        .order_by(
            db.case((PaceTier.up_to_minutes.is_(None), 1), else_=0),
            PaceTier.up_to_minutes,
        )
        .all()
    )

    overrides_rows = (
        TimeOverride.query
        .filter_by(route_id=route_id)
        .all()
    )
    overrides = {r.leg_id: r.override_minutes for r in overrides_rows}

    legs_data = [
        {
            'id': l.id, 'route_id': l.route_id, 'leg_num': l.leg_num,
            'location': l.location, 'distance_km': l.distance_km,
            'ascent_m': l.ascent_m, 'descent_m': l.descent_m, 'notes': l.notes,
        }
        for l in legs
    ]
    tiers_data = [
        {
            'id': t.id, 'route_id': t.route_id, 'up_to_minutes': t.up_to_minutes,
            'flat_pace_min_per_km': t.flat_pace_min_per_km,
            'ascent_pace_min_per_125m': t.ascent_pace_min_per_125m,
            'descent_pace_min_per_375m': t.descent_pace_min_per_375m,
        }
        for t in pace_tiers
    ]

    # Parse start time
    start_time_minutes = None
    if route.start_time:
        parts = route.start_time.split(':')
        if len(parts) == 2:
            start_time_minutes = int(parts[0]) * 60 + int(parts[1])

    calculated = calculate_leg_times(legs_data, tiers_data, overrides, start_time_minutes)

    totals = {
        'distance_km': sum(l['distance_km'] for l in calculated),
        'ascent_m': sum(l['ascent_m'] for l in calculated),
        'descent_m': sum(l['descent_m'] for l in calculated),
        'time': sum(l['time'] for l in calculated),
    }

    # Solar data
    solar = None
    solar_events = {'sunrise_leg': None, 'sunset_leg': None}
    if route.start_date and route.latitude and route.longitude:
        solar = solar_times(route.latitude, route.longitude, route.start_date)
        if solar and start_time_minutes is not None:
            solar_events = find_solar_events(calculated, start_time_minutes, solar)

    # Attempts
    attempts = (
        Attempt.query
        .filter_by(route_id=route_id)
        .order_by(Attempt.date.desc())
        .all()
    )

    attempts_data = []
    for attempt in attempts:
        a_legs = AttemptLeg.query.filter_by(attempt_id=attempt.id).all()
        leg_times = {r.leg_id: r.actual_time_minutes for r in a_legs}
        attempt_total = sum(t for t in leg_times.values() if t is not None)
        attempts_data.append({
            'id': attempt.id,
            'name': attempt.name,
            'date': attempt.date,
            'notes': attempt.notes,
            'leg_times': leg_times,
            'total_time': attempt_total,
        })

    attempts_json = json.dumps(attempts_data, default=str)
    calculated_json = json.dumps(calculated, default=str)

    return render_template('walks/detail.html',
                           route=route,
                           legs=calculated,
                           pace_tiers=tiers_data,
                           totals=totals,
                           solar=solar,
                           solar_events=solar_events,
                           attempts=attempts_data,
                           attempts_json=attempts_json,
                           calculated_json=calculated_json,
                           format_time=format_time,
                           format_time_of_day=format_time_of_day,
                           format_diff=format_diff)


@bp.route('/<int:route_id>/settings', methods=['POST'])
def save_settings(route_id):
    route = db.session.get(Route, route_id)
    try:
        form = SettingsForm(
            start_time=request.form.get('start_time', ''),
            start_date=request.form.get('start_date', ''),
        )
    except ValidationError as e:
        for err in e.errors():
            flash(f'{err["loc"][-1]}: {err["msg"]}', 'error')
        return redirect(url_for('walks.route_detail', route_id=route_id))
    route.start_time = form.start_time
    route.start_date = form.start_date
    db.session.commit()
    flash('Settings saved.', 'success')
    return redirect(url_for('walks.route_detail', route_id=route_id))


@bp.route('/<int:route_id>/paces', methods=['POST'])
def save_paces(route_id):
    PaceTier.query.filter_by(route_id=route_id).delete()

    i = 0
    while True:
        flat = request.form.get(f'flat_pace_{i}')
        if flat is None:
            break
        up_to = request.form.get(f'up_to_{i}', '').strip()
        try:
            form = PaceTierForm(
                up_to_minutes=float(up_to) if up_to else None,
                flat_pace_min_per_km=flat,
                ascent_pace_min_per_125m=request.form.get(f'ascent_pace_{i}', '0'),
                descent_pace_min_per_375m=request.form.get(f'descent_pace_{i}', '0'),
            )
        except (ValidationError, ValueError) as e:
            if isinstance(e, ValidationError):
                for err in e.errors():
                    flash(f'Pace tier {i + 1} {err["loc"][-1]}: {err["msg"]}', 'error')
            else:
                flash(f'Invalid number in pace tier {i + 1}.', 'error')
            return redirect(url_for('walks.route_detail', route_id=route_id))
        db.session.add(PaceTier(
            route_id=route_id,
            up_to_minutes=form.up_to_minutes,
            flat_pace_min_per_km=form.flat_pace_min_per_km,
            ascent_pace_min_per_125m=form.ascent_pace_min_per_125m,
            descent_pace_min_per_375m=form.descent_pace_min_per_375m,
        ))
        i += 1

    db.session.commit()
    flash('Pace tiers saved.', 'success')
    return redirect(url_for('walks.route_detail', route_id=route_id))


@bp.route('/<int:route_id>/legs', methods=['POST'])
def save_legs(route_id):
    legs = Leg.query.filter_by(route_id=route_id).all()

    for leg in legs:
        lid = leg.id
        try:
            form = LegUpdateForm(
                distance_km=request.form.get(f'distance_{lid}', '0'),
                ascent_m=request.form.get(f'ascent_{lid}', '0'),
                descent_m=request.form.get(f'descent_{lid}', '0'),
                notes=request.form.get(f'notes_{lid}', '').strip(),
                override_minutes=request.form.get(f'override_{lid}', ''),
            )
        except (ValidationError, ValueError):
            continue
        leg.distance_km = form.distance_km
        leg.ascent_m = form.ascent_m
        leg.descent_m = form.descent_m
        leg.notes = form.notes

        if form.override_minutes is not None:
            existing = TimeOverride.query.filter_by(leg_id=lid).first()
            if existing:
                existing.override_minutes = form.override_minutes
            else:
                db.session.add(TimeOverride(
                    route_id=route_id,
                    leg_id=lid,
                    override_minutes=form.override_minutes,
                ))
        else:
            TimeOverride.query.filter_by(leg_id=lid).delete()

    db.session.commit()
    return redirect(url_for('walks.route_detail', route_id=route_id))


@bp.route('/<int:route_id>/attempts', methods=['POST'])
def create_attempt(route_id):
    try:
        form = AttemptForm(
            name=request.form.get('attempt_name', ''),
            date=request.form.get('attempt_date', ''),
            notes=request.form.get('attempt_notes', ''),
        )
    except ValidationError as e:
        for err in e.errors():
            flash(f'{err["loc"][-1]}: {err["msg"]}', 'error')
        return redirect(url_for('walks.route_detail', route_id=route_id))

    attempt = Attempt(
        route_id=route_id,
        name=form.name,
        date=form.date,
        notes=form.notes,
    )
    db.session.add(attempt)
    db.session.flush()

    legs = Leg.query.filter_by(route_id=route_id).order_by(Leg.leg_num).all()

    for leg in legs:
        time_val = request.form.get(f'attempt_time_{leg.id}', '').strip()
        minutes = None
        if time_val:
            try:
                minutes = float(time_val)
            except ValueError:
                pass
        db.session.add(AttemptLeg(
            attempt_id=attempt.id,
            leg_id=leg.id,
            actual_time_minutes=minutes,
        ))

    db.session.commit()
    flash('Attempt saved.', 'success')
    return redirect(url_for('walks.route_detail', route_id=route_id))


@bp.route('/<int:route_id>/attempts/<int:attempt_id>/delete', methods=['POST'])
def delete_attempt(route_id, attempt_id):
    attempt = Attempt.query.filter_by(id=attempt_id, route_id=route_id).first()
    if attempt:
        db.session.delete(attempt)
        db.session.commit()
    flash('Attempt deleted.', 'success')
    return redirect(url_for('walks.route_detail', route_id=route_id))
