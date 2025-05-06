import datetime
import dv_processing as dv
import cv2 as cv
import argparse
import sys
import time
import os
import glob
from datetime import timedelta

sys.argv = [sys.argv[0]]

# output_path = "D:/Programs/DV/Recording/"

# try:
#     if 'camera' in globals() and camera is not None:
#         del camera
# except NameError:
#     pass  

# def get_file_name():
#     while True:
#         file_name = input("Enter a file name (must end with .aedat4): ")
#         if file_name.endswith(".aedat4"):
#             file_path = os.path.join(output_path, file_name)
#             if os.path.exists(file_path):
#                 overwrite = input("File already exists! Overwrite or not? (y/n): ").lower()
#                 if overwrite == 'y':
#                     return file_path  
#                 else:
#                     print("Enter a file name (must end with .aedat4): ")
#             else:
#                 return file_path 
#         else:
#             print("Must end with '.aedat4', try again: ")

# file_path = get_file_name()

cali_path = "D:/Programs/DV/Recording/cali/davis"
base_path = "D:/Programs/DV/Recording/temp"
stop_signal_path = "D:/Programs/DV/Recording/temp/stop_signal.txt"
src_path = "D:/Programs/DV/Recording/temp/src.txt"
sry_path = "D:/Programs/DV/Recording/temp/sry.txt"
ssc_path = "D:/Programs/DV/Recording/temp/ssc.txt"
ssy_path = "D:/Programs/DV/Recording/temp/ssy.txt"
calic_path = "D:/Programs/DV/Recording/temp/calic.txt"
caliy_path = "D:/Programs/DV/Recording/temp/caliy.txt"

def check_ss_signal():
    return os.path.exists(ssc_path)

def set_ss_signal():
    with open(ssy_path, "w") as f:
        f.write("STOP")

def check_sr_signal():
    return os.path.exists(src_path)

def set_sr_signal():
    with open(sry_path, "w") as f:
        f.write("START")

def check_stop_signal():
    return os.path.exists(stop_signal_path)

def set_stop_signal():
    with open(stop_signal_path, "w") as f:
        f.write("STOP")

def check_cali_signal():
    return os.path.exists(calic_path)

def set_cali_signal():
    with open(caliy_path, "w") as f:
        f.write("START")

def clear_folder():
    for file_path in glob.glob(os.path.join(base_path, "*")):
        try:
            os.remove(file_path)
        except Exception as e:
            print("Failed to delete")

temp_file = "D:/Programs/DV/Recording/temp/temp_file.txt"

with open(temp_file, "r") as f:
    file_path = f.read().strip()


camera = dv.io.CameraCapture()

camera.setDavisExposureDuration(timedelta(milliseconds=40))

# Initialize a multi-stream slicer
slicer = dv.EventMultiStreamSlicer("events")

# Add a frame stream to the slicer
slicer.addFrameStream("frames")

# Initialize a visualizer for the overlay
visualizer = dv.visualization.EventVisualizer(camera.getEventResolution(), dv.visualization.colors.black(),
                                              dv.visualization.colors.green(), dv.visualization.colors.red())


# visualizer = dv.visualization.EventVisualizer(camera.getEventResolution())
# visualizer.setBackgroundColor((0, 0, 0)) 
# visualizer.setPositiveColor((0, 255, 0)) 
# visualizer.setNegativeColor((0, 0, 255))  

cv.namedWindow("Frame Preview", cv.WINDOW_NORMAL)
cv.namedWindow("Event Preview", cv.WINDOW_NORMAL)
cv.namedWindow("Preview", cv.WINDOW_NORMAL)  

def display_preview(data):
    # Retrieve frame data using the named method and stream name
    frames = data.getFrames("frames")

    # Retrieve event data
    events = data.getEvents("events")

    event_image = visualizer.generateImage(events)

    # Retrieve and color convert the latest frame of retrieved frames
    latest_image = None
    if len(frames) > 0:
        if len(frames[-1].image.shape) == 3:
            # We already have colored image, no conversion
            latest_image = frames[-1].image
        else:
            # Image is grayscale, convert to color (BGR image)
            latest_image = cv.cvtColor(frames[-1].image, cv.COLOR_GRAY2BGR)
    else:
        return

    # Generate a preview and show the final image
    cv.imshow("Preview", visualizer.generateImage(events, latest_image))
    cv.imshow("Event Preview", event_image)


def preview_events(event_slice):
    global frame, prev_frame, frame_ready  

    if frame is not None:
        prev_frame = frame
        frame_ready = True

    if not frame_ready or prev_frame is None or prev_frame.image is None:
        return  

    frame_color = prev_frame.image 
    event_image = visualizer.generateImage(event_slice)

    # if event_image is None:
    #     return 

    # if event_image.shape[:2] != frame_color.shape[:2]:
    #     event_image = cv.resize(event_image, (frame_color.shape[1], frame_color.shape[0]))

    # if len(frame_color.shape) == 2:  
    #     frame_color = cv.cvtColor(frame_color, cv.COLOR_GRAY2BGR)

    # blended = cv.addWeighted(frame_color, 1.0, event_image, 0.5, 0)

    # cv.imshow("Preview", blended)

    cv.imshow("Event Preview", event_image)
    cv.imshow("Frame Preview", frame_color)

#slicer = dv.EventStreamSlicer()
#slicer.doEveryTimeInterval(timedelta(milliseconds=40), preview_events)
slicer.doEveryTimeInterval(timedelta(milliseconds=33), display_preview)

is_recording = False
frame_count = 0

eventsAvailable = camera.isEventStreamAvailable()
framesAvailable = camera.isFrameStreamAvailable()
imuAvailable = camera.isImuStreamAvailable()
triggersAvailable = camera.isTriggerStreamAvailable()

# def clear_camera_buffer():
#     while camera.getNextEventBatch() is not None:
#         pass
#     while camera.getNextFrame() is not None:
#         pass

writer = None

def toggle_recording():
    global is_recording, writer
    if not is_recording:
        writer = dv.io.MonoCameraWriter(file_path, camera)
        print(f"Recording started and saving to {file_path}")
        is_recording = True
    else:
        print(f"Recording stopped, file saved to {file_path}")
        del writer
        is_recording = False

# start_time = time.time()
# print("Waiting for camera to initialize...")
# while time.time() - start_time < 3:
#     camera.getNextEventBatch()  
#     camera.getNextFrame()  
# print("Done")

while True:
    frame = camera.getNextFrame()
    if frame is not None and frame.image is not None:
        frame_ready = True
        last_valid_frame = frame
        slicer.accept("frames", [frame])
        cv.imshow("Frame Preview", frame.image)
    else:
        frame_ready = False

    events = camera.getNextEventBatch()
    if events is not None:
        slicer.accept("events", events)

    key = cv.waitKey(1) & 0xFF
    if key == ord('q') or key == 27 or check_stop_signal(): 
        break
    
    if key == ord('c') or check_cali_signal():
        if check_cali_signal():
            if last_valid_frame is not None and last_valid_frame.image is not None:
                timestamp_str = datetime.datetime.now().strftime("%Y%m%d")
                frame_filename = os.path.join(cali_path, f"{timestamp_str}_{frame_count + 1}.png")
                cv.imwrite(frame_filename, last_valid_frame.image)
                print(f"Saved Frame: {frame_filename}")
                frame_count += 1
                clear_folder()
        else:
            set_cali_signal()
            if last_valid_frame is not None and last_valid_frame.image is not None:
                timestamp_str = datetime.datetime.now().strftime("%Y%m%d")
                frame_filename = os.path.join(cali_path, f"{timestamp_str}_{frame_count + 1}.png")
                cv.imwrite(frame_filename, last_valid_frame.image)
                print(f"Saved Frame: {frame_filename}")
                frame_count += 1
        
    # if key == ord('c') or check_cali_signal():
    #     if check_cali_signal():
    #         timestamp_str = datetime.datetime.now().strftime("%Y%m%d")
    #         frame_filename = os.path.join(cali_path, f"{timestamp_str}_{frame_count + 1}.png")
    #         cv.imwrite(frame_filename, frame.image)
    #         print(f"Saved Frame: {frame_filename}")
    #         frame_count += 1
    #         clear_folder()
    #     else:
    #         set_cali_signal()
    #         timestamp_str = datetime.datetime.now().strftime("%Y%m%d")
    #         frame_filename = os.path.join(cali_path, f"{timestamp_str}_{frame_count + 1}.png")
    #         cv.imwrite(frame_filename, frame.image)
    #         print(f"Saved Frame: {frame_filename}")
    #         frame_count += 1

    if key == ord(' ') or check_sr_signal() or check_ss_signal():  
        if(check_ss_signal() and not key == ord(' ')):
           if(is_recording):
               print(f"P1.Recording stopped, file saved to {file_path}")
               del writer
               is_recording = False
               clear_folder()
        elif(check_sr_signal() and not key == ord(' ')):
            if(not is_recording):
                writer = dv.io.MonoCameraWriter(file_path, camera)
                print(f"P2.Recording started and saving to {file_path}")
                is_recording = True
        elif(key == ord(' ') and not check_sr_signal() and not check_ss_signal()):
            if(is_recording):
                set_ss_signal()
                is_recording = False
                print(f"P3.Recording stopped, file saved to {file_path}")
                del writer
            else:
                set_sr_signal()
                is_recording = True
                writer = dv.io.MonoCameraWriter(file_path, camera)
                print(f"P4.Recording started and saving to {file_path}")
        elif(key == ord(' ') and check_sr_signal() and not check_ss_signal()):
            if(is_recording):
                clear_folder()
                set_ss_signal()
                is_recording = False
                print(f"P5.Recording stopped, file saved to {file_path}")
                del writer
            # else:
            #     set_sr_signal()
            #     is_recording = True
            #     writer = dv.io.MonoCameraWriter(file_path, camera)
            #     print(f"Recording started and saving to {file_path}")
        # elif(key == ord(' ') and check_ss_signal() and not check_sr_signal()):
        #     if(is_recording):
        #         set_ss_signal()
        #         is_recording = False
        #         print(f"Recording stopped, file saved to {file_path}")
        #         del writer
        #     else:
        #         set_sr_signal()
        #         is_recording = True
        #         writer = dv.io.MonoCameraWriter(file_path, camera)
        #         print(f"Recording started and saving to {file_path}")


    if is_recording:

        if framesAvailable:
            frame = camera.getNextFrame()
            if frame is not None:
                frame_ready = True
                writer.writeFrame(frame, streamName='frames')
            else:
                frame_ready = False

        if eventsAvailable:
            events = camera.getNextEventBatch()
            if events is not None:
                slicer.accept(events)
                writer.writeEvents(events, streamName='events')

        if imuAvailable:
            imus = camera.getNextImuBatch()
            if imus is not None:
                writer.writeImuPacket(imus, streamName='imu')

        if triggersAvailable:
            triggers = camera.getNextTriggerBatch()
            if triggers is not None:
                writer.writeTriggerPacket(triggers, streamName='triggers')

cv.destroyAllWindows()
del camera

if check_stop_signal():
    clear_folder()
else:
    set_stop_signal()
