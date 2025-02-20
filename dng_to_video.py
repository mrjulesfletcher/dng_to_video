#!/usr/bin/env python3
"""
DNG -> Flat -> LUT Pipeline Example
-------------------------------------
This script converts a sequence of DNG (RAW) images into a video,
demonstrating a complete workflow:
  1. Convert RAW images to flat, log-like JPEGs.
  2. Create a flat video (proxy or preview) from these JPEGs.
  3. Optionally apply a LUT (3D Look-Up Table) to grade the video.
  
This method can be used to generate proxies, create viewable albums in-camera,
or simply export for quick pre-viewing. The script is interactive and
allows the user to customize RAW processing parameters, output video formats,
and frame rates.

Tools and libraries used:
  - rawpy: To read and process RAW (DNG) files.
  - imageio: To save processed images as JPEG.
  - OpenCV (cv2): To assemble JPEGs into a video.
  - FFmpeg: For applying a LUT and encoding in ProRes or H.264 formats.
  - tqdm: For interactive progress bars.
  
This script is intended as both a working tool and a tutorial for integrating
DNG conversion into your own camera applications.

Customize the functions below to suit your needs!
"""

import os
import glob
import sys
import subprocess
import logging
import traceback
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

import rawpy       # Library to read RAW files (DNG)
import imageio     # Library for saving images
import cv2         # OpenCV library for video creation
from tqdm import tqdm  # For progress bars

# ------------------------------------------------------------------------------
# LOGGING SETUP
# ------------------------------------------------------------------------------
# We set up two loggers: one for detailed debugging (saved to file) and one
# for console output at INFO level, to keep the progress bars clean.
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

# File handler: Detailed debug logs (saved to dng_processing_debug.log)
fh = logging.FileHandler("dng_processing_debug.log")
fh.setLevel(logging.DEBUG)
fh_formatter = logging.Formatter('%(asctime)s [%(levelname)s] [%(funcName)s] %(message)s',
                                 datefmt='%Y-%m-%d %H:%M:%S')
fh.setFormatter(fh_formatter)
logger.addHandler(fh)

# Console handler: Only INFO-level messages for interactive prompts and progress.
ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.INFO)
ch_formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%H:%M:%S')
ch.setFormatter(ch_formatter)
logger.addHandler(ch)

# ------------------------------------------------------------------------------
# GLOBAL CONSTANTS
# ------------------------------------------------------------------------------
# Default LUT path (can be overridden by user input)
DEFAULT_LUT_PATH = "/home/pi/cinemate/resources/LUTs/LUT_ROMEO&JULIETTE.cube"
# Default frames per second for the output video
DEFAULT_FPS = 24

# Default RAW->JPEG conversion options
# These values are chosen to produce a flat, log-like image.
DEFAULT_RAWPY_OPTIONS = {
    "gamma": (10.1, 10.1),               # Gamma value applied during postprocessing.
    "no_auto_bright": True,              # Disable auto brightness adjustments.
    "bright": 3,                         # Brightness multiplier.
    "output_color": rawpy.ColorSpace.raw,  # Output in the raw (linear) color space.
    "use_camera_wb": True,               # Use camera white balance.
    "demosaic_algorithm": rawpy.DemosaicAlgorithm.LINEAR,  # Linear demosaicing for a flat look.
    "highlight_mode": rawpy.HighlightMode.Ignore,        # Ignore highlights (avoid blending/clipping).
    "user_black": 200,                   # User-defined black level (adjust for shadow detail).
    "user_sat": 10000                    # User-defined saturation threshold (preserve highlights).
}

# ------------------------------------------------------------------------------
# UTILITY FUNCTIONS
# ------------------------------------------------------------------------------

def prompt_yes_no(question: str) -> bool:
    """
    Prompt the user with a yes/no question.
    Returns True for "yes", False for "no".
    
    Example:
      if prompt_yes_no("Proceed?"):
          # Continue processing
    """
    while True:
        resp = input(f"{question} (y/n): ").strip().lower()
        if resp in ['y', 'yes']:
            return True
        elif resp in ['n', 'no']:
            return False
        else:
            print("Please answer with 'y' or 'n'.")

def prompt_choice(question: str, choices: list) -> str:
    """
    Prompt the user until one of the provided choices is entered.
    
    Example:
      format_choice = prompt_choice("Select format", ["mp4", "prores"])
    """
    choices_str = "/".join(choices)
    while True:
        resp = input(f"{question} ({choices_str}): ").strip().lower()
        if resp in choices:
            return resp
        else:
            print(f"Please choose one of: {choices_str}.")

def prompt_input(question: str, default: str) -> str:
    """
    Prompt the user with a question, returning the entered value,
    or the default if nothing is entered.
    
    Example:
      fps = prompt_input("Enter FPS", "24")
    """
    resp = input(f"{question} [default: {default}]: ").strip()
    return resp if resp else default

def list_folder_contents(path: str):
    """
    Logs the contents of the specified folder.
    Useful for debugging directory issues.
    """
    try:
        contents = os.listdir(path)
        logging.debug("Contents of '%s': %s", os.path.abspath(path), contents)
    except Exception as e:
        logging.debug("Error listing contents of '%s': %s", os.path.abspath(path), e, exc_info=True)

def customize_rawpy_options() -> dict:
    """
    Prompts the user to customize RAW->JPEG conversion parameters.
    Returns a dictionary with the customized options.
    
    Each parameter can be modified and these values can be integrated into your camera interface.
    For example, you might change gamma, brightness, or choose a different demosaic algorithm.
    """
    options = {}
    try:
        # Gamma: provide a value that will be used for both channels.
        gamma_str = prompt_input("Enter gamma value", "10.1")
        gamma_val = float(gamma_str)
        options["gamma"] = (gamma_val, gamma_val)

        # Disable auto brightness.
        options["no_auto_bright"] = prompt_yes_no("Disable auto brightness?")

        # Brightness multiplier.
        bright_str = prompt_input("Enter bright value", "3")
        options["bright"] = float(bright_str)

        # Output color space: "raw" or "srgb".
        out_color = prompt_input("Enter output color space ('raw' or 'srgb')", "raw").lower()
        if out_color == "srgb":
            options["output_color"] = rawpy.ColorSpace.sRGB
        else:
            options["output_color"] = rawpy.ColorSpace.raw

        # Use the camera's white balance.
        options["use_camera_wb"] = prompt_yes_no("Use camera white balance?")

        # Choose a demosaic algorithm (affects image sharpness and contrast).
        demosaic_choice = prompt_choice("Select demosaic algorithm", ["linear", "vng", "ahd"])
        if demosaic_choice == "vng":
            options["demosaic_algorithm"] = rawpy.DemosaicAlgorithm.VNG
        elif demosaic_choice == "ahd":
            options["demosaic_algorithm"] = rawpy.DemosaicAlgorithm.AHD
        else:
            options["demosaic_algorithm"] = rawpy.DemosaicAlgorithm.LINEAR

        # Highlight mode: how to handle highlights (ignore, clip, or blend).
        hl_choice = prompt_choice("Select highlight mode", ["ignore", "clip", "blend"])
        if hl_choice == "clip":
            options["highlight_mode"] = rawpy.HighlightMode.Clip
        elif hl_choice == "blend":
            options["highlight_mode"] = rawpy.HighlightMode.Blend
        else:
            options["highlight_mode"] = rawpy.HighlightMode.Ignore

        # User-defined black level.
        user_black_str = prompt_input("Enter user_black value", "200")
        options["user_black"] = float(user_black_str)

        # User-defined saturation threshold.
        user_sat_str = prompt_input("Enter user_sat value", "10000")
        options["user_sat"] = float(user_sat_str)
    except Exception as e:
        logging.error("Error customizing RAW settings: %s", e, exc_info=True)
        return DEFAULT_RAWPY_OPTIONS

    return options

def process_single_dng(dng_file: str, output_path: str, rawpy_options: dict):
    """
    Processes a single DNG file:
      - Reads the DNG using rawpy.
      - Applies the RAW->JPEG conversion with specified options.
      - Saves the resulting JPEG.
      
    Returns the output path on success, or None on failure.
    
    This function can be modified to integrate into your camera interface,
    where you might process frames on-the-fly.
    """
    try:
        with rawpy.imread(dng_file) as raw:
            rgb = raw.postprocess(**rawpy_options)
        imageio.imsave(output_path, rgb)
        # Log file details.
        if os.path.exists(output_path):
            file_size = os.path.getsize(output_path)
            logging.debug("Saved file %s (size: %d bytes)", output_path, file_size)
        else:
            logging.error("File %s was not saved!", output_path)
        logging.debug("Processed %s -> %s", dng_file, output_path)
        return output_path
    except Exception as e:
        logging.error("Error processing '%s': %s", dng_file, e, exc_info=True)
        return None

def process_dng_files_parallel(input_folder: str, half_size_value: bool = True, rawpy_options: dict = None) -> str or None:
    """
    Processes all DNG files in the specified input folder in parallel.
    JPEGs are saved into a local "processed" folder within the input folder.
    
    If rawpy_options is not provided, default options (with half_size set) are used.
    
    Returns the path to the processed folder.
    
    You can reimplement this function in your own application to manage the RAW-to-JPEG
    conversion pipeline, create proxies, or generate quick previews.
    """
    abs_input_folder = os.path.abspath(input_folder)
    logging.debug("Starting DNG processing in folder: %s", abs_input_folder)
    list_folder_contents(input_folder)

    # Create a local "processed" folder.
    output_folder = os.path.join(abs_input_folder, "processed")
    try:
        os.makedirs(output_folder, exist_ok=True)
        logging.debug("Output folder created/exists: %s", output_folder)
    except Exception as e:
        logging.error("Could not create output folder '%s': %s", output_folder, e, exc_info=True)
        return None

    # Find all DNG files in the folder.
    glob_pattern = os.path.join(abs_input_folder, "*.[dD][nN][gG]")
    dng_files = sorted(glob.glob(glob_pattern))
    logging.debug("Using pattern: %s | Found %d DNG files", glob_pattern, len(dng_files))
    if not dng_files:
        logging.info("No DNG files found in %s", abs_input_folder)
        return None

    logging.info("Found %d DNG files.", len(dng_files))

    # Use default options if none provided.
    if rawpy_options is None:
        rawpy_options = DEFAULT_RAWPY_OPTIONS.copy()
        rawpy_options["half_size"] = half_size_value
    else:
        rawpy_options["half_size"] = half_size_value

    start_time = time.time()
    results = []

    # Use a ProcessPoolExecutor for parallel processing.
    with ProcessPoolExecutor() as executor:
        futures = {}
        for idx, dng_file in enumerate(dng_files):
            out_path = os.path.join(output_folder, f"frame_{idx:05d}.jpg")
            future = executor.submit(process_single_dng, dng_file, out_path, rawpy_options)
            futures[future] = dng_file

        pbar = tqdm(total=len(futures), desc="Processing DNG files", unit="frame", dynamic_ncols=True)
        processed_count = 0
        for f in as_completed(futures):
            result = f.result()
            if result is None:
                logging.error("Failed to process: %s", futures[f])
            else:
                results.append(result)
            processed_count += 1
            pbar.set_postfix({"Processed": processed_count})
            pbar.update(1)
        pbar.close()

    total_time = time.time() - start_time
    num_frames = len(dng_files)
    avg_time = total_time / num_frames if num_frames else 0
    logging.info("Processed %d frames in %.2f sec (avg %.2f sec/frame)", num_frames, total_time, avg_time)

    # List processed files for debugging.
    logging.info("Listing files in processed folder: %s", output_folder)
    try:
        for f in os.listdir(output_folder):
            logging.info("Found: %s", f)
    except Exception as e:
        logging.error("Error listing processed folder: %s", e, exc_info=True)

    return output_folder

def create_video_from_images(image_folder: str, output_video: str, fps: int) -> str or None:
    """
    Creates a video from JPEG images in the specified folder using OpenCV.
    
    This function assembles the images (which can be used as proxies or for preview)
    into an H.264 encoded MP4 video.
    
    Returns the path to the output video.
    """
    abs_folder = os.path.abspath(image_folder)
    glob_pattern = os.path.join(abs_folder, "*.jpg")
    image_files = sorted(glob.glob(glob_pattern))
    logging.debug("Found %d JPEG images in %s", len(image_files), abs_folder)
    if not image_files:
        logging.info("No images found in '%s' for video creation.", abs_folder)
        return None

    first_frame = cv2.imread(image_files[0])
    if first_frame is None:
        logging.info("Unable to read first image: %s", image_files[0])
        return None
    height, width, _ = first_frame.shape

    try:
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        video_writer = cv2.VideoWriter(output_video, fourcc, fps, (width, height))
    except Exception as e:
        logging.error("VideoWriter initialization error: %s", e, exc_info=True)
        return None

    pbar = tqdm(total=len(image_files), desc="Creating flat video (OpenCV)", unit="frame", dynamic_ncols=True)
    for file in image_files:
        frame = cv2.imread(file)
        if frame is None:
            logging.error("Skipping unreadable image: %s", file)
            pbar.update(1)
            continue
        try:
            video_writer.write(frame)
        except Exception as e:
            logging.error("Error writing frame from %s: %s", file, e, exc_info=True)
        pbar.update(1)
    pbar.close()

    video_writer.release()
    logging.info("Flat video created: %s", os.path.abspath(output_video))
    return output_video

def create_flat_video_ffmpeg(image_folder: str, output_video: str, fps: int, prores_variant: str = "hq") -> str or None:
    """
    Creates a flat video from JPEG images in image_folder using FFmpeg with ProRes encoding.
    
    This method demonstrates how to generate a high-quality proxy using Apple ProRes.
    You can modify the FFmpeg command for further customizations.
    
    Returns the output video path.
    """
    prores_profiles = {
        "proxy": "0",
        "lt": "1",
        "422": "2",
        "hq": "3"
    }
    profile = prores_profiles.get(prores_variant, "3")
    cmd = [
        "ffmpeg", "-y", "-framerate", str(fps),
        "-pattern_type", "glob", "-i", os.path.join(image_folder, "*.jpg"),
        "-c:v", "prores_ks", "-profile:v", profile,
        "-c:a", "copy", output_video
    ]
    logging.info("Creating flat video with FFmpeg (ProRes)...")
    pbar = tqdm(total=0, desc="Creating flat video (FFmpeg)", dynamic_ncols=True)
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        logging.error("FFmpeg error (flat video ProRes): %s", e, exc_info=True)
        pbar.close()
        return None
    pbar.close()
    logging.info("Flat ProRes video created: %s", os.path.abspath(output_video))
    return output_video

def apply_lut_with_ffmpeg(input_video: str, lut_file: str, output_video: str, output_format: str = "mp4", prores_variant: str = None) -> str or None:
    """
    Applies a 3D LUT to the input video using FFmpeg's lut3d filter.
    
    For MP4 (H.264) output, a simple command is used.
    For ProRes output, the prores_ks encoder is used with the specified variant.
    
    This demonstrates how you can apply color grading in postprocessing.
    Returns the output video path.
    """
    if output_format == "mp4":
        cmd = [
            "ffmpeg", "-y", "-i", input_video,
            "-vf", f"lut3d='{lut_file}'",
            "-c:a", "copy", output_video
        ]
    elif output_format == "prores":
        prores_profiles = {
            "proxy": "0",
            "lt": "1",
            "422": "2",
            "hq": "3"
        }
        profile = prores_profiles.get(prores_variant, "3")
        cmd = [
            "ffmpeg", "-y", "-i", input_video,
            "-vf", f"lut3d='{lut_file}'",
            "-c:v", "prores_ks", "-profile:v", profile,
            "-c:a", "copy", output_video
        ]
    else:
        logging.error("Unknown output format: %s", output_format)
        return None

    logging.info("Running FFmpeg to apply LUT...")
    pbar = tqdm(total=0, desc="Applying LUT with FFmpeg", dynamic_ncols=True)
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        logging.error("FFmpeg error: %s", e, exc_info=True)
        pbar.close()
        return None
    pbar.close()
    logging.info("LUT-applied video created: %s", os.path.abspath(output_video))
    return output_video

# ------------------------------------------------------------------------------
# MAIN EXECUTION
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    print("Welcome to the advanced DNG -> Flat -> LUT pipeline!")
    
    # Prompt user for DNG folder path.
    input_folder = input("Please paste the path to your DNG folder: ").strip()
    if not input_folder:
        print("No input folder provided. Exiting.")
        sys.exit(1)
    logging.info("Script started. Input folder: %s", input_folder)

    # Prompt for quality: full or half resolution.
    quality_choice = prompt_choice("Select quality", ["full", "half"])
    half_size_value = False if quality_choice == "full" else True

    # Prompt for RAW configuration: use default or customize.
    use_default = prompt_yes_no("Use default RAW->JPEG color configuration?")
    if use_default:
        rawpy_options = DEFAULT_RAWPY_OPTIONS.copy()
    else:
        rawpy_options = customize_rawpy_options()
    # Ensure half_size is set based on the quality choice.
    rawpy_options["half_size"] = half_size_value

    # Prompt for LUT path.
    lut_path = prompt_input("Enter path to LUT", DEFAULT_LUT_PATH)
    
    # Prompt for FPS for the video.
    fps_str = prompt_input("Enter FPS for the video", str(DEFAULT_FPS))
    try:
        fps_value = int(fps_str)
    except ValueError:
        logging.error("Invalid FPS entered. Using default FPS: %d", DEFAULT_FPS)
        fps_value = DEFAULT_FPS

    # Check if processed folder exists. If yes, ask to reprocess or use existing.
    abs_input_folder = os.path.abspath(input_folder)
    processed_folder_path = os.path.join(abs_input_folder, "processed")
    if os.path.exists(processed_folder_path):
        reprocess_choice = prompt_choice("Processed folder already exists. Reprocess full DNGs (r) or export videos from existing JPEGs (e)", ["r", "e"])
        if reprocess_choice == "r":
            processed_folder = process_dng_files_parallel(input_folder, half_size_value=half_size_value, rawpy_options=rawpy_options)
        else:
            processed_folder = processed_folder_path
    else:
        processed_folder = process_dng_files_parallel(input_folder, half_size_value=half_size_value, rawpy_options=rawpy_options)
    if not processed_folder:
        logging.info("DNG processing failed. Exiting.")
        sys.exit(1)

    # Confirm before creating flat video.
    if not prompt_yes_no("Proceed with creating a flat video from the processed images?"):
        print("User chose not to create flat video. Exiting.")
        sys.exit(0)

    # Prompt for flat video output format.
    flat_format = prompt_choice("Select flat video format", ["mp4", "prores"])
    if flat_format == "prores":
        flat_prores_variant = prompt_choice("Select flat video ProRes variant", ["proxy", "lt", "422", "hq"])
        flat_video = os.path.join(input_folder, "flat_video.mov")
        flat_result = create_flat_video_ffmpeg(processed_folder, flat_video, fps=fps_value, prores_variant=flat_prores_variant)
    else:
        flat_video = os.path.join(input_folder, "flat_video.mp4")
        flat_result = create_video_from_images(processed_folder, flat_video, fps=fps_value)
    if not flat_result:
        logging.info("Failed to create flat video. Exiting.")
        sys.exit(1)

    # Prompt for LUT-applied video output format.
    lut_format = prompt_choice("Select LUT-applied video format", ["mp4", "prores"])
    lut_prores_variant = None
    if lut_format == "prores":
        lut_prores_variant = prompt_choice("Select Apple ProRes variant", ["proxy", "lt", "422", "hq"])
        final_output = os.path.join(input_folder, "lut_applied_video.mov")
    else:
        final_output = os.path.join(input_folder, "lut_applied_video.mp4")

    # Confirm before applying LUT.
    if not prompt_yes_no("Apply LUT to create a graded video?"):
        print("User chose not to apply LUT. Exiting.")
        sys.exit(0)

    # Apply LUT via FFmpeg.
    lut_result = apply_lut_with_ffmpeg(flat_video, lut_path, final_output, output_format=lut_format, prores_variant=lut_prores_variant)
    if not lut_result:
        logging.info("Error applying LUT. Exiting.")
        sys.exit(1)

    logging.info("All steps completed successfully. Script finished.")
    print(f"Done! 'flat_video' and '{os.path.basename(final_output)}' were created in your input folder.")
