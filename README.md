
# dng_to_video
Simple DNG sequence to Apple ProRes or H.264 using RawPy and FFmpeg


## Overview

This repository, hosted at [https://github.com/mrjulesfletcher/dng_to_video](https://github.com/mrjulesfletcher/dng_to_video), contains an example tool that converts a sequence of DNG (RAW) images into a video directly on the Raspberry Pi (or similar device). The project demonstrates a complete workflow:

1. **RAW Processing**  
   Converts RAW DNG images into flat, log‑like JPEGs using [rawpy](https://github.com/letmaik/rawpy).  
   You can use the default conversion settings or customize parameters such as gamma, brightness, demosaic algorithm, and more.

2. **Video Creation**  
   Assembles the processed JPEGs into a flat video. This video can be used as a proxy, a pre‑view, or to generate in‑camera albums.  
   Two methods are supported:
   - **MP4 (H.264)** using OpenCV.
   - **Apple ProRes** using FFmpeg (with support for Proxy, LT, 422, or HQ profiles).

3. **LUT Application**  
   Applies a 3D LUT (Look-Up Table) via FFmpeg’s `lut3d` filter to produce a final, graded video.

This method can be integrated into your own camera interfaces (such as those built with the CinePi SDK or CineMate) to provide in‑camera preview, proxy generation, or exporting for post‑production.

## Features

- **Interactive Workflow:**  
  The main Python script guides you through:
  - Entering the path to your DNG folder.
  - Choosing processing quality (“full” or “half”), which sets the `half_size` flag for RAW processing.
  - Using default or custom RAW→JPEG conversion settings.
  - Entering the path to your LUT and the desired FPS.
  - Deciding whether to reprocess RAW files or reuse existing JPEGs (if a processed folder already exists).
  - Selecting output formats (MP4 or ProRes) for both the flat video and the LUT‑applied video.
  
- **Customizable RAW Processing:**  
  The default conversion settings (gamma, brightness, demosaic algorithm, etc.) are designed to produce a flat, log‑like image. You can override these defaults interactively if needed.

- **Multiple Video Output Options:**  
  - **Flat Video:** Generated from JPEGs using OpenCV for MP4 output or FFmpeg for ProRes output.
  - **Graded Video:** Applies the LUT to the flat video to produce the final graded output.

- **Video Playback Support:**  
  A simple shell script (provided separately) allows you to preview the generated video using ffplay (SDL-based playback). This enables quick in‑camera preview of your footage.

- **Progress and Debugging:**  
  Real‑time progress bars (via tqdm) and detailed debug logs (saved to `dng_processing_debug.log`) help you monitor and troubleshoot the process.

## Installation

### Requirements

- **Python 3.x**
- **FFmpeg** (installed and available in your system’s PATH)
- The following Python libraries:
  - [rawpy](https://pypi.org/project/rawpy/)
  - [imageio](https://pypi.org/project/imageio/)
  - [opencv-python](https://pypi.org/project/opencv-python/)
  - [tqdm](https://pypi.org/project/tqdm/)

### Installing Dependencies

Clone the repository and install the required packages using:

```bash
git clone https://github.com/mrjulesfletcher/dng_to_video.git
cd dng_to_video
pip install -r requirements.txt
```

For FFmpeg installation, visit [FFmpeg Downloads](https://ffmpeg.org/download.html) for your platform.

## Usage

Run the main conversion script:

```bash
python3 dng_to_video.py
```

You will be guided through several interactive prompts:

- **DNG Folder:**  
  Paste the path to your folder containing DNG files.

- **Quality Selection:**  
  Choose between "full" or "half" quality, which sets the `half_size` flag for RAW processing.

- **RAW Configuration:**  
  Choose to use the default RAW→JPEG settings or customize parameters (gamma, brightness, output color space, white balance, demosaic algorithm, highlight mode, user_black, user_sat).

- **LUT Path & FPS:**  
  Enter the path to your LUT file (a default is provided) and the desired FPS for the output video.

- **Processed Folder Check:**  
  If a "processed" folder already exists, choose whether to reprocess the DNG files or reuse the existing JPEGs.

- **Flat Video Output Format:**  
  Choose MP4 (H.264) or ProRes (with variant selection) for the flat video.

- **LUT-Applied Video Output Format:**  
  Choose the output format for the graded video (MP4 or ProRes) and confirm before applying the LUT.

After processing, the script generates two videos:

- **flat_video:** The ungraded, flat proxy video.  
- **lut_applied_video:** The final graded video with the LUT applied.

## Video Playback

To preview the generated videos on your Pi, a simple shell script is provided for SDL-based playback using ffplay.

### play_video.sh

```bash
#!/bin/bash
# play_video.sh
# This script plays back a video file (mp4 or mov) using ffplay (SDL-based).
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
```

**Usage:**

1. Make the script executable:
   ```bash
   chmod +x play_video.sh
   ```
2. Run the script:
   ```bash
   ./play_video.sh
   ```
3. Enter the full path to the video file when prompted.

## Customization and Integration

Each function in the main Python script is thoroughly commented to serve as a tutorial for customization:

- **`customize_rawpy_options()`**  
  Allows you to modify RAW conversion parameters (gamma, brightness, demosaic algorithm, etc.). Integrate or extend these prompts as needed for your camera interface.

- **`process_dng_files_parallel()`**  
  Processes all DNG files in parallel and saves them into a "processed" folder. This function can be modified for real‑time processing or integrated with your application.

- **`create_video_from_images()`** and **`create_flat_video_ffmpeg()`**  
  Build flat videos using OpenCV or FFmpeg (for ProRes), which you can use as proxies.

- **`apply_lut_with_ffmpeg()`**  
  Applies a LUT to your video via FFmpeg’s `lut3d` filter. Customize the FFmpeg command for additional postprocessing if needed.

These functions serve as a foundation for integrating DNG-to-video conversion into your own projects or camera interfaces.

## Contributing

Contributions, issues, and feature requests are welcome! Please check the [issues page](https://github.com/mrjulesfletcher/dng_to_video/issues) for more details.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Author

**Jules Le Masson Fletcher**
