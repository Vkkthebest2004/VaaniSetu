#pragma once

#include <string>
#include <vector>
#include <memory>

#ifdef HAVE_SHERPA_ONNX
#include "sherpa-onnx/c-api/cxx-api.h"
#endif

namespace vaanisetu {

struct TTSConfig {
    std::string model;
    std::string tokens;
    std::string data_dir;

    int32_t sample_rate = 16000;
    int32_t num_threads = 2;
    int32_t max_num_sentences = 2;
    float length_scale = 1.0f;
    float speed = 1.0f;
    int32_t speaker_id = 0;
};

class TTSEngine {
public:
    TTSEngine();
    ~TTSEngine();

    bool Init(const TTSConfig &config);
    std::vector<float> Synthesize(const std::string &text, float speed = 1.0f, int32_t speaker_id = 0);
    float SynthesizeToFile(const std::string &text, const std::string &output_wav, float speed = 1.0f, int32_t speaker_id = 0);

    int32_t GetSampleRate() const { return sample_rate_; }
#ifdef HAVE_SHERPA_ONNX
    bool IsInitialized() const { return tts_ != nullptr && tts_->Get() != nullptr; }
#else
    bool IsInitialized() const { return initialized_; }
#endif

private:
    TTSConfig config_;
    int32_t sample_rate_ = 16000;
#ifdef HAVE_SHERPA_ONNX
    std::unique_ptr<sherpa_onnx::cxx::OfflineTts> tts_;
#else
    bool initialized_ = false;
#endif
};

} // namespace vaanisetu

