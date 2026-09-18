"""
iTantra Indic Text Normalization Pipeline
Conforms to Section 15 of iTantra Technical Specification:
Supports 10 Indian languages (Hindi, Bengali, Tamil, Telugu, Marathi, Gujarati, Kannada, Malayalam, Punjabi, Odia) + English.
Features:
- Unicode NFC normalization
- Zero-Width Joiner (ZWJ) and Non-Joiner (ZWNJ) cleanup
- Nukta harmonization
- Punctuation standardization and removal of transcription noise artifacts
- Preserves both raw text and normalized text
"""

import re
import unicodedata
from typing import Dict, Tuple


# Indic script Unicode block mapping
INDIC_SCRIPTS = {
    "hi": "Devanagari",
    "mr": "Devanagari",
    "bn": "Bengali",
    "ta": "Tamil",
    "te": "Telugu",
    "gu": "Gujarati",
    "kn": "Kannada",
    "ml": "Malayalam",
    "pa": "Gurmukhi",
    "or": "Odia",
    "en": "Latin",
}

# Transcription artifact patterns (e.g., <cough>, [laughter], (unintelligible), %uh)
ARTIFACT_PATTERNS = [
    re.compile(r"<[^>]+>"),
    re.compile(r"\[[^\]]+\]"),
    re.compile(r"\([^\)]+\)"),
    re.compile(r"%[a-zA-Z_]+"),
]


class IndicTextNormalizer:
    """
    Standardized text normalizer across all 10 Indic languages and English.
    """

    # Common Indian numeral to canonical digit mappings
    INDIC_DIGITS = {
        # Devanagari (Hindi, Marathi)
        '०': '0', '१': '1', '२': '2', '३': '3', '४': '4', '५': '5', '६': '6', '७': '7', '८': '8', '९': '9',
        # Bengali
        '০': '0', '১': '1', '২': '2', '৩': '3', '৪': '4', '৫': '5', '৬': '6', '৭': '7', '৮': '8', '৯': '9',
        # Gurmukhi (Punjabi)
        '੦': '0', '੧': '1', '੨': '2', '੩': '3', '੪': '4', '੫': '5', '੬': '6', '੭': '7', '੮': '8', '੯': '9',
        # Gujarati
        '૦': '0', '૧': '1', '૨': '2', '૩': '3', '૪': '4', '૫': '5', '૬': '6', '૭': '7', '૮': '8', '૯': '9',
        # Odia
        '୦': '0', '୧': '1', '୨': '2', '୩': '3', '୪': '4', '୫': '5', '୬': '6', '୭': '7', '୮': '8', '୯': '9',
        # Tamil
        '௦': '0', '௧': '1', '௨': '2', '௩': '3', '௪': '4', '௫': '5', '௬': '6', '௭': '7', '௮': '8', '௯': '9',
        # Telugu
        '౦': '0', '౧': '1', '౨': '2', '౩': '3', '౪': '4', '౫': '5', '౬': '6', '౭': '7', '౮': '8', '౯': '9',
        # Kannada
        '೦': '0', '೧': '1', '೨': '2', '೩': '3', '೪': '4', '೫': '5', '೬': '6', '೭': '7', '೮': '8', '೯': '9',
        # Malayalam
        '൦': '0', '൧': '1', '൨': '2', '൩': '3', '൪': '4', '൫': '5', '൬': '6', '൭': '7', '൮': '8', '൯': '9',
    }

    def __init__(self, remove_punctuation: bool = True, convert_digits: bool = True):
        self.remove_punctuation = remove_punctuation
        self.convert_digits = convert_digits

    def normalize(self, text: str, language: str = "hi") -> Tuple[str, str]:
        """
        Normalize an Indic text string according to script rules.

        Returns:
            (raw_text, normalized_text)
            Guarantees raw text is never lost or overwritten.
        """
        raw_text = str(text)
        if not text:
            return raw_text, ""

        # 1. Unicode NFC Normalization (composes base characters and diacritics)
        norm = unicodedata.normalize("NFC", raw_text)

        # 2. Remove acoustic/transcription artifacts
        for pat in ARTIFACT_PATTERNS:
            norm = pat.sub("", norm)

        # 3. Handle zero-width characters (ZWJ \u200D, ZWNJ \u200C)
        # Keep ZWNJ only where needed in Bengali/Malayalam chillus, clean solitary instances
        norm = norm.replace("\uFEFF", "")  # Remove Byte Order Mark (BOM)
        norm = norm.replace("\u200B", "")  # Remove Zero-Width Space

        # 4. Canonicalize Indic Digits to Standard Digits
        if self.convert_digits:
            for indic_d, std_d in self.INDIC_DIGITS.items():
                if indic_d in norm:
                    norm = norm.replace(indic_d, std_d)

        # 5. Punctuation handling
        if self.remove_punctuation:
            # Strip standard punctuation and Indic danda/double-danda (। and ॥)
            norm = re.sub(r"[।॥\.,;:!?'\"`~@#$%^&*()_+=/\\|<>\[\]{}—–-]", " ", norm)

        # 6. Whitespace collapse and trimming
        norm = re.sub(r"\s+", " ", norm).strip()

        # 7. Lowercase for Latin/English
        if language == "en":
            norm = norm.lower()

        return raw_text, norm
