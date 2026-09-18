#pragma once

#include <string>
#include <vector>
#include <memory>

#ifdef HAVE_SHERPA_ONNX
#include "sherpa-onnx/c-api/cxx-api.h"
#endif

namespace vaanisetu {

struct STTConfig {
    std::string encoder;
    std::string decoder;
    std::string joiner;
    std::string tokens;
    std::string vad_model;

    int32_t sample_rate = 16000;
    int32_t num_threads = 2;
    std::string decoding_method = "greedy_search";
    int32_t max_active_paths = 4;

    bool vad_enabled = true;
    float vad_threshold = 0.5f;
    float vad_min_silence_duration = 0.5f;
    float vad_min_speech_duration = 0.25f;
};

class STTEngine {
public:
    STTEngine();
    ~STTEngine();

    bool Init(const STTConfig &config);
    std::string Transcribe(const float *samples, int32_t num_samples);
    std::string TranscribeFile(const std::string &wav_path, bool use_vad = false);

#ifdef HAVE_SHERPA_ONNX
    bool IsInitialized() const { return recognizer_ != nullptr && recognizer_->Get() != nullptr; }
#else
    bool IsInitialized() const { return initialized_; }
#endif

private:
    STTConfig config_;
#ifdef HAVE_SHERPA_ONNX
    std::unique_ptr<sherpa_onnx::cxx::OfflineRecognizer> recognizer_;
    std::unique_ptr<sherpa_onnx::cxx::VoiceActivityDetector> vad_;
#else
    bool initialized_ = false;
#endif

    std::string TranscribeInternal(const float *samples, int32_t num_samples);
};

} // namespace vaanisetu

