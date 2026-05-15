from flask import Flask, render_template, jsonify, request
from googleapiclient.discovery import build
import os

app = Flask(__name__)

# YouTube API Key (set as environment variable or configure here)
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')


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
