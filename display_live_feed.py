import sys
import numpy as np
import pyzed.sl as sl
import cv2
import os
import time

def run():
    zed = sl.Camera()

    directory = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "captured_videos")
    os.makedirs(directory, exist_ok=True)

    resolution = sl.RESOLUTION.VGA

    init_params = sl.InitParameters()
    init_params.camera_resolution = resolution
    init_params.camera_fps = 30
    init_params.depth_mode = sl.DEPTH_MODE.PERFORMANCE
    init_params.coordinate_units = sl.UNIT.MILLIMETER

    if zed.open(init_params) != sl.ERROR_CODE.SUCCESS:
        print("Failed to open camera")
        return

    positional_tracking_params = sl.PositionalTrackingParameters()
    zed.enable_positional_tracking(positional_tracking_params)

    body_tracking_params = sl.BodyTrackingParameters()
    body_tracking_params.detection_model = sl.BODY_TRACKING_MODEL.HUMAN_BODY_ACCURATE
    body_tracking_params.enable_tracking = True
    body_tracking_params.enable_body_fitting = True
    body_tracking_params.body_format = sl.BODY_FORMAT.BODY_34

    if zed.enable_body_tracking(body_tracking_params) != sl.ERROR_CODE.SUCCESS:
        print("Failed to enable body tracking.")
        zed.close()
        return

    cv2.namedWindow("RGB View", cv2.WINDOW_NORMAL)
    cv2.namedWindow("Depth Map", cv2.WINDOW_NORMAL)
    cv2.namedWindow("Confidence Map", cv2.WINDOW_NORMAL)
    cv2.namedWindow("Body Tracking", cv2.WINDOW_NORMAL)

    # Set the window sizes
    cv2.moveWindow("RGB View", 0, 0)
    cv2.moveWindow("Depth Map", 640, 0)
    cv2.moveWindow("Confidence Map", 0, 480)
    cv2.moveWindow("Body Tracking", 640, 480)

    runtime_params = sl.RuntimeParameters()
    body_runtime_params = sl.BodyTrackingRuntimeParameters()
    body_runtime_params.detection_confidence_threshold = 40

    image = sl.Mat()
    depth = sl.Mat()
    confidence = sl.Mat()
    bodies = sl.Bodies()

    key = ' '
    print("Press 'q' to quit.")
    while key != 113:  # ASCII for 'q'
        if zed.grab(runtime_params) == sl.ERROR_CODE.SUCCESS:
            zed.retrieve_image(image, sl.VIEW.LEFT)
            zed.retrieve_image(depth, sl.VIEW.DEPTH)
            zed.retrieve_measure(confidence, sl.MEASURE.CONFIDENCE)
            zed.retrieve_bodies(bodies, body_runtime_params)

            img_np = image.get_data()

            # FoV adjustment (ZED -> DAVIS)
            zed_fov = 87.21  # ZED Horizontal FoV
            davis_fov = 59.94  # DAVIS Horizontal FoV
            zoom_factor = 3.0  # Fixed zoom factor to match

            # Crop the image to simulate a zoom effect while preserving aspect ratio
            h, w, _ = img_np.shape
            zoom_w = int(w / zoom_factor)
            zoom_h = int(h / zoom_factor)

            start_x = (w - zoom_w) // 2
            start_y = (h - zoom_h) // 2
            img_np = img_np[start_y:start_y + zoom_h, start_x:start_x + zoom_w]

            # Preserve the aspect ratio while resizing to fit the window size
            target_aspect_ratio = 1.33  # DAVIS aspect ratio
            window_width = 1280
            window_height = 720

            # Resize the image to fit the window while preserving the aspect ratio
            new_height = int(window_width / target_aspect_ratio)
            if new_height > window_height:
                # If the height exceeds the window height, adjust accordingly
                new_height = window_height
                new_width = int(new_height * target_aspect_ratio)
            else:
                new_width = window_width

            img_resized = cv2.resize(img_np, (new_width, new_height))

            # Process depth and confidence maps accordingly
            depth_map = cv2.normalize(depth.get_data(), None, 0, 255, cv2.NORM_MINMAX)
            depth_map = cv2.convertScaleAbs(depth_map)
            depth_map = depth_map[start_y:start_y + zoom_h, start_x:start_x + zoom_w]
            depth_map = cv2.resize(depth_map, (new_width, new_height))

            conf_map = cv2.normalize(confidence.get_data(), None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
            conf_map = cv2.applyColorMap(conf_map, cv2.COLORMAP_JET)
            conf_map = conf_map[start_y:start_y + zoom_h, start_x:start_x + zoom_w]
            conf_map = cv2.resize(conf_map, (new_width, new_height))

            # Draw body keypoints on resized image
            for body in bodies.body_list:
                if body.tracking_state == sl.OBJECT_TRACKING_STATE.OK:
                    for kp in body.keypoint_2d:
                        if not np.isnan(kp[0]) and not np.isnan(kp[1]):
                            if start_x <= kp[0] <= start_x + zoom_w:
                                cropped_x = int(kp[0] - start_x)
                                cropped_y = int(kp[1] - start_y)
                                cv2.circle(img_resized, (cropped_x, cropped_y), 3, (0, 255, 0), -1)

            # Display the images
            cv2.imshow("RGB View", img_resized)
            cv2.imshow("Depth Map", depth_map)
            cv2.imshow("Confidence Map", conf_map)
            cv2.imshow("Body Tracking", img_resized)

        key = cv2.waitKey(10)

    zed.close()
    cv2.destroyAllWindows()
    print("\nFINISH")

if __name__ == "__main__":
    run()
