from flask import jsonify
from flask_restful import Resource, abort, reqparse, Api

from data import db_session
from data.tracks import Track
from data.users import User

import yandex_music


def abort_if_track_not_found(track_id):
    session = db_session.create_session()
    tracks = session.query(Track).get(track_id)
    if not tracks:
        abort(404, message=f"Track {track_id} not found")


class TrackResource(Resource):
    def get(self, track_id):
        abort_if_track_not_found(track_id)
        session = db_session.create_session()
        track = session.query(Track).get(track_id)
        if track.y_track:
            track_sl = track.to_dict(only=('track_name', 'user_id', 'y_artist_name', 'y_track_name',
                                           'y_artist_id', 'y_album_id', 'y_track_id'))
        else:
            track_sl = track.to_dict(only=('track_name', 'user_id'))
        return jsonify({'track': track_sl})


class TrackListResource(Resource):
    def get(self):
        session = db_session.create_session()
        tracks = session.query(Track).all()
        return jsonify({'tracks': [item.to_dict(
            only=('id', 'track_name', 'user_id')) for item in tracks]})


class YandexMusicTrackResource(Resource):
    def get(self, y_track_id):
        session = db_session.create_session()
        tracks = session.query(Track).filter(Track.y_track_id == y_track_id).all()
        sc = []
        for i in tracks:
            sc.append(i.user_id)
        return jsonify({'users': sc})


class YandexMusicAlbumResource(Resource):
    def get(self, y_album_id):
        session = db_session.create_session()
        tracks = session.query(Track).filter(Track.y_album_id == y_album_id).all()
        return jsonify({'tracks': [item.to_dict(
            only=('id', 'track_name', 'user_id', 'y_track_id')) for item in tracks]})


class YandexMusicArtistResource(Resource):
    def get(self, y_artist_id):
        session = db_session.create_session()
        tracks = session.query(Track).filter(Track.y_artist_id == y_artist_id).all()
        return jsonify({'tracks': [item.to_dict(
            only=('id', 'track_name', 'user_id', 'y_track_id')) for item in tracks]})