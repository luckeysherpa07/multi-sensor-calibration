import sys
import pyzed.sl as sl
import cv2
import os
import time
import argparse
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

# --- Helper Functions for File-based IPC ---
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

# --- Main ZED Playback Function ---
def run(svo_filename):
    zed = sl.Camera()
    input_file = video_folder / svo_filename

    if not input_file.exists():
        print(f"Error: Expected SVO file not found: {input_file}")
        sys.exit(1)

    print(f"Auto-loaded ZED video: {input_file.name}")

    input_type = sl.InputType()
    input_type.set_from_svo_file(str(input_file))

    init = sl.InitParameters(input_t=input_type)
    init.camera_resolution = sl.RESOLUTION.HD1080
    init.depth_mode = sl.DEPTH_MODE.NONE
    init.coordinate_units = sl.UNIT.MILLIMETER

    err = zed.open(init)
    if err != sl.ERROR_CODE.SUCCESS:
        print(f"Error opening ZED SVO file: {repr(err)}")
        zed.close()
        sys.exit(1)

    camera_fps = zed.get_camera_information().camera_configuration.fps
    frame_delay = int(1000 / camera_fps) if camera_fps > 0 else 30

    runtime = sl.RuntimeParameters()
    image_size = zed.get_camera_information().camera_configuration.resolution
    image_zed = sl.Mat(image_size.width, image_size.height, sl.MAT_TYPE.U8_C4)

    cv2.namedWindow("ZED Image", cv2.WINDOW_AUTOSIZE)
    print('ZED Playback: Waiting for DVSense to be ready...')

    while not check_file_signal(DVSENSE_READY_FILE) and not check_file_signal(STOP_SIGNAL_FILE):
        time.sleep(0.05)

    if check_file_signal(STOP_SIGNAL_FILE):
        print("ZED Playback: Stop signal received before DVSense was ready. Exiting.")
        zed.close()
        sys.exit(0)

    print("ZED Playback: DVSense ready signal received. Starting playback.")
    clear_file_signal(DVSENSE_READY_FILE)

    zed.set_svo_position(0)
    grab_status = zed.grab(runtime)
    first_frame_timestamp_us = 0
    if grab_status == sl.ERROR_CODE.SUCCESS:
        zed.retrieve_image(image_zed, sl.VIEW.LEFT, sl.MEM.CPU, image_size)
        first_frame_timestamp_us = zed.get_timestamp(sl.TIME_REFERENCE.IMAGE).get_microseconds()
        zed.set_svo_position(0)
    else:
        print("Could not grab first frame to get ZED SVO start timestamp. Using 0.")

    print(f"ZED SVO estimated start timestamp: {first_frame_timestamp_us} us")

    while not check_file_signal(STOP_SIGNAL_FILE):
        if check_file_signal(DVSENSE_REWIND_FILE):
            zed.set_svo_position(0)
            print("ZED SVO rewound to start (DVSense rewind signal).")
            clear_file_signal(DVSENSE_REWIND_FILE)

        dvsense_timestamp = read_timestamp_from_file()
        err = zed.grab(runtime)

        if err == sl.ERROR_CODE.SUCCESS:
            zed.retrieve_image(image_zed, sl.VIEW.LEFT, sl.MEM.CPU, image_size)
            image_ocv = image_zed.get_data()
            current_zed_timestamp_us = zed.get_timestamp(sl.TIME_REFERENCE.IMAGE).get_microseconds()

            if dvsense_timestamp is not None and current_zed_timestamp_us > 0:
                time_diff_us = current_zed_timestamp_us - dvsense_timestamp
                if time_diff_us > 50000:
                    time.sleep(0.01)

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

# --- Main Execution ---
if __name__ == "__main__":
    try:
        TEMP_FOLDER.mkdir(parents=True, exist_ok=True)

        parser = argparse.ArgumentParser(description="Play ZED .svo2 video synced with DVSense.")
        parser.add_argument("raw_filename", help="Filename of the corresponding .raw file")

        args = parser.parse_args()

        if not args.raw_filename.endswith(".raw"):
            print("Error: Expected raw filename ending in .raw")
            sys.exit(1)

        base_name = os.path.splitext(args.raw_filename)[0]
        svo_filename = base_name + ".svo2"

        run(svo_filename)

    except KeyboardInterrupt:
        print("\nZED Playback interrupted by user (Ctrl+C).")
