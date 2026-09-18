package com.vaanisetu.core

import org.junit.Assert.*
import org.junit.Test

class CoreTransceiverUnitTest {

    @Test
    fun testMicroRadioPacketVoicePackAndUnpack() {
        val originalText = "HQ, TEAM ALPHA ADVANCING TO CHECKPOINT BRAVO"
        val packet = MicroRadioPacket(
            text = originalText,
            channel = 7,
            language = IndicLanguage.HINDI,
            packetType = PacketType.NORMAL_PTT
        )

        val packedBytes = packet.pack()
        assertTrue("Packed bytes must not be empty", packedBytes.isNotEmpty())
        assertTrue("Packed packet must be under 128 bytes", packedBytes.size < 128)

        val unpacked = MicroRadioPacket.unpack(packedBytes)
        assertNotNull("Unpacked packet must not be null", unpacked)
        assertEquals(PacketType.NORMAL_PTT, unpacked?.packetType)
        assertEquals(7, unpacked?.channel)
        assertEquals(IndicLanguage.HINDI, unpacked?.language)
        assertEquals(originalText, unpacked?.resolvedText)
        assertFalse(unpacked?.isEmergency ?: true)
    }

    @Test
    fun testMicroRadioPacketMacroPackAndUnpack() {
        val packet = MicroRadioPacket(
            channel = 12,
            language = IndicLanguage.ENGLISH,
            packetType = PacketType.TACTICAL_MACRO,
            macro = TacticalMacro.MEDICAL_URGENT
        )

        val packedBytes = packet.pack()
        // Header (3B) + 1B opcode + 2B CRC = 6 bytes
        assertEquals("Macro packet must be exactly 6 bytes", 6, packedBytes.size)

        val unpacked = MicroRadioPacket.unpack(packedBytes)
        assertNotNull("Unpacked packet must not be null", unpacked)
        assertEquals(PacketType.TACTICAL_MACRO, unpacked?.packetType)
        assertEquals(12, unpacked?.channel)
        assertEquals(TacticalMacro.MEDICAL_URGENT, unpacked?.macro)
        assertTrue("Medical macro must be marked as emergency", unpacked?.isEmergency ?: false)
        assertTrue("Resolved text must contain Medical", unpacked?.resolvedText?.contains("medical", ignoreCase = true) == true)
    }

    @Test
    fun testCorruptedCrcRejected() {
        val packet = MicroRadioPacket(
            text = "TACTICAL TEST",
            channel = 3,
            language = IndicLanguage.ENGLISH,
            packetType = PacketType.NORMAL_PTT
        )
        val packedBytes = packet.pack()

        // Corrupt payload byte
        packedBytes[3] = (packedBytes[3].toInt() xor 0xFF).toByte()

        val unpacked = MicroRadioPacket.unpack(packedBytes)
        assertNull("Corrupted packet must fail CRC check and return null", unpacked)
    }

    @Test
    fun testTacticalRescorer() {
        val raw1 = "team alpha mate team at coordinates"
        val rescored1 = TacticalRescorer.rescore(raw1)
        assertTrue(rescored1.contains("medical team"))

        val raw2 = "switch to channel seven immediately"
        val rescored2 = TacticalRescorer.rescore(raw2)
        assertTrue(rescored2.contains("Channel 07"))

        val raw3 = "we have casualty in sector nine"
        val rescored3 = TacticalRescorer.rescore(raw3)
        assertTrue(rescored3.contains("sector 09", ignoreCase = true))
    }

    @Test
    fun testAcousticProcessor() {
        val sampleRate = 16000
        val numSamples = 1600 // 100ms
        val input = FloatArray(numSamples) { i ->
            0.5f + 0.1f * Math.sin(2.0 * Math.PI * 440.0 * i / sampleRate).toFloat()
        }

        val processed = AcousticProcessor.process(input, sampleRate = sampleRate, forWhisper = true)
        // 120ms pre + 220ms post padding = 340ms = 5440 samples
        val expectedPadding = (16000 * 0.12).toInt() + (16000 * 0.22).toInt()
        assertEquals(numSamples + expectedPadding, processed.size)

        // Peak must not exceed AGC ceiling (0.85f)
        val maxPeak = processed.maxOrNull() ?: 0f
        assertTrue("Max peak must not exceed ceiling 0.85f", maxPeak <= 0.86f)
    }

    @Test
    fun testEmergencySirenGenerator() {
        val sampleRate = 16000
        val siren = EmergencySirenGenerator.generateSiren(durationSec = 0.5f, sampleRate = sampleRate)
        assertEquals((sampleRate * 0.5f).toInt(), siren.size)

        val speech = FloatArray(1600) { 0.1f }
        val prepended = EmergencySirenGenerator.prependSirenToSpeech(
            speechSamples = speech,
            sampleRate = sampleRate,
            sirenDurationSec = 0.2f,
            gainBoostDb = 6f
        )
        val expectedLength = (sampleRate * 0.2f).toInt() + (sampleRate / 10) + speech.size
        assertEquals(expectedLength, prepended.size)
    }

    @Test
    fun testBrahmiTransliterator() {
        val hindi = BrahmiTransliterator.toDevanagariPhonetic("namaste", "hi")
        assertNotNull(hindi)
        assertTrue(hindi.isNotBlank())
    }
}
