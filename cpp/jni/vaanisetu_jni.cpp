#include <jni.h>
#include <string>
#include <vector>
#include <memory>
#include "vaanisetu/stt_engine.hpp"
#include "vaanisetu/tts_engine.hpp"

static std::string JStringToStdString(JNIEnv *env, jstring jstr) {
    if (!jstr) return "";
    const char *chars = env->GetStringUTFChars(jstr, nullptr);
    std::string str(chars);
    env->ReleaseStringUTFChars(jstr, chars);
    return str;
}

extern "C" {

// ============================================================================
// STT JNI Methods (com.vaanisetu.core.NativeSTT)
// ============================================================================

JNIEXPORT jlong JNICALL
Java_com_vaanisetu_core_NativeSTT_nativeInit(
    JNIEnv *env,
    jobject /* thiz */,
    jstring encoder,
    jstring decoder,
    jstring joiner,
    jstring tokens,
    jstring vadModel,
    jint threads
) {
    vaanisetu::STTConfig config;
    config.encoder = JStringToStdString(env, encoder);
    config.decoder = JStringToStdString(env, decoder);
    config.joiner = JStringToStdString(env, joiner);
    config.tokens = JStringToStdString(env, tokens);
    config.vad_model = JStringToStdString(env, vadModel);
    config.vad_enabled = !config.vad_model.empty();
    config.num_threads = (threads > 0) ? threads : 2;

    auto *engine = new vaanisetu::STTEngine();
    if (!engine->Init(config)) {
        delete engine;
        return 0;
    }
    return reinterpret_cast<jlong>(engine);
}

JNIEXPORT jstring JNICALL
Java_com_vaanisetu_core_NativeSTT_nativeTranscribe(
    JNIEnv *env,
    jobject /* thiz */,
    jlong handle,
    jfloatArray samples
) {
    auto *engine = reinterpret_cast<vaanisetu::STTEngine *>(handle);
    if (!engine || !samples) {
        return env->NewStringUTF("");
    }

    jsize len = env->GetArrayLength(samples);
    jfloat *ptr = env->GetFloatArrayElements(samples, nullptr);
    std::string text = engine->Transcribe(ptr, len);
    env->ReleaseFloatArrayElements(samples, ptr, JNI_ABORT);

    return env->NewStringUTF(text.c_str());
}

JNIEXPORT jstring JNICALL
Java_com_vaanisetu_core_NativeSTT_nativeTranscribeFile(
    JNIEnv *env,
    jobject /* thiz */,
    jlong handle,
    jstring wavPath,
    jboolean useVad
) {
    auto *engine = reinterpret_cast<vaanisetu::STTEngine *>(handle);
    if (!engine || !wavPath) {
        return env->NewStringUTF("");
    }

    std::string path = JStringToStdString(env, wavPath);
    std::string text = engine->TranscribeFile(path, useVad);
    return env->NewStringUTF(text.c_str());
}

JNIEXPORT void JNICALL
Java_com_vaanisetu_core_NativeSTT_nativeRelease(
    JNIEnv * /* env */,
    jobject /* thiz */,
    jlong handle
) {
    auto *engine = reinterpret_cast<vaanisetu::STTEngine *>(handle);
    delete engine;
}

// ============================================================================
// TTS JNI Methods (com.vaanisetu.core.NativeTTS)
// ============================================================================

JNIEXPORT jlong JNICALL
Java_com_vaanisetu_core_NativeTTS_nativeInit(
    JNIEnv *env,
    jobject /* thiz */,
    jstring model,
    jstring tokens,
    jstring dataDir,
    jint threads
) {
    vaanisetu::TTSConfig config;
    config.model = JStringToStdString(env, model);
    config.tokens = JStringToStdString(env, tokens);
    config.data_dir = JStringToStdString(env, dataDir);
    config.num_threads = (threads > 0) ? threads : 2;

    auto *engine = new vaanisetu::TTSEngine();
    if (!engine->Init(config)) {
        delete engine;
        return 0;
    }
    return reinterpret_cast<jlong>(engine);
}

JNIEXPORT jfloatArray JNICALL
Java_com_vaanisetu_core_NativeTTS_nativeSynthesize(
    JNIEnv *env,
    jobject /* thiz */,
    jlong handle,
    jstring text,
    jfloat speed
) {
    auto *engine = reinterpret_cast<vaanisetu::TTSEngine *>(handle);
    if (!engine || !text) {
        return env->NewFloatArray(0);
    }

    std::string txt = JStringToStdString(env, text);
    auto samples = engine->Synthesize(txt, speed);

    jfloatArray result = env->NewFloatArray(static_cast<jsize>(samples.size()));
    if (result && !samples.empty()) {
        env->SetFloatArrayRegion(result, 0, static_cast<jsize>(samples.size()), samples.data());
    }
    return result;
}

JNIEXPORT jfloat JNICALL
Java_com_vaanisetu_core_NativeTTS_nativeSynthesizeToFile(
    JNIEnv *env,
    jobject /* thiz */,
    jlong handle,
    jstring text,
    jstring outputPath,
    jfloat speed
) {
    auto *engine = reinterpret_cast<vaanisetu::TTSEngine *>(handle);
    if (!engine || !text || !outputPath) {
        return 0.0f;
    }

    std::string txt = JStringToStdString(env, text);
    std::string path = JStringToStdString(env, outputPath);
    return engine->SynthesizeToFile(txt, path, speed);
}

JNIEXPORT jint JNICALL
Java_com_vaanisetu_core_NativeTTS_nativeGetSampleRate(
    JNIEnv * /* env */,
    jobject /* thiz */,
    jlong handle
) {
    auto *engine = reinterpret_cast<vaanisetu::TTSEngine *>(handle);
    return engine ? engine->GetSampleRate() : 16000;
}

JNIEXPORT void JNICALL
Java_com_vaanisetu_core_NativeTTS_nativeRelease(
    JNIEnv * /* env */,
    jobject /* thiz */,
    jlong handle
) {
    auto *engine = reinterpret_cast<vaanisetu::TTSEngine *>(handle);
    delete engine;
}

} // extern "C"
