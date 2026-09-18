cmake_minimum_required(VERSION 3.18)
project(vaanisetu_core LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Optimization flags for performance
if(NOT MSVC)
    set(CMAKE_CXX_FLAGS_RELEASE "-O3 -DNDEBUG")
endif()

# Locate sherpa-onnx installation
if(NOT ANDROID)
    # 1. Project virtual environment (default for local builds)
    set(SHERPA_ONNX_VENV_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../.venv/lib/python3.12/site-packages/sherpa_onnx")

    if(EXISTS "${SHERPA_ONNX_VENV_DIR}/include/sherpa-onnx/c-api/cxx-api.h")
        set(SHERPA_ONNX_INCLUDE_DIR "${SHERPA_ONNX_VENV_DIR}/include")
        set(SHERPA_ONNX_LIB_DIR "${SHERPA_ONNX_VENV_DIR}/lib")
        message(STATUS "Found sherpa-onnx in .venv: ${SHERPA_ONNX_VENV_DIR}")
        add_compile_definitions(HAVE_SHERPA_ONNX=1)
        set(HAVE_SHERPA_ONNX TRUE)
    elseif(DEFINED ENV{SHERPA_ONNX_DIR})
        set(SHERPA_ONNX_INCLUDE_DIR "$ENV{SHERPA_ONNX_DIR}/include")
        set(SHERPA_ONNX_LIB_DIR "$ENV{SHERPA_ONNX_DIR}/lib")
        message(STATUS "Found sherpa-onnx from ENV: $ENV{SHERPA_ONNX_DIR}")
        add_compile_definitions(HAVE_SHERPA_ONNX=1)
        set(HAVE_SHERPA_ONNX TRUE)
    endif()
    link_directories(${SHERPA_ONNX_LIB_DIR})
else()
    # Check if prebuilt Android sherpa-onnx libraries are available
    set(SHERPA_ANDROID_LIB_DIR "${CMAKE_CURRENT_SOURCE_DIR}/android_libs/${ANDROID_ABI}")
    if(EXISTS "${SHERPA_ANDROID_LIB_DIR}/libsherpa-onnx-cxx-api.so")
        set(SHERPA_ONNX_INCLUDE_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../.venv/lib/python3.12/site-packages/sherpa_onnx/include")
        link_directories(${SHERPA_ANDROID_LIB_DIR})
        add_compile_definitions(HAVE_SHERPA_ONNX=1)
        set(HAVE_SHERPA_ONNX TRUE)
        message(STATUS "Found Android prebuilt sherpa-onnx at: ${SHERPA_ANDROID_LIB_DIR}")
    else()
        message(STATUS "Sherpa-ONNX Android prebuilts not found for ${ANDROID_ABI}, compiling native stub bridge")
    endif()
endif()

include_directories(
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${SHERPA_ONNX_INCLUDE_DIR}
)

# Core C++ library
add_library(vaanisetu_core STATIC
    src/stt_engine.cpp
    src/tts_engine.cpp
)

target_include_directories(vaanisetu_core PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${SHERPA_ONNX_INCLUDE_DIR}
)

# Core CLI executables (desktop only)
if(NOT ANDROID)
    add_executable(vaanisetu_stt_cli src/main_stt.cpp)
    target_link_libraries(vaanisetu_stt_cli PRIVATE
        vaanisetu_core
        sherpa-onnx-cxx-api
        sherpa-onnx-c-api
    )

    add_executable(vaanisetu_tts_cli src/main_tts.cpp)
    target_link_libraries(vaanisetu_tts_cli PRIVATE
        vaanisetu_core
        sherpa-onnx-cxx-api
        sherpa-onnx-c-api
    )

    # Set rpath so CLI executables find dylibs automatically on macOS
    if(APPLE)
        set_target_properties(vaanisetu_stt_cli PROPERTIES
            BUILD_RPATH "${SHERPA_ONNX_LIB_DIR}"
            INSTALL_RPATH "${SHERPA_ONNX_LIB_DIR}"
        )
        set_target_properties(vaanisetu_tts_cli PROPERTIES
            BUILD_RPATH "${SHERPA_ONNX_LIB_DIR}"
            INSTALL_RPATH "${SHERPA_ONNX_LIB_DIR}"
        )
    endif()
endif()

# JNI Shared Library
find_package(JNI QUIET)

if(NOT JNI_FOUND)
    # Check default macOS Java paths
    set(JAVA_CANDIDATE_PATHS
        "/Library/Java/JavaVirtualMachines/temurin-24.jdk/Contents/Home"
        "/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home"
        "/opt/homebrew/opt/openjdk@17"
        "$ENV{JAVA_HOME}"
    )
    foreach(JPATH ${JAVA_CANDIDATE_PATHS})
        if(EXISTS "${JPATH}/include/jni.h")
            set(JNI_FOUND TRUE)
            set(JNI_INCLUDE_DIRS "${JPATH}/include" "${JPATH}/include/darwin")
            message(STATUS "Found JNI headers at: ${JPATH}/include")
            break()
        endif()
    endforeach()
endif()

if(JNI_FOUND OR ANDROID)
    add_library(vaanisetu_jni SHARED
        jni/vaanisetu_jni.cpp
    )

    target_include_directories(vaanisetu_jni PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/include
        ${SHERPA_ONNX_INCLUDE_DIR}
        ${JNI_INCLUDE_DIRS}
    )

    if(HAVE_SHERPA_ONNX)
        target_link_libraries(vaanisetu_jni PRIVATE
            vaanisetu_core
            sherpa-onnx-cxx-api
            sherpa-onnx-c-api
        )
    else()
        target_link_libraries(vaanisetu_jni PRIVATE
            vaanisetu_core
        )
    endif()

    if(APPLE)
        set_target_properties(vaanisetu_jni PROPERTIES
            BUILD_RPATH "${SHERPA_ONNX_LIB_DIR}"
            INSTALL_RPATH "${SHERPA_ONNX_LIB_DIR}"
        )
    endif()
    message(STATUS "Configured JNI library: vaanisetu_jni")
endif()

