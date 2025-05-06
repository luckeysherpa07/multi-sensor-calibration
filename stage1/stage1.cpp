#include <DvsenseDriver/camera/DvsCameraManager.hpp>
#include "stage1.h"
#include <DvsenseDriver/FileReader/DvsFileReader.h>
#include <iostream>
#include <vector>
#include <opencv2/opencv.hpp>
#include <DvsenseBase/logging/logger.hh>
#include <thread>
#include <filesystem>
#include <fstream>
#include <chrono>
#include <iomanip>
#include <sstream>

class EventAnalyzer {
public:
	cv::Mat img, img_swap;
	std::mutex m;

	// Gray
	cv::Vec3b color_bg = cv::Vec3b(0x70, 0x70, 0x70);
	cv::Vec3b color_on = cv::Vec3b(0xbf, 0xbc, 0xb4);
	cv::Vec3b color_off = cv::Vec3b(0x40, 0x3d, 0x33);

	void setup_display(const int width, const int height) {
		img = cv::Mat(height, width, CV_8UC3);
		img_swap = cv::Mat(height, width, CV_8UC3);
		img.setTo(color_bg);
	}

	// Called from main Thread
	void get_display_frame(cv::Mat& display) {
		// Swap images
		{
			std::unique_lock<std::mutex> lock(m);
			std::swap(img, img_swap);
			img.setTo(color_bg);
		}
		img_swap.copyTo(display);
	}

	// Called from decoding Thread
	void process_events(const dvsense::Event2D* begin, const dvsense::Event2D* end) {
		std::unique_lock<std::mutex> lock(m);

		for (auto it = begin; it != end; ++it) {
			img.at<cv::Vec3b>(it->y, it->x) = (it->polarity) ? color_on : color_off;
		}
	}
};

void run_python_script(const std::string& python_path, const std::string& script_path) {
	//std::string command = python_path + " " + script_path + " >nul 2>&1"; 
	std::string command = python_path + " " + script_path;
	std::system(command.c_str());
}

void set_stop_signal() {
	std::ofstream stopFile("D:/Programs/DV/Recording/temp/stop_signal.txt");
	stopFile << "STOP";
	stopFile.close();
}

bool check_stop_signal() {
	std::ifstream stopFile("D:/Programs/DV/Recording/temp/stop_signal.txt");
	return stopFile.good(); 
}

void set_sr_signal() {
	std::ofstream srFile("D:/Programs/DV/Recording/temp/src.txt");
	srFile << "START";
	srFile.close();
}

bool check_sr_signal() {
	std::ifstream srFile("D:/Programs/DV/Recording/temp/sry.txt");
	return srFile.good();
}

void set_ss_signal() {
	std::ofstream ssFile("D:/Programs/DV/Recording/temp/ssc.txt");
	ssFile << "STOP";
	ssFile.close();
}

bool check_ss_signal() {
	std::ifstream ssFile("D:/Programs/DV/Recording/temp/ssy.txt");
	return ssFile.good();
}

bool check_cali_signal() {
	std::ifstream caliFile("D:/Programs/DV/Recording/temp/caliy.txt");
	return caliFile.good();
}

void set_cali_signal() {
	std::ofstream caliFile("D:/Programs/DV/Recording/temp/calic.txt");
	caliFile << "START";
	caliFile.close();
}

//void set_to_record(bool start_recording) {
//	std::ofstream signal_file("D:/Programs/DV/Recording/temp/record_signal.txt");
//	if (signal_file.is_open()) {
//		signal_file << (start_recording ? "start" : "stop");
//		signal_file.close();
//	}
//	else {
//		std::cerr << "Failed to open" << std::endl;
//	}
//}
//
//bool check_record_signal(std::string& signal) {
//	std::ifstream signal_file("D:/Programs/DV/Recording/temp/record_signal.txt");
//	if (!signal_file.is_open()) {
//		signal = "";
//		return false;
//	}
//
//	std::getline(signal_file, signal); 
//	signal_file.close();
//
//	return (signal == "start" || signal == "stop");
//}


void clearTempFolder() {
	std::string temp_folder = "D:/Programs/DV/Recording/temp";

	if (!std::filesystem::exists(temp_folder)) {
		std::cout << "Folder not found" << std::endl;
		return;
	}

	try {
		for (const auto& entry : std::filesystem::directory_iterator(temp_folder)) {
			std::filesystem::remove(entry.path());
		}
	}
	catch (const std::exception& e) {
		std::cerr << "Failed to delete" << std::endl;
	}
}


int recordFromCamera(int argc, char* argv[]) {

	clearTempFolder();

	std::string python_path = "/usr/bin/python3";
	std::string live1_path = "../../live1.py";
	std::string live2_path = "../../live2.py";

	// 处理文件路径
	std::string base_path = "D:/Programs/DV/Recording/";
	std::string file_name;
	std::string out_file_path;

	std::string cali_path = "D:/Programs/DV/Recording/cali/dvsense/";

	std::chrono::system_clock::time_point now = std::chrono::system_clock::now();
	std::time_t now_c = std::chrono::system_clock::to_time_t(now);
	std::tm tm = *std::localtime(&now_c);

	std::stringstream date_str;
	date_str << std::put_time(&tm, "%Y%m%d");
	std::string date = date_str.str();

	// 显示帮助信息
	const std::string short_program_desc(
		"Simple viewer to stream events from device, using the SDK driver API\n");
	std::string long_program_desc(short_program_desc +
		"Press 'q' or Escape key to leave the program.\n"
		"Press 'Space' key to start/stop recording events to a raw file\n");

	if (argc > 1 && (std::string(argv[1]) == "-h" || std::string(argv[1]) == "--help")) {
		std::cout << "Usage: " << argv[0] << " [output_file_name.raw]" << std::endl;
		std::cout << "Default save path: " << base_path << "default_file_name.raw" << std::endl;
		std::cout << long_program_desc << std::endl;
		return 0;
	}

	std::cout << long_program_desc << std::endl;

	// ----------------- Camera initialization -----------------
	dvsense::DvsCameraManager cameraManager;
	dvsense::CameraDevice camera;
	const int fps = 30;
	const int wait_time = static_cast<int>(std::round(1.f / fps * 1000));

	if (argc == 2) {
		file_name = argv[1];
		out_file_path = base_path + file_name;
	}
	else {
		while (true) {
			std::cout << "Enter a file name (must end with .raw): ";
			std::cin >> file_name;

			if (file_name.size() < 5 || file_name.substr(file_name.size() - 4) != ".raw") {
				std::cerr << "Invalid file name! It must end with '.raw'" << std::endl;
				continue;
			}

			out_file_path = base_path + file_name;

			if (std::filesystem::exists(out_file_path)) {
				char choice;
				std::cout << "File already exists! Overwrite (o), re-enter (r), or cancel (c): ";
				std::cin >> choice;

				if (choice == 'o' || choice == 'O') {
					break;  // 选择覆盖
				}
				else if (choice == 'r' || choice == 'R') {
					continue;  // 重新输入
				}
				else {
					camera->stop();
					return 0;
				}
			}
			else {
				break;  // 无同名文件
			}
		}
	}
	std::cout << "Saving file to: " << out_file_path << std::endl;

	std::thread python_thread(run_python_script, python_path, live1_path);
	python_thread.join();
	
	cv::Mat display;
	const std::string window_name = "DVSense Camera Viewer";
	cv::namedWindow(window_name, cv::WINDOW_GUI_EXPANDED);

	EventAnalyzer event_analyzer;
	bool is_recording = false;
	bool stop_application = false;
	int save_count = 1;

	std::thread python_live2(run_python_script, python_path, live2_path);

	do {
		if (!camera || !camera->isConnected())
		{
			// If the camera is not connected, reconnect it.
			const std::vector<dvsense::CameraDescription> camera_descs = cameraManager.getCameraDescs();
			// Print all cameras found
			for (auto& cameraDesc : camera_descs) {
				LOG_INFO("Camera found: %s : %s", cameraDesc.manufacturer.c_str(), cameraDesc.serial.c_str());
			}
			if (camera_descs.size() > 0)
			{
				// Open the first camera found
				camera = cameraManager.openCamera(camera_descs[0].serial);
				if (camera)
				{
					LOG_INFO("Camera open success.");

					event_analyzer.setup_display(camera->getWidth(), camera->getHeight());

					// Start a thread to get events from the camera
					camera->setBatchEventsNum(10000);
					camera->addEventsStreamHandleCallback([&event_analyzer](const dvsense::Event2D* begin, const dvsense::Event2D* end) {
						event_analyzer.process_events(begin, end);
						});
					camera->addTriggerInCallback([](const dvsense::EventTriggerIn trigger) {
						LOG_INFO("Trigger info: id: %d, p: %d, time: %d", trigger.id, trigger.polarity, trigger.timestamp);
						});
					cv::resizeWindow(window_name, camera->getWidth(), camera->getHeight());

					camera->start();
				}
			}
			else
			{
				LOG_INFO("Watting camera connect...");
				std::this_thread::sleep_for(std::chrono::milliseconds(1000));
			}
		}
		event_analyzer.get_display_frame(display);
		if (!display.empty()) {
			cv::imshow(window_name, display);
		}

		// If user presses `q` key, exit loop and stop application
		int key = cv::waitKey(wait_time);
		if ((key & 0xff) == 'q' || (key & 0xff) == 27 || check_stop_signal()) {
			stop_application = true;
			std::cout << "Button triggered, exit" << std::endl;
			camera->stop();
		}
		else if (((key & 0xff) == 'c') || check_cali_signal()) {
			if (check_cali_signal()) {
				std::string img_filename = cali_path + date + "_" + std::to_string(save_count) + ".png";
				cv::imwrite(img_filename, display);
				std::cout << "Saved: " << img_filename << std::endl;
				save_count++;
				clearTempFolder();
			}
			else {
				set_cali_signal();
				std::string img_filename = cali_path + date + "_" + std::to_string(save_count) + ".png";
				cv::imwrite(img_filename, display);
				std::cout << "Saved: " << img_filename << std::endl;
				save_count++;
			}
		}
		else if (((key & 0xff) == ' ') || check_sr_signal() || check_ss_signal())
		{
			if (check_ss_signal() && !((key & 0xff) == ' ')) {
				if (is_recording) {
					is_recording = false;
					camera->stopRecording();
					std::cout << "C1.stop save raw file: " << out_file_path << std::endl;
					clearTempFolder();
				}
			}
			else if (check_sr_signal() && !((key & 0xff) == ' ')) {
				if (!is_recording) {
					is_recording = true;
					if (camera->startRecording(out_file_path) == 0)
					{
						std::cout << "C2.start save raw file: " << out_file_path << std::endl;
					}
				}
			}
			else if (((key & 0xff) == ' ') && !check_sr_signal() && !check_ss_signal()) {
				if (is_recording) {
					set_ss_signal();
					is_recording = false;
					camera->stopRecording();
					std::cout << "C3.stop save raw file: " << out_file_path << std::endl;
				}
				else {
					set_sr_signal();
					is_recording = true;
					if (camera->startRecording(out_file_path) == 0)
					{
						std::cout << "C4.start save raw file: " << out_file_path << std::endl;
					}
				}
			}
			else if (((key & 0xff) == ' ') && check_sr_signal() && !check_ss_signal()) {
				if (is_recording) {
					clearTempFolder();
					set_ss_signal();
					is_recording = false;
					camera->stopRecording();
					std::cout << "C5.stop save raw file: " << out_file_path << std::endl;
				}
				/*else {
					set_sr_signal();
					is_recording = true;
					if (camera->startRecording(out_file_path) == 0)
					{
						std::cout << "start save raw file: " << out_file_path << std::endl;
					}

				}*/
			}
			/*else if (((key & 0xff) == ' ') && check_ss_signal()) {
				if (is_recording) {
					set_ss_signal();
					is_recording = false;
					camera->stopRecording();
					std::cout << "stop save raw file: " << out_file_path << std::endl;
				}
				else {
					set_sr_signal();
					is_recording = true;
					if (camera->startRecording(out_file_path) == 0)
					{
						std::cout << "start save raw file: " << out_file_path << std::endl;
					}

				}
			}*/


			/*if (is_recording)
			{
				is_recording = false;
				camera->stopRecording();
				std::cout << "stop save raw file: " << out_file_path << std::endl;
			}
			else
			{
				is_recording = true;
				if (camera->startRecording(out_file_path) == 0)
				{
					std::cout << "start save raw file: " << out_file_path << std::endl;
				}
			}*/
		}
	} while (!stop_application);

	if (!check_stop_signal()) {
		set_stop_signal();
	}
	else {
		clearTempFolder();
	}

	python_live2.join();

	return 0;
	

	// 查找所有的摄像头
	/*dvsense::DvsCameraManager cameraManager;
	std::vector<dvsense::CameraDescription> cameraDescs = cameraManager.getCameraDescs();

	if (cameraDescs.empty()) {
		std::cout << "No cameras found" << std::endl;
	}
	else {
		std::cout << "Found " << cameraDescs.size() << " camera(s):\n";
		for (const auto& cam : cameraDescs) {
			std::cout << "Serial: " << cam.serial << std::endl;
		}
	}

	// 打开第一个摄像头
	dvsense::CameraDevice camera = cameraManager.openCamera(cameraDescs[0].serial);
	if (!camera) {
		std::cerr << "Failed to open camera" << std::endl;
		return -1;
	}

	camera->setBatchEventsTime(1000000);
	//camera->setBatchEventsNum(100000);
	camera->start();  // 开始取流

	std::string base_path = "D:/Programs/DV/";  // 固定路径
	std::string file_name;
	std::string save_path;

	while (true) {
		std::cout << "Enter a file name (must end with .raw): ";
		std::cin >> file_name;

		// 正确输入 .raw 
		if (file_name.size() < 5 || file_name.substr(file_name.size() - 4) != ".raw") {
			std::cerr << "Invalid file name! It must end with '.raw'" << std::endl;
			continue;
		}

		save_path = base_path + file_name;

		// 是否存在
		if (std::filesystem::exists(save_path)) {
			char choice;
			std::cout << "Warning: File " << save_path << " already exists!\n";
			std::cout << "Do you want to (o)verwrite, (r)e-enter name, or (c)ancel? ";
			std::cin >> choice;

			if (choice == 'o' || choice == 'O') {
				break;  // 覆盖文件
			}
			else if (choice == 'r' || choice == 'R') {
				continue;  // 重新输入
			}
			else {
				camera->stop();
				return 0;
			}
		}
		else {
			break;  // 文件不存在
		}
	}

	// 开始录制
	camera->startRecording(save_path);

	dvsense::Event2DVector events;
	bool ret = camera->getNextBatch(events);
	if (ret) {
		std::cout << "Received " << events.size() << " events" << std::endl;
	}
	else {
		std::cerr << "Failed to get events" << std::endl;
	}

	// 停止录制
	camera->stopRecording();

	// 检查创建
	if (std::filesystem::exists(save_path)) {
		std::cout << "Recording  successed: " << save_path << std::endl;
	}
	else {
		std::cerr << "Recording failed" << save_path << std::endl;
	}
	camera->stop();  // 停止取流

	std::cout << "Camera stopped." << std::endl;*/

	
}

int readFromFile(int argc, char* argv[]) {

	clearTempFolder();

	std::string python_path = "/usr/bin/python3";
	std::string read1_path = "D:/Programs/DV/read1.py";
	std::string read2_path = "D:/Programs/DV/read2.py";

	//读取文件
	/*dvsense::DvsFile reader = dvsense::DvsFileReader::createFileReader("D:/Programs/DV/test.raw");
	reader->loadFile();
	dvsense::TimeStamp start_timestamp, end_timestamp;
	reader->getStartTimeStamp(start_timestamp);
	reader->getEndTimeStamp(end_timestamp);
	reader->seekTime(start_timestamp);
	std::cout << "Start Timestamp: " << start_timestamp << std::endl;
	std::cout << "End Timestamp: " << end_timestamp << std::endl;
	if (reader->seekTime(start_timestamp)) {
		std::cout << "Seek successed" << std::endl;
	}
	else {
		std::cout << "Seek failed" << std::endl;
	}

	return 0;*/

	// 处理文件路径
	std::string base_path = "D:/Programs/DV/Recording/";
	std::string file_name;
	std::string event_file_path;

	// ----------------- Program description -----------------

	if (argc == 2) {
		file_name = argv[1];
		event_file_path = base_path + file_name;
	}
	else {
		while (true) {
			std::cout << "Enter the file name to read (must end with .raw): ";
			std::cin >> file_name;

			if (file_name.size() < 5 || file_name.substr(file_name.size() - 4) != ".raw") {
				std::cerr << "Invalid file name! It must end with '.raw'" << std::endl;
				continue;
			}

			event_file_path = base_path + file_name;

			if (!std::filesystem::exists(event_file_path)) {
				char choice;
				std::cout << "File does not exist! Re-enter (r) or cancel (c): ";
				std::cin >> choice;

				if (choice == 'r' || choice == 'R') {
					continue;  // 重新输入
				}
				else {
					return 0;  // 退出程序
				}
			}
			else {
				break;  // 文件存在
			}
		}
	}

	const std::string short_program_desc(
		"Simple viewer to stream events from an event file, using the SDK driver API\n");
	std::string long_program_desc(short_program_desc +
		"Press 'q' or Escape key to leave the program\n");
	std::cout << long_program_desc << std::endl;

	std::thread python_thread(run_python_script, python_path, read1_path);
	python_thread.join();

	// ----------------- Event file initialization -----------------

	std::cout << "Event file path: " << event_file_path << std::endl;

	dvsense::DvsFile reader = dvsense::DvsFileReader::createFileReader(event_file_path);
	reader->loadFile();

	EventAnalyzer event_analyzer;
	event_analyzer.setup_display(reader->getWidth(), reader->getHeight());

	const int fps = 25; // event-based cameras do not have a frame rate, but we need one for visualization
	const int wait_time = static_cast<int>(std::round(1.f / fps * 1000)); // how long we should wait between two frames
	cv::Mat display;                                                      // frame where events will be accumulated
	const std::string window_name = "DVSense File Viewer";
	cv::namedWindow(window_name, cv::WINDOW_GUI_EXPANDED);
	cv::resizeWindow(window_name, reader->getWidth(), reader->getHeight());

	// ----------------- Event processing and show -----------------

	dvsense::TimeStamp start_timestamp, end_timestamp;
	reader->getStartTimeStamp(start_timestamp);
	reader->getEndTimeStamp(end_timestamp);
	uint64_t max_events = 0;
	//reader->getMaxEvents(max_events);
	dvsense::TimeStamp get_time = start_timestamp;
	bool stop_application = false;

	std::cout << "Start Timestamp: " << start_timestamp << std::endl;
	std::cout << "End Timestamp: " << end_timestamp << std::endl;

	std::thread python_read2(run_python_script, python_path, read2_path);

	while (!stop_application) {
		//Control the acquisition time and display frame rate to determine the playback rate
		std::shared_ptr<dvsense::Event2DVector> events = reader->getNTimeEventsGivenStartTimeStamp(get_time, 10000);
		get_time += 40000;
		event_analyzer.process_events(events->data(), events->data() + events->size());

		if (get_time >= end_timestamp)
		{
			//replay
			get_time = start_timestamp;
			std::cout << "C.Playback finished, replaying" << std::endl;
			reader->seekTime(get_time);
		}
		event_analyzer.get_display_frame(display);
		if (!display.empty()) {
			cv::imshow(window_name, display);
		}

		// If user presses `q` key, exit loop and stop application
		int key = cv::waitKey(wait_time);
		if ((key & 0xff) == 'q' || (key & 0xff) == 27 || check_stop_signal()) {
			stop_application = true;
			std::cout << "Button triggered, exit" << std::endl;
		}
	}

	cv::destroyAllWindows();
	if (!check_stop_signal()) {
		set_stop_signal();
	}
	else {
		clearTempFolder();
	}

	python_read2.join();

	return 0;
}


int savepng1(int argc, char* argv[]) {


	//读取文件
	/*dvsense::DvsFile reader = dvsense::DvsFileReader::createFileReader("D:/Programs/DV/test.raw");
	reader->loadFile();
	dvsense::TimeStamp start_timestamp, end_timestamp;
	reader->getStartTimeStamp(start_timestamp);
	reader->getEndTimeStamp(end_timestamp);
	reader->seekTime(start_timestamp);
	std::cout << "Start Timestamp: " << start_timestamp << std::endl;
	std::cout << "End Timestamp: " << end_timestamp << std::endl;
	if (reader->seekTime(start_timestamp)) {
		std::cout << "Seek successed" << std::endl;
	}
	else {
		std::cout << "Seek failed" << std::endl;
	}

	return 0;*/

	// 处理文件路径
	std::string base_path = "D:/Programs/DV/Recording/";
	std::string file_name;
	std::string event_file_path;
	int number;
	std::string save_path = "D:/Programs/DV/Recording/dvsense/";

	std::chrono::system_clock::time_point now = std::chrono::system_clock::now();
	std::time_t now_c = std::chrono::system_clock::to_time_t(now);
	std::tm tm = *std::localtime(&now_c);

	std::stringstream date_str;
	date_str << std::put_time(&tm, "%Y%m%d"); 
	std::string date = date_str.str(); 

	// ----------------- Program description -----------------

	if (argc == 2) {
		file_name = argv[1];
		event_file_path = base_path + file_name;
	}
	else {
		while (true) {
			std::cout << "Enter the file name to read (must end with .raw): ";
			std::cin >> file_name;

			if (file_name.size() < 5 || file_name.substr(file_name.size() - 4) != ".raw") {
				std::cerr << "Invalid file name! It must end with '.raw'" << std::endl;
				continue;
			}

			event_file_path = base_path + file_name;

			if (!std::filesystem::exists(event_file_path)) {
				char choice;
				std::cout << "File does not exist! Re-enter (r) or cancel (c): ";
				std::cin >> choice;

				if (choice == 'r' || choice == 'R') {
					continue;  // 重新输入
				}
				else {
					return 0;  // 退出程序
				}
			}
			else {
				break;  // 文件存在
			}
		}
	}

	const std::string short_program_desc(
		"Simple viewer to stream events from an event file, using the SDK driver API\n");
	std::string long_program_desc(short_program_desc +
		"Press 'q' or Escape key to leave the program\n");
	std::cout << long_program_desc << std::endl;

	// ----------------- Event file initialization -----------------

	std::cout << "Event file path: " << event_file_path << std::endl;

	dvsense::DvsFile reader = dvsense::DvsFileReader::createFileReader(event_file_path);
	reader->loadFile();

	EventAnalyzer event_analyzer;
	event_analyzer.setup_display(reader->getWidth(), reader->getHeight());

	const int fps = 25; // event-based cameras do not have a frame rate, but we need one for visualization
	const int wait_time = static_cast<int>(std::round(1.f / fps * 1000)); // how long we should wait between two frames

	// ----------------- Event processing and show -----------------

	dvsense::TimeStamp start_timestamp, end_timestamp;
	reader->getStartTimeStamp(start_timestamp);
	reader->getEndTimeStamp(end_timestamp);
	dvsense::TimeStamp duration = end_timestamp - start_timestamp;
	uint64_t max_events = 0;
	//reader->getMaxEvents(max_events);
	dvsense::TimeStamp get_time = start_timestamp;
	bool stop_application = false;

	std::cout << "Start Timestamp: " << start_timestamp << std::endl;
	std::cout << "End Timestamp: " << end_timestamp << std::endl;
	std::cout << "Duration: " << duration << std::endl;
	bool firsttime = true;
	int save_count = 1;

	while (true) {
		std::cout << "Enter how many PNGs you want to save: ";
		std::cin >> number;

		if (std::cin.fail() || number <= 0) {
			std::cin.clear(); 
			std::cin.ignore(std::numeric_limits<std::streamsize>::max(), '\n');
			std::cerr << "Invalid input! Please enter a positive integer: " << std::endl;
			continue;
		}

		char confirm;
		std::cout << "You entered " << number << " PNGs. Confirm? (y/n): ";
		std::cin >> confirm;

		if (confirm == 'y' || confirm == 'Y') {
			break;  
		}
		else {
			std::cout << "Re-enter the number: " << std::endl;
		}
	}

	dvsense::TimeStamp interval = static_cast<dvsense::TimeStamp>(
		std::round(static_cast<double>(duration) / number)
		);
	interval = std::max(interval, static_cast<dvsense::TimeStamp>(1));  
	dvsense::TimeStamp next_save_time = start_timestamp;

	cv::Mat display;                                                      // frame where events will be accumulated
	const std::string window_name = "DVSense File Viewer";
	cv::namedWindow(window_name, cv::WINDOW_GUI_EXPANDED);
	cv::resizeWindow(window_name, reader->getWidth(), reader->getHeight());

	while (!stop_application) {
		//Control the acquisition time and display frame rate to determine the playback rate
		std::shared_ptr<dvsense::Event2DVector> events = reader->getNTimeEventsGivenStartTimeStamp(get_time, 10000);
		get_time += 40000;
		event_analyzer.process_events(events->data(), events->data() + events->size());

		if (get_time >= end_timestamp)
		{
			if (firsttime) {
				firsttime = false;
			}
			std::cout << "C.Playback finished" << std::endl;
			std::cout << "C.Press space to replay" << std::endl;
			int key = cv::waitKey(0);
			if ((key & 0xff) == ' ') {
				get_time = start_timestamp; 
				std::cout << "C.Playback finished, replaying" << std::endl;
				reader->seekTime(get_time);
			}
			if ((key & 0xff) == 'q' || (key & 0xff) == 27) {
				stop_application = true;
				std::cout << "Button triggered, exit" << std::endl;
				cv::destroyAllWindows();
			}

		}
		event_analyzer.get_display_frame(display);
		if (!display.empty()) {
			cv::imshow(window_name, display);
		}

		if (get_time >= next_save_time && get_time < end_timestamp && firsttime) {
			std::string img_filename = save_path + date + "_" + std::to_string(next_save_time) + "_" + std::to_string(save_count) + ".png";
			cv::imwrite(img_filename, display);
			std::cout << "Saved: " << img_filename << std::endl;
			next_save_time += interval;
			save_count++;
		}

		// If user presses `q` key, exit loop and stop application
		int key = cv::waitKey(wait_time);
		if ((key & 0xff) == 'q' || (key & 0xff) == 27) {
			stop_application = true;
			std::cout << "Button triggered, exit" << std::endl;
			cv::destroyAllWindows();
		}
		if ((key & 0xff) == ' ') {
			get_time = start_timestamp;
			std::cout << "C.Replaying" << std::endl;
			reader->seekTime(get_time);
		}
	}

	cv::destroyAllWindows();

	return 0;
}

int savepng2(int argc, char* argv[]) {


	//读取文件
	/*dvsense::DvsFile reader = dvsense::DvsFileReader::createFileReader("D:/Programs/DV/test.raw");
	reader->loadFile();
	dvsense::TimeStamp start_timestamp, end_timestamp;
	reader->getStartTimeStamp(start_timestamp);
	reader->getEndTimeStamp(end_timestamp);
	reader->seekTime(start_timestamp);
	std::cout << "Start Timestamp: " << start_timestamp << std::endl;
	std::cout << "End Timestamp: " << end_timestamp << std::endl;
	if (reader->seekTime(start_timestamp)) {
		std::cout << "Seek successed" << std::endl;
	}
	else {
		std::cout << "Seek failed" << std::endl;
	}

	return 0;*/

	// 处理文件路径
	std::string base_path = "D:/Programs/DV/Recording/";
	std::string file_name;
	std::string event_file_path;
	int number;
	std::string save_path = "D:/Programs/DV/Recording/dvsense/";

	std::chrono::system_clock::time_point now = std::chrono::system_clock::now();
	std::time_t now_c = std::chrono::system_clock::to_time_t(now);
	std::tm tm = *std::localtime(&now_c);

	std::stringstream date_str;
	date_str << std::put_time(&tm, "%Y%m%d");
	std::string date = date_str.str();

	// ----------------- Program description -----------------

	if (argc == 2) {
		file_name = argv[1];
		event_file_path = base_path + file_name;
	}
	else {
		while (true) {
			std::cout << "Enter the file name to read (must end with .raw): ";
			std::cin >> file_name;

			if (file_name.size() < 5 || file_name.substr(file_name.size() - 4) != ".raw") {
				std::cerr << "Invalid file name! It must end with '.raw'" << std::endl;
				continue;
			}

			event_file_path = base_path + file_name;

			if (!std::filesystem::exists(event_file_path)) {
				char choice;
				std::cout << "File does not exist! Re-enter (r) or cancel (c): ";
				std::cin >> choice;

				if (choice == 'r' || choice == 'R') {
					continue;  // 重新输入
				}
				else {
					return 0;  // 退出程序
				}
			}
			else {
				break;  // 文件存在
			}
		}
	}

	const std::string short_program_desc(
		"Simple viewer to stream events from an event file, using the SDK driver API\n");
	std::string long_program_desc(short_program_desc +
		"Press 'q' or Escape key to leave the program\n");
	std::cout << long_program_desc << std::endl;

	// ----------------- Event file initialization -----------------

	std::cout << "Event file path: " << event_file_path << std::endl;

	dvsense::DvsFile reader = dvsense::DvsFileReader::createFileReader(event_file_path);
	reader->loadFile();

	EventAnalyzer event_analyzer;
	event_analyzer.setup_display(reader->getWidth(), reader->getHeight());

	const int fps = 25; // event-based cameras do not have a frame rate, but we need one for visualization
	const int wait_time = static_cast<int>(std::round(1.f / fps * 1000)); // how long we should wait between two frames

	// ----------------- Event processing and show -----------------

	dvsense::TimeStamp start_timestamp, end_timestamp;
	reader->getStartTimeStamp(start_timestamp);
	reader->getEndTimeStamp(end_timestamp);
	dvsense::TimeStamp duration = end_timestamp - start_timestamp;
	uint64_t max_events = 0;
	//reader->getMaxEvents(max_events);
	dvsense::TimeStamp get_time = start_timestamp;
	bool stop_application = false;

	std::cout << "Start Timestamp: " << start_timestamp << std::endl;
	std::cout << "End Timestamp: " << end_timestamp << std::endl;
	std::cout << "Duration: " << duration << std::endl;
	bool firsttime = true;
	int save_count = 1;

	while (true) {
		std::cout << "Enter how many TIMESTAMP using for EVENT PNGs to save: ";
		std::cin >> number;

		if (std::cin.fail() || number <= 0) {
			std::cin.clear();
			std::cin.ignore(std::numeric_limits<std::streamsize>::max(), '\n');
			std::cerr << "Invalid input! Please enter a positive integer: " << std::endl;
			continue;
		}

		char confirm;
		std::cout << "You entered " << number << " TIMPSTAMPs. Confirm? (y/n): ";
		std::cin >> confirm;

		if (confirm == 'y' || confirm == 'Y') {
			break;
		}
		else {
			std::cout << "Re-enter the number: " << std::endl;
		}
	}

	dvsense::TimeStamp interval = static_cast<dvsense::TimeStamp>(number);
	interval = std::max(interval, static_cast<dvsense::TimeStamp>(1));

	//dvsense::TimeStamp interval = static_cast<dvsense::TimeStamp>(
	//	std::round(static_cast<double>(duration) / number)
	//	);
	//interval = std::max(interval, static_cast<dvsense::TimeStamp>(1));
	dvsense::TimeStamp next_save_time = start_timestamp;

	cv::Mat display;                                                      // frame where events will be accumulated
	const std::string window_name = "DVSense File Viewer";
	cv::namedWindow(window_name, cv::WINDOW_GUI_EXPANDED);
	cv::resizeWindow(window_name, reader->getWidth(), reader->getHeight());

	while (!stop_application) {
		//Control the acquisition time and display frame rate to determine the playback rate
		std::shared_ptr<dvsense::Event2DVector> events = reader->getNTimeEventsGivenStartTimeStamp(get_time, 10000);
		get_time += 40000;
		event_analyzer.process_events(events->data(), events->data() + events->size());

		if (get_time >= end_timestamp)
		{
			if (firsttime) {
				firsttime = false;
			}
			std::cout << "C.Playback finished" << std::endl;
			std::cout << "C.Press space to replay" << std::endl;
			int key = cv::waitKey(0);
			if ((key & 0xff) == ' ') {
				get_time = start_timestamp;
				std::cout << "C.Playback finished, replaying" << std::endl;
				reader->seekTime(get_time);
			}
			if ((key & 0xff) == 'q' || (key & 0xff) == 27) {
				stop_application = true;
				std::cout << "Button triggered, exit" << std::endl;
				cv::destroyAllWindows();
			}

		}
		event_analyzer.get_display_frame(display);
		if (!display.empty()) {
			cv::imshow(window_name, display);
		}

		if (get_time >= next_save_time && get_time < end_timestamp && firsttime) {
			std::string img_filename = save_path + date + "_" + std::to_string(next_save_time) + "_" + std::to_string(save_count) + ".png";
			cv::imwrite(img_filename, display);
			std::cout << "Saved: " << img_filename << std::endl;
			next_save_time += interval;
			save_count++;
		}

		// If user presses `q` key, exit loop and stop application
		int key = cv::waitKey(wait_time);
		if ((key & 0xff) == 'q' || (key & 0xff) == 27) {
			stop_application = true;
			std::cout << "Button triggered, exit" << std::endl;
			cv::destroyAllWindows();
		}
		if ((key & 0xff) == ' ') {
			get_time = start_timestamp;
			std::cout << "C.Replaying" << std::endl;
			reader->seekTime(get_time);
		}
	}

	cv::destroyAllWindows();

	return 0;
}


int main(int argc, char* argv[]) {

	std::string python_path = "/usr/bin/python3";
	std::string savepng1_path = "D:/Programs/DV/savepng1.py";
	std::string savepng2_path = "D:/Programs/DV/savepng2.py";

	int choice;
	std::cout << "Select an option:\n";
	std::cout << "1 - Open camera and record events\n";
	std::cout << "2 - Read from a recorded file\n";
	std::cout << "3 - Save timestamp into PNG\n";
	std::cout << "Enter your choice: ";
	std::cin >> choice;

	if (choice == 1) {
		recordFromCamera(argc, argv);
	}
	else if (choice == 2) {
		readFromFile(argc, argv);
		//std::thread python_thread(run_python_script, python_path, read2_path);
		//python_thread.join();
	}
	else if (choice == 3) {
		int choice;
		std::cout << "Select an option:\n";
		std::cout << "1 - Saving for DVSENSE\n";
		std::cout << "2 - Saving for DAVIS\n";
		std::cout << "Enter your choice: ";
		std::cin >> choice;
		if (choice == 1) {
			int choice;
			std::cout << "Select an option:\n";
			std::cout << "1 - Set TIMESTAMP for saving\n";
			std::cout << "2 - Set PHOTO NUMBER for saving\n";
			std::cout << "Enter your choice: ";
			std::cin >> choice;
			if (choice == 1) {
				savepng2(argc, argv);
			}
			else if (choice == 2) {
				savepng1(argc, argv);
			}
		}
		else if (choice == 2) {
			int choice;
			std::cout << "Select an option:\n";
			std::cout << "1 - Set TIMESTAMP for saving\n";
			std::cout << "2 - Set PHOTO NUMBER for saving\n";
			std::cout << "Enter your choice: ";
			std::cin >> choice;
			if (choice == 1) {
				std::thread python_savepng2(run_python_script, python_path, savepng2_path);
				python_savepng2.join();
			}
			else if (choice == 2) {
				std::thread python_savepng1(run_python_script, python_path, savepng1_path);
				python_savepng1.join();
			}
		}
	}
	else {
		std::cerr << "Invalid choice! Exiting program" << std::endl;
	}
	return 0;

}




