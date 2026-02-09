from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

from models.user import User
from models.conge import Conge
from models.parametrage import ParametrageAnnuel, AllocationConge
from models.jour_ferie import JourFerie
