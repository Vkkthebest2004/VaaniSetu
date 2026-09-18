#include "vaanisetu/stt_engine.hpp"
#include <iostream>
#include <chrono>
#include <filesystem>

namespace fs = std::filesystem;

int main(int argc, char **argv) {
    if (argc < 2) {
        std::cout << "Usage: " << argv[0] << " <audio.wav> [models_dir]" << std::endl;
        return 1;
    }

    std::string wav_path = argv[1];
    std::string model_dir = (argc >= 3) ? argv[2] : "models/stt/sherpa-onnx-zipformer-small-en-2023-06-26";
    std::string vad_model = "models/vad/silero_vad.onnx";

    // Check fallback relative paths
    if (!fs::exists(model_dir)) {
        if (fs::exists("../../" + model_dir)) {
            model_dir = "../../" + model_dir;
            vad_model = "../../" + vad_model;
        } else if (fs::exists("../" + model_dir)) {
            model_dir = "../" + model_dir;
            vad_model = "../" + vad_model;
        }
    }

    vaanisetu::STTConfig config;
    config.encoder = model_dir + "/encoder-epoch-99-avg-1.int8.onnx";
    config.decoder = model_dir + "/decoder-epoch-99-avg-1.onnx";
    config.joiner = model_dir + "/joiner-epoch-99-avg-1.int8.onnx";
    config.tokens = model_dir + "/tokens.txt";
    config.vad_model = fs::exists(vad_model) ? vad_model : "";
    config.vad_enabled = !config.vad_model.empty();
    config.num_threads = 2;

    std::cout << "==================================================" << std::endl;
    std::cout << "  VaaniSetu Native C++ STT Engine" << std::endl;
    std::cout << "==================================================" << std::endl;
    std::cout << "Model: " << model_dir << std::endl;
    std::cout << "Input: " << wav_path << std::endl;

    vaanisetu::STTEngine engine;
    auto t0 = std::chrono::high_resolution_clock::now();
    if (!engine.Init(config)) {
        std::cerr << "Failed to initialize STTEngine." << std::endl;
        return 1;
    }
    auto t1 = std::chrono::high_resolution_clock::now();
    double load_ms = std::chrono::duration<double, std::milli>(t1 - t0).count();
    std::cout << "Engine initialized in " << load_ms << " ms" << std::endl;

    auto start_time = std::chrono::high_resolution_clock::now();
    std::string result = engine.TranscribeFile(wav_path, false);
    auto end_time = std::chrono::high_resolution_clock::now();

    double elapsed_ms = std::chrono::duration<double, std::milli>(end_time - start_time).count();
    std::cout << "\n--------------------------------------------------" << std::endl;
    std::cout << "Transcription:" << std::endl;
    std::cout << result << std::endl;
    std::cout << "--------------------------------------------------" << std::endl;
    std::cout << "Time elapsed: " << elapsed_ms << " ms" << std::endl;
    std::cout << "==================================================" << std::endl;

    return 0;
}
