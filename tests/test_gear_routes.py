from flask.testing import FlaskClient

from walks.db import db
from gear.models import Loadout, LoadoutItem


def _make_loadout(client: FlaskClient, name: str) -> int:
    r = client.post('/gear/new', data={'name': name})
    assert r.status_code == 302
    loc = r.headers['Location']
    return int(loc.rstrip('/').split('/')[-1])


class TestGearIndex:
    def test_empty_state(self, client: FlaskClient) -> None:
        r = client.get('/gear/')
        assert r.status_code == 200
        assert b'No loadouts yet' in r.data

    def test_redirects_to_first_loadout(self, client: FlaskClient) -> None:
        loadout_id = _make_loadout(client, 'Summer')
        r = client.get('/gear/')
        assert r.status_code == 302
        assert f'/gear/{loadout_id}' in r.headers['Location']


class TestLoadoutCreate:
    def test_create_loadout(self, client: FlaskClient) -> None:
        loadout_id = _make_loadout(client, "Tranter's summer")
        loadout = db.session.get(Loadout, loadout_id)
        assert loadout is not None
        assert loadout.name == "Tranter's summer"

    def test_create_empty_name_rejected(self, client: FlaskClient) -> None:
        r = client.post('/gear/new', data={'name': ''}, follow_redirects=True)
        assert Loadout.query.count() == 0
        assert r.status_code == 200

    def test_create_duplicate_name_rejected(self, client: FlaskClient) -> None:
        _make_loadout(client, 'Summer')
        r = client.post('/gear/new', data={'name': 'Summer'}, follow_redirects=True)
        assert Loadout.query.count() == 1
        assert b'already exists' in r.data


class TestItemAdd:
    def test_add_item(self, client: FlaskClient) -> None:
        loadout_id = _make_loadout(client, 'Summer')
        r = client.post(f'/gear/{loadout_id}/items', data={
            'category': 'Clothes',
            'name': 'OMM Kamleika Smock',
            'weight_g': '230',
            'owned': '1',
        })
        assert r.status_code == 302
        items = LoadoutItem.query.filter_by(loadout_id=loadout_id).all()
        assert len(items) == 1
        assert items[0].name == 'OMM Kamleika Smock'
        assert items[0].weight_g == 230
        assert items[0].owned is True

    def test_add_item_unowned_default(self, client: FlaskClient) -> None:
        loadout_id = _make_loadout(client, 'Summer')
        client.post(f'/gear/{loadout_id}/items', data={
            'category': 'Cooking',
            'name': 'Gels',
            'weight_g': '120',
        })
        item = LoadoutItem.query.filter_by(loadout_id=loadout_id).first()
        assert item is not None
        assert item.owned is False

    def test_add_item_negative_weight_rejected(self, client: FlaskClient) -> None:
        loadout_id = _make_loadout(client, 'Summer')
        client.post(f'/gear/{loadout_id}/items', data={
            'category': 'Clothes',
            'name': 'X',
            'weight_g': '-5',
        })
        assert LoadoutItem.query.filter_by(loadout_id=loadout_id).count() == 0

    def test_add_item_missing_name_rejected(self, client: FlaskClient) -> None:
        loadout_id = _make_loadout(client, 'Summer')
        client.post(f'/gear/{loadout_id}/items', data={
            'category': 'Clothes',
            'name': '',
            'weight_g': '100',
        })
        assert LoadoutItem.query.filter_by(loadout_id=loadout_id).count() == 0


class TestDetailView:
    def test_grouped_totals(self, client: FlaskClient) -> None:
        loadout_id = _make_loadout(client, 'Summer')
        items = [
            ('Clothes', 'Jacket', 230, True),
            ('Clothes', 'Gloves', 50, False),
            ('Cooking / Water', 'Stove', 120, True),
            ('Cooking / Water', 'Gas', 80, True),
            ('Misc', 'Whistle', 10, True),
        ]
        for cat, name, weight, owned in items:
            data = {'category': cat, 'name': name, 'weight_g': str(weight)}
            if owned:
                data['owned'] = '1'
            client.post(f'/gear/{loadout_id}/items', data=data)

        r = client.get(f'/gear/{loadout_id}')
        assert r.status_code == 200
        body = r.data.decode('utf-8')
        # Categories appear
        assert 'Clothes' in body
        assert 'Cooking / Water' in body
        assert 'Misc' in body
        # Per-category totals
        assert '280 g' in body  # Clothes
        assert '200 g' in body  # Cooking / Water
        # Overall total: 230 + 50 + 120 + 80 + 10 = 490
        assert '490 g' in body


class TestToggleOwned:
    def test_toggle_owned(self, client: FlaskClient) -> None:
        loadout_id = _make_loadout(client, 'Summer')
        client.post(f'/gear/{loadout_id}/items', data={
            'category': 'Clothes', 'name': 'Hat', 'weight_g': '30',
        })
        item = LoadoutItem.query.first()
        assert item is not None
        assert item.owned is False

        r = client.post(f'/gear/items/{item.id}/toggle-owned')
        assert r.status_code == 302
        db.session.refresh(item)
        assert item.owned is True

        client.post(f'/gear/items/{item.id}/toggle-owned')
        db.session.refresh(item)
        assert item.owned is False


class TestEditWeight:
    def test_update_weight(self, client: FlaskClient) -> None:
        loadout_id = _make_loadout(client, 'Summer')
        client.post(f'/gear/{loadout_id}/items', data={
            'category': 'Clothes', 'name': 'Hat', 'weight_g': '30',
        })
        item = LoadoutItem.query.first()
        assert item is not None
        r = client.post(f'/gear/items/{item.id}/weight', data={'weight_g': '55'})
        assert r.status_code == 302
        db.session.refresh(item)
        assert item.weight_g == 55

    def test_update_weight_negative_rejected(self, client: FlaskClient) -> None:
        loadout_id = _make_loadout(client, 'Summer')
        client.post(f'/gear/{loadout_id}/items', data={
            'category': 'Clothes', 'name': 'Hat', 'weight_g': '30',
        })
        item = LoadoutItem.query.first()
        assert item is not None
        client.post(f'/gear/items/{item.id}/weight', data={'weight_g': '-1'})
        db.session.refresh(item)
        assert item.weight_g == 30


class TestWorn:
    def test_worn_defaults_false(self, client: FlaskClient) -> None:
        loadout_id = _make_loadout(client, 'Summer')
        client.post(f'/gear/{loadout_id}/items', data={
            'category': 'Clothes', 'name': 'Hat', 'weight_g': '30',
        })
        item = LoadoutItem.query.first()
        assert item is not None
        assert item.worn is False

    def test_worn_total_sums_separately(self, client: FlaskClient) -> None:
        loadout_id = _make_loadout(client, 'Summer')
        # Worn items
        client.post(f'/gear/{loadout_id}/items', data={
            'category': 'Clothes', 'name': 'Trail shoes', 'weight_g': '300', 'worn': '1',
        })
        client.post(f'/gear/{loadout_id}/items', data={
            'category': 'Clothes', 'name': 'Shorts', 'weight_g': '100', 'worn': '1',
        })
        # Not worn
        client.post(f'/gear/{loadout_id}/items', data={
            'category': 'Cooking / Water', 'name': 'Stove', 'weight_g': '120',
        })
        r = client.get(f'/gear/{loadout_id}')
        body = r.data.decode('utf-8')
        # Overall total: 300 + 100 + 120 = 520
        assert '520 g' in body
        # Worn total: 300 + 100 = 400
        assert '400 g' in body

    def test_toggle_worn(self, client: FlaskClient) -> None:
        loadout_id = _make_loadout(client, 'Summer')
        client.post(f'/gear/{loadout_id}/items', data={
            'category': 'Clothes', 'name': 'Hat', 'weight_g': '30',
        })
        item = LoadoutItem.query.first()
        assert item is not None
        assert item.worn is False

        client.post(f'/gear/items/{item.id}/toggle-worn')
        db.session.refresh(item)
        assert item.worn is True

        client.post(f'/gear/items/{item.id}/toggle-worn')
        db.session.refresh(item)
        assert item.worn is False


class TestDelete:
    def test_delete_item(self, client: FlaskClient) -> None:
        loadout_id = _make_loadout(client, 'Summer')
        client.post(f'/gear/{loadout_id}/items', data={
            'category': 'Clothes', 'name': 'Hat', 'weight_g': '30',
        })
        item = LoadoutItem.query.first()
        assert item is not None
        client.post(f'/gear/items/{item.id}/delete')
        assert LoadoutItem.query.count() == 0

    def test_delete_loadout_cascades(self, client: FlaskClient) -> None:
        loadout_id = _make_loadout(client, 'Summer')
        client.post(f'/gear/{loadout_id}/items', data={
            'category': 'Clothes', 'name': 'Hat', 'weight_g': '30',
        })
        assert LoadoutItem.query.count() == 1
        client.post(f'/gear/{loadout_id}/delete')
        assert Loadout.query.count() == 0
        assert LoadoutItem.query.count() == 0


class TestNotFound:
    def test_detail_missing_loadout_redirects(self, client: FlaskClient) -> None:
        r = client.get('/gear/9999')
        assert r.status_code == 302
        assert r.headers['Location'].endswith('/gear/')
