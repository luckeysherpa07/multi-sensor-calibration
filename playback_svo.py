import sys
import pyzed.sl as sl
import cv2
import os
import time
import argparse
import numpy as np
from pathlib import Path

# --- Absolute Paths Setup ---
script_dir_path = Path(os.path.abspath(__file__)).parent
video_folder = script_dir_path / 'captured_videos'
TEMP_FOLDER = script_dir_path / 'Recording' / 'temp'

# --- Debug Prints ---
print(f"Debug (Python): Script directory: {script_dir_path}")
print(f"Debug (Python): Constructed video_folder: {video_folder}")
print(f"Debug (Python): Constructed TEMP_FOLDER: {TEMP_FOLDER}")
print("-" * 50)

# --- File-based Communication Setup ---
DVSENSE_READY_FILE = TEMP_FOLDER / 'dvsense_ready.txt'
DVSENSE_TIMESTAMP_FILE = TEMP_FOLDER / 'dvsense_timestamp.txt'
DVSENSE_REWIND_FILE = TEMP_FOLDER / 'dvsense_rewind.txt'
STOP_SIGNAL_FILE = TEMP_FOLDER / 'stop_signal.txt'

# --- Helper Functions ---
def check_file_signal(file_path):
    return Path(file_path).exists()

def clear_file_signal(file_path):
    if Path(file_path).exists():
        Path(file_path).unlink()

def read_timestamp_from_file():
    if Path(DVSENSE_TIMESTAMP_FILE).exists():
        try:
            with open(DVSENSE_TIMESTAMP_FILE, 'r') as f:
                return int(f.read().strip())
        except (ValueError, IOError):
            return None
    return None

# --- Main Function ---
def run(svo_filename):
    zed = sl.Camera()
    input_file = video_folder / svo_filename

    if not input_file.exists():
        print(f"Error: SVO file not found: {input_file}")
        sys.exit(1)

    print(f"Loading ZED video: {input_file.name}")

    input_type = sl.InputType()
    input_type.set_from_svo_file(str(input_file))

    init = sl.InitParameters(input_t=input_type)
    init.camera_resolution = sl.RESOLUTION.HD1080
    init.depth_mode = sl.DEPTH_MODE.PERFORMANCE  # Enable depth
    init.coordinate_units = sl.UNIT.MILLIMETER

    err = zed.open(init)
    if err != sl.ERROR_CODE.SUCCESS:
        print(f"Error opening ZED: {err}")
        zed.close()
        sys.exit(1)

    camera_fps = zed.get_camera_information().camera_configuration.fps
    image_size = zed.get_camera_information().camera_configuration.resolution
    image_zed = sl.Mat(image_size.width, image_size.height, sl.MAT_TYPE.U8_C4)
    depth_zed = sl.Mat(image_size.width, image_size.height, sl.MAT_TYPE.F32_C1)

    runtime = sl.RuntimeParameters()

    # Set desired display window size
    DISPLAY_WIDTH = 640
    DISPLAY_HEIGHT = 360

    cv2.namedWindow("ZED Image", cv2.WINDOW_NORMAL)
    cv2.namedWindow("ZED Depth", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("ZED Image", DISPLAY_WIDTH, DISPLAY_HEIGHT)
    cv2.resizeWindow("ZED Depth", DISPLAY_WIDTH, DISPLAY_HEIGHT)

    print('Waiting for DVSense to be ready...')
    while not check_file_signal(DVSENSE_READY_FILE) and not check_file_signal(STOP_SIGNAL_FILE):
        time.sleep(0.05)

    if check_file_signal(STOP_SIGNAL_FILE):
        print("Stop signal received before start.")
        zed.close()
        sys.exit(0)

    clear_file_signal(DVSENSE_READY_FILE)
    print("Starting playback...")

    zed.set_svo_position(0)
    grab_status = zed.grab(runtime)
    first_timestamp = 0
    if grab_status == sl.ERROR_CODE.SUCCESS:
        zed.retrieve_image(image_zed, sl.VIEW.LEFT, sl.MEM.CPU, image_size)
        zed.retrieve_measure(depth_zed, sl.MEASURE.DEPTH, sl.MEM.CPU, image_size)
        first_timestamp = zed.get_timestamp(sl.TIME_REFERENCE.IMAGE).get_microseconds()
        zed.set_svo_position(0)
    else:
        print("Failed to grab first frame.")
    
    print(f"Start timestamp: {first_timestamp} μs")

    while not check_file_signal(STOP_SIGNAL_FILE):
        if check_file_signal(DVSENSE_REWIND_FILE):
            zed.set_svo_position(0)
            print("Rewind signal received.")
            clear_file_signal(DVSENSE_REWIND_FILE)

        dvsense_timestamp = read_timestamp_from_file()
        err = zed.grab(runtime)

        if err == sl.ERROR_CODE.SUCCESS:
            zed.retrieve_image(image_zed, sl.VIEW.LEFT, sl.MEM.CPU, image_size)
            zed.retrieve_measure(depth_zed, sl.MEASURE.DEPTH, sl.MEM.CPU, image_size)

            image_ocv = image_zed.get_data()
            depth_data = depth_zed.get_data()

            # Process depth data to grayscale
            valid_mask = np.logical_and(np.isfinite(depth_data), depth_data > 0)
            depth_valid = np.where(valid_mask, depth_data, 0)
            depth_clipped = np.clip(depth_valid, 0, 5000)  # Limit to 5 meters

            if np.count_nonzero(depth_clipped) == 0:
                depth_gray = np.zeros((depth_data.shape[0], depth_data.shape[1]), dtype=np.uint8)
            else:
                depth_normalized = cv2.normalize(depth_clipped, None, 0, 255, cv2.NORM_MINMAX)
                depth_gray = depth_normalized.astype(np.uint8)

            current_ts = zed.get_timestamp(sl.TIME_REFERENCE.IMAGE).get_microseconds()
            if dvsense_timestamp and current_ts:
                time_diff = current_ts - dvsense_timestamp
                if time_diff > 50000:
                    time.sleep(0.01)

            # Resize frames before showing
            image_small = cv2.resize(image_ocv, (DISPLAY_WIDTH, DISPLAY_HEIGHT))
            depth_small = cv2.resize(depth_gray, (DISPLAY_WIDTH, DISPLAY_HEIGHT))

            cv2.imshow("ZED Image", image_small)
            cv2.imshow("ZED Depth", depth_small)

        elif err == sl.ERROR_CODE.END_OF_SVOFILE_REACHED:
            print("End of SVO file reached.")
            while not check_file_signal(DVSENSE_REWIND_FILE) and not check_file_signal(STOP_SIGNAL_FILE):
                time.sleep(0.05)

        elif err == sl.ERROR_CODE.NOT_A_NEW_FRAME:
            time.sleep(0.001)
        else:
            print(f"Grab error: {err}")
            break

        key = cv2.waitKey(1)
        if key & 0xFF == ord('q'):
            print("Quit requested.")
            with open(STOP_SIGNAL_FILE, 'w') as f:
                f.write("STOP")
            break

    cv2.destroyAllWindows()
    zed.close()
    print("Playback finished.")

# --- Main Execution ---
if __name__ == "__main__":
    try:
        TEMP_FOLDER.mkdir(parents=True, exist_ok=True)

        parser = argparse.ArgumentParser(description="Play ZED .svo2 video with RGB and depth (grayscale).")
        parser.add_argument("raw_filename", help="Filename of the corresponding .raw file")

        args = parser.parse_args()
        if not args.raw_filename.endswith(".raw"):
            print("Error: Must be a .raw file")
            sys.exit(1)

        base_name = os.path.splitext(args.raw_filename)[0]
        svo_filename = base_name + ".svo2"

        run(svo_filename)

    except KeyboardInterrupt:
        print("\nInterrupted by user.")
