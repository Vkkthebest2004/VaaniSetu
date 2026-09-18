#include "vaanisetu/stt_engine.hpp"
#include "vaanisetu/wav_io.hpp"
#include <iostream>
#include <sstream>

namespace vaanisetu {

STTEngine::STTEngine() = default;
STTEngine::~STTEngine() = default;

#ifdef HAVE_SHERPA_ONNX

bool STTEngine::Init(const STTConfig &config) {
    config_ = config;

    sherpa_onnx::cxx::OfflineRecognizerConfig r_config;
    r_config.model_config.transducer.encoder = config.encoder;
    r_config.model_config.transducer.decoder = config.decoder;
    r_config.model_config.transducer.joiner = config.joiner;
    r_config.model_config.tokens = config.tokens;
    r_config.model_config.num_threads = config.num_threads;
    r_config.model_config.debug = false;
    r_config.decoding_method = config.decoding_method;
    r_config.max_active_paths = config.max_active_paths;

    auto recognizer = sherpa_onnx::cxx::OfflineRecognizer::Create(r_config);
    if (!recognizer.Get()) {
        std::cerr << "Failed to create Sherpa-ONNX OfflineRecognizer." << std::endl;
        return false;
    }

    recognizer_ = std::make_unique<sherpa_onnx::cxx::OfflineRecognizer>(std::move(recognizer));

    // Optional VAD initialization
    if (config.vad_enabled && !config.vad_model.empty()) {
        sherpa_onnx::cxx::VadModelConfig vad_config;
        vad_config.silero_vad.model = config.vad_model;
        vad_config.silero_vad.threshold = config.vad_threshold;
        vad_config.silero_vad.min_silence_duration = config.vad_min_silence_duration;
        vad_config.silero_vad.min_speech_duration = config.vad_min_speech_duration;
        vad_config.silero_vad.window_size = 512;
        vad_config.sample_rate = config.sample_rate;
        vad_config.num_threads = 1;

        auto vad = sherpa_onnx::cxx::VoiceActivityDetector::Create(vad_config, 60.0f);
        if (vad.Get()) {
            vad_ = std::make_unique<sherpa_onnx::cxx::VoiceActivityDetector>(std::move(vad));
        } else {
            std::cerr << "Warning: Failed to create VAD. Continuing without VAD." << std::endl;
        }
    }

    return true;
}

std::string STTEngine::TranscribeInternal(const float *samples, int32_t num_samples) {
    if (!recognizer_ || !recognizer_->Get() || num_samples <= 0) {
        return "";
    }

    auto stream = recognizer_->CreateStream();
    stream.AcceptWaveform(config_.sample_rate, samples, num_samples);
    recognizer_->Decode(&stream);
    auto result = recognizer_->GetResult(&stream);
    return result.text;
}

std::string STTEngine::Transcribe(const float *samples, int32_t num_samples) {
    return TranscribeInternal(samples, num_samples);
}

std::string STTEngine::TranscribeFile(const std::string &wav_path, bool use_vad) {
    if (!IsInitialized()) {
        throw std::runtime_error("STTEngine is not initialized");
    }

    auto wav = WavIO::ReadWav(wav_path);
    if (wav.samples.empty()) {
        return "";
    }

    if (use_vad && vad_ && vad_->Get()) {
        vad_->Reset();
        const int32_t window_size = 512;
        const int32_t total = static_cast<int32_t>(wav.samples.size());

        for (int32_t i = 0; i < total; i += window_size) {
            int32_t chunk_len = std::min(window_size, total - i);
            std::vector<float> chunk(window_size, 0.0f);
            for (int32_t j = 0; j < chunk_len; ++j) {
                chunk[j] = wav.samples[i + j];
            }
            vad_->AcceptWaveform(chunk.data(), window_size);
        }
        vad_->Flush();

        std::ostringstream oss;
        bool first = true;
        while (!vad_->IsEmpty()) {
            auto seg = vad_->Front();
            if (!seg.samples.empty()) {
                std::string text = TranscribeInternal(seg.samples.data(), static_cast<int32_t>(seg.samples.size()));
                if (!text.empty()) {
                    if (!first) oss << " ";
                    oss << text;
                    first = false;
                }
            }
            vad_->Pop();
        }
        return oss.str();
    }

    return TranscribeInternal(wav.samples.data(), static_cast<int32_t>(wav.samples.size()));
}

#else

bool STTEngine::Init(const STTConfig &config) {
    config_ = config;
    initialized_ = true;
    return true;
}

std::string STTEngine::TranscribeInternal(const float *samples, int32_t num_samples) {
    return "";
}

std::string STTEngine::Transcribe(const float *samples, int32_t num_samples) {
    return "";
}

std::string STTEngine::TranscribeFile(const std::string &wav_path, bool use_vad) {
    return "";
}

#endif

} // namespace vaanisetu

