import shutil
import os

from flask import Flask, render_template

from walks import db
import walks.models  # noqa: F401 — registers models with SQLAlchemy
import hills.models  # noqa: F401 — registers hills models with SQLAlchemy


def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = 'dev'

    if os.path.exists(db.DATABASE):
        shutil.copy2(db.DATABASE, db.DATABASE + '.bak')

    db.init_app(app)

    with app.app_context():
        db.init_db()

    from walks import bp as walks_bp
    app.register_blueprint(walks_bp, url_prefix='/walks')

    from hills import bp as hills_bp
    app.register_blueprint(hills_bp, url_prefix='/hills')

    @app.route('/')
    def home() -> str:
        return render_template('home.html')

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
