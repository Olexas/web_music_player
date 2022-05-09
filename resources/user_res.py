from flask import jsonify
from flask_restful import Resource, abort, reqparse, Api

from data import db_session
from data.tracks import Track
from data.users import User

import os


def abort_if_user_not_found(user_id):
    session = db_session.create_session()
    tracks = session.query(User).get(user_id)
    if not tracks:
        abort(404, message=f"User {user_id} not found")


class UserResource(Resource):
    def get(self, user_id):
        abort_if_user_not_found(user_id)
        session = db_session.create_session()
        user = session.query(User).get(user_id)
        tracks = session.query(Track).filter(Track.user_id == user_id).all()
        sc = []
        for i in tracks:
            sc.append(i.track_name)
        user_sl = user.to_dict(only=('name', 'email', 'y_music_token'))
        user_sl['tracks'] = sc
        return jsonify({'user': user_sl})


class UserListResource(Resource):
    def get(self):
        session = db_session.create_session()
        users = session.query(User).all()
        return jsonify({'users': [item.to_dict(
            only=('id', 'name', 'email', 'y_music_token')) for item in users]})