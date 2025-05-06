# CMakeList.txt: stage1 的 CMake 项目，在此处包括源代码并定义
# 项目特定的逻辑。
#
cmake_minimum_required (VERSION 3.10)

# 如果支持，请为 MSVC 编译器启用热重载。
if (POLICY CMP0141)
  cmake_policy(SET CMP0141 NEW)
  set(CMAKE_MSVC_DEBUG_INFORMATION_FORMAT "$<IF:$<AND:$<C_COMPILER_ID:MSVC>,$<CXX_COMPILER_ID:MSVC>>,$<$<CONFIG:Debug,RelWithDebInfo>:EditAndContinue>,$<$<CONFIG:Debug,RelWithDebInfo>:ProgramDatabase>>")
endif()


project ("stage1")

# 将源代码添加到此项目的可执行文件。
set(CMAKE_CXX_STANDARD 20)
add_definitions(-D NOMINMAX)
 

set(DvsenseDriver_DIR "D:/Programs/DvsenseDriver/share/cmake/DvsenseDriver")
find_package(DvsenseDriver COMPONENTS Driver REQUIRED)


# set(dv-processing_DIR "D:/Programs/DV/dv_processing/share/dv-processing")
# find_package(dv-processing REQUIRED)


set(OpenCV_DIR "D:/Programs/opencv/build")
find_package(OpenCV REQUIRED)


include_directories("D:/Programs/opencv/build/include/")

include_directories("D:/Programs/DvsenseDriver/include")

# include_directories("D:/Programs/DV/fmt/include/")

# include_directories("D:/Programs/DV/dv_processing/include/dv-processing")


add_executable (stage1 "stage1.cpp" "stage1.h")

target_link_libraries("stage1"
    DvsenseDriver::Driver
    ${OpenCV_LIBS}
    # dv::processing
)


if (CMAKE_VERSION VERSION_GREATER 3.12)
  set_property(TARGET stage1 PROPERTY CXX_STANDARD 20)
endif()

# TODO: 如有需要，请添加测试并安装目标。
add_custom_command(TARGET stage1 POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E copy_directory
        "D:/Programs/DvsenseDriver/bin"
        "$<TARGET_FILE_DIR:stage1>"
)