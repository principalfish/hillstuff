"""Import wainwright data from old_data/wainwrights.csv into the hills database."""
import csv
import math

from app import create_app
from walks.db import db
from hills.models import Hill, HillAscent

BOOK_REGIONS: dict[str, str] = {
    'E': 'Eastern Fells',
    'FE': 'Far Eastern Fells',
    'C': 'Central Fells',
    'S': 'Southern Fells',
    'N': 'Northern Fells',
    'NW': 'North Western Fells',
    'W': 'Western Fells',
}


def import_wainwrights() -> None:
    app = create_app()
    with app.app_context():
        # Clear existing wainwrights
        HillAscent.query.filter(
            HillAscent.hill_id.in_(
                db.session.query(Hill.id).filter_by(hill_type='wainwright')
            )
        ).delete(synchronize_session=False)
        Hill.query.filter_by(hill_type='wainwright').delete()
        db.session.commit()

        with open('old_data/wainwrights.csv', newline='') as f:
            reader = csv.reader(f)
            next(reader)  # skip header

            count = 0
            for row in reader:
                name = row[1].strip()
                if not name:
                    continue

                rank_str = row[0].strip()
                if not rank_str.isdigit():
                    continue

                rank = int(rank_str)
                height_ft = int(row[2])
                height_m = round(height_ft * 0.3048)
                book_code = row[5].strip()
                region = BOOK_REGIONS.get(book_code, book_code)

                hill = Hill(
                    name=name,
                    height_m=height_m,
                    rank=rank,
                    region=region,
                    hill_type='wainwright',
                )
                db.session.add(hill)
                db.session.flush()

                # Create placeholder ascent if climbed
                latest_asc = row[3].strip()
                tick = row[8].strip()
                if tick == '1' and latest_asc:
                    db.session.add(HillAscent(
                        hill_id=hill.id,
                        date=f'{latest_asc}-01-01',
                    ))

                count += 1

            db.session.commit()
            print(f'Imported {count} wainwrights.')


if __name__ == '__main__':
    import_wainwrights()
