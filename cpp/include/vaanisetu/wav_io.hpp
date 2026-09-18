#pragma once

#include <cstdint>
#include <fstream>
#include <iostream>
#include <string>
#include <vector>
#include <stdexcept>
#include <algorithm>

namespace vaanisetu {

struct WavData {
    int32_t sample_rate = 16000;
    int32_t channels = 1;
    std::vector<float> samples; // Normalized [-1.0, 1.0]
};

class WavIO {
public:
    static WavData ReadWav(const std::string &path) {
        std::ifstream file(path, std::ios::binary);
        if (!file.is_open()) {
            throw std::runtime_error("Cannot open WAV file: " + path);
        }

        char riff[4];
        file.read(riff, 4);
        if (std::string(riff, 4) != "RIFF") {
            throw std::runtime_error("Invalid WAV: missing RIFF header");
        }

        uint32_t file_size;
        file.read(reinterpret_cast<char *>(&file_size), 4);

        char wave[4];
        file.read(wave, 4);
        if (std::string(wave, 4) != "WAVE") {
            throw std::runtime_error("Invalid WAV: missing WAVE format");
        }

        WavData data;
        bool found_data = false;

        while (file.good() && !found_data) {
            char chunk_id[4];
            file.read(chunk_id, 4);
            uint32_t chunk_size = 0;
            file.read(reinterpret_cast<char *>(&chunk_size), 4);

            std::string id(chunk_id, 4);
            if (id == "fmt ") {
                uint16_t audio_format = 0;
                uint16_t num_channels = 0;
                uint32_t sample_rate = 0;
                uint32_t byte_rate = 0;
                uint16_t block_align = 0;
                uint16_t bits_per_sample = 0;

                file.read(reinterpret_cast<char *>(&audio_format), 2);
                file.read(reinterpret_cast<char *>(&num_channels), 2);
                file.read(reinterpret_cast<char *>(&sample_rate), 4);
                file.read(reinterpret_cast<char *>(&byte_rate), 4);
                file.read(reinterpret_cast<char *>(&block_align), 2);
                file.read(reinterpret_cast<char *>(&bits_per_sample), 2);

                data.sample_rate = sample_rate;
                data.channels = num_channels;

                // Skip any extra format bytes
                if (chunk_size > 16) {
                    file.seekg(chunk_size - 16, std::ios::cur);
                }
            } else if (id == "data") {
                found_data = true;
                size_t num_samples = chunk_size / sizeof(int16_t);
                std::vector<int16_t> pcm(num_samples);
                file.read(reinterpret_cast<char *>(pcm.data()), chunk_size);

                data.samples.resize(num_samples);
                for (size_t i = 0; i < num_samples; ++i) {
                    data.samples[i] = static_cast<float>(pcm[i]) / 32768.0f;
                }
            } else {
                file.seekg(chunk_size, std::ios::cur);
            }
        }

        return data;
    }

    static void WriteWav(const std::string &path, const std::vector<float> &samples, int32_t sample_rate = 16000) {
        std::ofstream file(path, std::ios::binary);
        if (!file.is_open()) {
            throw std::runtime_error("Cannot open file for writing WAV: " + path);
        }

        uint16_t num_channels = 1;
        uint16_t bits_per_sample = 16;
        uint32_t byte_rate = sample_rate * num_channels * (bits_per_sample / 8);
        uint16_t block_align = num_channels * (bits_per_sample / 8);
        uint32_t data_size = static_cast<uint32_t>(samples.size() * sizeof(int16_t));
        uint32_t riff_size = 36 + data_size;

        // RIFF chunk
        file.write("RIFF", 4);
        file.write(reinterpret_cast<const char *>(&riff_size), 4);
        file.write("WAVE", 4);

        // fmt chunk
        file.write("fmt ", 4);
        uint32_t fmt_size = 16;
        uint16_t audio_format = 1; // PCM
        file.write(reinterpret_cast<const char *>(&fmt_size), 4);
        file.write(reinterpret_cast<const char *>(&audio_format), 2);
        file.write(reinterpret_cast<const char *>(&num_channels), 2);
        file.write(reinterpret_cast<const char *>(&sample_rate), 4);
        file.write(reinterpret_cast<const char *>(&byte_rate), 4);
        file.write(reinterpret_cast<const char *>(&block_align), 2);
        file.write(reinterpret_cast<const char *>(&bits_per_sample), 2);

        // data chunk
        file.write("data", 4);
        file.write(reinterpret_cast<const char *>(&data_size), 4);

        std::vector<int16_t> pcm(samples.size());
        for (size_t i = 0; i < samples.size(); ++i) {
            float s = std::clamp(samples[i], -1.0f, 1.0f);
            pcm[i] = static_cast<int16_t>(s * 32767.0f);
        }
        file.write(reinterpret_cast<const char *>(pcm.data()), data_size);
    }
};

} // namespace vaanisetu
