from datetime import datetime, timedelta, timezone
from pathlib import Path
from flask import Flask, render_template, jsonify, request, redirect, session, url_for
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
import os

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-only-change-me')

# YouTube API Key (set as environment variable or configure here)
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')

BASE_DIR = Path(__file__).resolve().parent
GOOGLE_CLIENT_SECRETS_FILE = Path(os.getenv('GOOGLE_CLIENT_SECRETS_FILE', BASE_DIR / 'google_client_secret.json'))
GOOGLE_TOKEN_FILE = Path(os.getenv('GOOGLE_TOKEN_FILE', BASE_DIR / 'google_calendar_token.json'))
GOOGLE_REDIRECT_URI = os.getenv('GOOGLE_REDIRECT_URI', 'http://localhost:5050/oauth2callback')
GOOGLE_CALENDAR_SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']


def save_google_calendar_credentials(credentials):
    """Persist Google Calendar OAuth credentials to disk."""
    GOOGLE_TOKEN_FILE.write_text(credentials.to_json(), encoding='utf-8')


def load_google_calendar_credentials():
    """Load stored Google Calendar OAuth credentials if available."""
    if not GOOGLE_TOKEN_FILE.exists():
        return None

    credentials = Credentials.from_authorized_user_file(
        str(GOOGLE_TOKEN_FILE),
        GOOGLE_CALENDAR_SCOPES,
    )

    if credentials and credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        save_google_calendar_credentials(credentials)

    return credentials


def build_google_calendar_service():
    """Create an authenticated Google Calendar service client."""
    credentials = load_google_calendar_credentials()
    if not credentials or not credentials.valid:
        return None

    return build('calendar', 'v3', credentials=credentials)


def parse_iso_datetime(value):
    """Parse an ISO datetime string and normalize it to UTC."""
    normalized_value = value.replace('Z', '+00:00')
    parsed_value = datetime.fromisoformat(normalized_value)
    if parsed_value.tzinfo is None:
        return parsed_value.replace(tzinfo=timezone.utc)
    return parsed_value.astimezone(timezone.utc)


def get_youtube_subscribers(channel_url_or_id):
    """
    Retrieve the number of subscribers for a YouTube channel.
    
    Args:
        channel_url_or_id: Can be a channel URL like 'https://www.youtube.com/@ChannelName',
                          or a channel ID like 'UCxxxxxxxxxxxxxxxxxxxxx'
    
    Returns:
        dict: Contains subscriber_count, channel_name, and video_count, or error message
    """
    if not YOUTUBE_API_KEY:
        return {'error': 'YouTube API key not configured. Set YOUTUBE_API_KEY environment variable.'}
    
    try:
        youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
        
        # Resolve channel identifier from URL/handle/ID
        channel_id = channel_url_or_id
        handle = None

        if channel_url_or_id.startswith('@'):
            handle = channel_url_or_id[1:]
        elif 'youtube.com/@' in channel_url_or_id:
            handle = channel_url_or_id.split('@')[-1].split('?')[0].split('&')[0]

        if handle:
            # Prefer direct handle lookup for reliability.
            request_obj = youtube.channels().list(
                forHandle=handle,
                part='statistics,snippet'
            )
            response = request_obj.execute()
            if response.get('items'):
                channel_data = response['items'][0]
                thumbnails = channel_data['snippet'].get('thumbnails', {})
                channel_icon_url = (
                    thumbnails.get('high', {}).get('url')
                    or thumbnails.get('medium', {}).get('url')
                    or thumbnails.get('default', {}).get('url')
                )
                return {
                    'channel_name': channel_data['snippet']['title'],
                    'channel_icon_url': channel_icon_url,
                    'subscriber_count': int(channel_data['statistics']['subscriberCount']),
                    'video_count': int(channel_data['statistics']['videoCount']),
                    'view_count': int(channel_data['statistics']['viewCount'])
                }

            # Fallback search for handles that are not resolved by forHandle.
            request_obj = youtube.search().list(
                q=f'@{handle}',
                type='channel',
                part='id',
                maxResults=1
            )
            response = request_obj.execute()
            if response.get('items'):
                channel_id = response['items'][0]['id']['channelId']
            else:
                return {'error': f'Channel not found: {handle}'}
        
        # Get channel statistics
        request_obj = youtube.channels().list(
            id=channel_id,
            part='statistics,snippet'
        )
        response = request_obj.execute()
        
        if not response.get('items'):
            return {'error': 'Channel not found'}
        
        channel_data = response['items'][0]
        thumbnails = channel_data['snippet'].get('thumbnails', {})
        channel_icon_url = (
            thumbnails.get('high', {}).get('url')
            or thumbnails.get('medium', {}).get('url')
            or thumbnails.get('default', {}).get('url')
        )
        
        return {
            'channel_name': channel_data['snippet']['title'],
            'channel_icon_url': channel_icon_url,
            'subscriber_count': int(channel_data['statistics']['subscriberCount']),
            'video_count': int(channel_data['statistics']['videoCount']),
            'view_count': int(channel_data['statistics']['viewCount'])
        }
    
    except Exception as e:
        return {'error': f'Error fetching data: {str(e)}'}


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/add')
def add_entry():
    """
    Page to add a new calendar entry.
    Accepts optional 'date' parameter in format YYYY-MM-DD
    """
    date = request.args.get('date', None)
    return render_template('add.html', date=date)


@app.route('/google/login')
def google_login():
    if not GOOGLE_CLIENT_SECRETS_FILE.exists():
        return jsonify({
            'error': (
                'Google OAuth client secrets file is missing. '
                'Set GOOGLE_CLIENT_SECRETS_FILE or place google_client_secret.json in the app folder.'
            )
        }), 400

    flow = Flow.from_client_secrets_file(
        str(GOOGLE_CLIENT_SECRETS_FILE),
        scopes=GOOGLE_CALENDAR_SCOPES,
        redirect_uri=GOOGLE_REDIRECT_URI,
    )
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent',
    )
    session['google_oauth_state'] = state
    return redirect(authorization_url)


@app.route('/oauth2callback')
def google_oauth2callback():
    state = session.get('google_oauth_state')
    if not state:
        return jsonify({'error': 'Missing OAuth state. Start the login flow again.'}), 400

    if not GOOGLE_CLIENT_SECRETS_FILE.exists():
        return jsonify({'error': 'Google OAuth client secrets file is missing.'}), 400

    flow = Flow.from_client_secrets_file(
        str(GOOGLE_CLIENT_SECRETS_FILE),
        scopes=GOOGLE_CALENDAR_SCOPES,
        state=state,
        redirect_uri=GOOGLE_REDIRECT_URI,
    )
    flow.fetch_token(authorization_response=request.url)
    credentials = flow.credentials
    save_google_calendar_credentials(credentials)
    session.pop('google_oauth_state', None)
    return redirect(url_for('home'))


@app.route('/api/calendar-events', methods=['GET'])
def calendar_events():
    service = build_google_calendar_service()
    if not service:
        return jsonify({
            'error': 'Google Calendar is not authorized yet. Visit /google/login first.'
        }), 401

    start_param = request.args.get('start')
    end_param = request.args.get('end')

    try:
        if start_param:
            time_min = parse_iso_datetime(start_param)
        else:
            time_min = datetime.now(timezone.utc)

        if end_param:
            time_max = parse_iso_datetime(end_param)
        else:
            time_max = time_min + timedelta(days=35)
    except ValueError:
        return jsonify({'error': 'Invalid start or end date. Use ISO format, for example 2026-05-20T00:00:00Z.'}), 400

    request_obj = service.events().list(
        calendarId='primary',
        timeMin=time_min.isoformat(),
        timeMax=time_max.isoformat(),
        singleEvents=True,
        orderBy='startTime',
        maxResults=250,
    )
    response = request_obj.execute()

    events = []
    for item in response.get('items', []):
        start_value = item.get('start', {}).get('dateTime') or item.get('start', {}).get('date')
        end_value = item.get('end', {}).get('dateTime') or item.get('end', {}).get('date')
        events.append({
            'id': item.get('id'),
            'summary': item.get('summary', 'Untitled event'),
            'description': item.get('description', ''),
            'location': item.get('location', ''),
            'start': start_value,
            'end': end_value,
            'htmlLink': item.get('htmlLink'),
        })

    return jsonify({'events': events})


@app.route('/api/youtube-subscribers', methods=['POST'])
def youtube_subscribers():
    """
    API endpoint to get YouTube channel subscribers.
    Expected JSON: {"channel": "@ChannelName" or "UCxxxxx"}
    """
    data = request.get_json()
    channel = data.get('channel')
    
    if not channel:
        return jsonify({'error': 'Channel parameter is required'}), 400
    
    result = get_youtube_subscribers(channel)
    return jsonify(result)


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5050)
