import sys
import numpy as np
import pyzed.sl as sl
import cv2
import os
import time

def get_next_filename(directory, base_filename):
    """Generates a unique filename with a timestamp."""
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    return os.path.join(directory, f"{base_filename}_{timestamp}.svo")

def run():
    """
    Initializes ZED camera, displays live feed, and records to SVO when 'r' is pressed.
    """
    zed = sl.Camera()

    # Define directory for captured videos and create if it doesn't exist
    directory = os.path.join(os.path.dirname(os.path.abspath(__file__)), "captured_videos")
    os.makedirs(directory, exist_ok=True)

    # Initialize output_path. It will be updated if recording starts.
    output_path = "" 

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

    print("Press 'q' to quit.")
    print("Press 'r' to toggle ZED SVO recording.")

    key = ' '
    while key != 113:  # ASCII for 'q'
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

        # Check for 'r' key press to toggle recording
        if key == 114: # ASCII for 'r'
            if not recording_active:
                # Start recording: Generate new path and enable recording
                output_path = get_next_filename(directory, "captured_video") 
                recording_params = sl.RecordingParameters(output_path, sl.SVO_COMPRESSION_MODE.H264)
                err = zed.enable_recording(recording_params)
                if err == sl.ERROR_CODE.SUCCESS:
                    recording_active = True
                    print(f"ZED SVO recording started: {output_path}")
                else:
                    print(f"Failed to start ZED SVO recording: {err}")
            else:
                # Stop recording: Disable recording
                zed.disable_recording()
                recording_active = False
                print("ZED SVO recording stopped.")
                print(f"SVO file saved to {output_path}") # Confirm where the previous file was saved

    # --- Cleanup on exit ---
    if recording_active: # Ensure recording is stopped if the loop exits while recording
        zed.disable_recording()
        print("ZED SVO recording stopped on exit.")

    zed.close()
    cv2.destroyAllWindows()
    print("\nFINISH")

if __name__ == "__main__":
    run()