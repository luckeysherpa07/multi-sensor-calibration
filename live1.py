import datetime
import dv_processing as dv
import cv2 as cv
import argparse
import sys
import time
import os
import glob

sys.argv = [sys.argv[0]]

output_path = "D:/Programs/DV/Recording/"

try:
    if 'camera' in globals() and camera is not None:
        del camera
except NameError:
    pass  

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


base_path = "D:/Programs/DV/Recording/"
temp_file = "D:/Programs/DV/Recording/temp/temp_file.txt"

while True:
    file_name = input("Enter a file name to read (must end with .aedat4): ")

    if not file_name.endswith(".aedat4"):
        print("Must end with '.aedat4', try again: ")
        continue

    file_path = os.path.join(base_path, file_name)

    if os.path.exists(file_path):
        overwrite = input("File already exists! Overwrite or not? (y/n): ").lower()
        if overwrite == 'y':
            break
        else:
            print("Enter a file name (must end with .aedat4): ")
    else:
        break
with open(temp_file, "w") as f:
    f.write(file_path)
print(f"File path saved: {file_path}")
        