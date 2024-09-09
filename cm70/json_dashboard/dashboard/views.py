# dashboard/views.py

from django.shortcuts import render, redirect
from django.http import JsonResponse
import os
import json
from django.conf import settings

# Path to the folder containing video files and metadata
VIDEO_FOLDER_PATH = settings.VIDEO_DIR

def get_videos_and_metadata(folder_path):
    """Retrieve a list of videos and their associated metadata."""
    videos = []
    for file in os.listdir(folder_path):
        if file.endswith('.mp4'):
            video_path = os.path.join('media', file)  # Construct the correct relative URL path
            metadata_path = os.path.join(folder_path, file.replace('.mp4', '.json'))
            metadata = None
            if os.path.exists(metadata_path):
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)
            videos.append({
                'filename': file,
                'video_path': video_path,  # Relative URL for the media files
                'metadata': metadata,
            })
    return videos

def index(request):
    """Display all videos and their metadata."""
    videos = get_videos_and_metadata(VIDEO_FOLDER_PATH)
    return render(request, 'dashboard/index.html', {'videos': videos})

def delete_video(request, filename):
    """Delete a video and its associated metadata."""
    video_path = os.path.join(VIDEO_FOLDER_PATH, filename)
    metadata_path = video_path.replace('.mp4', '.json')
    
    if request.method == "GET":  # Ensures only GET requests attempt to delete
        try:
            # Check if the video file exists and delete it
            if os.path.exists(video_path):
                os.remove(video_path)
                print(f"Deleted video: {filename}")
            else:
                return JsonResponse({'success': False, 'error': 'Video file not found.'})

            # Check if the metadata file exists and delete it
            if os.path.exists(metadata_path):
                os.remove(metadata_path)
                print(f"Deleted metadata for: {filename}")

            return JsonResponse({'success': True})
        
        except Exception as e:
            print(f"Error deleting files: {e}")
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': 'Invalid request method.'})
