# iTantra Offline Model Training & Quantization Pipelines

This directory houses the offline model fine-tuning and quantization routines for Indic ASR, acoustic adapters, language identification, and speech synthesis.

## Quick Start
To train or fine-tune the 10-language Indic neural adapter and quantize it to INT8 for low-end ARM devices:

```bash
# Run the training and quantization pipeline
python scripts/train_indic_model.py
```

## Acceleration Support
- **Apple Silicon GPU**: Automatically detected via Metal Performance Shaders (`mps`).
- **NVIDIA CUDA**: Automatically detected when CUDA-enabled GPU is present.
- **Multi-Core CPU**: Fallback SIMD/AVX vector acceleration.

## Output Target
All trained weights and INT8 quantized ONNX models are written to:
- `models/indic_adapter/`
- `models/stt/`
- `models/tts/`
