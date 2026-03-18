from flask import Blueprint

bp = Blueprint('walks', __name__,
               template_folder='templates',
               static_folder='static')

from walks import routes  # noqa: E402, F401
