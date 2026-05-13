from flask import Blueprint

bp = Blueprint('gear', __name__,
               template_folder='templates',
               static_folder='static')

from gear import routes  # noqa: E402, F401
