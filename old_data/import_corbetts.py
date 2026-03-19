"""Import corbett data from old_data/corbetts.csv into the hills database."""
import csv
from datetime import datetime

from app import create_app
from walks.db import db
from hills.models import Hill, HillAscent


def import_corbetts() -> None:
    app = create_app()
    with app.app_context():
        # Clear existing corbetts
        HillAscent.query.filter(
            HillAscent.hill_id.in_(
                db.session.query(Hill.id).filter_by(hill_type='corbett')
            )
        ).delete(synchronize_session=False)
        Hill.query.filter_by(hill_type='corbett').delete()
        db.session.commit()

        with open('old_data/corbetts.csv', newline='') as f:
            reader = csv.reader(f)
            next(reader)  # skip header

            count = 0
            for row in reader:
                name = row[6].strip()
                if not name:
                    continue

                height_m = int(round(float(row[7])))
                rank = int(row[9])
                region = row[10].strip()

                hill = Hill(
                    name=name,
                    height_m=height_m,
                    rank=rank,
                    region=region,
                    hill_type='corbett',
                )
                db.session.add(hill)
                db.session.flush()

                # Dates start at column 13
                for col in row[13:]:
                    date_str = col.strip()
                    if not date_str:
                        continue
                    dt = datetime.strptime(date_str, '%d/%m/%Y')
                    db.session.add(HillAscent(
                        hill_id=hill.id,
                        date=dt.strftime('%Y-%m-%d'),
                    ))

                count += 1

            db.session.commit()
            print(f'Imported {count} corbetts.')


if __name__ == '__main__':
    import_corbetts()
