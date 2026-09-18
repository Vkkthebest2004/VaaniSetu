#include "vaanisetu/tts_engine.hpp"
#include <iostream>
#include <chrono>
#include <filesystem>

namespace fs = std::filesystem;

int main(int argc, char **argv) {
    std::string text = (argc >= 2) ? argv[1] : "Hello from native C++ VaaniSetu";
    std::string output_wav = (argc >= 3) ? argv[2] : "output_native.wav";
    std::string model_dir = "models/tts/vits-piper-en_US-lessac-low";

    // Check fallback relative paths
    if (!fs::exists(model_dir)) {
        if (fs::exists("../../" + model_dir)) {
            model_dir = "../../" + model_dir;
        } else if (fs::exists("../" + model_dir)) {
            model_dir = "../" + model_dir;
        }
    }

    vaanisetu::TTSConfig config;
    config.model = model_dir + "/en_US-lessac-low.onnx";
    config.tokens = model_dir + "/tokens.txt";
    config.data_dir = model_dir + "/espeak-ng-data";
    config.num_threads = 2;

    std::cout << "==================================================" << std::endl;
    std::cout << "  VaaniSetu Native C++ TTS Engine" << std::endl;
    std::cout << "==================================================" << std::endl;
    std::cout << "Text: \"" << text << "\"" << std::endl;
    std::cout << "Output: " << output_wav << std::endl;

    vaanisetu::TTSEngine engine;
    auto t0 = std::chrono::high_resolution_clock::now();
    if (!engine.Init(config)) {
        std::cerr << "Failed to initialize TTSEngine." << std::endl;
        return 1;
    }
    auto t1 = std::chrono::high_resolution_clock::now();
    double load_ms = std::chrono::duration<double, std::milli>(t1 - t0).count();
    std::cout << "Engine initialized in " << load_ms << " ms" << std::endl;

    auto start_time = std::chrono::high_resolution_clock::now();
    float duration = engine.SynthesizeToFile(text, output_wav, 1.0f);
    auto end_time = std::chrono::high_resolution_clock::now();

    double elapsed_ms = std::chrono::duration<double, std::milli>(end_time - start_time).count();
    double rtf = (duration > 0.0f) ? (elapsed_ms / 1000.0) / duration : 0.0;

    std::cout << "\n--------------------------------------------------" << std::endl;
    std::cout << "Generated " << duration << "s audio to " << output_wav << std::endl;
    std::cout << "Time elapsed: " << elapsed_ms << " ms (RTF = " << rtf << ")" << std::endl;
    std::cout << "==================================================" << std::endl;

    return 0;
}
