"""Import munro data from old_data/munro.csv into the hills database."""
import csv
from datetime import datetime

from app import create_app
from walks.db import db
from hills.models import Hill, HillAscent


def import_munros() -> None:
    app = create_app()
    with app.app_context():
        # Clear existing munros
        HillAscent.query.filter(
            HillAscent.hill_id.in_(
                db.session.query(Hill.id).filter_by(hill_type='munro')
            )
        ).delete(synchronize_session=False)
        Hill.query.filter_by(hill_type='munro').delete()
        db.session.commit()

        with open('old_data/munro.csv', newline='') as f:
            reader = csv.reader(f)
            header = next(reader)  # skip header row

            count = 0
            for row in reader:
                # Hill data starts at column 6 (index 6)
                name = row[6].strip()
                if not name:
                    continue

                height_m = int(row[7])
                rank = int(row[9])
                region = row[11].strip()

                hill = Hill(
                    name=name,
                    height_m=height_m,
                    rank=rank,
                    region=region,
                    hill_type='munro',
                )
                db.session.add(hill)
                db.session.flush()

                # Ascent dates start at column 14 onwards
                for col in row[14:]:
                    date_str = col.strip()
                    if not date_str:
                        continue
                    # Convert DD/MM/YYYY to YYYY-MM-DD
                    dt = datetime.strptime(date_str, '%d/%m/%Y')
                    db.session.add(HillAscent(
                        hill_id=hill.id,
                        date=dt.strftime('%Y-%m-%d'),
                    ))

                count += 1

            db.session.commit()
            print(f'Imported {count} munros.')


if __name__ == '__main__':
    import_munros()
