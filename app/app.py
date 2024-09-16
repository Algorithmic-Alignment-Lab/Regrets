"""
app.py

This Flask application handles video file uploads, processes user sessions, collects regrets, and performs attention checks.
It interacts with a PostgreSQL database to store and manage data related to video sessions and user regrets.

Routes:
- /: Displays the upload page
- /upload: Handles file uploads
- /process/<uid>: Processes uploaded files
- /session: Displays session overview
- /regret_video: Handles regret recording for videos
- /attention_check: Manages attention checks
- /review: Displays regret summary
- /post_submit: Submits regrets and cleans up temporary files
"""

import os
import uuid
import json
import random
import datetime
import logging
import yaml
import pandas as pd
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_migrate import Migrate
from flask_session import Session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from redis import Redis
from utils.yt_utils import get_youtube_video_info, beautify_video_info
from utils.file_utils import create_sessions, parse_yt_url
from werkzeug.utils import secure_filename


load_dotenv('.env')

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET')
app.config['ALLOWED_EXTENSIONS'] = set(['json'])
app.config['SQLALCHEMY_DATABASE_URI'] = f'postgresql://{os.getenv("PG_USER")}:{os.getenv("PG_PW")}@db/{os.getenv("PG_DB")}'
app.config['SESSION_TYPE'] = 'redis'
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_REDIS'] = Redis(host='redis', port=6379, db=0)
Session(app)

# Load non-secret config values from config.yaml
with open('config.yaml', 'r') as file:
    config = yaml.safe_load(file)
# Set other configuration values from the loaded YAML config
app.config['UPLOAD_FOLDER'] = config['UPLOAD_FOLDER']
app.config['MIN_NUM_SESSIONS'] = config['MIN_NUM_SESSIONS']
app.config['MIN_TIME_BETWEEN_SESSIONS'] = config['MIN_TIME_BETWEEN_SESSIONS']
app.config['MIN_VIDEOS_PER_SESSION'] = config['MIN_VIDEOS_PER_SESSION']
app.config['MAX_VIDEOS_PER_SESSION'] = config['MAX_VIDEOS_PER_SESSION']
app.config['MIN_TOTAL_VIDEOS'] = config['MIN_TOTAL_VIDEOS']
app.config['MAX_TOTAL_VIDEOS'] = config['MAX_TOTAL_VIDEOS']
app.config['LATEST_EVENT'] = config['LATEST_EVENT']
app.config['ATTENTION_LEFT'] = config['ATTENTION_LEFT']
app.config['ATTENTION_RIGHT'] = config['ATTENTION_RIGHT']
app.config['ATTENTION_LEFT_RELATIVE_TIME'] = config['ATTENTION_LEFT_RELATIVE_TIME']
app.config['ATTENTION_RIGHT_RELATIVE_TIME'] = config['ATTENTION_RIGHT_RELATIVE_TIME']

# Calculate and set derived values
app.config['ATTENTION_LEFT_TIME'] = int(app.config['ATTENTION_LEFT_RELATIVE_TIME'] * app.config['MIN_TOTAL_VIDEOS'])
app.config['ATTENTION_RIGHT_TIME'] = int(app.config['ATTENTION_RIGHT_RELATIVE_TIME'] * app.config['MIN_TOTAL_VIDEOS'])

db = SQLAlchemy(app)
migrate = Migrate(app, db)

class Files(db.Model):
    """Table for storing file metadata."""
    filename = db.Column(db.String(80), primary_key=True)
    user_id = db.Column(db.String(20), nullable=False)
    tz_offset = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False)
    completed = db.Column(db.Boolean, default=False)
    updated_at = db.Column(db.DateTime, nullable=True)
    
class HistoryInfo(db.Model):
    """Table for storing video history information."""
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(80), nullable=False)
    video_id = db.Column(db.String(20), nullable=False)
    event_ts = db.Column(db.DateTime, nullable=True)
    session_num = db.Column(db.Integer, nullable=True)
    
class Selected(db.Model):
    """Table for storing the selected sessions and their videos."""
    id = db.Column(db.Integer, primary_key=True)
    session_num = db.Column(db.Integer, nullable=False)
    position = db.Column(db.Integer, nullable=False)
    history_id = db.Column(db.Integer, db.ForeignKey('history_info.id'), nullable=False)

class Regrets(db.Model):
    """Table for storing user regrets."""
    id = db.Column(db.Integer, primary_key=True)
    history_id = db.Column(db.Integer, db.ForeignKey('history_info.id'), nullable=False)
    regret = db.Column(db.String(20), nullable=False)
    reason = db.Column(db.String(120), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False)
    
class Attention(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(80), nullable=False)
    created_at = db.Column(db.DateTime, nullable=True)
    check_passed = db.Column(db.Boolean, nullable=True)
    attention_side = db.Column(db.String(20), nullable=True)
    attention_time = db.Column(db.Integer, nullable=True)


class Video(db.Model):
    """Table for storing video metadata."""
    video_id = db.Column(db.String(20), nullable=False, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    view_count = db.Column(db.Integer, nullable=True)
    like_count = db.Column(db.Integer, nullable=True)
    favorite_count = db.Column(db.Integer, nullable=True)
    comment_count = db.Column(db.Integer, nullable=True)
    publish_time = db.Column(db.DateTime, nullable=True)
    duration = db.Column(db.Float, nullable=True)
    category_id = db.Column(db.Integer, nullable=True)
    thumbnail = db.Column(db.String(120), nullable=True)
    channel_id = db.Column(db.String(120), nullable=True)
    channel_title = db.Column(db.String(120), nullable=True)
    channel_icon = db.Column(db.String(400), nullable=True)
    description = db.Column(db.String(1200), nullable=True)

logging.basicConfig(level=logging.DEBUG) 
# Configure loggers
info_file_handler = RotatingFileHandler(
    'flask_info.log', maxBytes=10000000, backupCount=5)
info_file_handler.setLevel(logging.INFO)
info_file_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
))

error_file_handler = RotatingFileHandler(
    'flask_error.log', maxBytes=10000000, backupCount=5)
error_file_handler.setLevel(logging.ERROR)
error_file_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
))

# if not app.debug:
app.logger.addHandler(info_file_handler)
app.logger.addHandler(error_file_handler)

class CustomEncoder(json.JSONEncoder):
    """Custom JSON encoder for handling datetime objects."""
    def default(self, obj):
        if isinstance(obj, pd.Timestamp) or isinstance(obj, datetime.datetime):
            return obj.isoformat()
        # Let the base class default method raise the TypeError
        return json.JSONEncoder.default(self, obj)
    
def object_as_dict(obj):
    """Convert an object to a dictionary, excluding private attributes."""
    return {key: value for key, value in obj.__dict__.items() if not key.startswith('_')}

@app.context_processor
def inject_config():
    """Inject configuration into templates."""
    return dict(config=app.config)

@app.errorhandler(500)
def handle_500_error(exception):
    """Handle internal server errors."""
    app.logger.error(f'Server Error: ', str(exception))
    return "Internal server error", 500

@app.errorhandler(404)
def handle_404_error(exception):
    """Handle not found errors."""
    app.logger.error('Not Found: %s', request.path)
    return "Page not found", 404


@app.route('/')
def index():
    """Render the upload page."""
    return render_template('upload.html') 


@app.route('/upload')
def upload():
    """Handle upload page access and user ID retrieval."""
    uid = request.args.get('uid')
    if not uid:
        if 'uid' in session:
            uid = session['uid']
        else:
            app.logger.warning('Upload attempted without user ID')
            flash("Missing user ID in the request")
            return redirect(url_for('index'))
    
    app.logger.info(f'Upload page accessed with UID: {uid}')
    session.clear()
    session['uid'] = uid
    # check if the upload folder exists
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
        app.logger.info(f'Upload folder created')
    return render_template('upload.html')


@app.route('/process/<uid>', methods=['POST'])
def process(uid):
    """Process the uploaded file and create session history."""
    try:
        if 'file' not in request.files:
            app.logger.warning(f'No file in the request to process for user {uid}')
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            app.logger.warning(f'Empty file in the request to process for user {uid}')
            flash('Please upload file')
            return redirect(request.url)
        if file is None:
            app.logger.warning(f'Empty file in the request to process for user {uid}')
            flash('Please upload a file')
            return redirect(request.url)
        if file:
            filename = secure_filename(f'{uuid.uuid4()}')
            tz_offset = request.form.get('timezone')
            # convert to float
            tz_offset = float(tz_offset) if tz_offset else None
            if tz_offset== -8:
                session['timezone'] = 'PST'
            elif tz_offset == -7:
                session['timezone'] = 'MST'
            elif tz_offset == -6:
                session['timezone'] = 'CST'
            elif tz_offset == -5:
                session['timezone'] = 'EST'
            app.logger.info(f'Processing file {filename} for user {uid}')
            # Create and save file record
            ts_now = datetime.datetime.now()
            try:
                new_file = Files(filename=filename,
                                user_id=uid,
                                tz_offset=tz_offset,
                                created_at=ts_now)
                db.session.add(new_file) 
            except Exception as e:
                app.logger.error(f'Error creating file record: {str(e)} for user {uid}')   
            session['filename'] = filename
            session['uid'] = uid

            try:
                df = pd.read_json(file, orient='records')
                app.logger.info(f'File {file.filename} read successfully for user {uid}')
            except Exception as e:
                app.logger.error(f'Error reading file: {str(e)} for user {uid}')
            df['video_id'] = df['titleUrl'].apply(lambda x: parse_yt_url(x) if pd.notnull(x) else None)
            df.dropna(subset=['video_id'], inplace=True)
            # drop items corresponding to ads
            if 'details' in df.columns:
                df = df[df['details'].isna()]
            df = df[['time', 'video_id']]
            df['time'] = pd.to_datetime(df['time'], format='ISO8601')
            # offset the time
            if tz_offset:
                df['time'] = df['time'] + pd.Timedelta(hours=tz_offset)
            # save the file locally
            df.dropna(inplace=True)
            df = df[df['video_id'].str.len() == 11]
            
            # break up history into sessions
            view_sessions = create_sessions(df, delta_minutes=app.config['MIN_TIME_BETWEEN_SESSIONS'])
            if len(view_sessions) < app.config['MIN_NUM_SESSIONS']:
                app.logger.error(f'Not enough sessions in file for user {uid}')
                return render_template('error.html', message='Not enough sessions in recent history. Make sure you uploaded the correct file.')
            
            total_videos = sum([min(len(sess), app.config['MAX_VIDEOS_PER_SESSION']) for sess in view_sessions])
            if total_videos < app.config['MAX_TOTAL_VIDEOS']:
                app.logger.error(f'Not enough videos in file for user {uid}, only {total_videos} found, expected > {app.config["MAX_TOTAL_VIDEOS"]}')
                return render_template('error.html', message='Not enough videos in history file. Make sure you uploaded the correct file.')
             
            try:
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], f'{filename}.csv')
                df.to_csv(filepath, index=False)
                app.logger.info(f'File {filepath} saved successfully for user {uid}')
            except Exception as e:
                app.logger.error(f'Error saving file: {str(e)} for user {uid}')
            
            session['n_total_videos'] = total_videos
            session['current_video'] = 0 #<- current video in the session
            session['current_session'] = 0 #<- current session
            session['n_rated_videos'] = 0
            session['n_eligible_sessions'] = 0
            session['n_attention_checks'] = 0
            eligible_sessions = []
            # populate HistoryInfo
            try:
                for index_sess, view_sess in enumerate(view_sessions):
                    for (ts, video_id) in view_sess:
                        new_history = HistoryInfo(
                            filename=filename,
                            video_id=video_id,
                            event_ts=ts,
                            session_num=index_sess,
                        )
                        db.session.add(new_history)
                    last_ts = view_sess[-1][0]
                    if last_ts >= pd.Timestamp(app.config['LATEST_EVENT']).tz_localize('UTC') and len(view_sess) >= app.config['MIN_VIDEOS_PER_SESSION']:
                        eligible_sessions.append(index_sess)
                db.session.commit()
                app.logger.info(f'History records created successfully for user {uid}')
                session['eligible_sessions'] = eligible_sessions
                session['n_eligible_sessions'] = len(eligible_sessions)
            except Exception as e:
                app.logger.error(f'Error creating history records: {str(e)} for user {uid}')

            # point to session_overview function
            return redirect(url_for('session_overview'))
        else:
            return redirect(request.url)
    except Exception as e:
        app.logger.error(f'Error processing file: {str(e)} for user {uid}')
        return render_template('error.html', message='Error processing file')     
    
@app.route('/session_overview')
def session_overview():
    """Render the session overview page."""
    eligible_sessions = session.get('eligible_sessions', [])
    session_data = {}
    while len(eligible_sessions) > 0:
        current_session = random.choice(eligible_sessions)
        try:
            history_info = HistoryInfo.query.filter_by(filename=session['filename'], 
                                                        session_num=current_session).all()
            app.logger.info(f'History records fetched successfully for user {session["uid"]} in file {session["filename"]} for session {current_session}')
        except Exception as e:
            app.logger.error(f'Error fetching history records: {str(e)} for user {session["uid"]} in file {session["filename"]} for session {current_session}')
        session_data = {}
        start = history_info[0].event_ts
        day = start.strftime('%B %d, %Y')
        session_data['day'] = day
        start_time = start.strftime('%-I:%M %p')
        session_data['start_time'] = start_time
        end_time = history_info[-1].event_ts.strftime('%-I:%M %p')
        session_data['end_time'] = end_time
        session_data['sess_num_videos'] = len(history_info)
        session_data['videos'] = []
        selected_videos = 0
        for index, history in enumerate(history_info):
            if selected_videos < app.config['MAX_VIDEOS_PER_SESSION']:
                video_id = history.video_id
                video_info = Video.query.get(video_id)
                if video_info:
                    app.logger.info(f'Video {video_id} fetched from database for user {session["uid"]} in file {session["filename"]} for session {current_session}')
                    video_info = object_as_dict(video_info)
                else:
                    app.logger.info(f'Fetching video {video_id} from YouTube for user {session["uid"]} in file {session["filename"]} for session {current_session}')
                    video_info = get_youtube_video_info(video_id)
                    if video_info is None:
                        app.logger.error(f'Error fetching video {video_id} from YouTube for user {session["uid"]} in file {session["filename"]} for session {current_session}')
                    else:
                        # save the video to the databaseß
                        app.logger.info(f'Video {video_id} fetched from YouTube for user {session["uid"]} in file {session["filename"]} for session {current_session}')
                        video_info['video_id'] = video_id
                        video = Video(**video_info)
                        db.session.add(video)
                        db.session.commit()
                if video_info:
                    video_info = beautify_video_info(video_info)
                    watched_at = HistoryInfo.query.filter_by(filename=session['filename'], id=history.id).first().event_ts
                    watched_at = watched_at.strftime('%-I:%M %p')
                    video_info['watched_at'] = watched_at
                    video_info['history_id'] = history.id
                    video_info['session_num'] = session['current_session']
                    session_data['videos'].append(video_info)
                    new_selected = Selected(
                                session_num=session['current_session'],
                                position=index,
                                history_id=history.id
                            )
                    db.session.add(new_selected)
                    app.logger.info(f'Video {video_id} added to session data for user {session["uid"]} in file {session["filename"]} for session {current_session}')
                    selected_videos += 1
        db.session.commit()
        if len(session_data['videos']) >= app.config['MIN_VIDEOS_PER_SESSION']:
            session['current_session'] +=1
            eligible_sessions.remove(current_session)
            session['current_data'] = session_data
            session['eligible_sessions'] = eligible_sessions
            session['n_eligible_sessions'] = len(eligible_sessions)
            break
    return render_template('session_overview.html', session_data=session_data)

@app.route('/regret_video', methods=['GET', 'POST'])
def regret_video():
    try:
        if session['n_rated_videos'] >= app.config['MAX_TOTAL_VIDEOS']:
            return redirect(url_for('regret_summary'))
        
        if session['n_eligible_sessions'] == 0:
            if session['n_rated_videos'] < app.config['MIN_TOTAL_VIDEOS']:
                return render_template('error.html', message='No more sessions to show. You have not completed rating enough videos to qualify.')
            else:
                return redirect(url_for('regret_summary'))

        
        # Load session data safely
        session_filename = session.get('filename')
        if not session_filename:
            raise ValueError("Session filename is missing")
        session_data = session.get('current_data')
        
        if request.method == 'POST':
            video_id = request.form.get('video_id')
            regret = request.form.get('regret')
            created_at = datetime.datetime.now()
            history_id = request.form.get('history_id')
            new_regret = Regrets(history_id=history_id,
                                 regret=regret,
                                 created_at=created_at)
            app.logger.info(f'Regret recorded for video {video_id} in session {session["filename"]} for user {session["uid"]}')
            db.session.add(new_regret)
            db.session.commit()
            
            if regret != 'skip':
                session['n_rated_videos'] += 1
                session.modified = True
            
            # Update session data
            if session['current_video'] < len(session_data['videos']) - 1:
                session['current_video'] += 1
            else:
                session['current_video'] = 0
                session['current_session'] += 1
                return redirect(url_for('session_overview'))
                
            session.modified = True  # Ensure session modifications are saved
            
        need_attention = ((session['n_rated_videos'] == app.config['ATTENTION_LEFT_TIME'] and session['n_attention_checks'] == 0) or 
            (session['n_rated_videos'] == app.config['ATTENTION_RIGHT_TIME'] and session['n_attention_checks'] == 1))
    
        if need_attention:
            return redirect(url_for('attention_check'))
        
        # Serve the current video
        video_info = session_data['videos'][session['current_video']]
        progress = min(100, session['n_rated_videos'] / app.config['MIN_TOTAL_VIDEOS'] * 100)
        return render_template('regret.html', 
                               video=video_info, 
                               progress=progress, 
                               num_total_videos=max(session['n_rated_videos'], app.config['MIN_TOTAL_VIDEOS']), 
                               session_data=session_data)
    except Exception as e:
        app.logger.error(f'Error regretting video: {str(e)} for user {session["uid"]} in session {session["filename"]} for video {session["current_video"]}')
        return render_template('error.html', message=f'Error showing video')

@app.route('/attention_check', methods=['GET', 'POST'])
def attention_check():
    """Handle attention checks."""
    try:
        # Determine the side and image for the attention check
        attention_side = 'LEFT' if session['n_rated_videos'] == app.config['ATTENTION_LEFT_TIME'] else 'RIGHT'
        attention_image = app.config[f'ATTENTION_{attention_side}']

        if request.method == 'POST':
            regret = request.form.get('regret')
            if (regret == 'yes' and attention_side == 'LEFT') or (regret == 'no' and attention_side == 'RIGHT'):
                attention_value = True 
            else:
                attention_value = False
            created_at = datetime.datetime.now()
            new_attention_check = Attention(
                filename=session['filename'],
                created_at=created_at,
                check_passed=attention_value,
                attention_side=attention_side,
                attention_time=session['n_rated_videos']
            )
            db.session.add(new_attention_check)
            db.session.commit()
            app.logger.info(f'{attention_side} attention status for user {session["uid"]} in session {session["filename"]} returned {attention_value}')
            session['n_attention_checks'] += 1
            session.modified = True  # Ensure session modifications are saved
            return redirect(url_for('regret_video'))

        progress = min(100, session['n_rated_videos'] / app.config['MIN_TOTAL_VIDEOS'] * 100)
        fake_video_info = {
            'title': 'Please pay attention to the image',
            'thumbnail': attention_image,
            'watched_at': '00:00 AM',
            'display_duration': '0:00',
            'channel_title': 'Attention Check',
            'description': 'Please indicate whether you paid attention to the image by performing the required action.',
            'display_views': '0',
            'display_age': '0 seconds ago',
            'video_id': None,
            'channel_icon': 'https://i.postimg.cc/PJfVxbfz/ac.png'
        }
        
        fake_session_data = {
            'day': 'Today',
            'start_time': '00:00 AM',
            'end_time': '00:00 AM',
            'sess_num_videos': 1,
        }
        return render_template('regret.html', 
                               video=fake_video_info, 
                               progress=progress, 
                               num_total_videos=max(session['n_rated_videos'], app.config['MIN_TOTAL_VIDEOS']), 
                               session_data=fake_session_data)

    except Exception as e:
        app.logger.error(f'Error during attention check: {str(e)} for user {session["uid"]} in session {session["filename"]}')
        return render_template('error.html', message=f'Error during attention check')

@app.route('/review')
def review():
    try:
        regrets_query = (
            db.session.query(Regrets)
            .join(HistoryInfo, Regrets.history_id == HistoryInfo.id)
            .join(Files, HistoryInfo.filename == Files.filename)
            .filter(Files.filename == session['filename'])
            .order_by(Regrets.created_at.asc())
            .all()
        )
        all_regrets = []
        for regret in regrets_query:
            this_regret = {}
            this_regret['regret'] = regret.regret
            video_id = HistoryInfo.query.get(regret.history_id).video_id
            this_regret['title'] = Video.query.get(video_id).title
            all_regrets.append(this_regret)
        file = Files.query.filter_by(filename=session['filename']).first()
        file.completed = True
        file.updated_at = datetime.datetime.now()
        db.session.commit()
        app.logger.info(f'Regrets recorded for user {session["uid"]} in session {session["filename"]}')
        return render_template('regrets_summary.html', regrets=all_regrets)
    except Exception as e:
        app.logger.error(f'Error showing regret summary: {str(e)} for user {session["uid"]} in session {session["filename"]}')
        return render_template('error.html', message='No regrets to display or session expired.')

@app.route('/post_submit', methods=['POST'])
def post_submit():
    return render_template('submission_success.html')

   
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5001)
