import dv_processing as dv
import cv2 as cv
import os
import sys
import glob

# base_path = "D:/Programs/DV/Recording/"

# while True:
#     file_name = input("Enter a file name to read (must end with .aedat4): ")

#     if not file_name.endswith(".aedat4"):
#         print("Invalid file extension! It must end with '.aedat4'")
#         continue

#     file_path = os.path.join(base_path, file_name)

#     if os.path.exists(file_path):
#         break
#     else:
#         print("File does not exist, try again.")

cv.namedWindow("Frame Preview", cv.WINDOW_NORMAL)
cv.namedWindow("Event Preview", cv.WINDOW_NORMAL)
cv.namedWindow("Preview", cv.WINDOW_NORMAL) 

# def preview_events_both(event_slice):
#     global frame, prev_frame, frame_ready  

#     if frame is not None:
#         prev_frame = frame
#         frame_ready = True

#     if not frame_ready or prev_frame is None or prev_frame.image is None:
#         return  

#     frame_color = prev_frame.image
#     event_image = visualizer.generateImage(event_slice)

#     if event_image is None:
#         print("No event image generated!") 
#         return 

#     if event_image.shape[:2] != frame_color.shape[:2]:
#         print(f"Resizing event image from {event_image.shape} to {frame_color.shape}") 
#         event_image = cv.resize(event_image, (frame_color.shape[1], frame_color.shape[0]))

#     if len(frame_color.shape) == 2:  
#         frame_color = cv.cvtColor(frame_color, cv.COLOR_GRAY2BGR)

#     blended = cv.addWeighted(frame_color, 1.0, event_image, 0.5, 0)

#     cv.imshow("Combined Preview", blended)

def display_preview(data):
    # Retrieve frame data using the named method and stream name
    frames = data.getFrames("frames")

    # Retrieve event data
    events = data.getEvents("events")

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

class FakeSlicedPacket:
    def __init__(self, events, frames):
        self._events = events
        self._frames = frames

    def getEvents(self, name):
        if name == "events":
            return self._events
        return []

    def getFrames(self, name):
        if name == "frames":
            return self._frames
        return []

def preview_events_both(event_slice):
    global frame, prev_frame, frame_ready  

    if frame is not None:
        prev_frame = frame
        frame_ready = True

    if not frame_ready or prev_frame is None or prev_frame.image is None:
        return  

    frame_color = prev_frame.image
    event_image = visualizer.generateImage(event_slice)

    if event_image is None:
        print("No event image generated!") 
        return 

    if event_image.shape[:2] != frame_color.shape[:2]:
        print(f"Resizing event image from {event_image.shape} to {frame_color.shape}") 
        event_image = cv.resize(event_image, (frame_color.shape[1], frame_color.shape[0]))

    if len(frame_color.shape) == 2:  
        frame_color = cv.cvtColor(frame_color, cv.COLOR_GRAY2BGR)

    blended = cv.addWeighted(frame_color, 1.0, event_image, 0.5, 0)

    cv.imshow("Preview", blended)


running = True 
first_playback = True

base_path = "D:/Programs/DV/Recording/temp"
stop_signal_path = "D:/Programs/DV/Recording/temp/stop_signal.txt"

def check_stop_signal():
    return os.path.exists(stop_signal_path)

def set_stop_signal():
    with open(stop_signal_path, "w") as f:
        f.write("STOP")

temp_file = "D:/Programs/DV/Recording/temp/temp_file.txt"

with open(temp_file, "r") as f:
    file_path = f.read().strip()

while running: 
    recording = dv.io.MonoCameraRecording(file_path)

    assert recording.isEventStreamAvailable()
    assert recording.isFrameStreamAvailable()
    assert recording.getFrameResolution() == recording.getEventResolution()

    if first_playback:
        event_batches = []
        while True:
            events = recording.getNextEventBatch()
            if events is None or len(events) == 0:
                break
            event_batches.append(events)

        if len(event_batches) > 0:
            start_events = list(event_batches[0])  
            end_events = list(event_batches[-1]) 

            if len(start_events) > 0 and len(end_events) > 0:
                start_timestamp_events = start_events[0].timestamp()
                end_timestamp_events = end_events[-1].timestamp()
                print(f"Event Start Timestamp: {start_timestamp_events}")
                print(f"Event End Timestamp: {end_timestamp_events}")
            else:
                print("No valid events found!")

        frame = recording.getNextFrame()
        if frame is not None:
            start_timestamp_frames = frame.timestamp
            while frame is not None:
                end_timestamp_frames = frame.timestamp
                frame = recording.getNextFrame()
            print(f"Frame Start Timestamp: {start_timestamp_frames}")
            print(f"Frame End Timestamp: {end_timestamp_frames}")
        else:
            print("No frames found!")

        first_playback = False
    
    visualizer = dv.visualization.EventVisualizer(recording.getEventResolution(), dv.visualization.colors.black(),
                                              dv.visualization.colors.green(), dv.visualization.colors.red())

    # visualizer = dv.visualization.EventVisualizer(recording.getEventResolution())
    # visualizer.setBackgroundColor((0, 0, 0))
    # visualizer.setPositiveColor((0, 255, 0))
    # visualizer.setNegativeColor((0, 0, 255))

    def preview_events(event_slice):
        cv.imshow("Event Preview", visualizer.generateImage(event_slice))

    lastFrame = None
    frame = recording.getNextFrame()

    # start_timestamp = frame.timestamp
    # end_timestamp = lastFrame.timestamp
    # print(f"Start Timestamp: {start_timestamp}")
    # print(f"End Timestamp: {end_timestamp}")


    while frame is not None:
        if lastFrame is not None:
            delay = frame.timestamp - lastFrame.timestamp

            events = recording.getEventsTimeRange(lastFrame.timestamp, frame.timestamp)
            preview_events(events)

            if len(frame.image.shape) > 2:
                frame.image = cv.cvtColor(frame.image, cv.COLOR_BGR2GRAY)

            cv.imshow("Frame Preview", frame.image)

            if frame.timestamp >= end_timestamp_frames:
                print("P.Playback finished, replaying")
            
            data = FakeSlicedPacket(events, [lastFrame])
            display_preview(data)
            # preview_events_both(events) 

            key = cv.waitKey(int(delay / 1000)) & 0xFF

            if key == ord('q') or key == 27 or check_stop_signal(): 
                running = False 
                break

        lastFrame = frame
        frame = recording.getNextFrame()

    if not running:
        break  

cv.destroyAllWindows()

if check_stop_signal():
    for file_path in glob.glob(os.path.join(base_path, "*")):
        try:
            os.remove(file_path)
        except Exception as e:
            print("Failed to delete ")
else:
    set_stop_signal()