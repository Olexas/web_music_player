from flask import Flask
from data import db_session
from flask import Flask, render_template, redirect, url_for, request
from flask_restful import reqparse, abort, Api, Resource
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
import requests
from mutagen.id3 import ID3
from yandex_music import Client

from data.tracks import Track
from data.users import User
from forms.y_music_token import TokenForm, YMusicForm, YMusicIdForm
from forms.user import RegisterForm, LoginForm
from forms.track import LoadForm
from resources import track_res, user_res

from os import path
import os


app = Flask(__name__)
app.config['SECRET_KEY'] = 'olexas_web_player_key'
api = Api(app)

login_manager = LoginManager()
login_manager.init_app(app)

api.add_resource(track_res.TrackListResource, '/api/tracks')
api.add_resource(user_res.UserListResource, '/api/users')

api.add_resource(user_res.UserResource, '/api/users/<int:user_id>')
api.add_resource(track_res.TrackResource, '/api/tracks/<int:track_id>')

api.add_resource(track_res.YandexMusicTrackResource, '/api/yandex_music_track/<int:y_track_id>')
api.add_resource(track_res.YandexMusicAlbumResource, '/api/yandex_music_album/<int:y_album_id>')
api.add_resource(track_res.YandexMusicArtistResource, '/api/yandex_music_artist/<int:y_artist_id>')


@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect("/player")
    return redirect("/login")


@app.route("/instruction")
def instruction():
    return render_template('y_music_instruction.html')


@app.route("/delete_track/<int:track_id>", methods=['GET', 'POST'])
@login_required
def delete_track(track_id):
    session = db_session.create_session()
    track = session.query(Track).filter(Track.user_id == current_user.id).all()
    track_name = track[track_id].track_name
    session.delete(track[track_id])
    session.commit()

    try:
        if os.path.isfile(f'static/{current_user.name}/music/{track_name}'):
            os.remove(f'static/{current_user.name}/music/{track_name}')
    except(Exception):
        pass

    try:
        if os.path.isfile(f'static/{current_user.name}/img/{track_name[:-4]}.jpg'):
            os.remove(f'static/{current_user.name}/img/{track_name[:-4]}.jpg')
    except(Exception):
        pass

    return redirect("/player")


@app.route("/yandex_music/add_track/<int:track_id>", methods=['GET', 'POST'])
@login_required
def yandex_music_add_track(track_id):
    session = db_session.create_session()
    user = session.query(User).filter(current_user.id == User.id).first()
    form = YMusicIdForm()
    token = user.y_music_token
    client = Client(token).init()

    account_info = f'Ваш аккаунт: {client.accountStatus().account["full_name"]} ({client.accountStatus().account["login"]})'
    music_folder = f'static/{current_user.name}/music/'
    image_folder = f'static/{current_user.name}/img/'
    print('Начало загрузки')

    y_track = client.tracks(track_ids=track_id)[0]
    filename = f"{', '.join(y_track.artists_name())} - {y_track.title}" + '.mp3'

    for i in '/|*?"<>?':
        filename = filename.replace(i, '')

    print(f'Загрузка трека: {filename}')

    if session.query(Track).filter(Track.track_name == filename,
                                   Track.user_id == current_user.id).first():
        return '<script>document.location.href = document.referrer</script>'
    sc = []
    for i in y_track.artists:
        sc.append(str(i.id))

    sc = ', '.join(sc)

    track_id, album_id = y_track.track_id.split(':')

    track = Track(
        track_name=filename,
        user_id=current_user.id,
        y_track=True,
        y_artist_name=', '.join(y_track.artists_name()),
        y_track_name=y_track.title,
        y_artist_id=sc,
        y_album_id=album_id,
        y_track_id=track_id
    )
    session.add(track)
    session.commit()

    track_file = open(f'{music_folder}{filename}', 'x')
    track_file.close()

    y_track.download(f'{music_folder}{filename}')
    y_track.download_cover(f'{image_folder}{filename[:-4]}.jpg')

    print('Загрузка завершена успешно')

    return '<script>document.location.href = document.referrer</script>'


@app.route("/yandex_music", methods=['GET', 'POST'])
@login_required
def yandex_music_menu():
    session = db_session.create_session()
    user = session.query(User).filter(current_user.id == User.id).first()

    if not user.y_music_token:
        form = TokenForm()
        if form.validate_on_submit():
            token = form.token.data
            try:
                client = Client(token).init()
                a = client.users_likes_tracks()[0].fetch_track()
            except Exception:
                return render_template('y_music_token.html',
                                       message='Ошибка: Токен введен неверно или является недействительным', form=form)
            user.y_music_token = form.token.data
            session.commit()
            session.close()
            return redirect('/yandex_music')
        return render_template('y_music_token.html', title='Авторизация Яндекс Музыки', form=form)

    form = YMusicIdForm()
    token = user.y_music_token
    client = Client(token).init()
    account_info = f'Ваш аккаунт: {client.accountStatus().account["full_name"]} ({client.accountStatus().account["login"]})'

    if form.validate_on_submit():
        if form.album_id_submit.data:
            return redirect(f'/yandex_music/albums/{form.album_id_form.data}')
        elif form.artist_id_submit.data:
            return redirect(f'/yandex_music/artists/{form.artist_id_form.data}')
        elif form.track_id_submit.data:
            session = db_session.create_session()
            music_folder = f'static/{current_user.name}/music/'
            image_folder = f'static/{current_user.name}/img/'
            print('Начало загрузки')

            y_track = client.tracks(track_ids=form.track_id_form.data)[0]
            filename = f"{', '.join(y_track.artists_name())} - {y_track.title}" + '.mp3'

            for i in '/|*?"<>?':
                filename = filename.replace(i, '')

            print(f'Загрузка трека: {filename}')

            if session.query(Track).filter(Track.track_name == filename, Track.user_id == current_user.id).first():
                return render_template('y_music_api_menu.html', message=f'Ошибка: {filename} уже загружен', form=form,
                                       acinfo=account_info)

            sc = []
            for i in y_track.artists:
                sc.append(str(i.id))

            sc = ', '.join(sc)


            track_id, album_id = y_track.track_id.split(':')

            track = Track(
                track_name=filename,
                user_id=current_user.id,
                y_track=True,
                y_artist_name=', '.join(y_track.artists_name()),
                y_track_name=y_track.title,
                y_artist_id=sc,
                y_album_id=album_id,
                y_track_id=track_id
            )
            session.add(track)
            session.commit()

            track_file = open(f'{music_folder}{filename}', 'x')
            track_file.close()

            y_track.download(f'{music_folder}{filename}')
            y_track.download_cover(f'{image_folder}{filename[:-4]}.jpg')

            print('Загрузка завершена успешно')

            return redirect(f"/yandex_music")

    playlists = list(client.users_playlists_list())
    playlists_names = list()
    for i in playlists:
        playlists_names.append(i.title)
    print(playlists_names)

    return render_template('y_music_api_menu.html', acinfo=account_info, playlists=playlists_names, form=form)


@app.route("/yandex_music/artists/<current_artist_id>", methods=['GET', 'POST'])
@login_required
def artists(current_artist_id):
    session = db_session.create_session()
    user = session.query(User).filter(current_user.id == User.id).first()
    if not user.y_music_token:
        form = TokenForm()
        if form.validate_on_submit():
            token = form.token.data
            try:
                client = Client(token).init()
                a = client.users_likes_tracks()[0].fetch_track()
            except Exception:
                return render_template('y_music_token.html',
                                       message='Ошибка: Токен введен неверно или является недействительным', form=form)
            user.y_music_token = form.token.data
            session.commit()
            session.close()
            return redirect(f"/yandex_music/albums/{current_artist_id}")
        return render_template('y_music_token.html', title='Авторизация Яндекс Музыки', form=form)

    form = YMusicForm()
    token = user.y_music_token
    client = Client(token).init()
    page_size = client.artists(current_artist_id)[0]['counts']['tracks']
    current_artist_tracks = client.artists_tracks(current_artist_id, page_size=page_size)
    current_artist = client.artists(current_artist_id)[0]
    account_info = f'Ваш аккаунт: {client.accountStatus().account["full_name"]} ({client.accountStatus().account["login"]})'
    first_text = f'Функция №1: Добавить первый трек артиста: "{current_artist.name}"'
    second_text = f'Функция №2: Добавить определенный трек/треки артиста: "{current_artist.name}"'
    third_text = f'Функция №3: Добавить все треки артиста: "{current_artist.name}"'
    track_list = []
    track_num = 1
    for track in current_artist_tracks:
        fetch_track = track
        track_list.append([track_num, ', '.join(fetch_track.artists_name()), fetch_track.title, fetch_track.id])
        track_num += 1
    print(track_list)

    if form.validate_on_submit():
        session = db_session.create_session()
        music_folder = f'static/{current_user.name}/music/'
        image_folder = f'static/{current_user.name}/img/'

        if form.submit_last_track.data:
            try:
                print('Начало загрузки')
                y_track = current_artist_tracks[0]
                filename = f"{', '.join(y_track.artists_name())} - {y_track.title}" + '.mp3'

                for i in '/|*?"<>?':
                    filename = filename.replace(i, '')

                print(f'Загрузка трека: {filename}')

                if session.query(Track).filter(Track.track_name == filename, Track.user_id == current_user.id).first():
                    return render_template('y_music_api.html', message=f'Ошибка: {filename} уже загружен', form=form,
                                           acinfo=account_info, first_text=first_text,
                                           second_text=second_text,
                                           third_text=third_text, track_list=track_list)

                sc = []
                for i in y_track.artists:
                    sc.append(str(i.id))

                sc = ', '.join(sc)

                track_id, album_id = y_track.track_id.split(':')

                track = Track(
                    track_name=filename,
                    user_id=current_user.id,
                    y_track=True,
                    y_artist_name=', '.join(y_track.artists_name()),
                    y_track_name=y_track.title,
                    y_artist_id=sc,
                    y_album_id=album_id,
                    y_track_id=track_id
                )
                session.add(track)
                session.commit()

                track_file = open(f'{music_folder}{filename}', 'x')
                track_file.close()

                y_track.download(f'{music_folder}{filename}')
                y_track.download_cover(f'{image_folder}{filename[:-4]}.jpg')

                print('Загрузка завершена успешно')

                return render_template('y_music_api.html', title='Яндекс Музыка API', form=form,
                                       acinfo=account_info,
                                       message='Готово!', first_text=first_text,
                                       second_text=second_text,
                                       third_text=third_text, track_list=track_list)
            except Exception as e:
                print(e)
                return render_template('y_music_api.html', title='Яндекс Музыка API', form=form, acinfo=account_info,
                                       message='Произошла ошибка при загрузке', first_text=first_text,
                                       second_text=second_text,
                                       third_text=third_text, track_list=track_list)

        elif form.function2_submit.data:
            try:
                if form.function2_id.data.isdigit():
                    print('Начало загрузки')
                    index = int(form.function2_id.data) - 1
                    y_track = current_artist_tracks[index]
                    filename = f"{', '.join(y_track.artists_name())} - {y_track.title}" + '.mp3'

                    if session.query(Track).filter(Track.track_name == filename,
                                                   Track.user_id == current_user.id).first():
                        return render_template('y_music_api.html', message1=f'Ошибка: {filename} уже загружен',
                                               form=form,
                                               first_text=first_text,
                                               second_text=second_text,
                                               third_text=third_text, track_list=track_list)

                    for i in '/|*?"<>?':
                        filename = filename.replace(i, '')

                    print(f'Загрузка трека: {filename}')

                    sc = []
                    for i in y_track.artists:
                        sc.append(str(i.id))

                    sc = ', '.join(sc)

                    track_id, album_id = y_track.track_id.split(':')

                    track = Track(
                        track_name=filename,
                        user_id=current_user.id,
                        y_track=True,
                        y_artist_name=', '.join(y_track.artists_name()),
                        y_track_name=y_track.title,
                        y_artist_id=sc,
                        y_album_id=album_id,
                        y_track_id=track_id
                    )
                    session.add(track)
                    session.commit()

                    track_file = open(f'{music_folder}{filename}', 'x')
                    track_file.close()

                    y_track.download(f'{music_folder}{filename}')
                    y_track.download_cover(f'{image_folder}{filename[:-4]}.jpg')
                    print('Загрузка завершена успешно')
                    return render_template('y_music_api.html', title='Яндекс Музыка API', form=form,
                                           acinfo=account_info,
                                           message1='Готово!', first_text=first_text,
                                           second_text=second_text,
                                           third_text=third_text, track_list=track_list)
                else:
                    index1, index2 = list(map(int, form.function2_id.data.split(':')))
                    print('Начало загрузки')
                    for index in range(index1 - 1, index2):
                        y_track = current_artist_tracks[index]
                        filename = f"{', '.join(y_track.artists_name())} - {y_track.title}" + '.mp3'

                        for i in '/|*?"<>?':
                            filename = filename.replace(i, '')

                        print(f'Загрузка трека: {filename}')

                        if session.query(Track).filter(Track.track_name == filename,
                                                       Track.user_id == current_user.id).first():
                            continue

                        sc = []
                        for i in y_track.artists:
                            sc.append(str(i.id))

                        sc = ', '.join(sc)

                        track_id, album_id = y_track.track_id.split(':')

                        track = Track(
                            track_name=filename,
                            user_id=current_user.id,
                            y_track=True,
                            y_artist_name=', '.join(y_track.artists_name()),
                            y_track_name=y_track.title,
                            y_artist_id=sc,
                            y_album_id=album_id,
                            y_track_id=track_id
                        )
                        session.add(track)
                        session.commit()

                        # track_file = open(f'{music_folder}{filename}', 'x')
                        # track_file.close()

                        y_track.download(f'{music_folder}{filename}')
                        y_track.download_cover(f'{image_folder}{filename[:-4]}.jpg')
                    print('Загрузка завершена успешно')
                    return render_template('y_music_api.html', title='Яндекс Музыка API', form=form, message1='Готово!',
                                           acinfo=account_info, first_text=first_text,
                                           second_text=second_text,
                                           third_text=third_text, track_list=track_list)
            except Exception as e:
                print(e)
                return render_template('y_music_api.html', title='Яндекс Музыка API', form=form, acinfo=account_info,
                                       message1='Произошла ошибка при загрузке', first_text=first_text,
                                       second_text=second_text,
                                       third_text=third_text, track_list=track_list)

        elif form.function3_submit.data:
            try:
                print('Начало загрузки')
                for track in current_artist_tracks:
                    y_track = track
                    filename = f"{', '.join(y_track.artists_name())} - {y_track.title}" + '.mp3'

                    for i in '/|*?"<>?':
                        filename = filename.replace(i, '')

                    print(f'Загрузка трека: {filename}')

                    if session.query(Track).filter(Track.track_name == filename,
                                                   Track.user_id == current_user.id).first():
                        continue

                    sc = []
                    for i in y_track.artists:
                        sc.append(str(i.id))

                    sc = ', '.join(sc)

                    track_id, album_id = y_track.track_id.split(':')

                    track = Track(
                        track_name=filename,
                        user_id=current_user.id,
                        y_track=True,
                        y_artist_name=', '.join(y_track.artists_name()),
                        y_track_name=y_track.title,
                        y_artist_id=sc,
                        y_album_id=album_id,
                        y_track_id=track_id
                    )
                    session.add(track)
                    session.commit()

                    y_track.download(f'{music_folder}{filename}')
                    y_track.download_cover(f'{image_folder}{filename[:-4]}.jpg')

                print('Загрузка завершена успешно')
                return render_template('y_music_api.html', title='Яндекс Музыка API', form=form, message2='Готово!',
                                       acinfo=account_info, first_text=first_text,
                                       second_text=second_text,
                                       third_text=third_text, track_list=track_list)

            except Exception as e:
                print(e)
                return render_template('y_music_api.html', title='Яндекс Музыка API', form=form, acinfo=account_info,
                                       message2='Произошла ошибка при загрузке', first_text=first_text,
                                       second_text=second_text,
                                       third_text=third_text, track_list=track_list)

    return render_template('y_music_api.html', title='Яндекс Музыка API', form=form, acinfo=account_info,
                           first_text=first_text, second_text=second_text, third_text=third_text, track_list=track_list)


@app.route("/yandex_music/albums/<current_album_id>", methods=['GET', 'POST'])
@login_required
def albums(current_album_id):
    session = db_session.create_session()
    user = session.query(User).filter(current_user.id == User.id).first()
    if not user.y_music_token:
        form = TokenForm()
        if form.validate_on_submit():
            token = form.token.data
            try:
                client = Client(token).init()
                a = client.users_likes_tracks()[0].fetch_track()
            except Exception:
                return render_template('y_music_token.html',
                                       message='Ошибка: Токен введен неверно или является недействительным', form=form)
            user.y_music_token = form.token.data
            session.commit()
            session.close()
            return redirect(f"/yandex_music/albums/{current_album_id}")
        return render_template('y_music_token.html', title='Авторизация Яндекс Музыки', form=form)

    form = YMusicForm()
    token = user.y_music_token
    client = Client(token).init()
    current_album_with_tracks = client.albums_with_tracks(album_id=current_album_id)
    current_album = client.albums(album_ids=current_album_id)[0]
    account_info = f'Ваш аккаунт: {client.accountStatus().account["full_name"]} ({client.accountStatus().account["login"]})'
    first_text = f'Функция №1: Добавить первый трек из альбома: "{", ".join(current_album.artists_name())} - {current_album.title}"'
    second_text = f'Функция №2: Добавить определенный трек/треки из альбома: "{", ".join(current_album.artists_name())} - {current_album.title}"'
    third_text = f'Функция №3: Добавить все треки из альбома "{", ".join(current_album.artists_name())} - {current_album.title}"'
    track_list = []
    track_num = 1
    for track in current_album_with_tracks['volumes'][0]:
        fetch_track = track
        track_list.append([track_num, ', '.join(fetch_track.artists_name()), fetch_track.title, fetch_track.id])
        track_num += 1
    print(track_list)

    if form.validate_on_submit():
        session = db_session.create_session()
        music_folder = f'static/{current_user.name}/music/'
        image_folder = f'static/{current_user.name}/img/'

        if form.submit_last_track.data:
            try:
                print('Начало загрузки')
                y_track = current_album_with_tracks['volumes'][0][0]
                filename = f"{', '.join(y_track.artists_name())} - {y_track.title}" + '.mp3'

                for i in '/|*?"<>?':
                    filename = filename.replace(i, '')

                print(f'Загрузка трека: {filename}')

                if session.query(Track).filter(Track.track_name == filename, Track.user_id == current_user.id).first():
                    return render_template('y_music_api.html', message=f'Ошибка: {filename} уже загружен', form=form,
                                           acinfo=account_info, first_text=first_text,
                                           second_text=second_text,
                                           third_text=third_text, track_list=track_list)

                sc = []
                for i in y_track.artists:
                    sc.append(str(i.id))

                sc = ', '.join(sc)

                track_id, album_id = y_track.track_id.split(':')

                track = Track(
                    track_name=filename,
                    user_id=current_user.id,
                    y_track=True,
                    y_artist_name=', '.join(y_track.artists_name()),
                    y_track_name=y_track.title,
                    y_artist_id=sc,
                    y_album_id=album_id,
                    y_track_id=track_id
                )
                session.add(track)
                session.commit()

                track_file = open(f'{music_folder}{filename}', 'x')
                track_file.close()

                y_track.download(f'{music_folder}{filename}')
                y_track.download_cover(f'{image_folder}{filename[:-4]}.jpg')

                print('Загрузка завершена успешно')

                return render_template('y_music_api.html', title='Яндекс Музыка API', form=form,
                                       acinfo=account_info,
                                       message='Готово!', first_text=first_text,
                                       second_text=second_text,
                                       third_text=third_text, track_list=track_list)
            except Exception as e:
                print(e)
                return render_template('y_music_api.html', title='Яндекс Музыка API', form=form, acinfo=account_info,
                                       message='Произошла ошибка при загрузке', first_text=first_text,
                                       second_text=second_text,
                                       third_text=third_text, track_list=track_list)

        elif form.function2_submit.data:
            try:
                if form.function2_id.data.isdigit():
                    print('Начало загрузки')
                    index = int(form.function2_id.data) - 1
                    y_track = current_album_with_tracks['volumes'][0][index]
                    filename = f"{', '.join(y_track.artists_name())} - {y_track.title}" + '.mp3'


                    a = session.query(Track).all()
                    for i in a:
                        print(i.track_name, filename)
                    if session.query(Track).filter(Track.track_name == filename,
                                                   Track.user_id == current_user.id).first():
                        print('okok')
                        return render_template('y_music_api.html', message1=f'Ошибка: {filename} уже загружен',
                                               form=form,
                                               first_text=first_text,
                                               second_text=second_text,
                                               third_text=third_text, track_list=track_list)

                    for i in '/|*?"<>?':
                        filename = filename.replace(i, '')

                    print(f'Загрузка трека: {filename}')

                    sc = []
                    for i in y_track.artists:
                        sc.append(str(i.id))

                    sc = ', '.join(sc)

                    track_id, album_id = y_track.track_id.split(':')

                    track = Track(
                        track_name=filename,
                        user_id=current_user.id,
                        y_track=True,
                        y_artist_name=', '.join(y_track.artists_name()),
                        y_track_name=y_track.title,
                        y_artist_id=sc,
                        y_album_id=album_id,
                        y_track_id=track_id
                    )
                    session.add(track)
                    session.commit()

                    track_file = open(f'{music_folder}{filename}', 'x')
                    track_file.close()

                    y_track.download(f'{music_folder}{filename}')
                    y_track.download_cover(f'{image_folder}{filename[:-4]}.jpg')
                    print('Загрузка завершена успешно')
                    return render_template('y_music_api.html', title='Яндекс Музыка API', form=form,
                                           acinfo=account_info,
                                           message1='Готово!', first_text=first_text,
                                           second_text=second_text,
                                           third_text=third_text, track_list=track_list)
                else:
                    index1, index2 = list(map(int, form.function2_id.data.split(':')))
                    print('Начало загрузки')
                    for index in range(index1 - 1, index2):
                        y_track = current_album_with_tracks['volumes'][0][index]
                        filename = f"{', '.join(y_track.artists_name())} - {y_track.title}" + '.mp3'

                        for i in '/|*?"<>?':
                            filename = filename.replace(i, '')

                        print(f'Загрузка трека: {filename}')

                        if session.query(Track).filter(Track.track_name == filename,
                                                       Track.user_id == current_user.id).first():
                            continue

                        sc = []
                        for i in y_track.artists:
                            sc.append(str(i.id))

                        sc = ', '.join(sc)

                        track_id, album_id = y_track.track_id.split(':')

                        track = Track(
                            track_name=filename,
                            user_id=current_user.id,
                            y_track=True,
                            y_artist_name=', '.join(y_track.artists_name()),
                            y_track_name=y_track.title,
                            y_artist_id=sc,
                            y_album_id=album_id,
                            y_track_id=track_id
                        )
                        session.add(track)
                        session.commit()

                        # track_file = open(f'{music_folder}{filename}', 'x')
                        # track_file.close()

                        y_track.download(f'{music_folder}{filename}')
                        y_track.download_cover(f'{image_folder}{filename[:-4]}.jpg')
                    print('Загрузка завершена успешно')
                    return render_template('y_music_api.html', title='Яндекс Музыка API', form=form, message1='Готово!',
                                           acinfo=account_info, first_text=first_text,
                                           second_text=second_text,
                                           third_text=third_text, track_list=track_list)
            except Exception as e:
                print(e)
                return render_template('y_music_api.html', title='Яндекс Музыка API', form=form, acinfo=account_info,
                                       message1='Произошла ошибка при загрузке', first_text=first_text,
                                       second_text=second_text,
                                       third_text=third_text, track_list=track_list)

        elif form.function3_submit.data:
            try:
                print('Начало загрузки')
                print(current_album_with_tracks['volumes'][0])
                for track in current_album_with_tracks['volumes'][0]:
                    y_track = track
                    filename = f"{', '.join(y_track.artists_name())} - {y_track.title}" + '.mp3'

                    for i in '/|*?"<>?':
                        filename = filename.replace(i, '')

                    print(f'Загрузка трека: {filename}')

                    if session.query(Track).filter(Track.track_name == filename,
                                                   Track.user_id == current_user.id).first():
                        continue

                    sc = []
                    for i in y_track.artists:
                        sc.append(str(i.id))

                    sc = ', '.join(sc)

                    track_id, album_id = y_track.track_id.split(':')

                    track = Track(
                        track_name=filename,
                        user_id=current_user.id,
                        y_track=True,
                        y_artist_name=', '.join(y_track.artists_name()),
                        y_track_name=y_track.title,
                        y_artist_id=sc,
                        y_album_id=album_id,
                        y_track_id=track_id
                    )
                    session.add(track)
                    session.commit()

                    y_track.download(f'{music_folder}{filename}')
                    y_track.download_cover(f'{image_folder}{filename[:-4]}.jpg')

                print('Загрузка завершена успешно')
                return render_template('y_music_api.html', title='Яндекс Музыка API', form=form, message2='Готово!',
                                       acinfo=account_info, first_text=first_text,
                                       second_text=second_text,
                                       third_text=third_text, track_list=track_list)

            except Exception as e:
                print(e)
                return render_template('y_music_api.html', title='Яндекс Музыка API', form=form, acinfo=account_info,
                                       message2='Произошла ошибка при загрузке', first_text=first_text,
                                       second_text=second_text,
                                       third_text=third_text, track_list=track_list)

    return render_template('y_music_api.html', title='Яндекс Музыка API', form=form, acinfo=account_info,
                           first_text=first_text, second_text=second_text, third_text=third_text, track_list=track_list)


@app.route("/yandex_music/users_playlists/<current_playlist>", methods=['GET', 'POST'])
@login_required
def users_playlists(current_playlist):
    session = db_session.create_session()
    user = session.query(User).filter(current_user.id == User.id).first()
    if not user.y_music_token:
        form = TokenForm()
        if form.validate_on_submit():
            token = form.token.data
            try:
                client = Client(token).init()
                a = client.users_likes_tracks()[0].fetch_track()
            except Exception:
                return render_template('y_music_token.html',
                                       message='Ошибка: Токен введен неверно или является недействительным', form=form)
            user.y_music_token = form.token.data
            session.commit()
            session.close()
            return redirect(f"/yandex_music/users_playlists/{current_playlist}")
        return render_template('y_music_token.html', title='Авторизация Яндекс Музыки', form=form)

    form = YMusicForm()
    token = user.y_music_token
    client = Client(token).init()
    account_info = f'Ваш аккаунт: {client.accountStatus().account["full_name"]} ({client.accountStatus().account["login"]})'
    first_text = f'Функция №1: Добавить первый трек из плейлиста: "{current_playlist}"'
    second_text = f'Функция №2: Добавить определенный трек/треки из плейлиста: "{current_playlist}"'
    third_text = f'Функция №3: Добавить все треки из плейлиста: "{current_playlist}"'
    track_list = []
    current_playlist_data = ''
    for i in client.users_playlists_list():
        if i.title == current_playlist:
            current_playlist_data = i
    uid, kind = current_playlist_data.playlistId.split(":")
    track_num = 1
    for track in client.users_playlists(kind=kind, user_id=uid).tracks:
        fetch_track = track.fetch_track()
        track_list.append([track_num, ', '.join(fetch_track.artists_name()), fetch_track.title, fetch_track.id])
        track_num += 1
    print(track_list)

    if form.validate_on_submit():
        session = db_session.create_session()
        music_folder = f'static/{current_user.name}/music/'
        image_folder = f'static/{current_user.name}/img/'

        if form.submit_last_track.data:
            try:
                print('Начало загрузки')
                current_playlist_data = ''
                for i in client.users_playlists_list():
                    if i.title == current_playlist:
                        current_playlist_data = i
                uid, kind = current_playlist_data.playlistId.split(":")
                y_track = client.users_playlists(kind=kind, user_id=uid).tracks[0].fetch_track()
                filename = f"{', '.join(y_track.artists_name())} - {y_track.title}" + '.mp3'

                for i in '/|*?"<>?':
                    filename = filename.replace(i, '')

                print(f'Загрузка трека: {filename}')

                if session.query(Track).filter(Track.track_name == filename, Track.user_id == current_user.id).first():
                    return render_template('y_music_api.html', message=f'Ошибка: {filename} уже загружен', form=form,
                                           acinfo=account_info, first_text=first_text,
                                           second_text=second_text,
                                           third_text=third_text, track_list=track_list)

                sc = []
                for i in y_track.artists:
                    sc.append(str(i.id))

                sc = ', '.join(sc)

                track_id, album_id = y_track.track_id.split(':')

                track = Track(
                    track_name=filename,
                    user_id=current_user.id,
                    y_track=True,
                    y_artist_name=', '.join(y_track.artists_name()),
                    y_track_name=y_track.title,
                    y_artist_id=sc,
                    y_album_id=album_id,
                    y_track_id=track_id
                )
                session.add(track)
                session.commit()

                track_file = open(f'{music_folder}{filename}', 'x')
                track_file.close()

                y_track.download(f'{music_folder}{filename}')
                y_track.download_cover(f'{image_folder}{filename[:-4]}.jpg')

                print('Загрузка завершена успешно')

                return render_template('y_music_api.html', title='Яндекс Музыка API', form=form,
                                       acinfo=account_info,
                                       message='Готово!', first_text=first_text,
                                       second_text=second_text,
                                       third_text=third_text, track_list=track_list)
            except Exception as e:
                print(e)
                return render_template('y_music_api.html', title='Яндекс Музыка API', form=form, acinfo=account_info,
                                       message='Произошла ошибка при загрузке', first_text=first_text,
                                       second_text=second_text,
                                       third_text=third_text, track_list=track_list)

        elif form.function2_submit.data:
            try:
                if form.function2_id.data.isdigit():
                    print('Начало загрузки')
                    index = int(form.function2_id.data) - 1
                    current_playlist_data = ''
                    for i in client.users_playlists_list():
                        if i.title == current_playlist:
                            current_playlist_data = i
                    uid, kind = current_playlist_data.playlistId.split(":")
                    y_track = client.users_playlists(kind=kind, user_id=uid).tracks[index].fetch_track()
                    filename = f"{', '.join(y_track.artists_name())} - {y_track.title}" + '.mp3'

                    if session.query(Track).filter(Track.track_name == filename,
                                                   Track.user_id == current_user.id).first():
                        return render_template('y_music_api.html', message1=f'Ошибка: {filename} уже загружен',
                                               form=form,
                                               first_text=first_text,
                                               second_text=second_text,
                                               third_text=third_text, track_list=track_list)

                    for i in '/|*?"<>?':
                        filename = filename.replace(i, '')

                    print(f'Загрузка трека: {filename}')

                    sc = []
                    for i in y_track.artists:
                        sc.append(str(i.id))

                    sc = ', '.join(sc)

                    track_id, album_id = y_track.track_id.split(':')

                    track = Track(
                        track_name=filename,
                        user_id=current_user.id,
                        y_track=True,
                        y_artist_name=', '.join(y_track.artists_name()),
                        y_track_name=y_track.title,
                        y_artist_id=sc,
                        y_album_id=album_id,
                        y_track_id=track_id
                    )
                    session.add(track)
                    session.commit()

                    track_file = open(f'{music_folder}{filename}', 'x')
                    track_file.close()

                    y_track.download(f'{music_folder}{filename}')
                    y_track.download_cover(f'{image_folder}{filename[:-4]}.jpg')
                    print('Загрузка завершена успешно')
                    return render_template('y_music_api.html', title='Яндекс Музыка API', form=form,
                                           acinfo=account_info,
                                           message1='Готово!', first_text=first_text,
                                           second_text=second_text,
                                           third_text=third_text, track_list=track_list)
                else:
                    index1, index2 = list(map(int, form.function2_id.data.split(':')))
                    print('Начало загрузки')
                    current_playlist_data = ''
                    for i in client.users_playlists_list():
                        if i.title == current_playlist:
                            current_playlist_data = i
                    uid, kind = current_playlist_data.playlistId.split(":")
                    for index in range(index1 - 1, index2):
                        y_track = client.users_playlists(kind=kind, user_id=uid).tracks[index].fetch_track()
                        filename = f"{', '.join(y_track.artists_name())} - {y_track.title}" + '.mp3'

                        for i in '/|*?"<>?':
                            filename = filename.replace(i, '')

                        print(f'Загрузка трека: {filename}')

                        if session.query(Track).filter(Track.track_name == filename,
                                                       Track.user_id == current_user.id).first():
                            continue

                        sc = []
                        for i in y_track.artists:
                            sc.append(str(i.id))

                        sc = ', '.join(sc)

                        track_id, album_id = y_track.track_id.split(':')

                        track = Track(
                            track_name=filename,
                            user_id=current_user.id,
                            y_track=True,
                            y_artist_name=', '.join(y_track.artists_name()),
                            y_track_name=y_track.title,
                            y_artist_id=sc,
                            y_album_id=album_id,
                            y_track_id=track_id
                        )
                        session.add(track)
                        session.commit()

                        # track_file = open(f'{music_folder}{filename}', 'x')
                        # track_file.close()

                        y_track.download(f'{music_folder}{filename}')
                        y_track.download_cover(f'{image_folder}{filename[:-4]}.jpg')
                    print('Загрузка завершена успешно')
                    return render_template('y_music_api.html', title='Яндекс Музыка API', form=form, message1='Готово!',
                                           acinfo=account_info, first_text=first_text,
                                           second_text=second_text,
                                           third_text=third_text, track_list=track_list)
            except Exception as e:
                print(e)
                return render_template('y_music_api.html', title='Яндекс Музыка API', form=form, acinfo=account_info,
                                       message1='Произошла ошибка при загрузке', first_text=first_text,
                                       second_text=second_text,
                                       third_text=third_text, track_list=track_list)

        elif form.function3_submit.data:
            try:
                print('Начало загрузки')
                current_playlist_data = ''
                for i in client.users_playlists_list():
                    if i.title == current_playlist:
                        current_playlist_data = i
                uid, kind = current_playlist_data.playlistId.split(":")
                for track in client.users_playlists(kind=kind, user_id=uid).tracks:
                    y_track = track.fetch_track()
                    filename = f"{', '.join(y_track.artists_name())} - {y_track.title}" + '.mp3'

                    for i in '/|*?"<>?':
                        filename = filename.replace(i, '')

                    print(f'Загрузка трека: {filename}')

                    if session.query(Track).filter(Track.track_name == filename,
                                                   Track.user_id == current_user.id).first():
                        continue

                    sc = []
                    for i in y_track.artists:
                        sc.append(str(i.id))

                    sc = ', '.join(sc)

                    track_id, album_id = y_track.track_id.split(':')

                    track = Track(
                        track_name=filename,
                        user_id=current_user.id,
                        y_track=True,
                        y_artist_name=', '.join(y_track.artists_name()),
                        y_track_name=y_track.title,
                        y_artist_id=sc,
                        y_album_id=album_id,
                        y_track_id=track_id
                    )
                    session.add(track)
                    session.commit()

                    y_track.download(f'{music_folder}{filename}')
                    y_track.download_cover(f'{image_folder}{filename[:-4]}.jpg')

                print('Загрузка завершена успешно')
                return render_template('y_music_api.html', title='Яндекс Музыка API', form=form, message2='Готово!',
                                       acinfo=account_info, first_text=first_text,
                                       second_text=second_text,
                                       third_text=third_text, track_list=track_list)

            except Exception as e:
                print(e)
                return render_template('y_music_api.html', title='Яндекс Музыка API', form=form, acinfo=account_info,
                                       message2='Произошла ошибка при загрузке', first_text=first_text,
                                       second_text=second_text,
                                       third_text=third_text, track_list=track_list)

    return render_template('y_music_api.html', title='Яндекс Музыка API', form=form, acinfo=account_info,
                           first_text=first_text, second_text=second_text, third_text=third_text, track_list=track_list)


@app.route("/yandex_music/users_like_tracks", methods=['GET', 'POST'])
@login_required
def users_like_tracks():
    session = db_session.create_session()
    user = session.query(User).filter(current_user.id == User.id).first()
    if not user.y_music_token:
        form = TokenForm()
        if form.validate_on_submit():
            token = form.token.data
            try:
                client = Client(token).init()
                a = client.users_likes_tracks()[0].fetch_track()
            except Exception:
                return render_template('y_music_token.html', message='Ошибка: Токен введен неверно или является недействительным', form=form)
            user.y_music_token = form.token.data
            session.commit()
            session.close()
            return redirect("/yandex_music/users_like_tracks")
        return render_template('y_music_token.html', title='Авторизация Яндекс Музыки', form=form)

    form = YMusicForm()
    token = user.y_music_token
    client = Client(token).init()
    account_info = f'Ваш аккаунт: {client.accountStatus().account["full_name"]} ({client.accountStatus().account["login"]})'
    first_text = 'Функция №1: Добавить последний добавленный трек из плейлиста: "Мне нравится"'
    second_text = 'Функция №2: Добавить определенный трек/треки из плейлиста: "Мне нравится"'
    third_text = 'Функция №3: Добавить все треки из плейлиста "Мне нравится"'
    track_list = []
    track_num = 1
    for track in client.users_likes_tracks():
        fetch_track = track.fetch_track()
        track_list.append([track_num, ', '.join(fetch_track.artists_name()), fetch_track.title, fetch_track.id])
        track_num += 1
    print(track_list)

    if form.validate_on_submit():
        session = db_session.create_session()
        music_folder = f'static/{current_user.name}/music/'
        image_folder = f'static/{current_user.name}/img/'

        if form.submit_last_track.data:
            try:
                print('Начало загрузки')
                y_track = client.users_likes_tracks()[0].fetch_track()
                filename = f"{', '.join(y_track.artists_name())} - {y_track.title}" + '.mp3'

                for i in '/|*?"<>?':
                    filename = filename.replace(i, '')

                print(f'Загрузка трека: {filename}')

                if session.query(Track).filter(Track.track_name == filename, Track.user_id == current_user.id).first():
                    return render_template('y_music_api.html', message=f'Ошибка: {filename} уже загружен', form=form,
                                           acinfo=account_info, first_text=first_text,
                                           second_text=second_text,
                                           third_text=third_text, track_list=track_list)

                sc = []
                for i in y_track.artists:
                    sc.append(str(i.id))

                sc = ', '.join(sc)

                track_id, album_id = y_track.track_id.split(':')

                track = Track(
                    track_name=filename,
                    user_id=current_user.id,
                    y_track=True,
                    y_artist_name=', '.join(y_track.artists_name()),
                    y_track_name=y_track.title,
                    y_artist_id=sc,
                    y_album_id=album_id,
                    y_track_id=track_id
                )
                session.add(track)
                session.commit()

                track_file = open(f'{music_folder}{filename}', 'x')
                track_file.close()

                y_track.download(f'{music_folder}{filename}')
                y_track.download_cover(f'{image_folder}{filename[:-4]}.jpg')

                print('Загрузка завершена успешно')

                return render_template('y_music_api.html', title='Яндекс Музыка API', form=form, acinfo=account_info,
                                       message='Готово!', first_text=first_text,
                                       second_text=second_text,
                                       third_text=third_text, track_list=track_list)
            except Exception:
                return render_template('y_music_api.html', title='Яндекс Музыка API', form=form, acinfo=account_info,
                                       message='Готово!', first_text=first_text,
                                           second_text=second_text,
                                           third_text=third_text, track_list=track_list)

        elif form.function2_submit.data:
            try:
                if form.function2_id.data.isdigit():
                    print('Начало загрузки')
                    index = int(form.function2_id.data) - 1
                    y_track = client.users_likes_tracks()[index].fetch_track()
                    filename = f"{', '.join(y_track.artists_name())} - {y_track.title}" + '.mp3'

                    for i in '/|*?"<>?':
                        filename = filename.replace(i, '')

                    print(f'Загрузка трека: {filename}')


                    if session.query(Track).filter(Track.track_name == filename, Track.user_id == current_user.id).first():

                        return render_template('y_music_api.html', message1=f'Ошибка: {filename} уже загружен', form=form,
                                            first_text=first_text,
                                            second_text=second_text,
                                            third_text=third_text, track_list=track_list)

                    sc = []
                    for i in y_track.artists:
                        sc.append(str(i.id))

                    sc = ', '.join(sc)

                    track_id, album_id = y_track.track_id.split(':')

                    track = Track(
                        track_name=filename,
                        user_id=current_user.id,
                        y_track=True,
                        y_artist_name=', '.join(y_track.artists_name()),
                        y_track_name=y_track.title,
                        y_artist_id=sc,
                        y_album_id=album_id,
                        y_track_id=track_id
                    )
                    session.add(track)
                    session.commit()

                    track_file = open(f'{music_folder}{filename}', 'x')
                    track_file.close()

                    y_track.download(f'{music_folder}{filename}')
                    y_track.download_cover(f'{image_folder}{filename[:-4]}.jpg')
                    print('Загрузка завершена успешно')
                    return render_template('y_music_api.html', title='Яндекс Музыка API', form=form, acinfo=account_info,
                                           message1='Готово!', first_text=first_text,
                                           second_text=second_text,
                                           third_text=third_text, track_list=track_list)
                else:
                    index1, index2 = list(map(int, form.function2_id.data.split(':')))
                    print('Начало загрузки')
                    for index in range(index1 - 1, index2):
                        y_track = client.users_likes_tracks()[index].fetch_track()
                        filename = f"{', '.join(y_track.artists_name())} - {y_track.title}" + '.mp3'

                        for i in '/|*?"<>?':
                            filename = filename.replace(i, '')

                        print(f'Загрузка трека: {filename}')

                        if session.query(Track).filter(Track.track_name == filename,
                                                       Track.user_id == current_user.id).first():
                            continue
                        sc = []
                        for i in y_track.artists:
                            sc.append(str(i.id))

                        sc = ', '.join(sc)

                        track_id, album_id = y_track.track_id.split(':')

                        track = Track(
                            track_name=filename,
                            user_id=current_user.id,
                            y_track=True,
                            y_artist_name=', '.join(y_track.artists_name()),
                            y_track_name=y_track.title,
                            y_artist_id=sc,
                            y_album_id=album_id,
                            y_track_id=track_id
                        )
                        session.add(track)
                        session.commit()

                        # track_file = open(f'{music_folder}{filename}', 'x')
                        # track_file.close()

                        y_track.download(f'{music_folder}{filename}')
                        y_track.download_cover(f'{image_folder}{filename[:-4]}.jpg')
                    print('Загрузка завершена успешно')
                    return render_template('y_music_api.html', title='Яндекс Музыка API', form=form, message1='Готово!',
                                           acinfo=account_info, first_text=first_text,
                                           second_text=second_text,
                                           third_text=third_text, track_list=track_list)
            except Exception as e:
                print(e)
                return render_template('y_music_api.html', title='Яндекс Музыка API', form=form, acinfo=account_info,
                                       message1='Произошла ошибка при загрузке', first_text=first_text,
                                           second_text=second_text,
                                           third_text=third_text, track_list=track_list)

        elif form.function3_submit.data:
            try:
                print('Начало загрузки')
                for track in client.users_likes_tracks():
                    y_track = track.fetch_track()
                    filename = f"{', '.join(y_track.artists_name())} - {y_track.title}" + '.mp3'

                    for i in '/|*?"<>?':
                        filename = filename.replace(i, '')

                    print(f'Загрузка трека: {filename}')

                    if session.query(Track).filter(Track.track_name == filename,
                                                   Track.user_id == current_user.id).first():
                        continue

                    sc = []
                    for i in y_track.artists:
                        sc.append(str(i.id))

                    sc = ', '.join(sc)

                    track_id, album_id = y_track.track_id.split(':')

                    track = Track(
                        track_name=filename,
                        user_id=current_user.id,
                        y_track=True,
                        y_artist_name=', '.join(y_track.artists_name()),
                        y_track_name=y_track.title,
                        y_artist_id=sc,
                        y_album_id=album_id,
                        y_track_id=track_id
                    )
                    session.add(track)
                    session.commit()

                    y_track.download(f'{music_folder}{filename}')
                    y_track.download_cover(f'{image_folder}{filename[:-4]}.jpg')

                print('Загрузка завершена успешно')
                return render_template('y_music_api.html', title='Яндекс Музыка API', form=form, message2='Готово!',
                                       acinfo=account_info, first_text=first_text,
                                           second_text=second_text,
                                           third_text=third_text, track_list=track_list)

            except Exception as e:
                print(e)
                return render_template('y_music_api.html', title='Яндекс Музыка API', form=form, acinfo=account_info,
                                       message2='Произошла ошибка при загрузке', first_text=first_text,
                                           second_text=second_text,
                                           third_text=third_text, track_list=track_list)

    return render_template('y_music_api.html', title='Яндекс Музыка API', form=form, acinfo=account_info,
                                            first_text=first_text,
                                           second_text=second_text,
                                           third_text=third_text, track_list=track_list)


@app.route("/player", methods=['GET', 'POST'])
@login_required
def player():
    if request.method == 'POST':
        f = request.files['file']

        session = db_session.create_session()

        songs = list()
        list_track_id = 0
        for i in session.query(Track).filter(Track.user_id == current_user.id).all():
            track_name_mp3 = path.splitext(i.track_name)[0]
            songs.append([track_name_mp3, list_track_id])
            list_track_id += 1
        current = current_user.name
        if session.query(Track).filter(Track.track_name == f.filename, Track.user_id == current_user.id).first():
            return render_template('player.html', message='Ошибка: Данный трек уже загружен', songs=songs, current=current)
        if f.filename[-4:] != '.mp3':
            return render_template('player.html', message='Ошибка: Загружаемый файл имеет расширение отличное от .mp3', songs=songs,
                                   current=current)

        # requests.post('http://127.0.0.1:5000/api/tracks', data={
        #     'track_name': f.filename,
        #     'user_id': current_user.id
        # })

        music_folder = f'static/{current_user.name}/music/'
        image_folder = f'static/{current_user.name}/img/'

        track_file = open(music_folder + f.filename, 'x')
        track_file.close()

        session = db_session.create_session()
        track = Track(
            track_name=f.filename,
            user_id=current_user.id
        )
        session.add(track)
        session.commit()

        with open(music_folder + f.filename, 'wb') as track_file:
            track_file.write(f.read())

        try:
            music = ID3(music_folder + f.filename)
            data = music.getall("APIC")[0].data
            with open(image_folder + f.filename[:-4] + '.jpg', "wb") as image_file:
                image_file.write(data)
        except(Exception):
            pass

        return redirect('/player')

    session = db_session.create_session()

    songs = list()
    list_track_id = 0
    for i in session.query(Track).filter(Track.user_id == current_user.id).all():
        track_name_mp3 = path.splitext(i.track_name)[0]
        songs.append([track_name_mp3, list_track_id])
        list_track_id += 1

    # songs = os.listdir(f'static/{current_user.name}/music/')
    # for i in range(len(songs)):
    #     a = songs.pop(0)
    #     songs.append(path.splitext(a)[0])

    current = current_user.name

    return render_template('player.html', songs=songs, current=current)


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        db_sess = db_session.create_session()
        user = db_sess.query(User).filter((User.email == form.email.data) | (User.name == form.email.data)).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            return redirect("/")
        return render_template('login.html',
                               message="Неправильный логин или пароль",
                               form=form)
    return render_template('login.html', title='Авторизация', form=form)


@app.route('/register', methods=['GET', 'POST'])
def reqister():
    form = RegisterForm()
    if form.validate_on_submit():
        if form.password.data != form.password_again.data:
            return render_template('register.html', title='Регистрация',
                                   form=form,
                                   message="Пароли не совпадают")
        db_sess = db_session.create_session()
        if db_sess.query(User).filter((User.email == form.email.data) | (User.name == form.name.data)).first():
            return render_template('register.html', title='Регистрация',
                                   form=form,
                                   message="Пользователь с такой почтой или именем аккаунта уже существует. Попробуйте еще раз")
        user = User(
            name=form.name.data,
            email=form.email.data,
        )
        user.set_password(form.password.data)
        db_sess.add(user)
        db_sess.commit()
        os.mkdir('static/' + form.name.data)
        os.mkdir('static/' + form.name.data + '/' + 'music')
        os.mkdir('static/' + form.name.data + '/' + 'img')
        return redirect('/login')
    return render_template('register.html', title='Регистрация', form=form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect("/")


@login_manager.user_loader
def load_user(user_id):
    db_sess = db_session.create_session()
    return db_sess.query(User).get(user_id)


def main():
    db_session.global_init("db/blogs.db")
    app.run()


if __name__ == '__main__':
    main()