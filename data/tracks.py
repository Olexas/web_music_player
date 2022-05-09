import sqlalchemy
from sqlalchemy import orm
from sqlalchemy_serializer import SerializerMixin

from .db_session import SqlAlchemyBase


class Track(SqlAlchemyBase, SerializerMixin):
    __tablename__ = 'track'
    id = sqlalchemy.Column(sqlalchemy.Integer,
                           primary_key=True, autoincrement=True)
    track_name = sqlalchemy.Column(sqlalchemy.String, nullable=False)
    y_track = sqlalchemy.Column(sqlalchemy.Boolean, default=False)
    y_artist_name = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    y_track_name = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    y_artist_id = sqlalchemy.Column(sqlalchemy.String, nullable=True)
    y_album_id = sqlalchemy.Column(sqlalchemy.Integer, nullable=True)
    y_track_id = sqlalchemy.Column(sqlalchemy.Integer, nullable=True)
    user_id = sqlalchemy.Column(sqlalchemy.Integer,
                                sqlalchemy.ForeignKey("users.id"))
    user = orm.relation('User')
