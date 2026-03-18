import os

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

DATABASE = os.path.join(os.path.dirname(__file__), 'walks.db')


def init_app(app):
    app.config.setdefault('SQLALCHEMY_DATABASE_URI', f'sqlite:///{DATABASE}')
    db.init_app(app)


def init_db():
    db.create_all()
