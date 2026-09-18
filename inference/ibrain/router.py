"""
iTantra Conversation Router
Conforms to Section 42 of iTantra Technical Specification:
Input: Recognized text + language metadata
Decision:
- SIMPLE_TRANSLATION -> routes directly to iTranslate (saving compute)
- REASONING_REQUIRED -> routes to iBrain local LLM
"""

from enum import Enum
import re
from typing import Dict, Any, Tuple


class RouteDestination(Enum):
    SIMPLE_TRANSLATION = "SIMPLE_TRANSLATION"
    REASONING_REQUIRED = "REASONING_REQUIRED"


class ConversationRouter:
    """
    High-speed intent router determining whether an utterance demands
    direct translation or complex conversational reasoning.
    """

    TRANSLATION_TRIGGERS = [
        # English patterns
        re.compile(r"\b(translate|say this in|how do you say|in hindi|in tamil|in telugu|in bengali)\b", re.IGNORECASE),
        # Hindi patterns (e.g. इसका अनुवाद करो, तमिल में बोलो)
        re.compile(r"(अनुवाद|ट्रांसलेट|तमिल में|तेलुगु में|हिंदी में|अंग्रेजी में)"),
        # Bengali patterns (e.g. অনুবাদ করো)
        re.compile(r"(অনুবাদ|তামিল ভাষায়)"),
        # Tamil patterns (e.g. மொழிபெயர்)
        re.compile(r"(மொழிபெயர்|இந்தியில்)")
    ]

    def route(self, text: str, detected_language: str = "hi") -> Tuple[RouteDestination, Dict[str, Any]]:
        """
        Evaluate user utterance and return routing decision.

        Returns:
            (RouteDestination, routing_metadata)
        """
        if not text:
            return RouteDestination.REASONING_REQUIRED, {"reason": "empty_input"}

        cleaned = text.strip()

        # Check for explicit translation directives
        for pattern in self.TRANSLATION_TRIGGERS:
            match = pattern.search(cleaned)
            if match:
                # Target language extraction heuristic
                target_lang = self._extract_target_lang(cleaned)
                return RouteDestination.SIMPLE_TRANSLATION, {
                    "matched_trigger": match.group(0),
                    "target_language": target_lang,
                    "clean_text_to_translate": self._strip_translation_command(cleaned)
                }

        # Default to contextual reasoning
        return RouteDestination.REASONING_REQUIRED, {
            "reason": "conversational_or_factual"
        }

    def _extract_target_lang(self, text: str) -> str:
        """Extract requested target language from utterance."""
        lower = text.lower()
        if "tamil" in lower or "तमिल" in lower or "தமிழ்" in lower:
            return "ta"
        elif "telugu" in lower or "तेलुगु" in lower or "తెలుగు" in lower:
            return "te"
        elif "bengali" in lower or "बंगाली" in lower or "বাংলা" in lower:
            return "bn"
        elif "marathi" in lower or "मराठी" in lower:
            return "mr"
        elif "gujarati" in lower or "गुजराती" in lower or "ગુજરાતી" in lower:
            return "gu"
        elif "kannada" in lower or "कन्नड़" in lower or "ಕನ್ನಡ" in lower:
            return "kn"
        elif "malayalam" in lower or "मलयालम" in lower or "മലയാളം" in lower:
            return "ml"
        elif "punjabi" in lower or "पंजाबी" in lower or "ਪੰਜਾਬੀ" in lower:
            return "pa"
        elif "odia" in lower or "ओड़िया" in lower or "ଓଡ଼ିଆ" in lower:
            return "or"
        elif "hindi" in lower or "हिंदी" in lower:
            return "hi"
        return "en"

    def _strip_translation_command(self, text: str) -> str:
        """Strip translation prompt prefixes to get the core message."""
        cleaned = re.sub(r"^(translate|say this in [a-zA-Z]+:|in [a-zA-Z]+:)", "", text, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"(का अनुवाद करो|में बोलो)$", "", cleaned).strip()
        return cleaned if cleaned else text
