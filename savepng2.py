import dv_processing as dv
import cv2 as cv
import os
import datetime

base_path = "D:/Programs/DV/Recording/"
sf_path = "D:/Programs/DV/Recording/davis/frame"
se_path = "D:/Programs/DV/Recording/davis/event"

while True:
    file_name = input("Enter a file name to read (must end with .aedat4): ")

    if not file_name.endswith(".aedat4"):
        print("Invalid file extension! It must end with '.aedat4'")
        continue

    file_path = os.path.join(base_path, file_name)

    if os.path.exists(file_path):
        break
    else:
        print("File does not exist, try again.")

while True:
    num_frames_to_save = int(input("Enter how many TIMESTAMP using for FRAME PNGs to save: "))
    num_events_to_save = int(input("Enter how many TIMESTAMP using for EVENT PNGs to save: "))

    print(f"{num_frames_to_save} for FRAME TIMPSTAMPs and {num_events_to_save} for EVENT TIMPSTAMPs.")

    # Ask for confirmation
    confirmation = input("Is this correct? (y/n): ")

    if confirmation.lower() == 'y':
        print("Confirmed")
        break
    else:
        print("Please re-enter the values.")

cv.namedWindow("Frame Preview", cv.WINDOW_NORMAL)
cv.namedWindow("Event Preview", cv.WINDOW_NORMAL)
cv.namedWindow("Combined Preview", cv.WINDOW_NORMAL)

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

    cv.imshow("Combined Preview", blended)

running = True
first_playback = True
first_check = True

while first_check:
    recording = dv.io.MonoCameraRecording(file_path)

    if first_check:
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
                print(f"Event duration: {end_timestamp_events - start_timestamp_events}")
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
            print(f"Frame duration: {end_timestamp_frames - start_timestamp_frames}")
        else:
            print("No frames found!")

        first_check = False

# frame_interval = max(1, (end_timestamp_frames - start_timestamp_frames) // num_frames_to_save)
# event_interval = max(1, (end_timestamp_frames - start_timestamp_frames) // num_events_to_save)
frame_interval = num_frames_to_save
event_interval = num_events_to_save

lastFrame = None
frame_count = 0
event_count = 0
next_frame_save_time = start_timestamp_frames
next_event_save_time = start_timestamp_frames

while running:
    recording = dv.io.MonoCameraRecording(file_path)

    assert recording.isEventStreamAvailable()
    assert recording.isFrameStreamAvailable()
    assert recording.getFrameResolution() == recording.getEventResolution()

    visualizer = dv.visualization.EventVisualizer(recording.getEventResolution())
    visualizer.setBackgroundColor((0, 0, 0))
    visualizer.setPositiveColor((0, 255, 0))  
    visualizer.setNegativeColor((0, 0, 255))  

    lastFrame = None
    frame = recording.getNextFrame()

    def preview_events(event_slice):
        cv.imshow("Event Preview", visualizer.generateImage(event_slice))

    while frame is not None:
        if lastFrame is not None:
            delay = frame.timestamp - lastFrame.timestamp

            start_timestamp = min(lastFrame.timestamp, frame.timestamp)
            end_timestamp = max(lastFrame.timestamp, frame.timestamp)

            events = recording.getEventsTimeRange(start_timestamp, end_timestamp)
            preview_events(events)

            if frame.timestamp >= next_frame_save_time and frame_count < num_frames_to_save and first_playback:
                timestamp_str = datetime.datetime.now().strftime("%Y%m%d")
                frame_filename = os.path.join(sf_path, f"{timestamp_str}_{next_frame_save_time}_{frame_count + 1}.png")
                cv.imwrite(frame_filename, frame.image)
                print(f"Saved Frame: {frame_filename}")
                frame_count += 1
                next_frame_save_time += frame_interval
            
            if events is not None:
                event_img = visualizer.generateImage(events)
                if event_img is not None:
                    cv.imshow("Event Preview", event_img)

                    if frame.timestamp >= next_event_save_time and event_count < num_events_to_save and first_playback:
                        timestamp_str = datetime.datetime.now().strftime("%Y%m%d")
                        event_filename = os.path.join(se_path, f"{timestamp_str}_{next_event_save_time}_{event_count + 1}.png")
                        cv.imwrite(event_filename, event_img)
                        print(f"Saved Event Image: {event_filename}")
                        event_count += 1
                        next_event_save_time += event_interval

            if frame.timestamp >= end_timestamp_frames:
                if first_playback:
                    first_playback = False
                print("P.Playback finished")
                print("P.Press space to replay")

                key = cv.waitKey(0) 
                if key == ord('q') or key == 27:  
                    running = False
                    break
                if key == ord(' '): 
                    print("P.Replaying")
                    lastFrame = None
                    frame = recording.getNextFrame() 
                    recording = dv.io.MonoCameraRecording(file_path)  

            if frame is not None and len(frame.image.shape) > 2: 
                frame.image = cv.cvtColor(frame.image, cv.COLOR_BGR2GRAY)

            if frame is not None: 
                cv.imshow("Frame Preview", frame.image)

            preview_events_both(events) 

            key = cv.waitKey(int(delay / 1000)) & 0xFF

            if key == ord('q') or key == 27:  
                print("Button triggered, exit")
                running = False
                break
            if key == ord(' '): 
                print("P.Replaying")
                recording = dv.io.MonoCameraRecording(file_path)
                lastFrame = None
                frame = recording.getNextFrame()

        lastFrame = frame
        frame = recording.getNextFrame()

    if not running:
        break

cv.destroyAllWindows()
