"""
file_utils.py

This module provides utility functions for processing and extracting sessions from video event data.
It includes functions for creating sessions based on time intervals, extracting specific sessions based on
various criteria, and parsing YouTube URLs to extract video IDs.
"""

import random
import pandas as pd


def create_sessions(df: pd.DataFrame, delta_minutes=30, min_events=1):
    """
    Create sessions by grouping events that occur within a specified time delta.

    Parameters:
    df (pd.DataFrame): DataFrame containing event data with a 'time' column.
    delta_minutes (int): Time delta in minutes to define session boundaries.
    min_events (int): Minimum number of events required to form a session.

    Returns:
    list: List of sessions, each session is a list of tuples (time, video_id).
    """
    df.sort_values(by='time', inplace=True)
    df.loc[:, 'group'] = (df['time'].diff() > pd.Timedelta(minutes=delta_minutes)).astype(int).cumsum()
    sessions = [list(zip(group['time'], group['video_id'])) for _, group in df.groupby('group') if len(group) >= min_events]
    return sessions


def extract_sessions(df: pd.DataFrame, delta_minutes=30, min_events=1, latest_event=None, n_sessions=None, n_videos_per_session=None, n_total_videos=None):
    """
    Extract sessions based on various criteria, including time delta, minimum events, and specific constraints on sessions and videos.

    Parameters:
    df (pd.DataFrame): DataFrame containing event data with a 'time' column.
    delta_minutes (int): Time delta in minutes to define session boundaries.
    min_events (int): Minimum number of events required to form a session.
    latest_event (str, optional): ISO format date string to filter events occurring after this time.
    n_sessions (int, optional): Maximum number of sessions to return.
    n_videos_per_session (int, optional): Maximum number of videos per session.
    n_total_videos (int, optional): Maximum total number of videos across all sessions.

    Returns:
    list: List of sessions, each session is a list of tuples (time, video_id).
    """
    df.sort_values(by='time', inplace=True)

    if latest_event:
        latest_event = pd.to_datetime(latest_event, utc=True)
        df = df[df['time'] >= latest_event].copy()

    df.loc[:, 'group'] = (df['time'].diff() > pd.Timedelta(minutes=delta_minutes)).astype(int).cumsum()
    sessions = [list(zip(group['time'], group['video_id'])) for _, group in df.groupby('group') if len(group) >= min_events]

    if n_sessions and len(sessions) > n_sessions:
        sessions = random.sample(sessions, n_sessions)

    if n_videos_per_session:
        sessions = [session[:min(n_videos_per_session, len(session))] for session in sessions]

    if n_total_videos:
        current_total = sum(len(session) for session in sessions)
        if current_total > n_total_videos:
            selected_sessions = []
            n = 0
            for session in sessions:
                if n + len(session) > n_total_videos:
                    selected_sessions.append(session[:n_total_videos - n])
                    break
                selected_sessions.append(session)
                n += len(session)
            sessions = selected_sessions

    return sessions


def parse_yt_url(url):
    """
    Parse a YouTube URL to extract the video ID.

    Parameters:
    url (str): YouTube URL.

    Returns:
    str: Extracted video ID or None if the URL is invalid.
    """
    if url.startswith('https://www.youtube.com/watch?v='):
        return url.split('=')[-1]
    return None


if __name__ == "__main__":
    # Example usage
    # Create a DataFrame with example data
    data = {
        'time': pd.date_range(start='2023-01-01', periods=5, freq='10T'),
        'video_id': ['vid1', 'vid2', 'vid3', 'vid4', 'vid5']
    }
    df = pd.DataFrame(data)

    # Create sessions
    sessions = create_sessions(df, delta_minutes=15)
    print("Sessions:", sessions)

    # Extract sessions
    extracted_sessions = extract_sessions(df, delta_minutes=15, n_sessions=1)
    print("Extracted Sessions:", extracted_sessions)

    # Parse YouTube URL
    url = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'
    video_id = parse_yt_url(url)
    print("Parsed Video ID:", video_id)