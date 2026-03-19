from flask import Blueprint

bp = Blueprint('logs', __name__,
               template_folder='templates',
               static_folder='static')

from logs import routes  # noqa: E402, F401
