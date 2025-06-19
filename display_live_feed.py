import sys
import numpy as np
import pyzed.sl as sl
import cv2
import os
import time

def get_next_filename(directory, base_filename):
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    return os.path.join(directory, f"{base_filename}_{timestamp}.svo")

def run():
    zed = sl.Camera()

    directory = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "captured_videos")
    os.makedirs(directory, exist_ok=True)

    output_path = get_next_filename(directory, "captured_video")

    resolution = sl.RESOLUTION.HD1080

    init_params = sl.InitParameters()
    init_params.camera_resolution = resolution
    init_params.camera_fps = 30
    init_params.depth_mode = sl.DEPTH_MODE.NEURAL
    init_params.coordinate_units = sl.UNIT.MILLIMETER

    if zed.open(init_params) != sl.ERROR_CODE.SUCCESS:
        print("Failed to open camera")
        return

    positional_tracking_params = sl.PositionalTrackingParameters()
    zed.enable_positional_tracking(positional_tracking_params)

    cv2.namedWindow("RGB View", cv2.WINDOW_NORMAL)
    cv2.namedWindow("Depth Map", cv2.WINDOW_NORMAL)
    cv2.namedWindow("Confidence Map", cv2.WINDOW_NORMAL)

    cv2.moveWindow("RGB View", 0, 0)
    cv2.moveWindow("Depth Map", 640, 0)
    cv2.moveWindow("Confidence Map", 0, 480)

    runtime_params = sl.RuntimeParameters()

    image = sl.Mat()
    depth = sl.Mat()
    confidence = sl.Mat()

    key = ' '
    print("Press 'q' to quit.")
    while key != 113:  # ASCII for 'q'
        if zed.grab(runtime_params) == sl.ERROR_CODE.SUCCESS:
            zed.retrieve_image(image, sl.VIEW.LEFT)
            zed.retrieve_image(depth, sl.VIEW.DEPTH)
            zed.retrieve_measure(confidence, sl.MEASURE.CONFIDENCE)

            img_np = image.get_data()
            img_resized = img_np.copy()

            depth_map = cv2.normalize(depth.get_data(), None, 0, 255, cv2.NORM_MINMAX)
            depth_map = cv2.convertScaleAbs(depth_map)

            conf_map = cv2.normalize(confidence.get_data(), None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
            conf_map = cv2.applyColorMap(conf_map, cv2.COLORMAP_JET)

            cv2.imshow("RGB View", img_resized)
            cv2.imshow("Depth Map", depth_map)
            cv2.imshow("Confidence Map", conf_map)

        key = cv2.waitKey(10)

    zed.close()
    cv2.destroyAllWindows()
    print("\nFINISH")

if __name__ == "__main__":
    run()
