import shutil
import os
import datetime

from flask import Flask, render_template, request

from walks import db
import walks.models  # noqa: F401 — registers models with SQLAlchemy
import hills.models  # noqa: F401 — registers hills models with SQLAlchemy
import logs.models   # noqa: F401 — registers logs models with SQLAlchemy


def _ordinal(n: int) -> str:
    if 11 <= n % 100 <= 13:
        suffix = 'th'
    else:
        suffix = ['th', 'st', 'nd', 'rd', 'th'][min(n % 10, 4)]
    return f'{n}{suffix}'


def _friendly_date(value: str) -> str:
    """Format YYYY-MM-DD as '2nd January'."""
    try:
        d = datetime.date.fromisoformat(value)
        return f'{_ordinal(d.day)} {d.strftime("%B")}'
    except (ValueError, TypeError):
        return value


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.secret_key = 'dev'

    if test_config:
        app.config.update(test_config)
    elif os.path.exists(db.DATABASE):
        shutil.copyfile(db.DATABASE, db.DATABASE + '.bak')

    app.jinja_env.filters['friendly_date'] = _friendly_date

    db.init_app(app)

    with app.app_context():
        db.init_db()

    @app.after_request
    def sync_db_after_write(response):
        if request.method in ("POST", "PUT", "DELETE", "PATCH"):
            db.sync_db()
        return response

    from walks import bp as walks_bp
    app.register_blueprint(walks_bp, url_prefix='/bigruns')

    from hills import bp as hills_bp
    app.register_blueprint(hills_bp, url_prefix='/hills')

    from logs import bp as logs_bp
    app.register_blueprint(logs_bp, url_prefix='/logs')

    @app.route('/')
    def home() -> str:
        return render_template('home.html')

    return app


if __name__ == '__main__':
    app = create_app()
    print(f'Database: {os.path.abspath(db.DATABASE)}')
    db.sync_db()
    app.run(debug=True)
