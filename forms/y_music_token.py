from flask_wtf import FlaskForm
from wtforms import SubmitField, StringField, Field
from wtforms.validators import DataRequired


class TokenForm(FlaskForm):
    token = StringField('Токен', validators=[DataRequired()])
    submit = SubmitField('Загрузить')


class YMusicIdForm(FlaskForm):
    album_id_form = StringField('ID альбома')
    album_id_submit = SubmitField('Перейти')

    artist_id_form = StringField('ID артиста')
    artist_id_submit = SubmitField('Перейти')

    track_id_form = StringField('ID трека')
    track_id_submit = SubmitField('Перейти')


class YMusicForm(FlaskForm):
    submit_last_track = SubmitField('Добавить')

    function2_id = StringField('Номер трека/треков')
    function2_submit = SubmitField('Добавить')

    function3_submit = SubmitField('Добавить')