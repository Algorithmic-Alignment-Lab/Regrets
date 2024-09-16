"""
yt_utils.py

This module provides utility functions for retrieving and processing YouTube video information.
It includes functions for fetching video details from YouTube using the YouTube Data API and
formatting this information for display.
"""

import os
from datetime import datetime
import googleapiclient.discovery
from isodate import parse_duration
from dotenv import load_dotenv

# Load environment variables from the .env file
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
load_dotenv(dotenv_path)

# Retrieve the YouTube developer key from environment variables
YT_DEVELOPER_KEY = os.getenv("YT_DEVELOPER_KEY")

# Create a YouTube service object using the API key
api_service_name = "youtube"
api_version = "v3"
youtube = googleapiclient.discovery.build(api_service_name, api_version, developerKey=YT_DEVELOPER_KEY)


def get_youtube_video_info(video_id, session_date=None, youtube=youtube):
    """
    Retrieve YouTube video details using the YouTube Data API.

    Parameters:
    video_id (str): The ID of the YouTube video.
    session_date (datetime, optional): The date of the session.
    youtube (googleapiclient.discovery.Resource, optional): YouTube API service object.

    Returns:
    dict: A dictionary containing video information, or None if the video is not found.
    """
    # Call the videos.list method to retrieve video details
    video_request = youtube.videos().list(
        part="snippet,contentDetails,statistics",
        id=video_id
    )
    video_response = video_request.execute()

    if video_response['items']:
        video_item = video_response['items'][0]
        video_info = video_item['snippet']

        title = video_info.get('title', None)
        description = video_info.get('description', None)
        if description and len(description) > 1200:
            description = description[:1195] + '...'
        view_count = video_item['statistics'].get('viewCount', None)
        like_count = video_item['statistics'].get('likeCount', None)
        comment_count = video_item['statistics'].get('commentCount', None)
        favorite_count = video_item['statistics'].get('favoriteCount', None)
        category_id = video_item['statistics'].get('categoryId', None)
        publish_time = video_info.get('publishedAt', None)
        if publish_time:
            if isinstance(publish_time, str):
                publish_time = publish_time.replace('Z', '+00:00')
        duration = parse_duration(video_item['contentDetails']['duration']).total_seconds()

        thumbnail_url = f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"

        channel_id = video_info.get('channelId', None)
        channel_title = video_info['channelTitle']
        # Call the channels.list method to retrieve channel details
        channel_request = youtube.channels().list(
            part="snippet",
            id=channel_id
        )
        channel_response = channel_request.execute()

        if channel_response['items']:
            channel_icon = channel_response['items'][0]['snippet']['thumbnails']['default']['url']
        else:
            channel_icon = None

        video_info = {
            'title': title,
            'description': description,
            'view_count': view_count,
            'like_count': like_count,
            'comment_count': comment_count,
            'favorite_count': favorite_count,
            'publish_time': publish_time,
            'duration': duration,
            'category_id': category_id,
            'thumbnail': thumbnail_url,
            'channel_id': channel_id,
            'channel_title': channel_title,
            'channel_icon': channel_icon
        }
        return video_info
    return None


def beautify_video_info(video_info):
    """
    Beautify and format YouTube video information for display.

    Parameters:
    video_info (dict): A dictionary containing raw video information.

    Returns:
    dict: A dictionary containing beautified video information.
    """
    publish_time = video_info['publish_time']
    if not isinstance(publish_time, str):
        publish_time = str(publish_time)
    publish_date = datetime.fromisoformat(publish_time)
    if publish_date.tzinfo is not None:
        publish_date = publish_date.replace(tzinfo=None)
    session_date = datetime.now()
    age = session_date - publish_date
    age_seconds = age.total_seconds()

    if age_seconds < 60:
        display_age = f"{int(age_seconds)} seconds ago"
    elif age_seconds < 3600:
        display_age = f"{int(age_seconds // 60)} minutes ago"
    elif age_seconds < 86400:
        display_age = f"{int(age_seconds // 3600)} hours ago"
    elif age_seconds < 604800:
        display_age = f"{int(age_seconds // 86400)} days ago"
    elif age_seconds < 2592000:
        display_age = f"{int(age_seconds // 604800)} weeks ago"
    elif age_seconds < 31536000:
        display_age = f"{int(age_seconds // 2592000)} months ago"
    else:
        display_age = f"{int(age_seconds // 31536000)} years ago"

    view_count = video_info['view_count']
    if view_count is None:
        display_views = ""
    elif int(view_count) < 1000:
        display_views = f"{view_count}"
    elif int(view_count) < 1000000:
        display_views = f'{int(view_count) // 1000}K'
    else:
        display_views = f'{int(view_count) // 1000000}.{int(view_count) % 1000000 // 100000}M'

    duration = video_info['duration']
    hours = int(duration // 3600)
    minutes = int((duration % 3600) // 60)
    seconds = int(duration % 60)

    if hours > 0:
        display_duration = f"{hours}:{minutes:02}:{seconds:02}"
    else:
        display_duration = f"{minutes}:{seconds:02}"

    video_info['display_age'] = display_age
    video_info['display_views'] = display_views
    video_info['display_duration'] = display_duration
    return video_info


if __name__ == "__main__":
    video_id = "nSn6A6cfzNs"
    video_info = get_youtube_video_info(video_id)
    if video_info:
        video_info = beautify_video_info(video_info)
        print(video_info)
    else:
        print("Video not found")

