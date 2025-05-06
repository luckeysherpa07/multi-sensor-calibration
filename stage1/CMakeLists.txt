cmake_minimum_required(VERSION 3.10)

# Project definition
project("stage1")

# Set C++ standard
set(CMAKE_CXX_STANDARD 20)
add_definitions(-D NOMINMAX)

# Set DvsenseDriver path
set(DvsenseDriver_DIR "/usr/share/cmake/DvsenseDriver")
find_package(DvsenseDriver COMPONENTS Driver REQUIRED)

# Find OpenCV using pkg-config
find_package(PkgConfig REQUIRED)
pkg_check_modules(OpenCV REQUIRED opencv4)

# Include directories
include_directories("/usr/include/DvsenseDriver")
include_directories(${OpenCV_INCLUDE_DIRS})

# Add executable
add_executable(stage1 "stage1.cpp" "stage1.h")

# Link libraries
target_link_libraries(stage1
    DvsenseDriver::Driver
    ${OpenCV_LIBRARIES}
)

# Set the C++ standard for newer CMake versions
if (CMAKE_VERSION VERSION_GREATER 3.12)
    set_property(TARGET stage1 PROPERTY CXX_STANDARD 20)
endif()

# Post-build command to copy binaries to the executable's directory
add_custom_command(TARGET stage1 POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E copy
        "/usr/lib/libDvsenseDriver.so"
        "$<TARGET_FILE_DIR:stage1>"
)

# Optional: If using user-specific libDvsenseDriver.so, copy it too
# add_custom_command(TARGET stage1 POST_BUILD
#     COMMAND ${CMAKE_COMMAND} -E copy
#         "/home/ruluckeysherpa/.local/lib/python3.10/site-packages/libDvsenseDriver.so"
#         "$<TARGET_FILE_DIR:stage1>"
# )
