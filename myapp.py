import win32event
import win32api
import sys
from winerror import ERROR_ALREADY_EXISTS
import tkinter as tk
from tkinter.ttk import *
import cv2
from PIL import Image, ImageTk
from tkinter import filedialog
import pandas as pd
from ultralytics import YOLO
import cvzone
import threading
import numpy as np
import asyncio
from datetime import datetime
import pytz
import telegram

# Global variables for OpenCV-related objects and flags
cap = None
is_camera_on = False
frame_count = 0
area = []
frame_skip_threshold = 3
model = YOLO('yolov8s.pt')
video_paused = False
alert_telegram_each = 15
last_alert = None


# Function to read coco.txt
def read_classes_from_file(file_path):
    with open(file_path, 'r') as file:
        classes = [line.strip() for line in file]
    return classes


# Function to start the webcam feed
def start_webcam():
    global cap, is_camera_on, video_paused
    if not is_camera_on:
        cap = cv2.VideoCapture(0)  # Use the default webcam (you can change the index if needed)
        is_camera_on = True
        video_paused = False
        update_canvas()  # Start updating the canvas


# Function to stop the webcam feed
def stop_webcam():
    global cap, is_camera_on, video_paused
    if cap is not None:
        cap.release()
        is_camera_on = False
        video_paused = False


# Function to pause or resume the video
def pause_resume_video():
    global video_paused
    video_paused = not video_paused


# Function to send message to Telegram using user-provided token and chat ID
async def send_telegram():
    photo_path = "alert.png"
    try:
        # Use the token provided by the user
        my_token = token_entry.get()
        bot = telegram.Bot(token=my_token)
        chat_id = id_entry.get()
        await bot.sendPhoto(chat_id=chat_id, photo=open(photo_path, "rb"),
                            caption="Phát hiện người xâm nhập !!!")
    except Exception as ex:
        print("Không thể gửi tin nhắn tới telegram ", ex)
    print("Gửi thành công")


# Function print "WARNING" and capture image
def warning(image):
    cv2.putText(image, "CANH BAO CO NGUOI XAM NHAP!!!", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
    global last_alert
    if (last_alert is None) or ((datetime.now(pytz.utc) - last_alert).total_seconds() > alert_telegram_each):
        last_alert = datetime.now(pytz.utc)  # Gán giá trị mới cho last_alert
        cv2.imwrite("alert.png", cv2.resize(image, dsize=None, fx=0.5, fy=0.5))
        asyncio.run(send_telegram())
    return image


# Function to start video playback from a file
def select_file():
    global cap, is_camera_on, video_paused
    if is_camera_on:
        stop_webcam()  # Stop the webcam feed if running
    file_path = filedialog.askopenfilename(filetypes=[("Video files", "*.mp4 *.avi *.mov")])
    if file_path:
        cap = cv2.VideoCapture(file_path)
        is_camera_on = True
        video_paused = False
        update_canvas()  # Start updating the canvas with the video

# Print point(x, y) click mouse
#def on_click(event):
#    print("Mouse clicked at", event.x, event.y)


def reset_app():
    stop_webcam()  # Dừng webcam nếu đang chạy
    area.clear()  # Xóa các điểm trong area
    canvas.delete("all")  # Xóa hình ảnh trên canvas

def on_canvas_click(event):
    global area
    # Get the coordinates of the click event
    x, y = event.x, event.y
    # Append the new point to the list
    area.append((x, y))
    # Print the updated list of points
    print("Area points:", area)


# Function to update the Canvas with the webcam frame or video frame
def update_canvas():
    global is_camera_on, frame_count, video_paused
    if is_camera_on:
        if not video_paused:
            ret, frame = cap.read()
            if ret:
                frame_count += 1
                if frame_count % frame_skip_threshold != 0:
                    canvas.after(10, update_canvas)
                    return

                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frame = cv2.resize(frame, (1020, 500))
                selected_class = class_selection.get()

                results = model.predict(frame)
                a = results[0].boxes.data
                px = pd.DataFrame(a).astype("float")
                for index, row in px.iterrows():
                    x1 = int(row[0])
                    y1 = int(row[1])
                    x2 = int(row[2])
                    y2 = int(row[3])
                    d = int(row[5])
                    c = class_list[d]
                    if selected_class == "All" or c == selected_class:
                        #cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                        cv2.polylines(frame, [np.array(area, np.int32)], True, (209, 21, 102), 2)
                        mid_x = (x1 + x2) // 2
                        mid_y = y2
                        #cv2.circle(frame, (mid_x, mid_y), 4, (255, 0, 0), -1)
                        #cvzone.putTextRect(frame, f'{c}', (x1, y1), 1, 1)
                        if len(area) >= 3:
                            result = cv2.pointPolygonTest(np.array(area), (mid_x, mid_y), False)
                            if result >= 0:  # Nếu điểm nằm trong đa giác
                                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                                cv2.circle(frame, (mid_x, mid_y), 4, (255, 0, 0), -1)
                                cvzone.putTextRect(frame, f'{c}', (x1, y1), 1, 1)
                                warning(image=frame)

                photo = ImageTk.PhotoImage(image=Image.fromarray(frame))
                canvas.img = photo
                canvas.create_image(0, 0, anchor=tk.NW, image=photo)

        canvas.after(10, update_canvas)


# Function to quit the application
def quit_app():
    stop_webcam()
    root.quit()
    root.destroy()


# Create the main Tkinter window
root = tk.Tk()
root.title("Detect Objects On Region App")

# Create a Canvas widget to display the webcam feed or video
canvas = tk.Canvas(root, width=1020, height=500)
canvas.pack(fill='both', expand=True)

class_list = read_classes_from_file('coco.txt')

class_selection = tk.StringVar()
class_selection.set("All")  # Default selection is "All"
class_selection_label = tk.Label(root, text="Select Class:")
class_selection_label.pack(side='left')
class_selection_entry = tk.OptionMenu(root, class_selection, "All",
                                      *class_list)  # Populate dropdown with classes from the text file
class_selection_entry.pack(side='left')

# Create a frame to hold the buttons
button_frame = tk.Frame(root)
button_frame.pack(fill='x')

# Create a "Play" button to start the webcam feed
play_button = tk.Button(button_frame, text="Play", command=start_webcam)
play_button.pack(side='left')

# Create a "Stop" button to stop the webcam feed
stop_button = tk.Button(button_frame, text="Stop", command=stop_webcam)
stop_button.pack(side='left')

# Create a "Select File" button to choose a video file
file_button = tk.Button(button_frame, text="Select File", command=select_file)
file_button.pack(side='left')

# Create a "Pause/Resume" button to pause or resume video
pause_button = tk.Button(button_frame, text="Pause/Resume", command=pause_resume_video)
pause_button.pack(side='left')

# Create a "Quit" button to close the application
quit_button = tk.Button(button_frame, text="Quit", command=quit_app)
quit_button.pack(side='left')

# Display an initial image on the canvas (replace 'initial_image.jpg' with your image)
initial_image = Image.open('error404_bg.png')  # Replace 'initial_image.jpg' with your image path
initial_photo = ImageTk.PhotoImage(image=initial_image)
canvas.img = initial_photo
canvas.create_image(0, 0, anchor=tk.NW, image=initial_photo)

# Create entry widgets for Telegram token and chat ID
token_label = tk.Label(root, text="Telegram Token:")
token_label.pack(side='left')
token_entry = tk.Entry(root)
token_entry.pack(side='left')

id_label = tk.Label(root, text="Telegram ID:")
id_label.pack(side='left')
id_entry = tk.Entry(root)
id_entry.pack(side='left')

reset_button = tk.Button(button_frame, text="Reset", command=reset_app)
reset_button.pack(side='left')

#canvas.bind("<Button-1>", on_click)
canvas.bind("<Button-1>", on_canvas_click)
# Start the Tkinter main loop
root.mainloop()
