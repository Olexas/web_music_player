from flask_wtf import FlaskForm
from wtforms import SubmitField
from flask_wtf.file import FileRequired, FileField


class LoadForm(FlaskForm):
    track_file = FileField('Загрузите трек:', validators=[FileRequired()])
    submit = SubmitField('Загрузить')