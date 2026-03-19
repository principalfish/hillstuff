from collections import defaultdict

from flask import render_template, request, redirect, url_for, flash
from pydantic import ValidationError
from werkzeug.wrappers import Response as WerkzeugResponse

import unicodedata

from hills import bp
from hills.models import Hill, HillAscent
from hills.schemas import HillForm, AscentForm
from hills.ascent_import import parse_ascent_csv
from walks.db import db


HILL_TYPES = {
    'munros': 'munro',
    'corbetts': 'corbett',
    'wainwrights': 'wainwright',
}

HILL_TYPE_LABELS = {
    'munro': 'Munros',
    'corbett': 'Corbetts',
    'wainwright': 'Wainwrights',
}

HILL_TYPE_DESCRIPTIONS = {
    'munro': 'Scottish mountains over 3,000ft (914m).',
    'corbett': 'Scottish mountains between 2,500ft and 3,000ft.',
    'wainwright': 'Lake District fells catalogued by Alfred Wainwright.',
}


def _resolve_hill_type(slug: str) -> str | None:
    """Convert URL slug (munros/corbetts/wainwrights) to hill_type value."""
    return HILL_TYPES.get(slug)


@bp.route('/<slug>')
def hill_list(slug: str) -> str | WerkzeugResponse:
    hill_type = _resolve_hill_type(slug)
    if hill_type is None:
        flash('Unknown hill type.', 'error')
        return redirect(url_for('home'))

    hills = (
        Hill.query
        .filter_by(hill_type=hill_type)
        .order_by(Hill.rank.asc().nullslast(), Hill.height_m.desc())
        .all()
    )

    # Build hill rows with ascent stats
    hill_rows = []
    all_years: set[int] = set()
    for h in hills:
        ascent_dates: list[str] = [a.date for a in h.ascents]  # type: ignore[attr-defined]
        ascent_years = sorted({int(d[:4]) for d in ascent_dates if d and len(d) >= 4})
        first_year = ascent_years[0] if ascent_years else None
        all_years.update(ascent_years)
        hill_rows.append({
            'id': h.id,
            'name': h.name,
            'height_m': h.height_m,
            'rank': h.rank,
            'region': h.region,
            'ascent_count': len(ascent_dates),
            'first_year': first_year,
            'ascent_dates': ascent_dates,
        })

    # Year breakdown stats
    year_stats = _build_year_stats(hills)

    # Summary counts
    total_hills = len(hills)
    climbed_count = sum(1 for h in hill_rows if h['ascent_count'] > 0)

    return render_template('hills/list.html',
                           slug=slug,
                           hill_type=hill_type,
                           label=HILL_TYPE_LABELS[hill_type],
                           description=HILL_TYPE_DESCRIPTIONS[hill_type],
                           hills=hill_rows,
                           year_stats=year_stats,
                           total_hills=total_hills,
                           climbed_count=climbed_count)


def _build_year_stats(hills: list[Hill]) -> list[dict[str, int]]:
    """Build per-year stats: new hills climbed that year, total unique climbed by end of year."""
    # Track first-ascent year for each hill
    first_ascent_year: dict[int, int] = {}
    for h in hills:
        for a in h.ascents:  # type: ignore[attr-defined]
            if a.date and len(a.date) >= 4:
                year = int(a.date[:4])
                if h.id not in first_ascent_year or year < first_ascent_year[h.id]:
                    first_ascent_year[h.id] = year

    if not first_ascent_year:
        return []

    # Count new per year
    new_per_year: dict[int, int] = defaultdict(int)
    for hill_id, year in first_ascent_year.items():
        new_per_year[year] += 1

    # Also count total ascents per year (including repeats)
    ascents_per_year: dict[int, int] = defaultdict(int)
    for h in hills:
        for a in h.ascents:  # type: ignore[attr-defined]
            if a.date and len(a.date) >= 4:
                ascents_per_year[int(a.date[:4])] += 1

    all_years = set(new_per_year.keys()) | set(ascents_per_year.keys())
    min_year = min(all_years)
    max_year = max(all_years)

    stats = []
    cumulative = 0
    for year in range(min_year, max_year + 1):
        new = new_per_year.get(year, 0)
        total_ascents = ascents_per_year.get(year, 0)
        cumulative += new
        if new or total_ascents:
            stats.append({
                'year': year,
                'new': new,
                'ascents': total_ascents,
                'cumulative': cumulative,
            })

    return stats


@bp.route('/<slug>/new', methods=['GET', 'POST'])
def hill_new(slug: str) -> str | WerkzeugResponse:
    hill_type = _resolve_hill_type(slug)
    if hill_type is None:
        flash('Unknown hill type.', 'error')
        return redirect(url_for('home'))

    if request.method == 'POST':
        return _save_hill(slug, hill_type, None)

    return render_template('hills/form.html',
                           slug=slug,
                           hill_type=hill_type,
                           label=HILL_TYPE_LABELS[hill_type],
                           hill=None)


@bp.route('/<slug>/<int:hill_id>/edit', methods=['GET', 'POST'])
def hill_edit(slug: str, hill_id: int) -> str | WerkzeugResponse:
    hill_type = _resolve_hill_type(slug)
    if hill_type is None:
        flash('Unknown hill type.', 'error')
        return redirect(url_for('home'))

    hill = db.session.get(Hill, hill_id)
    if not hill or hill.hill_type != hill_type:
        flash('Hill not found.', 'error')
        return redirect(url_for('hills.hill_list', slug=slug))

    if request.method == 'POST':
        return _save_hill(slug, hill_type, hill_id)

    return render_template('hills/form.html',
                           slug=slug,
                           hill_type=hill_type,
                           label=HILL_TYPE_LABELS[hill_type],
                           hill=hill)


def _save_hill(slug: str, hill_type: str, hill_id: int | None) -> WerkzeugResponse:
    try:
        form = HillForm.model_validate({
            'name': request.form.get('name', ''),
            'height_m': request.form.get('height_m', '0'),
            'rank': request.form.get('rank', '') or None,
            'region': request.form.get('region', ''),
            'hill_type': hill_type,
        })
    except ValidationError as e:
        for err in e.errors():
            flash(f'{err["loc"][-1]}: {err["msg"]}', 'error')
        if hill_id:
            return redirect(url_for('hills.hill_edit', slug=slug, hill_id=hill_id))
        return redirect(url_for('hills.hill_new', slug=slug))

    if hill_id is None:
        hill = Hill(
            name=form.name, height_m=form.height_m,
            rank=form.rank, region=form.region, hill_type=form.hill_type,
        )
        db.session.add(hill)
    else:
        existing = db.session.get(Hill, hill_id)
        assert existing is not None
        hill = existing
        hill.name = form.name
        hill.height_m = form.height_m
        hill.rank = form.rank
        hill.region = form.region

    db.session.commit()
    flash('Hill saved.', 'success')
    return redirect(url_for('hills.hill_list', slug=slug))


@bp.route('/<slug>/<int:hill_id>/delete', methods=['POST'])
def hill_delete(slug: str, hill_id: int) -> WerkzeugResponse:
    hill = db.session.get(Hill, hill_id)
    if hill:
        db.session.delete(hill)
        db.session.commit()
    flash('Hill deleted.', 'success')
    return redirect(url_for('hills.hill_list', slug=slug))


@bp.route('/<slug>/<int:hill_id>/ascents', methods=['POST'])
def add_ascent(slug: str, hill_id: int) -> WerkzeugResponse:
    hill_type = _resolve_hill_type(slug)
    if hill_type is None:
        flash('Unknown hill type.', 'error')
        return redirect(url_for('home'))

    hill = db.session.get(Hill, hill_id)
    if not hill or hill.hill_type != hill_type:
        flash('Hill not found.', 'error')
        return redirect(url_for('hills.hill_list', slug=slug))

    try:
        form = AscentForm(date=request.form.get('date', ''))
    except ValidationError as e:
        for err in e.errors():
            flash(f'{err["loc"][-1]}: {err["msg"]}', 'error')
        return redirect(url_for('hills.hill_list', slug=slug))

    db.session.add(HillAscent(hill_id=hill_id, date=form.date))
    db.session.commit()
    flash('Ascent recorded.', 'success')
    return redirect(url_for('hills.hill_list', slug=slug))


@bp.route('/<slug>/import', methods=['GET', 'POST'])
def import_ascents(slug: str) -> str | WerkzeugResponse:
    hill_type = _resolve_hill_type(slug)
    if hill_type is None:
        flash('Unknown hill type.', 'error')
        return redirect(url_for('home'))

    hills = (Hill.query.filter_by(hill_type=hill_type)
             .order_by(Hill.name).all())
    hills_by_name = {unicodedata.normalize('NFC', h.name.lower()): h.id for h in hills}

    csv_text = ''
    result = None

    if request.method == 'POST':
        csv_text = request.form.get('csv_data', '').strip()
        if not csv_text:
            flash('No data provided.', 'error')
        else:
            result = parse_ascent_csv(csv_text, hills_by_name)
            if result.ok:
                if not result.ascents:
                    flash('No ascents found in the data.', 'error')
                else:
                    # Reset ascents for all hills present in the import
                    hill_ids = {a.hill_id for a in result.ascents}
                    HillAscent.query.filter(
                        HillAscent.hill_id.in_(hill_ids)
                    ).delete(synchronize_session=False)
                    for a in result.ascents:
                        db.session.add(HillAscent(hill_id=a.hill_id, date=a.date))
                    db.session.commit()
                    flash(
                        f'Imported {len(result.ascents)} ascent(s) for '
                        f'{len(hill_ids)} hill(s).',
                        'success',
                    )
                    return redirect(url_for('hills.hill_list', slug=slug))

    return render_template(
        'hills/import.html',
        slug=slug,
        label=HILL_TYPE_LABELS[hill_type],
        csv_text=csv_text,
        result=result,
    )


@bp.route('/<slug>/<int:hill_id>/ascents/<int:ascent_id>/delete', methods=['POST'])
def delete_ascent(slug: str, hill_id: int, ascent_id: int) -> WerkzeugResponse:
    ascent = HillAscent.query.filter_by(id=ascent_id, hill_id=hill_id).first()
    if ascent:
        db.session.delete(ascent)
        db.session.commit()
    flash('Ascent deleted.', 'success')
    return redirect(url_for('hills.hill_list', slug=slug))
