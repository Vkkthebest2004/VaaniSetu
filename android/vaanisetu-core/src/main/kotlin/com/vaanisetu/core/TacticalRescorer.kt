package com.vaanisetu.core

/**
 * Tactical Domain Language Model Rescorer for Android.
 *
 * Corrects phonetic acoustic confusions common in noisy battlefield
 * and disaster environments, and normalizes spoken numerals to
 * standard radio protocol format.
 *
 * Mirrors Python tactical_rescorer.py.
 */
object TacticalRescorer {

    /** Phonetic confusion correction map: common misrecognitions → correct terms. */
    private val CONFUSION_MAP = mapOf(
        "of accuation" to "evacuation",
        "of a cuation" to "evacuation",
        "off a cuation" to "evacuation",
        "evac u ation" to "evacuation",
        "evacuaction" to "evacuation",
        "mate team" to "medical team",
        "met team" to "medical team",
        "medical teem" to "medical team",
        "medic team" to "medical team",
        "med team" to "medical team",
        "casual tea" to "casualty",
        "casual tee" to "casualty",
        "casuality" to "casualty",
        "cas u alty" to "casualty",
        "fire you nit" to "fire unit",
        "fire unite" to "fire unit",
        "resque" to "rescue",
        "resqu" to "rescue",
        "sos call" to "SOS call",
        "may day" to "mayday",
        "sector niner" to "sector 09",
        "sector nine" to "sector 09",
        "alfa" to "alpha",
        "brovo" to "bravo"
    )

    /** Spoken number words to digits for radio channel normalization. */
    private val NUMBER_WORDS = mapOf(
        "zero" to "00", "one" to "01", "two" to "02", "three" to "03",
        "four" to "04", "five" to "05", "six" to "06", "seven" to "07",
        "eight" to "08", "nine" to "09", "ten" to "10", "eleven" to "11",
        "twelve" to "12", "thirteen" to "13", "fourteen" to "14",
        "fifteen" to "15", "sixteen" to "16"
    )

    /**
     * Apply tactical domain rescoring to recognized text.
     *
     * 1. Fix phonetic confusion patterns.
     * 2. Normalize spoken channel numbers (e.g., "Channel Seven" → "Channel 07").
     * 3. Normalize spoken sector numbers.
     *
     * @param text Raw STT output text.
     * @return Rescored text with tactical corrections applied.
     */
    fun rescore(text: String): String {
        var result = text

        // 1. Fix phonetic confusions (case-insensitive search)
        for ((wrong, correct) in CONFUSION_MAP) {
            val regex = Regex(Regex.escape(wrong), RegexOption.IGNORE_CASE)
            result = result.replace(regex, correct)
        }

        // 2. Normalize "Channel <word>" → "Channel <number>"
        for ((word, digits) in NUMBER_WORDS) {
            val channelRegex = Regex("(?i)channel\\s+$word")
            result = result.replace(channelRegex, "Channel $digits")
        }

        // 3. Normalize "Sector <word>" → "Sector <number>"
        for ((word, digits) in NUMBER_WORDS) {
            val sectorRegex = Regex("(?i)sector\\s+$word")
            result = result.replace(sectorRegex, "Sector $digits")
        }

        return result
    }
}
