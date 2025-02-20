#!/bin/bash
# play_video.sh
# This script plays back a video file (mp4 or mov) using ffplay (SDL).
# It is suitable for devices where hardware-accelerated players are not available.
#
# Usage:
#   chmod +x play_video.sh
#   ./play_video.sh

echo "SDL Playback using ffplay"
read -p "Enter the full path to the video file (mp4 or mov): " video_file

if [ ! -f "$video_file" ]; then
    echo "File not found: $video_file"
    exit 1
fi

echo "Playing video using ffplay..."
ffplay -autoexit "$video_file"
