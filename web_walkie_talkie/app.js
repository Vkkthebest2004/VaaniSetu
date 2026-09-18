// iTantra Neural Transceiver Walkie-Talkie Controller
// Supports Direct Mac Hardware Microphone (zero browser latency) & Web Audio API

document.addEventListener("DOMContentLoaded", () => {
  const pttBtn = document.getElementById("ptt-button");
  const channelSelect = document.getElementById("channel-select");
  const languageSelect = document.getElementById("language-select");
  const audioSourceSelect = document.getElementById("audio-source-select");
  const emergencyToggle = document.getElementById("emergency-toggle");
  const txScreenText = document.getElementById("tx-screen-text");
  const rxScreenText = document.getElementById("rx-screen-text");
  const txStatusIndicator = document.getElementById("tx-status-indicator");
  const rxStatusIndicator = document.getElementById("rx-status-indicator");
  const speakerWaves = document.getElementById("speaker-waves");
  const speakerStatusLabel = document.getElementById("speaker-status-label");
  const audioPlayback = document.getElementById("audio-playback");
  const replayBtn = document.getElementById("replay-btn");
  const customTextInput = document.getElementById("custom-text-input");
  const sendTextBtn = document.getElementById("send-text-btn");
  const feedLog = document.getElementById("feed-log");

  // Mic level meter elements
  const micLevelBar = document.getElementById("mic-level-bar");
  const micLevelVal = document.getElementById("mic-level-val");

  // Telemetry elements
  const telemetrySaving = document.getElementById("telemetry-saving");
  const telemetryPktSize = document.getElementById("telemetry-pkt-size");
  const telemetryRawSize = document.getElementById("telemetry-raw-size");
  const telemetrySttLat = document.getElementById("telemetry-stt-lat");
  const telemetryAirLat = document.getElementById("telemetry-air-lat");
  const telemetryTtsLat = document.getElementById("telemetry-tts-lat");
  const telemetryTotalLat = document.getElementById("telemetry-total-lat");
  const telemetryHex = document.getElementById("telemetry-hex");

  // Waveform canvas
  const canvas = document.getElementById("tx-waveform");
  const canvasCtx = canvas.getContext("2d");

  // Audio recording state
  let audioContext = null;
  let micStream = null;
  let scriptProcessor = null;
  let analyser = null;
  let isRecordingPtt = false;
  let pttAudioBuffers = [];
  let animId = null;
  let lastAudioB64 = null;
  let micInitialized = false;
  let hwPollInterval = null;
  let hwCurrentPeak = 0.0;
  let wavePhase = 0;

  // Initialize Waveform Canvas
  function drawIdleWaveform() {
    canvasCtx.fillStyle = "#050b11";
    canvasCtx.fillRect(0, 0, canvas.width, canvas.height);
    canvasCtx.strokeStyle = "#162636";
    canvasCtx.lineWidth = 1;
    canvasCtx.beginPath();
    canvasCtx.moveTo(0, canvas.height / 2);
    canvasCtx.lineTo(canvas.width, canvas.height / 2);
    canvasCtx.stroke();
  }
  drawIdleWaveform();

  // Query server status to confirm connected hardware mic
  async function checkServerStatus() {
    try {
      const res = await fetch("/api/status");
      const data = await res.json();
      if (data.hardware_mic) {
        console.log("🎙️ Server active hardware mic:", data.hardware_mic);
        if (audioSourceSelect && audioSourceSelect.options[0]) {
          audioSourceSelect.options[0].text = `🎙️ Mac Hardware Mic (${data.hardware_mic}) — Recommended`;
        }
      }
    } catch (e) {
      console.warn("Could not query /api/status:", e);
    }
  }
  checkServerStatus();

  // Channel & Language Display Update
  function updateDisplays() {
    const chText = channelSelect.options[channelSelect.selectedIndex].text.split(" - ")[0];
    const langCode = languageSelect.value.toUpperCase();
    document.getElementById("tx-screen-ch").innerText = chText;
    document.getElementById("rx-screen-ch").innerText = chText;
    document.getElementById("tx-screen-lang").innerText = `${languageSelect.options[languageSelect.selectedIndex].text.split(" ")[0]} [${langCode}]`;
  }
  channelSelect.addEventListener("change", updateDisplays);
  languageSelect.addEventListener("change", updateDisplays);
  updateDisplays();

  // Emergency Toggle
  emergencyToggle.addEventListener("change", () => {
    const rxPrio = document.getElementById("rx-screen-prio");
    if (emergencyToggle.checked) {
      rxPrio.innerText = "🚨 DISTRESS";
      rxPrio.style.color = "var(--accent-red)";
      document.body.style.boxShadow = "inset 0 0 40px rgba(255, 61, 0, 0.25)";
    } else {
      rxPrio.innerText = "NORMAL";
      rxPrio.style.color = "var(--accent-green)";
      document.body.style.boxShadow = "none";
    }
  });

  // Setup High-Quality PCM Web Audio (Mode: web_mic)
  async function initBrowserMicrophone() {
    if (micInitialized && audioContext) {
      if (audioContext.state === "suspended") {
        await audioContext.resume();
      }
      return true;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: false,
          noiseSuppression: false,
          autoGainControl: true,
        }
      });
      micStream = stream;

      audioContext = new (window.AudioContext || window.webkitAudioContext)();
      const source = audioContext.createMediaStreamSource(stream);

      analyser = audioContext.createAnalyser();
      analyser.fftSize = 512;
      source.connect(analyser);

      const bufferSize = 4096;
      scriptProcessor = audioContext.createScriptProcessor(bufferSize, 1, 1);

      scriptProcessor.onaudioprocess = (e) => {
        if (!isRecordingPtt) return;
        const inputData = e.inputBuffer.getChannelData(0);
        pttAudioBuffers.push(new Float32Array(inputData));

        // Update live meter bar
        let maxPeak = 0;
        for (let i = 0; i < inputData.length; i++) {
          const abs = Math.abs(inputData[i]);
          if (abs > maxPeak) maxPeak = abs;
        }
        const pct = Math.min(100, Math.round(maxPeak * 500));
        if (micLevelBar) micLevelBar.style.width = pct + "%";
        if (micLevelVal) micLevelVal.innerText = pct + "%";
      };

      source.connect(scriptProcessor);
      scriptProcessor.connect(audioContext.destination);

      micInitialized = true;
      console.log("✅ Browser microphone initialized at sample rate:", audioContext.sampleRate);
      return true;
    } catch (err) {
      console.error("Browser microphone access error:", err);
      txStatusIndicator.innerText = "MIC PERMISSION ERROR";
      txStatusIndicator.style.color = "var(--accent-red)";
      txScreenText.innerText = "⚠️ Browser mic access denied. Switching to 'Mac Hardware Mic' recommended!";
      return false;
    }
  }

  // Pre-request mic permission on first click if browser mic mode is selected
  document.addEventListener("click", () => {
    if (audioSourceSelect.value === "web_mic" && !micInitialized) {
      initBrowserMicrophone();
    }
  }, { once: true });

  // Web Audio Waveform Visualizer
  function startBrowserWaveformVisualization() {
    if (!analyser) return;
    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);

    function draw() {
      if (!isRecordingPtt) return;
      animId = requestAnimationFrame(draw);
      analyser.getByteTimeDomainData(dataArray);

      canvasCtx.fillStyle = "#050b11";
      canvasCtx.fillRect(0, 0, canvas.width, canvas.height);
      canvasCtx.lineWidth = 2.5;
      canvasCtx.strokeStyle = emergencyToggle.checked ? "#ff3d00" : "#00e676";
      canvasCtx.beginPath();

      const sliceWidth = (canvas.width * 1.0) / bufferLength;
      let x = 0;
      let maxVal = 0;
      for (let i = 0; i < bufferLength; i++) {
        const v = dataArray[i] / 128.0;
        const y = (v * canvas.height) / 2;
        maxVal = Math.max(maxVal, Math.abs(dataArray[i] - 128));
        if (i === 0) canvasCtx.moveTo(x, y);
        else canvasCtx.lineTo(x, y);
        x += sliceWidth;
      }
      canvasCtx.lineTo(canvas.width, canvas.height / 2);
      canvasCtx.stroke();

      if (maxVal > 8) {
        txStatusIndicator.innerText = "TRANSMITTING (VOICE DETECTED)";
        txStatusIndicator.style.color = "#00e676";
      } else {
        txStatusIndicator.innerText = "TRANSMITTING (SPEAK NOW...)";
        txStatusIndicator.style.color = "var(--accent-amber)";
      }
    }
    draw();
  }

  // Hardware Mic Live Waveform & Meter Visualizer
  function startHwWaveformVisualization() {
    function drawHw() {
      if (!isRecordingPtt) return;
      animId = requestAnimationFrame(drawHw);

      canvasCtx.fillStyle = "#050b11";
      canvasCtx.fillRect(0, 0, canvas.width, canvas.height);
      canvasCtx.lineWidth = 2.5;
      canvasCtx.strokeStyle = emergencyToggle.checked ? "#ff3d00" : "#00e676";
      canvasCtx.beginPath();

      const width = canvas.width;
      const height = canvas.height;
      const halfH = height / 2;
      const amp = Math.max(4, Math.min(halfH - 4, hwCurrentPeak * 250));

      wavePhase += 0.25;
      canvasCtx.moveTo(0, halfH);
      for (let x = 0; x <= width; x += 4) {
        const y = halfH + Math.sin((x * 0.08) + wavePhase) * amp * (0.6 + 0.4 * Math.sin(x * 0.02));
        canvasCtx.lineTo(x, y);
      }
      canvasCtx.stroke();

      if (hwCurrentPeak > 0.005) {
        txStatusIndicator.innerText = "TRANSMITTING (VOICE DETECTED)";
        txStatusIndicator.style.color = "#00e676";
      } else {
        txStatusIndicator.innerText = "TRANSMITTING (SPEAK INTO MIC...)";
        txStatusIndicator.style.color = "var(--accent-amber)";
      }
    }
    drawHw();

    // Poll live mic peak from server
    hwPollInterval = setInterval(async () => {
      if (!isRecordingPtt) return;
      try {
        const res = await fetch("/api/hw_mic_level");
        const data = await res.json();
        hwCurrentPeak = data.latest_peak || 0.0;
        const pct = Math.min(100, Math.round(hwCurrentPeak * 600));
        if (micLevelBar) micLevelBar.style.width = pct + "%";
        if (micLevelVal) micLevelVal.innerText = pct + "%";
      } catch (e) {
        // quiet fallback
      }
    }, 80);
  }

  // PTT Press handler
  async function onPttDown() {
    if (isRecordingPtt) return;
    isRecordingPtt = true;

    pttBtn.classList.add("active");
    const isHwMode = (audioSourceSelect.value === "hw_mic");

    if (isHwMode) {
      // 1. Direct Mac Hardware Microphone
      txStatusIndicator.innerText = "TRANSMITTING (MAC MIC DIRECT)";
      txStatusIndicator.style.color = "var(--accent-red)";
      txScreenText.innerText = "🎙️ Recording on MacBook Pro Microphone... (Speak now, release to send)";

      try {
        await fetch("/api/hw_ptt_start", { method: "POST" });
      } catch (err) {
        console.error("hw_ptt_start error:", err);
      }

      startHwWaveformVisualization();
    } else {
      // 2. Browser Web Audio
      if (!micInitialized) {
        const ok = await initBrowserMicrophone();
        if (!ok) {
          isRecordingPtt = false;
          pttBtn.classList.remove("active");
          return;
        }
      }

      if (audioContext && audioContext.state === "suspended") {
        await audioContext.resume();
      }

      pttAudioBuffers = [];
      txStatusIndicator.innerText = "TRANSMITTING (BROWSER MIC)";
      txStatusIndicator.style.color = "var(--accent-red)";
      txScreenText.innerText = "🎙️ Speaking into browser mic... (Release PTT button to send)";
      startBrowserWaveformVisualization();
    }
  }

  // PTT Release handler
  async function onPttUp() {
    if (!isRecordingPtt) return;
    isRecordingPtt = false;

    pttBtn.classList.remove("active");
    txStatusIndicator.innerText = "PROCESSING";
    txStatusIndicator.style.color = "var(--accent-amber)";
    txScreenText.innerText = "⚡ Transcribing speech & creating neural radio packet...";

    if (hwPollInterval) {
      clearInterval(hwPollInterval);
      hwPollInterval = null;
    }
    if (animId) cancelAnimationFrame(animId);
    drawIdleWaveform();
    if (micLevelBar) micLevelBar.style.width = "0%";
    if (micLevelVal) micLevelVal.innerText = "0%";

    const isHwMode = (audioSourceSelect.value === "hw_mic");

    if (isHwMode) {
      // Stop Mac Hardware Recording & execute transmission
      try {
        const res = await fetch("/api/hw_ptt_stop", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            channel: parseInt(channelSelect.value),
            language: languageSelect.value,
            is_emergency: emergencyToggle.checked,
          }),
        });
        const data = await res.json();
        if (data.success) {
          handleTransmitSuccess(data);
        } else {
          txStatusIndicator.innerText = "NO SPEECH DETECTED";
          txStatusIndicator.style.color = "var(--accent-red)";
          txScreenText.innerText = "⚠️ " + (data.error || "No speech detected. Hold PTT and speak into your MacBook Pro microphone.");
        }
      } catch (err) {
        console.error("HW PTT stop error:", err);
        txStatusIndicator.innerText = "LINK ERROR";
        txStatusIndicator.style.color = "var(--accent-red)";
        txScreenText.innerText = "⚠️ Hardware microphone communication error.";
      }
      return;
    }

    // Browser Web Audio Mode
    if (pttAudioBuffers.length === 0) {
      const fallback = customTextInput.value.trim();
      if (fallback) {
        transmitMessage({ text: fallback });
      } else {
        txStatusIndicator.innerText = "IDLE";
        txScreenText.innerText = "⚠️ No audio captured. Hold PTT longer while speaking.";
      }
      return;
    }

    // Concatenate chunks
    let totalLength = 0;
    for (const chunk of pttAudioBuffers) {
      totalLength += chunk.length;
    }

    const merged = new Float32Array(totalLength);
    let offset = 0;
    for (const chunk of pttAudioBuffers) {
      merged.set(chunk, offset);
      offset += chunk.length;
    }
    pttAudioBuffers = [];

    // Resample to 16,000 Hz if necessary
    const srcRate = audioContext ? audioContext.sampleRate : 44100;
    const resampled = resampleAudio(merged, srcRate, 16000);

    // Encode into standard 16kHz 16-bit PCM WAV Blob
    const wavBlob = encodeWAV(resampled, 16000);

    // Convert to base64
    const reader = new FileReader();
    reader.readAsDataURL(wavBlob);
    reader.onloadend = () => {
      const b64 = reader.result.split(",")[1];
      transmitMessage({ audio: b64 });
    };
  }

  // Pure Client-side Audio Resampler
  function resampleAudio(samples, fromRate, toRate) {
    if (fromRate === toRate) return samples;
    const ratio = fromRate / toRate;
    const newLength = Math.round(samples.length / ratio);
    const result = new Float32Array(newLength);
    for (let i = 0; i < newLength; i++) {
      const srcIndex = i * ratio;
      const indexFloor = Math.floor(srcIndex);
      const indexCeil = Math.min(samples.length - 1, Math.ceil(srcIndex));
      const t = srcIndex - indexFloor;
      result[i] = (1 - t) * samples[indexFloor] + t * samples[indexCeil];
    }
    return result;
  }

  // Pure Client-side 16-bit PCM WAV Encoder
  function encodeWAV(samples, sampleRate) {
    const buffer = new ArrayBuffer(44 + samples.length * 2);
    const view = new DataView(buffer);

    writeString(view, 0, "RIFF");
    view.setUint32(4, 36 + samples.length * 2, true);
    writeString(view, 8, "WAVE");

    writeString(view, 12, "fmt ");
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true); // PCM
    view.setUint16(22, 1, true); // Mono
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * 2, true);
    view.setUint16(32, 2, true);
    view.setUint16(34, 16, true);

    writeString(view, 36, "data");
    view.setUint32(40, samples.length * 2, true);

    let index = 44;
    for (let i = 0; i < samples.length; i++, index += 2) {
      let s = Math.max(-1, Math.min(1, samples[i]));
      view.setInt16(index, s < 0 ? s * 0x8000 : s * 0x7fff, true);
    }

    return new Blob([view], { type: "audio/wav" });
  }

  function writeString(view, offset, string) {
    for (let i = 0; i < string.length; i++) {
      view.setUint8(offset + i, string.charCodeAt(i));
    }
  }

  // Bind Mouse, Touch & Spacebar for PTT
  pttBtn.addEventListener("mousedown", (e) => {
    e.preventDefault();
    onPttDown();
  });
  window.addEventListener("mouseup", (e) => {
    if (isRecordingPtt) onPttUp();
  });

  pttBtn.addEventListener("touchstart", (e) => {
    e.preventDefault();
    onPttDown();
  });
  window.addEventListener("touchend", (e) => {
    if (isRecordingPtt) onPttUp();
  });

  window.addEventListener("keydown", (e) => {
    if (e.code === "Space" && document.activeElement !== customTextInput && !isRecordingPtt) {
      e.preventDefault();
      onPttDown();
    }
  });
  window.addEventListener("keyup", (e) => {
    if (e.code === "Space" && document.activeElement !== customTextInput && isRecordingPtt) {
      e.preventDefault();
      onPttUp();
    }
  });

  // Transmit Message API (for manual text, browser mic audio, presets)
  async function transmitMessage(payload) {
    payload.channel = parseInt(channelSelect.value);
    payload.language = languageSelect.value;
    payload.is_emergency = emergencyToggle.checked;

    txStatusIndicator.innerText = "TRANSMITTING";
    txStatusIndicator.style.color = "var(--accent-amber)";

    try {
      const res = await fetch("/api/transmit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (data.success) {
        handleTransmitSuccess(data);
      } else {
        txStatusIndicator.innerText = "TX REJECTED";
        txStatusIndicator.style.color = "var(--accent-red)";
        txScreenText.innerText = "⚠️ " + (data.error || "Speech could not be recognized.");
      }
    } catch (err) {
      console.error("Transmission error:", err);
      txStatusIndicator.innerText = "LINK ERROR";
      txStatusIndicator.style.color = "var(--accent-red)";
      txScreenText.innerText = "⚠️ Transmission link error.";
    }
  }

  function handleTransmitSuccess(data) {
    // 1. Update Transmitter Screen
    txStatusIndicator.innerText = "IDLE";
    txStatusIndicator.style.color = "var(--text-muted)";
    txScreenText.innerText = `Sent: "${data.text}"`;

    // 2. Update Receiver Screen
    rxStatusIndicator.innerText = data.is_emergency ? "🚨 EMERGENCY ALERT" : "RECEIVING (RX)";
    rxStatusIndicator.style.color = data.is_emergency ? "var(--accent-red)" : "var(--accent-green)";
    rxScreenText.innerText = `Received: "${data.text}"`;

    // 3. Update Telemetry HUD
    telemetrySaving.innerText = `${data.telemetry.bandwidth_saving_pct}%`;
    telemetryPktSize.innerText = `${data.telemetry.packet_size_bytes} B`;
    telemetryRawSize.innerText = `${(data.telemetry.raw_voice_bytes / 1024).toFixed(1)} KB`;
    telemetrySttLat.innerText = `${data.telemetry.stt_latency_ms} ms`;
    telemetryAirLat.innerText = `${data.telemetry.airtime_latency_ms} ms`;
    telemetryTtsLat.innerText = `${data.telemetry.tts_latency_ms} ms`;
    telemetryTotalLat.innerText = `${data.telemetry.total_e2e_latency_ms} ms`;
    telemetryHex.innerText = data.telemetry.packet_hex;

    // 4. Trigger Speaker Grill Animation and Audio Playback
    speakerWaves.classList.add("active");
    if (data.is_emergency) {
      speakerWaves.classList.add("emergency");
      speakerStatusLabel.innerText = "🚨 HIGH-VOLUME NON-INTERRUPTIBLE VOICE PLAYBACK";
      speakerStatusLabel.style.color = "var(--accent-red)";
    } else {
      speakerWaves.classList.remove("emergency");
      speakerStatusLabel.innerText = "🔊 PLAYING VOICE NOTE";
      speakerStatusLabel.style.color = "var(--accent-green)";
    }

    lastAudioB64 = data.audio_base64;
    audioPlayback.src = `data:audio/wav;base64,${data.audio_base64}`;
    audioPlayback.currentTime = 0;
    audioPlayback.play().catch((e) => console.log("Audio autoplay prevented, click replay:", e));

    replayBtn.disabled = false;

    audioPlayback.onended = () => {
      speakerWaves.classList.remove("active");
      speakerWaves.classList.remove("emergency");
      speakerStatusLabel.innerText = "SPEAKER STANDBY";
      speakerStatusLabel.style.color = "var(--text-muted)";
      rxStatusIndicator.innerText = "MONITORING";
      rxStatusIndicator.style.color = "var(--accent-green)";
    };

    // 5. Append to Feed Log
    const feedItem = document.createElement("div");
    feedItem.className = `feed-item ${data.is_emergency ? "emergency" : ""}`;
    const timestamp = new Date().toLocaleTimeString();
    feedItem.innerHTML = `
      <div class="feed-meta">CH ${data.channel} &bull; ${data.language_name} &bull; ${timestamp} &bull; ${data.telemetry.packet_size_bytes}B (${data.telemetry.total_e2e_latency_ms}ms)</div>
      <div>${data.is_emergency ? "🚨 " : ""}"${data.text}"</div>
    `;
    feedLog.prepend(feedItem);
  }

  // Replay Button
  replayBtn.addEventListener("click", () => {
    if (lastAudioB64) {
      audioPlayback.currentTime = 0;
      audioPlayback.play();
      speakerWaves.classList.add("active");
    }
  });

  // Quick Preset & Tactical Macro Chips Click
  document.querySelectorAll(".preset-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      const macroAttr = chip.getAttribute("data-macro");
      const text = chip.getAttribute("data-text");
      const lang = chip.getAttribute("data-lang");
      const isAlert = chip.getAttribute("data-alert") === "true";

      if (lang) {
        languageSelect.value = lang;
      }
      emergencyToggle.checked = isAlert;
      emergencyToggle.dispatchEvent(new Event("change"));
      updateDisplays();

      if (macroAttr) {
        const macroId = parseInt(macroAttr);
        txScreenText.innerText = `Transmitting Tactical Macro [0x0${macroId}] (4 Bytes)...`;
        transmitMessage({ macro: macroId, text: "" });
      } else if (text) {
        txScreenText.innerText = `Transmitting preset: "${text}"`;
        transmitMessage({ text: text });
      }
    });
  });

  // Manual Send Button
  sendTextBtn.addEventListener("click", () => {
    const text = customTextInput.value.trim();
    if (text) {
      transmitMessage({ text: text });
      customTextInput.value = "";
    }
  });

  customTextInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      sendTextBtn.click();
    }
  });
});
