import os

from flask import Flask
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

PROJECT_ROOT: str = os.path.dirname(os.path.dirname(__file__))
DATABASE: str = os.environ.get('WALKS_DB') or os.path.join(PROJECT_ROOT, 'walks.db')


def init_app(app: Flask) -> None:
    app.config.setdefault('SQLALCHEMY_DATABASE_URI', f'sqlite:///{DATABASE}')
    db.init_app(app)


def init_db() -> None:
    db.create_all()
