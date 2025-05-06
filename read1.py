import dv_processing as dv
import cv2 as cv
import os

base_path = "D:/Programs/DV/Recording/"
temp_file = "D:/Programs/DV/Recording/temp/temp_file.txt"

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

with open(temp_file, "w") as f:
    f.write(file_path)

