from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

from models.user import User
from models.conge import Conge
from models.notification import Notification
from models.push_subscription import PushSubscription
from models.parametrage import ParametrageAnnuel, AllocationConge
from models.jour_ferie import JourFerie
