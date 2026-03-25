import csv
import datetime
import io

from flask import render_template, request, redirect, url_for, flash, jsonify, Response
from werkzeug.wrappers import Response as WerkzeugResponse

from logs import bp
from logs.models import LogEntry, LogEntryHill
from hills.models import Hill, HillAscent
from walks.db import db

CURRENT_YEAR = datetime.date.today().year


@bp.route('/')
def index() -> WerkzeugResponse:
    # Go to most recent year that has data, falling back to current year
    row = (db.session.query(LogEntry.year)
           .distinct()
           .order_by(LogEntry.year.desc())
           .first())
    year = row.year if row else CURRENT_YEAR
    return redirect(url_for('logs.year_view', year=year))


@bp.route('/<int:year>')
def year_view(year: int) -> str:
    entries = (
        LogEntry.query
        .filter_by(year=year)
        .order_by(LogEntry.date.asc())
        .all()
    )
    rated = [e.rating for e in entries if e.rating is not None]
    avg_rating = round(sum(rated) / len(rated), 1) if rated else None

    # Hill counts split by activity type (computed from entries, not meta)
    munros_run      = sum(e.munros_count      for e in entries if e.activity_type == 'run')
    munros_walk     = sum(e.munros_count      for e in entries if e.activity_type == 'walk')
    munros_total    = sum(e.munros_count      for e in entries)
    corbetts_run    = sum(e.corbetts_count    for e in entries if e.activity_type == 'run')
    corbetts_walk   = sum(e.corbetts_count    for e in entries if e.activity_type == 'walk')
    corbetts_total  = sum(e.corbetts_count    for e in entries)
    wainwrights_run   = sum(e.wainwrights_count for e in entries if e.activity_type == 'run')
    wainwrights_walk  = sum(e.wainwrights_count for e in entries if e.activity_type == 'walk')
    wainwrights_total = sum(e.wainwrights_count for e in entries)

    available_years = [
        row.year for row in
        db.session.query(LogEntry.year).distinct().order_by(LogEntry.year.desc()).all()
    ]
    if year not in available_years:
        available_years = sorted(set(available_years + [year]), reverse=True)

    return render_template(
        'logs/year.html',
        year=year,
        entries=entries,
        avg_rating=avg_rating,
        munros_run=munros_run, munros_walk=munros_walk, munros_total=munros_total,
        corbetts_run=corbetts_run, corbetts_walk=corbetts_walk, corbetts_total=corbetts_total,
        wainwrights_run=wainwrights_run, wainwrights_walk=wainwrights_walk,
        wainwrights_total=wainwrights_total,
        available_years=available_years,
        current_year=CURRENT_YEAR,
    )


@bp.route('/<int:year>/new', methods=['GET', 'POST'])
def new_entry(year: int) -> str | WerkzeugResponse:
    if year != CURRENT_YEAR:
        flash('New entries can only be added for the current year.', 'error')
        return redirect(url_for('logs.year_view', year=year))

    if request.method == 'POST':
        return _save_entry(year)

    return render_template('logs/new_entry.html', year=year)


def _save_entry(year: int) -> WerkzeugResponse:
    date_str = request.form.get('date', '').strip()
    if not date_str:
        flash('Date is required.', 'error')
        return redirect(url_for('logs.new_entry', year=year))

    try:
        datetime.date.fromisoformat(date_str)
    except ValueError:
        flash('Invalid date.', 'error')
        return redirect(url_for('logs.new_entry', year=year))

    try:
        distance_raw = request.form.get('distance_km', '').strip()
        ascent_raw = request.form.get('ascent_m', '').strip()
        rating_raw = request.form.get('rating', '').strip()
        corbetts_count = int(request.form.get('corbetts_count', '0') or '0')
        munros_count = int(request.form.get('munros_count', '0') or '0')
        wainwrights_count = int(request.form.get('wainwrights_count', '0') or '0')
        distance_km = float(distance_raw) if distance_raw else None
        ascent_m = int(ascent_raw) if ascent_raw else None
        rating = int(rating_raw) if rating_raw else None
    except ValueError:
        flash('Invalid value in a numeric field.', 'error')
        return redirect(url_for('logs.new_entry', year=year))

    # Collect linked hill IDs from hidden inputs hill_id_0, hill_id_1, ...
    linked_hill_ids: list[int] = []
    i = 0
    while True:
        raw = request.form.get(f'hill_id_{i}')
        if raw is None:
            break
        try:
            linked_hill_ids.append(int(raw))
        except ValueError:
            pass
        i += 1

    # Auto-count from linked hills if provided
    if linked_hill_ids:
        linked = Hill.query.filter(Hill.id.in_(linked_hill_ids)).all()
        munros_count = sum(1 for h in linked if h.hill_type == 'munro')
        corbetts_count = sum(1 for h in linked if h.hill_type == 'corbett')
        wainwrights_count = sum(1 for h in linked if h.hill_type == 'wainwright')

    entry = LogEntry(
        year=year,
        date=date_str,
        date_display=date_str,
        distance_km=distance_km,
        ascent_m=ascent_m,
        activity_type=request.form.get('activity_type', '').strip().lower() or None,
        with_whom=request.form.get('with_whom', '').strip() or None,
        region=request.form.get('region', '').strip() or None,
        notes=request.form.get('notes', '').strip() or None,
        hills_text=request.form.get('hills_text', '').strip() or None,
        corbetts_count=corbetts_count,
        munros_count=munros_count,
        wainwrights_count=wainwrights_count,
        rating=rating,
    )
    db.session.add(entry)
    db.session.flush()

    for hid in linked_hill_ids:
        db.session.add(LogEntryHill(log_entry_id=entry.id, hill_id=hid))

    _sync_hill_ascents(entry, linked_hill_ids)
    db.session.commit()
    flash('Entry saved.', 'success')
    return redirect(url_for('logs.year_view', year=year))


def _sync_hill_ascents(entry: LogEntry, hill_ids: list[int], old_date: str | None = None) -> None:
    """Keep HillAscent records in sync with this entry's linked hills.

    Removes ascents for previously-linked hills on old_date (falls back to
    entry.date for new entries), then adds fresh ones on entry.date.
    """
    new_date = entry.date
    cleanup_date = old_date if old_date is not None else new_date

    old_hill_ids = [leh.hill_id for leh in
                    LogEntryHill.query.filter_by(log_entry_id=entry.id).all()]
    if old_hill_ids:
        (HillAscent.query
         .filter(HillAscent.hill_id.in_(old_hill_ids),
                 HillAscent.date == cleanup_date)
         .delete(synchronize_session=False))

    for hid in hill_ids:
        db.session.add(HillAscent(hill_id=hid, date=new_date))


@bp.route('/<int:year>/<int:entry_id>/edit', methods=['GET', 'POST'])
def edit_entry(year: int, entry_id: int) -> str | WerkzeugResponse:
    entry = LogEntry.query.filter_by(id=entry_id, year=year).first_or_404()

    if request.method == 'POST':
        return _update_entry(entry)

    linked = (
        db.session.query(Hill)
        .join(LogEntryHill, Hill.id == LogEntryHill.hill_id)
        .filter(LogEntryHill.log_entry_id == entry.id)
        .all()
    )
    initial_hills = [{'id': h.id, 'name': h.name, 'type': h.hill_type} for h in linked]
    return render_template('logs/edit_entry.html', year=year, entry=entry, initial_hills=initial_hills)


def _update_entry(entry: LogEntry) -> WerkzeugResponse:
    year = entry.year
    date_str = request.form.get('date', '').strip()
    if not date_str:
        flash('Date is required.', 'error')
        return redirect(url_for('logs.edit_entry', year=year, entry_id=entry.id))

    try:
        datetime.date.fromisoformat(date_str)
    except ValueError:
        flash('Invalid date.', 'error')
        return redirect(url_for('logs.edit_entry', year=year, entry_id=entry.id))

    try:
        distance_raw = request.form.get('distance_km', '').strip()
        ascent_raw = request.form.get('ascent_m', '').strip()
        rating_raw = request.form.get('rating', '').strip()
        corbetts_count = int(request.form.get('corbetts_count', '0') or '0')
        munros_count = int(request.form.get('munros_count', '0') or '0')
        wainwrights_count = int(request.form.get('wainwrights_count', '0') or '0')
        distance_km = float(distance_raw) if distance_raw else None
        ascent_m = int(ascent_raw) if ascent_raw else None
        rating = int(rating_raw) if rating_raw else None
    except ValueError:
        flash('Invalid value in a numeric field.', 'error')
        return redirect(url_for('logs.edit_entry', year=year, entry_id=entry.id))

    linked_hill_ids: list[int] = []
    i = 0
    while True:
        raw = request.form.get(f'hill_id_{i}')
        if raw is None:
            break
        try:
            linked_hill_ids.append(int(raw))
        except ValueError:
            pass
        i += 1

    if linked_hill_ids:
        linked = Hill.query.filter(Hill.id.in_(linked_hill_ids)).all()
        munros_count = sum(1 for h in linked if h.hill_type == 'munro')
        corbetts_count = sum(1 for h in linked if h.hill_type == 'corbett')
        wainwrights_count = sum(1 for h in linked if h.hill_type == 'wainwright')

    old_date = entry.date
    entry.date = date_str
    entry.date_display = date_str
    entry.distance_km = distance_km
    entry.ascent_m = ascent_m
    entry.activity_type = request.form.get('activity_type', '').strip().lower() or None
    entry.with_whom = request.form.get('with_whom', '').strip() or None
    entry.region = request.form.get('region', '').strip() or None
    entry.notes = request.form.get('notes', '').strip() or None
    entry.hills_text = request.form.get('hills_text', '').strip() or None
    entry.corbetts_count = corbetts_count
    entry.munros_count = munros_count
    entry.wainwrights_count = wainwrights_count
    entry.rating = rating

    _sync_hill_ascents(entry, linked_hill_ids, old_date=old_date)
    LogEntryHill.query.filter_by(log_entry_id=entry.id).delete()
    for hid in linked_hill_ids:
        db.session.add(LogEntryHill(log_entry_id=entry.id, hill_id=hid))

    db.session.commit()
    flash('Entry updated.', 'success')
    return redirect(url_for('logs.year_view', year=year))


@bp.route('/<int:year>/<int:entry_id>/delete', methods=['POST'])
def delete_entry(year: int, entry_id: int) -> WerkzeugResponse:
    entry = LogEntry.query.filter_by(id=entry_id, year=year).first_or_404()

    linked_hill_ids = [leh.hill_id for leh in LogEntryHill.query.filter_by(log_entry_id=entry.id).all()]
    if linked_hill_ids:
        (HillAscent.query
         .filter(HillAscent.hill_id.in_(linked_hill_ids), HillAscent.date == entry.date)
         .delete(synchronize_session=False))
    LogEntryHill.query.filter_by(log_entry_id=entry.id).delete()
    db.session.delete(entry)
    db.session.commit()
    flash('Entry deleted.', 'success')
    return redirect(url_for('logs.year_view', year=year))


@bp.route('/import', methods=['GET', 'POST'])
def import_csv() -> str | WerkzeugResponse:
    available_years = [
        row.year for row in
        db.session.query(LogEntry.year).distinct().order_by(LogEntry.year.desc()).all()
    ]
    # Always include current year
    if CURRENT_YEAR not in available_years:
        available_years = sorted(set(available_years + [CURRENT_YEAR]), reverse=True)

    if request.method == 'GET':
        return render_template('logs/import.html', available_years=available_years,
                               current_year=CURRENT_YEAR)

    year_raw = request.form.get('year', '').strip()
    csv_text = request.form.get('csv_data', '').strip()

    try:
        year = int(year_raw)
    except ValueError:
        flash('Please select a year.', 'error')
        return render_template('logs/import.html', available_years=available_years,
                               current_year=CURRENT_YEAR)

    if not csv_text:
        flash('No CSV data provided.', 'error')
        return render_template('logs/import.html', available_years=available_years,
                               current_year=CURRENT_YEAR)

    reader = csv.DictReader(io.StringIO(csv_text))
    imported = skipped = 0
    errors: list[str] = []

    for i, row in enumerate(reader, start=2):
        date_str = (row.get('date') or '').strip()
        if not date_str:
            continue
        try:
            datetime.date.fromisoformat(date_str)
        except ValueError:
            errors.append(f'Row {i}: invalid date {repr(date_str)} — skipped')
            skipped += 1
            continue

        def _si(key: str) -> int | None:
            v = (row.get(key) or '').strip()
            try:
                return int(float(v)) if v else None
            except ValueError:
                return None

        def _sf(key: str) -> float | None:
            v = (row.get(key) or '').strip()
            try:
                return float(v) if v else None
            except ValueError:
                return None

        def _st(key: str) -> str | None:
            v = (row.get(key) or '').strip()
            return v or None

        act = (_st('activity_type') or '').lower()
        activity_type = act if act in ('walk', 'run', 'cycle') else None

        entry = LogEntry(
            year=year,
            date=date_str,
            date_display=date_str,
            distance_km=_sf('distance_km'),
            ascent_m=_si('ascent_m'),
            activity_type=activity_type,
            with_whom=_st('with_whom'),
            region=_st('region'),
            notes=_st('notes'),
            hills_text=_st('hills_text'),
            corbetts_count=_si('corbetts_count') or 0,
            munros_count=_si('munros_count') or 0,
            wainwrights_count=_si('wainwrights_count') or 0,
            rating=_si('rating'),
        )
        db.session.add(entry)
        imported += 1

    db.session.commit()

    for e in errors:
        flash(e, 'error')
    flash(f'Imported {imported} entries for {year}' + (f' ({skipped} skipped).' if skipped else '.'), 'success')
    return redirect(url_for('logs.year_view', year=year))


@bp.route('/api/hills/<hill_type>')
def api_hills(hill_type: str) -> Response:
    if hill_type not in ('munro', 'corbett', 'wainwright'):
        return jsonify({'error': 'Unknown hill type'}), 404  # type: ignore[return-value]
    hills = (Hill.query
             .filter_by(hill_type=hill_type)
             .order_by(Hill.name.asc())
             .all())
    return jsonify([{'id': h.id, 'name': h.name, 'height_m': h.height_m, 'region': h.region} for h in hills])
