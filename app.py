from flask import Flask, render_template

from walks import db
import walks.models  # noqa: F401 — registers models with SQLAlchemy


def create_app():
    app = Flask(__name__)
    app.secret_key = 'dev'

    db.init_app(app)

    with app.app_context():
        db.init_db()

    from walks import bp as walks_bp
    app.register_blueprint(walks_bp, url_prefix='/walks')

    @app.route('/')
    def home():
        return render_template('home.html')

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
