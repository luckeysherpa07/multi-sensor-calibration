import sys
import pyzed.sl as sl
import cv2
import os
import time
import threading
from pathlib import Path

# --- Absolute Paths Setup ---
# Get the absolute path to the directory where this script resides.
# Based on your confirmed structure and debug output, this will be:
# /home/ruluckeysherpa/Desktop/Multi-Camera Sensor/DV/
script_dir_path = Path(os.path.abspath(__file__)).parent

# Now, construct the paths relative to this script's directory.
# 'captured_videos' and 'Recording' are direct child directories of script_dir_path.

# Path to the folder containing ZED SVO videos
video_folder = script_dir_path / 'captured_videos'

# Path to the temporary folder for signal files
TEMP_FOLDER = script_dir_path / 'Recording' / 'temp'

# --- Debug Prints (Keep these in for now!) ---
print(f"Debug (Python): Script directory: {script_dir_path}")
# Removed 'DV directory' print as it's no longer a distinct variable
print(f"Debug (Python): Constructed video_folder: {video_folder}")
print(f"Debug (Python): Constructed TEMP_FOLDER: {TEMP_FOLDER}")
print("-" * 50)


# --- File-based Communication Setup ---
DVSENSE_READY_FILE = TEMP_FOLDER / 'dvsense_ready.txt'
DVSENSE_TIMESTAMP_FILE = TEMP_FOLDER / 'dvsense_timestamp.txt'
DVSENSE_REWIND_FILE = TEMP_FOLDER / 'dvsense_rewind.txt'
STOP_SIGNAL_FILE = TEMP_FOLDER / 'stop_signal.txt'


# --- Helper Functions for File-based IPC ---
def check_file_signal(file_path):
    """Checks if a signal file exists."""
    return Path(file_path).exists()

def clear_file_signal(file_path):
    """Deletes a signal file if it exists."""
    if Path(file_path).exists():
        Path(file_path).unlink() # Use unlink for files

def read_timestamp_from_file():
    """Reads the timestamp from the signal file."""
    if Path(DVSENSE_TIMESTAMP_FILE).exists():
        try:
            with open(DVSENSE_TIMESTAMP_FILE, 'r') as f:
                return int(f.read().strip())
        except (ValueError, IOError):
            # Handle cases where file is empty, corrupted, or not an integer
            return None
    return None

# --- Main ZED Playback Function ---
def run():
    # Create a ZED camera object
    zed = sl.Camera()

    # List all SVO files in the directory
    try:
        video_files = [f for f in os.listdir(str(video_folder)) if f.endswith('.svo2')]
    except FileNotFoundError:
        print(f"Error: The video folder '{video_folder}' does not exist or is inaccessible. Please check the path.")
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred while listing video files: {e}")
        sys.exit(1)

    if not video_files:
        print(f"No SVO files found in the directory: {video_folder}. Exiting ZED playback.")
        sys.exit(1)

    print("Available ZED video files:")
    for idx, video in enumerate(video_files, start=1):
        print(f"{idx}. {video}")

    # Ask the user to select a video
    choice = input(f"Select a ZED video (1-{len(video_files)}): ")
    
    try:
        choice = int(choice)
        if choice < 1 or choice > len(video_files):
            raise ValueError
    except ValueError:
        print("Invalid choice. Exiting ZED playback.")
        sys.exit(1)

    input_file = os.path.join(str(video_folder), video_files[choice - 1])

    print(f"Playing ZED video: {video_files[choice - 1]}")

    input_type = sl.InputType()
    input_type.set_from_svo_file(input_file)

    init = sl.InitParameters(input_t=input_type)
    init.camera_resolution = sl.RESOLUTION.HD1080 # This sets max resolution, SVO will dictate
    init.depth_mode = sl.DEPTH_MODE.NONE # Not strictly needed for display, but can be set
    init.coordinate_units = sl.UNIT.MILLIMETER

    # Open the ZED camera or load the SVO file
    err = zed.open(init)
    if err != sl.ERROR_CODE.SUCCESS:
        print(f"Error opening ZED SVO file: {repr(err)}")
        zed.close()
        sys.exit(1)

    # Get original recording FPS (for initial delay, though seeking will be primary)
    camera_fps = zed.get_camera_information().camera_configuration.fps
    frame_delay = int(1000 / camera_fps) if camera_fps > 0 else 30 # Default to 30ms if fps is 0

    runtime = sl.RuntimeParameters()
    image_size = zed.get_camera_information().camera_configuration.resolution
    image_zed = sl.Mat(image_size.width, image_size.height, sl.MAT_TYPE.U8_C4)

    cv2.namedWindow("ZED Image", cv2.WINDOW_AUTOSIZE)
    print('ZED Playback: Waiting for DVSense to be ready...')

    # --- Wait for DVSense ready signal ---
    while not check_file_signal(DVSENSE_READY_FILE) and not check_file_signal(STOP_SIGNAL_FILE):
        time.sleep(0.05) # Wait for 50ms before checking again

    if check_file_signal(STOP_SIGNAL_FILE):
        print("ZED Playback: Stop signal received before DVSense was ready. Exiting.")
        zed.close()
        sys.exit(0)
    
    print("ZED Playback: DVSense ready signal received. Starting playback.")
    clear_file_signal(DVSENSE_READY_FILE) # Clear the ready signal once read

    # Get the actual start timestamp of the ZED SVO by grabbing first frame
    zed.set_svo_position(0) # Ensure at start
    grab_status = zed.grab(runtime)
    first_frame_timestamp_us = 0
    if grab_status == sl.ERROR_CODE.SUCCESS:
        zed.retrieve_image(image_zed, sl.VIEW.LEFT, sl.MEM.CPU, image_size)
        first_frame_timestamp_us = zed.get_timestamp(sl.TIME_REFERENCE.IMAGE).get_microseconds()
        zed.set_svo_position(0) # Rewind to start after getting timestamp
    else:
        print("Could not grab first frame to get ZED SVO start timestamp. Using 0.")
    
    print(f"ZED SVO estimated start timestamp: {first_frame_timestamp_us} us")

    while not check_file_signal(STOP_SIGNAL_FILE):
        # Check for rewind signal from DVSense
        if check_file_signal(DVSENSE_REWIND_FILE):
            zed.set_svo_position(0)
            print("ZED SVO rewound to start (DVSense rewind signal).")
            clear_file_signal(DVSENSE_REWIND_FILE)

        # Read the latest DVSense timestamp for coarse sync
        dvsense_timestamp = read_timestamp_from_file()

        # Grab the next frame from ZED SVO
        err = zed.grab(runtime)
        
        if err == sl.ERROR_CODE.SUCCESS:
            zed.retrieve_image(image_zed, sl.VIEW.LEFT, sl.MEM.CPU, image_size)
            image_ocv = image_zed.get_data()
            current_zed_timestamp_us = zed.get_timestamp(sl.TIME_REFERENCE.IMAGE).get_microseconds()

            if dvsense_timestamp is not None and current_zed_timestamp_us > 0:
                # Basic coarse synchronization: if ZED is too far ahead of DVSense, wait a bit
                time_diff_us = current_zed_timestamp_us - dvsense_timestamp

                # If ZED is significantly ahead (e.g., more than 50ms), introduce a small delay
                if time_diff_us > 50000: # 50000 us = 50 ms
                    # print(f"ZED ahead by {time_diff_us / 1000:.1f}ms. Waiting.") # Uncomment for debugging sync
                    time.sleep(0.01) # Small pause (10ms) to let DVSense catch up

            cv2.imshow("ZED Image", image_ocv)

        elif err == sl.ERROR_CODE.END_OF_SVOFILE_REACHED:
            print("End of ZED SVO file reached. Waiting for DVSense rewind signal or stop.")
            while not check_file_signal(DVSENSE_REWIND_FILE) and not check_file_signal(STOP_SIGNAL_FILE):
                time.sleep(0.05) 

        elif err == sl.ERROR_CODE.NOT_A_NEW_FRAME:
            time.sleep(0.001) 
        else:
            print(f"ZED grab error: {repr(err)}")
            break 

        key = cv2.waitKey(1)
        if key & 0xFF == ord('q'):
            print("ZED Playback: 'q' pressed. Signaling C++ to stop.")
            with open(STOP_SIGNAL_FILE, 'w') as f:
                f.write("STOP")
            break

    cv2.destroyAllWindows()
    zed.close()
    print("\nZED Playback FINISHED")

# --- Main execution block ---
if __name__ == "__main__":
    try:
        # Ensure temp folder exists for signals for Python script too
        TEMP_FOLDER.mkdir(parents=True, exist_ok=True)
        run()
    except KeyboardInterrupt:
        print("\nZED Playback interrupted by user (Ctrl+C).")