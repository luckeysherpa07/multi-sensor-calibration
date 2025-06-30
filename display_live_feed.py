import sys
import numpy as np
import pyzed.sl as sl
import cv2
import os
import time

# Define the paths for the signal files, matching the C++ application
# IMPORTANT: Adjust these paths if your Python script is not in the same relative location
# to the 'Recording/temp' folder as your C++ executable.
# Assume C++ executable is in 'build/Release' and Recording/temp is '../../Recording/temp'
# If Python script is at the same level as 'build' and 'Recording', then just 'Recording/temp'
TEMP_FOLDER = "../../Recording/temp" # Adjust this path as needed!
SR_SIGNAL_FILE = os.path.join(TEMP_FOLDER, "src.txt") # Start Record Signal
SS_SIGNAL_FILE = os.path.join(TEMP_FOLDER, "ssc.txt") # Stop Record Signal

def check_sr_signal():
    return os.path.exists(SR_SIGNAL_FILE)

def check_ss_signal():
    return os.path.exists(SS_SIGNAL_FILE)

def clear_signal_files():
    # This function is crucial to ensure signals are acted upon only once
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

def get_next_filename(directory, base_filename):
    """Generates a unique filename with a timestamp."""
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    return os.path.join(directory, f"{base_filename}_{timestamp}.svo")

def run():
    """
    Initializes ZED camera, displays live feed, and records to SVO when 'r' is pressed
    or when external signals are detected.
    """
    zed = sl.Camera()

    # Define directory for captured videos and create if it doesn't exist
    directory = os.path.join(os.path.dirname(os.path.abspath(__file__)), "captured_videos")
    os.makedirs(directory, exist_ok=True)

    output_path = "" # Initialize output_path. It will be updated if recording starts.

    # ZED camera initialization parameters
    resolution = sl.RESOLUTION.HD1080

    init_params = sl.InitParameters()
    init_params.camera_resolution = resolution
    init_params.camera_fps = 30
    init_params.depth_mode = sl.DEPTH_MODE.NEURAL
    init_params.coordinate_units = sl.UNIT.MILLIMETER

    # Open the ZED camera
    if zed.open(init_params) != sl.ERROR_CODE.SUCCESS:
        print("Failed to open ZED camera")
        return

    # Enable positional tracking (optional, but in original script)
    positional_tracking_params = sl.PositionalTrackingParameters()
    zed.enable_positional_tracking(positional_tracking_params)

    # Create OpenCV windows for display
    cv2.namedWindow("RGB View", cv2.WINDOW_NORMAL)
    cv2.namedWindow("Depth Map", cv2.WINDOW_NORMAL)
    cv2.namedWindow("Confidence Map", cv2.WINDOW_NORMAL)

    # Set window positions
    cv2.moveWindow("RGB View", 0, 0)
    cv2.moveWindow("Depth Map", 640, 0)
    cv2.moveWindow("Confidence Map", 0, 480)

    # Recording state flag for this script
    recording_active = False
    runtime_params = sl.RuntimeParameters()

    # ZED Mat objects for image, depth, and confidence data
    image = sl.Mat()
    depth = sl.Mat()
    confidence = sl.Mat()

    print("Press 'q' to quit (from this window).")
    print("Recording will be controlled by Spacebar in the DVSense window.")

    key = ' '
    while key != 113:  # ASCII for 'q'
        # Check for external start/stop signals
        should_start_recording = check_sr_signal()
        should_stop_recording = check_ss_signal()

        if should_start_recording and not recording_active:
            # Start recording
            output_path = get_next_filename(directory, "captured_video")
            recording_params = sl.RecordingParameters(output_path, sl.SVO_COMPRESSION_MODE.H264)
            err = zed.enable_recording(recording_params)
            if err == sl.ERROR_CODE.SUCCESS:
                recording_active = True
                print(f"ZED SVO recording started: {output_path}")
            else:
                print(f"Failed to start ZED SVO recording: {err}")
            clear_signal_files() # Clear the signal after acting on it

        elif should_stop_recording and recording_active:
            # Stop recording
            zed.disable_recording()
            recording_active = False
            print("ZED SVO recording stopped.")
            print(f"SVO file saved to {output_path}")
            clear_signal_files() # Clear the signal after acting on it

        # The zed.grab() call is what captures the data,
        # and if recording is enabled, it's automatically saved.
        if zed.grab(runtime_params) == sl.ERROR_CODE.SUCCESS:
            zed.retrieve_image(image, sl.VIEW.LEFT)
            zed.retrieve_image(depth, sl.VIEW.DEPTH)
            zed.retrieve_measure(confidence, sl.MEASURE.CONFIDENCE)

            # --- Visual Feedback for Recording ---
            if recording_active:
                # Add "REC" text to the display for visual feedback
                cv2.putText(image.get_data(), "REC", (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

            # --- Display Logic ---
            img_np = image.get_data()

            depth_data = depth.get_data()
            conf_data = confidence.get_data()

            # Handle cases where depth/confidence data might not be immediately available
            if depth_data is None or conf_data is None:
                cv2.imshow("RGB View", img_np) # Still show RGB if possible
                cv2.imshow("Depth Map", np.zeros((resolution.height, resolution.width), dtype=np.uint8))
                cv2.imshow("Confidence Map", np.zeros((resolution.height, resolution.width, 3), dtype=np.uint8))
            else:
                depth_map = cv2.normalize(depth_data, None, 0, 255, cv2.NORM_MINMAX)
                depth_map = cv2.convertScaleAbs(depth_map) # Convert to 8-bit for display

                conf_map = cv2.normalize(conf_data, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
                conf_map = cv2.applyColorMap(conf_map, cv2.COLORMAP_JET)

                cv2.imshow("RGB View", img_np)
                cv2.imshow("Depth Map", depth_map)
                cv2.imshow("Confidence Map", conf_map)

        key = cv2.waitKey(10) # Wait 10ms for key press and refresh display

        # Removed 'r' key press logic for recording, now solely relies on signals
        # if key == 114: # ASCII for 'r'
        #    ... (old 'r' key logic) ...


    # --- Cleanup on exit ---
    if recording_active: # Ensure recording is stopped if the loop exits while recording
        zed.disable_recording()
        print("ZED SVO recording stopped on exit.")
    clear_signal_files() # Ensure signal files are clean on exit

    zed.close()
    cv2.destroyAllWindows()
    print("\nFINISH")

if __name__ == "__main__":
    run()