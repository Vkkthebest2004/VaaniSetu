#include "vaanisetu/tts_engine.hpp"
#include "vaanisetu/wav_io.hpp"
#include <iostream>

namespace vaanisetu {

TTSEngine::TTSEngine() = default;
TTSEngine::~TTSEngine() = default;

#ifdef HAVE_SHERPA_ONNX

bool TTSEngine::Init(const TTSConfig &config) {
    config_ = config;

    sherpa_onnx::cxx::OfflineTtsConfig tts_config;
    tts_config.model.vits.model = config.model;
    tts_config.model.vits.tokens = config.tokens;
    tts_config.model.vits.data_dir = config.data_dir;
    tts_config.model.vits.length_scale = config.length_scale;
    tts_config.model.num_threads = config.num_threads;
    tts_config.model.debug = false;
    tts_config.max_num_sentences = config.max_num_sentences;

    auto tts = sherpa_onnx::cxx::OfflineTts::Create(tts_config);
    if (!tts.Get()) {
        std::cerr << "Failed to create Sherpa-ONNX OfflineTts." << std::endl;
        return false;
    }

    sample_rate_ = tts.SampleRate();
    tts_ = std::make_unique<sherpa_onnx::cxx::OfflineTts>(std::move(tts));
    return true;
}

std::vector<float> TTSEngine::Synthesize(const std::string &text, float speed, int32_t speaker_id) {
    if (!IsInitialized() || text.empty()) {
        return {};
    }

    float spd = (speed > 0.0f) ? speed : config_.speed;
    int32_t sid = (speaker_id >= 0) ? speaker_id : config_.speaker_id;

    auto audio = tts_->Generate(text, sid, spd);
    return audio.samples;
}

float TTSEngine::SynthesizeToFile(const std::string &text, const std::string &output_wav, float speed, int32_t speaker_id) {
    auto samples = Synthesize(text, speed, speaker_id);
    if (samples.empty()) {
        return 0.0f;
    }

    WavIO::WriteWav(output_wav, samples, sample_rate_);
    return static_cast<float>(samples.size()) / static_cast<float>(sample_rate_);
}

#else

bool TTSEngine::Init(const TTSConfig &config) {
    config_ = config;
    initialized_ = true;
    return true;
}

std::vector<float> TTSEngine::Synthesize(const std::string &text, float speed, int32_t speaker_id) {
    return {};
}

float TTSEngine::SynthesizeToFile(const std::string &text, const std::string &output_wav, float speed, int32_t speaker_id) {
    return 0.0f;
}

#endif

} // namespace vaanisetu

