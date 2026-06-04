from flask import Blueprint

bp = Blueprint('goals', __name__,
               template_folder='templates',
               static_folder='static')

from goals import routes  # noqa: E402, F401
