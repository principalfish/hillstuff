from flask import Blueprint

bp = Blueprint('hills', __name__,
               template_folder='templates',
               static_folder='static')

from hills import routes  # noqa: E402, F401
