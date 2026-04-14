from flask import Blueprint, render_template
from backend.helpers import login_required

more_bp = Blueprint('more', __name__)


@more_bp.route('/wiecej')
@login_required
def more():
    return render_template('more.html')
