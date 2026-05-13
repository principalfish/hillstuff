from flask import render_template, request, redirect, url_for, flash
from pydantic import ValidationError
from werkzeug.wrappers import Response as WerkzeugResponse

from gear import bp
from gear.models import Loadout, LoadoutItem
from gear.schemas import LoadoutCreate, LoadoutItemCreate, LoadoutItemWeightUpdate
from walks.db import db


CATEGORIES = [
    'Tent',
    'Rucksack',
    'Sleeping',
    'Electronics',
    'Clothes',
    'Cooking / Water',
    'Dry Bags',
    'Misc',
]


@bp.route('/')
def index() -> WerkzeugResponse | str:
    first = Loadout.query.order_by(Loadout.name).first()
    if first is None:
        return render_template('gear/detail.html',
                               loadouts=[],
                               loadout=None,
                               items_by_category=[],
                               category_totals={},
                               overall_total=0,
                               worn_total=0,
                               pack_total=0,
                               categories=CATEGORIES)
    return redirect(url_for('gear.detail', loadout_id=first.id))


@bp.route('/<int:loadout_id>')
def detail(loadout_id: int) -> WerkzeugResponse | str:
    loadout = db.session.get(Loadout, loadout_id)
    if loadout is None:
        flash('Loadout not found.', 'error')
        return redirect(url_for('gear.index'))

    loadouts = Loadout.query.order_by(Loadout.name).all()

    items_by_cat: dict[str, list[LoadoutItem]] = {}
    for item in loadout.items:  # type: ignore[attr-defined]
        items_by_cat.setdefault(item.category, []).append(item)

    cat_order = {c: i for i, c in enumerate(CATEGORIES)}

    def _cat_sort_key(cat: str) -> tuple[int, str]:
        return (cat_order.get(cat, len(CATEGORIES)), cat.casefold())

    items_by_category = []
    category_totals: dict[str, int] = {}
    for cat in sorted(items_by_cat.keys(), key=_cat_sort_key):
        items = sorted(items_by_cat[cat], key=lambda i: i.name.casefold())
        total = sum(i.weight_g for i in items)
        items_by_category.append({'category': cat, 'items': items, 'total': total})
        category_totals[cat] = total

    overall_total = sum(category_totals.values())
    worn_total = sum(i.weight_g for i in loadout.items if i.worn)  # type: ignore[attr-defined]
    pack_total = overall_total - worn_total

    return render_template('gear/detail.html',
                           loadouts=loadouts,
                           loadout=loadout,
                           items_by_category=items_by_category,
                           category_totals=category_totals,
                           overall_total=overall_total,
                           worn_total=worn_total,
                           pack_total=pack_total,
                           categories=CATEGORIES)


@bp.route('/new', methods=['POST'])
def loadout_new() -> WerkzeugResponse:
    try:
        form = LoadoutCreate.model_validate({'name': request.form.get('name', '')})
    except ValidationError as e:
        for err in e.errors():
            flash(f'{err["loc"][-1]}: {err["msg"]}', 'error')
        return redirect(url_for('gear.index'))

    existing = Loadout.query.filter_by(name=form.name).first()
    if existing is not None:
        flash('A loadout with that name already exists.', 'error')
        return redirect(url_for('gear.detail', loadout_id=existing.id))

    loadout = Loadout(name=form.name)
    db.session.add(loadout)
    db.session.commit()
    flash('Loadout created.', 'success')
    return redirect(url_for('gear.detail', loadout_id=loadout.id))


@bp.route('/<int:loadout_id>/items', methods=['POST'])
def item_add(loadout_id: int) -> WerkzeugResponse:
    loadout = db.session.get(Loadout, loadout_id)
    if loadout is None:
        flash('Loadout not found.', 'error')
        return redirect(url_for('gear.index'))

    try:
        form = LoadoutItemCreate.model_validate({
            'category': request.form.get('category', ''),
            'name': request.form.get('name', ''),
            'weight_g': request.form.get('weight_g', '0'),
            'owned': bool(request.form.get('owned')),
            'worn': bool(request.form.get('worn')),
        })
    except ValidationError as e:
        for err in e.errors():
            flash(f'{err["loc"][-1]}: {err["msg"]}', 'error')
        return redirect(url_for('gear.detail', loadout_id=loadout_id))

    db.session.add(LoadoutItem(
        loadout_id=loadout_id,
        category=form.category,
        name=form.name,
        weight_g=form.weight_g,
        owned=form.owned,
        worn=form.worn,
    ))
    db.session.commit()
    flash('Item added.', 'success')
    return redirect(url_for('gear.detail', loadout_id=loadout_id))


@bp.route('/items/<int:item_id>/toggle-owned', methods=['POST'])
def item_toggle_owned(item_id: int) -> WerkzeugResponse:
    item = db.session.get(LoadoutItem, item_id)
    if item is None:
        flash('Item not found.', 'error')
        return redirect(url_for('gear.index'))
    item.owned = not item.owned
    loadout_id = item.loadout_id
    db.session.commit()
    return redirect(url_for('gear.detail', loadout_id=loadout_id))


@bp.route('/items/<int:item_id>/weight', methods=['POST'])
def item_update_weight(item_id: int) -> WerkzeugResponse:
    item = db.session.get(LoadoutItem, item_id)
    if item is None:
        flash('Item not found.', 'error')
        return redirect(url_for('gear.index'))
    loadout_id = item.loadout_id
    try:
        form = LoadoutItemWeightUpdate.model_validate({
            'weight_g': request.form.get('weight_g', '0'),
        })
    except ValidationError as e:
        for err in e.errors():
            flash(f'{err["loc"][-1]}: {err["msg"]}', 'error')
        return redirect(url_for('gear.detail', loadout_id=loadout_id))
    item.weight_g = form.weight_g
    db.session.commit()
    return redirect(url_for('gear.detail', loadout_id=loadout_id))


@bp.route('/items/<int:item_id>/toggle-worn', methods=['POST'])
def item_toggle_worn(item_id: int) -> WerkzeugResponse:
    item = db.session.get(LoadoutItem, item_id)
    if item is None:
        flash('Item not found.', 'error')
        return redirect(url_for('gear.index'))
    item.worn = not item.worn
    loadout_id = item.loadout_id
    db.session.commit()
    return redirect(url_for('gear.detail', loadout_id=loadout_id))


@bp.route('/items/<int:item_id>/delete', methods=['POST'])
def item_delete(item_id: int) -> WerkzeugResponse:
    item = db.session.get(LoadoutItem, item_id)
    if item is None:
        flash('Item not found.', 'error')
        return redirect(url_for('gear.index'))
    loadout_id = item.loadout_id
    db.session.delete(item)
    db.session.commit()
    flash('Item deleted.', 'success')
    return redirect(url_for('gear.detail', loadout_id=loadout_id))


@bp.route('/<int:loadout_id>/delete', methods=['POST'])
def loadout_delete(loadout_id: int) -> WerkzeugResponse:
    loadout = db.session.get(Loadout, loadout_id)
    if loadout is None:
        flash('Loadout not found.', 'error')
        return redirect(url_for('gear.index'))
    db.session.delete(loadout)
    db.session.commit()
    flash('Loadout deleted.', 'success')
    return redirect(url_for('gear.index'))
