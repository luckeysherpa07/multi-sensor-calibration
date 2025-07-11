import sys
import numpy as np
import pyzed.sl as sl
import cv2
import os
import time

TEMP_FOLDER = "../../Recording/temp"
SR_SIGNAL_FILE = os.path.join(TEMP_FOLDER, "src.txt")  # Start Record Signal
SS_SIGNAL_FILE = os.path.join(TEMP_FOLDER, "ssc.txt")  # Stop Record Signal

def check_sr_signal():
    return os.path.exists(SR_SIGNAL_FILE)

def check_ss_signal():
    return os.path.exists(SS_SIGNAL_FILE)

def clear_signal_files():
    if os.path.exists(SR_SIGNAL_FILE):
        try:
            os.remove(SR_SIGNAL_FILE)
            print(f"Removed: {SR_SIGNAL_FILE}")
        except OSError as e:
            print(f"Error removing {SR_SIGNAL_FILE}: {e}")
    if os.path.exists(SS_SIGNAL_FILE):
        try:
            os.remove(SS_SIGNAL_FILE)
            print(f"Removed: {SS_SIGNAL_FILE}")
        except OSError as e:
            print(f"Error removing {SS_SIGNAL_FILE}: {e}")

def run():
    # ✅ Read the base file name from command line
    if len(sys.argv) < 2:
        print("Usage: python live2.py <base_file_name>")
        return
    base_filename = sys.argv[1].split('.')[0]  # Remove .raw if included

    zed = sl.Camera()

    directory = os.path.join(os.path.dirname(os.path.abspath(__file__)), "captured_videos")
    os.makedirs(directory, exist_ok=True)

    output_path = os.path.join(directory, f"{base_filename}.svo")

    init_params = sl.InitParameters()
    init_params.camera_resolution = sl.RESOLUTION.HD1080
    init_params.camera_fps = 30
    init_params.depth_mode = sl.DEPTH_MODE.NEURAL
    init_params.coordinate_units = sl.UNIT.MILLIMETER

    if zed.open(init_params) != sl.ERROR_CODE.SUCCESS:
        print("Failed to open ZED camera")
        return

    positional_tracking_params = sl.PositionalTrackingParameters()
    zed.enable_positional_tracking(positional_tracking_params)

    cv2.namedWindow("RGB View", cv2.WINDOW_NORMAL)
    cv2.namedWindow("Depth Map", cv2.WINDOW_NORMAL)
    cv2.namedWindow("Confidence Map", cv2.WINDOW_NORMAL)
    cv2.moveWindow("RGB View", 0, 0)
    cv2.moveWindow("Depth Map", 640, 0)
    cv2.moveWindow("Confidence Map", 0, 480)

    recording_active = False
    runtime_params = sl.RuntimeParameters()
    image = sl.Mat()
    depth = sl.Mat()
    confidence = sl.Mat()

    print("Press 'q' to quit. Recording controlled via DVSense window.")

    key = ' '
    while key != 113:  # ASCII for 'q'
        should_start_recording = check_sr_signal()
        should_stop_recording = check_ss_signal()

        if should_start_recording and not recording_active:
            recording_params = sl.RecordingParameters(output_path, sl.SVO_COMPRESSION_MODE.H264)
            err = zed.enable_recording(recording_params)
            if err == sl.ERROR_CODE.SUCCESS:
                recording_active = True
                print(f"ZED SVO recording started: {output_path}")
            else:
                print(f"Failed to start ZED SVO recording: {err}")
            clear_signal_files()

        elif should_stop_recording and recording_active:
            zed.disable_recording()
            recording_active = False
            print("ZED SVO recording stopped.")
            print(f"SVO file saved to {output_path}")
            clear_signal_files()

        if zed.grab(runtime_params) == sl.ERROR_CODE.SUCCESS:
            zed.retrieve_image(image, sl.VIEW.LEFT)
            zed.retrieve_image(depth, sl.VIEW.DEPTH)
            zed.retrieve_measure(confidence, sl.MEASURE.CONFIDENCE)

            if recording_active:
                cv2.putText(image.get_data(), "REC", (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

            img_np = image.get_data()
            depth_data = depth.get_data()
            conf_data = confidence.get_data()

            if depth_data is None or conf_data is None:
                cv2.imshow("RGB View", img_np)
                cv2.imshow("Depth Map", np.zeros((1080, 1920), dtype=np.uint8))
                cv2.imshow("Confidence Map", np.zeros((1080, 1920, 3), dtype=np.uint8))
            else:
                depth_map = cv2.normalize(depth_data, None, 0, 255, cv2.NORM_MINMAX)
                depth_map = cv2.convertScaleAbs(depth_map)
                conf_map = cv2.normalize(conf_data, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
                conf_map = cv2.applyColorMap(conf_map, cv2.COLORMAP_JET)

                cv2.imshow("RGB View", img_np)
                cv2.imshow("Depth Map", depth_map)
                cv2.imshow("Confidence Map", conf_map)

        key = cv2.waitKey(10)

    if recording_active:
        zed.disable_recording()
        print("ZED SVO recording stopped on exit.")
    clear_signal_files()
    zed.close()
    cv2.destroyAllWindows()
    print("FINISH")

if __name__ == "__main__":
    run()
