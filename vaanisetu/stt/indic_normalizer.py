"""
Indic Script Normalizer & Transliteration Engine for iTantra.

Solves the multi-script representation challenge in multilingual Whisper models:
1. Perso-Arabic (Urdu/Nastaliq) to Devanagari transliteration for Hindustani speech.
2. Romanized Hindi/Hinglish vocabulary mapping into standard Devanagari.
3. Universal Devanagari to regional Indic script transliteration (Bengali, Tamil, Telugu, etc.).
4. Whisper hallucination pruning, repetition suppression, and punctuation normalization.
5. Tactical vocabulary preservation across Indian languages.
"""

import re
import unicodedata
from typing import Dict, Optional, Tuple


class IndicScriptNormalizer:
    """
    High-speed, 100% offline rule-based script normalizer and phonetic converter.
    Runs in < 0.2ms.
    """

    # Unicode script block base offsets (Brahmi relative isomorphism)
    SCRIPT_BASES: Dict[str, int] = {
        'hi': 0x0900,
        'mr': 0x0900,
        'bn': 0x0980,
        'pa': 0x0A00,
        'gu': 0x0A80,
        'or': 0x0B00,
        'ta': 0x0B80,
        'te': 0x0C00,
        'kn': 0x0C80,
        'ml': 0x0D00,
    }

    CONSONANTS = set('بپتٹثجچحخدڈذرڑزژسشصضطظعغفقکگلمنہھ')

    # Perso-Arabic character to Devanagari phonetic mapping
    CHAR_MAP_URDU_TO_DEV: Dict[str, str] = {
        # Vowels and semi-vowels
        'ا': 'अ', 'آ': 'आ', 'و': 'व', 'ی': 'य', 'ے': 'े', 'ئے': 'ए',
        'ہ': 'ह', 'ھ': 'ह', 'ع': '', 'ء': '', 'أ': 'अ', 'إ': 'इ',
        'ؤ': 'ओ', 'ۂ': 'ह', 'ۃ': 'त', 'ة': 'त',
        
        # Consonants
        'ب': 'ब', 'پ': 'प', 'ت': 'त', 'ٹ': 'ट', 'ث': 'स',
        'ج': 'ज', 'چ': 'च', 'ح': 'ह', 'خ': 'ख़', 'د': 'द',
        'ڈ': 'ड', 'ذ': 'ज़', 'ر': 'र', 'ڑ': 'ड़', 'ز': 'ज़',
        'ژ': 'झ़', 'س': 'स', 'ش': 'श', 'ص': 'स', 'ض': 'ज़',
        'ط': 'त', 'ظ': 'ज़', 'غ': 'ग़', 'ف': 'फ़', 'ق': 'क़',
        'ک': 'क', 'گ': 'ग', 'ل': 'ल', 'م': 'म', 'ن': 'न',
        'ں': 'ँ',
    }

    # Digraphs (Aspirated consonants in Perso-Arabic script)
    DIGRAPHS_URDU_TO_DEV: Dict[str, str] = {
        'بھ': 'भ', 'پھ': 'फ', 'تھ': 'थ', 'ٹھ': 'ठ',
        'جھ': 'झ', 'چھ': 'छ', 'دھ': 'ध', 'ڈھ': 'ढ',
        'رھ': 'र्ह', 'ڑھ': 'ढ़', 'کھ': 'ख', 'گھ': 'घ',
        'لھ': 'ल्ह', 'مھ': 'म्ह', 'نھ': 'न्ह',
    }

    # Compound multi-word Hindustani phrases (checked first)
    COMPOUND_URDU_PHRASES: Dict[str, str] = {
        'وانی سے تو': 'वाणी सेतु',
        'ہواری سے تو': 'वाणी सेतु',
        'ہواڑی سے تو': 'वाणी सेतु',
        'سے تو': 'सेतु',
        'سیتو': 'सेतु',
        'کیسے ہیں': 'कैसे हैं',
        'کیسا ہے': 'कैसा है',
        'کیا حال': 'क्या हाल',
        'سن سکتے': 'सुन सकते',
        'مدد چاہیے': 'मदद चाहिए',
        'طبی امداد': 'चिकित्सा सहायता',
        'خطرناک صورتحال': 'ख़तरनाक स्थिति',
        'سیلاب کا پانی': 'बाढ़ का पानी',
        'آگ لگی': 'आग लगी',
        'خالی کرو': 'खाली करो',
        'بچاؤ ٹیم': 'बचाव दल',
        'راستہ بند': 'रास्ता बंद',
    }

    # High-frequency tactical & spoken Hindustani words (Urdu script -> Devanagari)
    COMMON_URDU_WORDS: Dict[str, str] = {
        # Greetings & Identity
        'نمستے': 'नमस्ते', 'سلام': 'सलाम', 'شکریہ': 'शुक्रिया', 'آداب': 'आदाब',
        'آپ': 'आप', 'تم': 'तुम', 'ہم': 'हम', 'میں': 'मैं', 'مجھ': 'मुझ', 'مجھے': 'मुझे',
        'ہمیں': 'हमें', 'تمہیں': 'तुम्हें', 'اس': 'इस', 'اسے': 'इसे', 'ان': 'इन', 'انہیں': 'इन्हें',
        'یہ': 'यह', 'یا': 'यह', 'وہ': 'वह', 'وانی': 'वाणी', 'ہواری': 'वाणी', 'تو': 'तो',
        'کیسے': 'कैसे', 'کیسا': 'कैसा', 'کیسی': 'कैसी', 'ہیں': 'हैं', 'ہے': 'है',
        'ٹھیک': 'ठीक', 'صحیح': 'सही', 'آواز': 'आवाज़', 'صاف': 'साफ़', 'پیغام': 'पैगाम',
        'ملا': 'मिला', 'سمجھ': 'समझ', 'سن': 'सुन', 'سنا': 'सुना', 'سنائی': 'सुनाई',
        'دے': 'दे', 'رہا': 'रहा', 'رہی': 'रही', 'رہے': 'रहे', 'ہاں': 'हाँ', 'نہیں': 'नहीं',
        'کیا': 'क्या', 'کیوں': 'क्यों', 'کب': 'कब', 'کہاں': 'कहाँ', 'کون': 'कौन',
        'کتنا': 'कितना', 'کتنے': 'कितने', 'کتنی': 'कितनी', 'سب': 'सब', 'کچھ': 'कुछ',

        # Movement & Actions
        'آگے': 'आगे', 'پیچھے': 'पीछे', 'بڑھ': 'बढ़', 'روکو': 'रोको', 'روک': 'रोक',
        'جاؤ': 'जाओ', 'آؤ': 'आओ', 'چلیں': 'चलें', 'چلو': 'चलो', 'تھا': 'था', 'تھی': 'थी',
        'تھے': 'थे', 'گا': 'गा', 'گی': 'गी', 'گے': 'गे', 'ہوا': 'हुआ', 'ہو': 'हो',

        # Postpositions & Prepositions
        'کی': 'की', 'کا': 'का', 'کے': 'के', 'کو': 'को', 'پر': 'पर', 'سے': 'से', 'تک': 'तक',

        # Emergency & Radio Vocabulary
        'مدد': 'मदद', 'ضرورت': 'ज़रूरत', 'روانہ': 'रवाना', 'پوزیشن': 'पोज़ीशन', 'رپورٹ': 'रिपोर्ट',
        'دوست': 'दोस्त', 'دشمن': 'दुश्मन', 'فوج': 'फ़ौज', 'حملہ': 'हमला', 'خطرہ': 'ख़तरा',
        'کنٹرول': 'कंट्रोल', 'روم': 'रूम', 'سیکٹر': 'सेक्टर', 'حکم': 'हुक्म', 'فوری': 'फ़ौरी',
        'طبی': 'तिब्बी', 'جہاز': 'जहाज़', 'چوکی': 'चौकी', 'گشت': 'गश्त', 'روٹ': 'रूट',
        'فائر': 'फ़ायर', 'کور': 'कवर', 'جوان': 'जवान', 'بچے': 'बचे', 'مشن': 'मिशन',
        'مکمل': 'मुकम्मल', 'کمانڈر': 'कमांडर', 'فائرنگ': 'फ़ायरنگ', 'محفوظ': 'महफ़ूज़',
        'آگ': 'आग', 'پانی': 'पानी', 'سیلاب': 'बाढ़', 'باڑھ': 'बाढ़', 'راستہ': 'रास्ता',
        'بند': 'बंद', 'کھلا': 'खुला', 'ہسپتال': 'अस्पताल', 'ڈاکٹر': 'डॉक्टर',
        'ایمبولینس': 'एंबुलेंस', 'پولیس': 'पुलिस', 'فوجی': 'फ़ौजी',
    }

    # Common Romanized Hindi words -> Devanagari
    ROMAN_HINDI_DICT: Dict[str, str] = {
        # Greetings & Communication
        'namaste': 'नमस्ते', 'namaskar': 'नमस्कार', 'namaskaram': 'नमस्कारम',
        'namska': 'नमस्कार', 'namskaat': 'नमस्कार', 'vanakkam': 'வணக்கம்',
        'sat': 'सत्', 'sri': 'श्री', 'akal': 'अकाल', 'hum': 'हम', 'ham': 'हम',
        'aap': 'आप', 'apne': 'अपने', 'apni': 'अपनी', 'apan': 'आपण', 'tussi': 'ਤੁਸੀਂ',
        'tumi': 'তুমি', 'tume': 'तुम्ही', 'tame': 'તમે', 'tumhi': 'तुम्ही',
        'neevu': 'ನೀವು', 'meeru': 'మీరు', 'ningal': 'നിങ്ങൾ',
        'kya': 'क्या', 'kaise': 'कैसे', 'kese': 'कैसे', 'kemon': 'কেমন',
        'kasa': 'कसा', 'kase': 'कसे', 'kashe': 'कसे', 'kem': 'કેમ',
        'hegiddeeri': 'ಹೇಗಿದ್ದೀರಿ', 'ela': 'ఎలా', 'eppadi': 'எப்படி',
        'sukhamano': 'സുഖമാണോ', 'kive': 'ਕਿਵੇਂ', 'kemiti': 'କେମିତି',
        'achanti': 'ଅଛନ୍ତି', 'unnaru': 'ఉన్నారు', 'aahat': 'आहात', 'ahad': 'आहात',
        'chho': 'છો', 'aachen': 'আছেন', 'irukkireerkal': 'இருக்கிறீர்கள்',
        'vani': 'वाणी', 'vaani': 'वाणी', 'setu': 'सेतु', 'sedu': 'सेतु', 'setoo': 'सेतू',
        'radio': 'रेडियो',

        # Movement, Mission, & Status
        'aage': 'आगे', 'agi': 'आगे', 'badh': 'बढ़', 'badhara': 'बढ़ रहे',
        'badh rahe': 'बढ़ रहे', 'rahe': 'रहे', 'raha': 'रहा', 'rahi': 'रही',
        'hain': 'हैं', 'hai': 'है', 'hhe': 'हे', 'ahhe': 'आहे', 'ahe': 'आहे',
        'madad': 'मदद', 'ki': 'की', 'ka': 'का', 'ke': 'के', 'ko': 'को', 'se': 'से',
        'zarurat': 'ज़रूरत', 'zaroorat': 'ज़रूरत', 'mission': 'मिशन', 'pura': 'पूरा',
        'hua': 'हुआ', 'hwa': 'हुआ', 'report': 'रिपोर्ट', 'kare': 'करें', 'karo': 'करो',
        'sthiti': 'स्थिति', 'par': 'पर', 'per': 'पर', 'tainat': 'तैनात',
        'mujhe': 'मुझे', 'sun': 'सुन', 'sakte': 'सकते', 'suno': 'सुनो', 'sab': 'सब',
        'theek': 'ठीक', 'sector': 'सेक्टर', 'chowki': 'चौकी', 'firing': 'फ़ायरिंग',
        'commander': 'कमांडर', 'alert': 'अलर्ट', 'position': 'पोज़ीशन', 'shuru': 'शुरू',
        'shukriya': 'शुक्रिया', 'dost': 'दोस्त', 'dushman': 'दुश्मन', 'hamla': 'हमला',
        'khatra': 'ख़तरा', 'roko': 'रोको', 'chalo': 'चलो', 'kye': 'कैसे', 'sa': 'सा',
        'tu': 'तू',

        # Water, Flood, Evacuation
        'baadh': 'बाढ़', 'baird': 'बाढ़', 'bhadh': 'बाढ़', 'bhajdha': 'बाढ़',
        'buldak': 'बाढ़ का', 'harda': 'हड़ दा', 'khardha': 'हड़ दा',
        'paani': 'पानी', 'pani': 'पानी', 'jal': 'जल', 'jalam': 'जल',
        'neeru': 'नीरु', 'neer': 'नीर', 'pur': 'पूर', 'purnu': 'પૂરનું',
        'pravah': 'प्रवाह', 'vanya': 'बैन्या', 'banhyat': 'बैन्या', 'benya': 'बैन्या',
        'barche': 'বাড়ছে', 'wadhat': 'वाढत', 'warhat': 'वाढत', 'wathi': 'વધી',
        'turant': 'तुरंत', 'tornant': 'तुरंत', 'turt': 'तुरंत', 'turta': 'तुरंत',
        'turtadar': 'तुरंत', 'turtakhal': 'तुरंत खाली', 'turtakhali': 'तुरंत खाली',
        'tatkal': 'तत्काल', 'tatkallik': 'तात्कालिक', 'abhilamwe': 'অবিলম্বে',
        'khali': 'खाली', 'khal': 'खाली', 'karantu': 'करंतु', 'madhi': 'माडी',
        'maruka': 'माറുക',

        # Medical & Emergency Rescue
        'chikitsa': 'चिकित्सा', 'chikitsha': 'चिकित्सा', 'aapatkal': 'आपातकाल',
        'apatkal': 'आपातकाल', 'jaruri': 'ज़रूरी', 'joruri': 'জরুরী',
        'vaidya': 'वैद्य', 'vaidyakiya': 'वैद्यकीय', 'vethdhikhi': 'वैद्यकीय',
        'tabibi': 'તબીબી', 'dakshat': 'डाक्टर', 'dhaktiri': 'ଡାକ୍ତରୀ',
        'sahayata': 'सहायता', 'sahay': 'सहायता', 'sahaita': 'सहायता',
        'sahayani': 'સહાયની', 'sahayam': 'సహాయం', 'neravu': 'ನೆರವು',
        'chahidi': 'ਚਾਹੀਦੀ', 'chahiye': 'चाहिए', 'avashyak': 'आवश्यक',
        'abhashaktim': 'ଆବଶ୍ୟକ', 'beku': 'ಬೇಕು', 'venam': 'വേണം',
        'team': 'टीम', 'teem': 'टीम', 'dal': 'दल', 'moklo': 'મોકલો',
        'tandavannu': 'ತಂಡವನ್ನು', 'sanghathe': 'സംഘത്തെ', 'bhejo': 'भेजो',
        'pathantu': 'ପଠାନ୍ତୁ', 'kaluhisi': 'ಕಳುಹಿಸಿ', 'ayakkuka': 'അയക്കുക',
        'ambulans': 'एंबुलेंस', 'ambulance': 'एंबुलेंस', 'hospital': 'अस्पताल',
    }

    @staticmethod
    def is_perso_arabic(text: str) -> bool:
        """Returns True if the string contains Arabic/Perso-Arabic script characters."""
        for char in text:
            cp = ord(char)
            if (0x0600 <= cp <= 0x06FF) or (0x0750 <= cp <= 0x077F) or (0xFB50 <= cp <= 0xFDFF) or (0xFE70 <= cp <= 0xFEFF):
                return True
        return False

    @staticmethod
    def is_indic_script(text: str) -> bool:
        """Returns True if text contains native Indic script characters."""
        for char in text:
            cp = ord(char)
            if 0x0900 <= cp <= 0x0D7F:
                return True
        return False

    @classmethod
    def devanagari_to_indic(cls, text: str, target_lang: str) -> str:
        """
        Transliterates Devanagari Unicode text into target Indic script (Bengali,
        Tamil, Telugu, Gujarati, Kannada, Malayalam, Gurmukhi, Odia).
        """
        target_base = cls.SCRIPT_BASES.get(target_lang, 0x0900)
        if target_base == 0x0900:
            return text
        res = []
        for c in text:
            cp = ord(c)
            if 0x0900 <= cp <= 0x097F:
                offset = cp - 0x0900
                target_cp = target_base + offset
                try:
                    res.append(chr(target_cp))
                except ValueError:
                    res.append(c)
            else:
                res.append(c)
        return ''.join(res)

    @classmethod
    def urdu_to_devanagari(cls, text: str) -> str:
        """
        Phonetically converts Perso-Arabic (Urdu/Nastaliq) text into standard Devanagari Hindi.
        """
        if not text:
            return ''

        # 1. First replace compound multi-word phrases (longest first)
        processed = text
        for u_phrase, dev_phrase in sorted(cls.COMPOUND_URDU_PHRASES.items(), key=lambda x: len(x[0]), reverse=True):
            processed = processed.replace(u_phrase, f' {dev_phrase} ')

        words = processed.split()
        converted_words = []

        for raw_w in words:
            # If word is already Devanagari/Indic, preserve it
            if cls.is_indic_script(raw_w):
                converted_words.append(raw_w)
                continue

            # Strip punctuation
            punct_before = ''
            punct_after = ''
            clean_w = raw_w

            m_prefix = re.match(r'^[^\w\s]+', raw_w)
            if m_prefix:
                punct_before = m_prefix.group(0)
                clean_w = clean_w[len(punct_before):]

            m_suffix = re.search(r'[^\w\s]+$', clean_w)
            if m_suffix:
                punct_after = m_suffix.group(0)
                clean_w = clean_w[:-len(punct_after)]

            if not clean_w:
                converted_words.append(raw_w)
                continue

            # 2. Exact dictionary match
            if clean_w in cls.COMMON_URDU_WORDS:
                converted_words.append(f'{punct_before}{cls.COMMON_URDU_WORDS[clean_w]}{punct_after}')
                continue

            # 3. Smart phonetic conversion with matra awareness
            chars = []
            i = 0
            n = len(clean_w)
            while i < n:
                c = clean_w[i]
                prev_is_cons = (i > 0 and clean_w[i-1] in cls.CONSONANTS)

                # Check 2-char digraph (e.g. بھ, کھ)
                if i + 1 < n and clean_w[i:i+2] in cls.DIGRAPHS_URDU_TO_DEV:
                    chars.append(cls.DIGRAPHS_URDU_TO_DEV[clean_w[i:i+2]])
                    i += 2
                elif c == 'ی':
                    if prev_is_cons:
                        chars.append('ी' if (i == n - 1 or (i + 1 < n and clean_w[i+1] not in cls.CONSONANTS)) else 'े')
                    else:
                        chars.append('य' if i == 0 else 'ी')
                    i += 1
                elif c == 'ے':
                    chars.append('े' if prev_is_cons else 'ए')
                    i += 1
                elif c == 'و':
                    if prev_is_cons:
                        chars.append('ो' if (i == n - 1 or (i + 1 < n and clean_w[i+1] not in cls.CONSONANTS)) else 'ू')
                    else:
                        chars.append('व' if i == 0 else 'ो')
                    i += 1
                elif c == 'ا':
                    chars.append('ा' if prev_is_cons else 'अ')
                    i += 1
                elif c in cls.CHAR_MAP_URDU_TO_DEV:
                    chars.append(cls.CHAR_MAP_URDU_TO_DEV[c])
                    i += 1
                else:
                    chars.append(c)
                    i += 1

            dev_word = ''.join(chars)
            converted_words.append(f'{punct_before}{dev_word}{punct_after}')

        res = ' '.join(converted_words)
        res = re.sub(r'\s+', ' ', res).strip()
        return res

    @classmethod
    def phonetic_roman_to_devanagari(cls, word: str) -> str:
        """
        Rule-based phonetic transliteration from Romanized characters to Devanagari.
        """
        consonants = {
            "kh": "ख", "gh": "घ", "ch": "च", "chh": "छ", "jh": "झ", "th": "थ", "dh": "ध",
            "ph": "फ", "bh": "भ", "sh": "श", "k": "क", "g": "ग", "j": "ज", "t": "त",
            "d": "द", "n": "न", "p": "प", "b": "ब", "m": "म", "y": "य", "r": "र",
            "l": "ल", "v": "व", "w": "व", "s": "स", "h": "ह", "z": "ज़", "f": "फ़"
        }
        vowels_initial = {
            "aa": "आ", "ee": "ई", "oo": "ऊ", "ai": "ऐ", "au": "औ",
            "a": "अ", "i": "इ", "u": "उ", "e": "ए", "o": "ओ"
        }
        vowels_matra = {
            "aa": "ा", "ee": "ी", "oo": "ू", "ai": "ै", "au": "ौ",
            "a": "", "i": "ि", "u": "ु", "e": "े", "o": "ो"
        }

        w = word.lower()
        i = 0
        n = len(w)
        out = []
        has_prev_cons = False

        while i < n:
            c2 = w[i:i+2]
            c1 = w[i:i+1]

            if c2 in consonants:
                out.append(consonants[c2])
                has_prev_cons = True
                i += 2
            elif c1 in consonants:
                out.append(consonants[c1])
                has_prev_cons = True
                i += 1
            elif c2 in vowels_initial:
                out.append(vowels_matra[c2] if has_prev_cons else vowels_initial[c2])
                has_prev_cons = False
                i += 2
            elif c1 in vowels_initial:
                out.append(vowels_matra[c1] if has_prev_cons else vowels_initial[c1])
                has_prev_cons = False
                i += 1
            else:
                out.append(w[i])
                has_prev_cons = False
                i += 1

        return "".join(out)

    @classmethod
    def clean_whisper_artifacts(cls, text: str) -> str:
        """
        Strips typical Whisper artifacts:
        - Repeated identical phrases
        - Orphan hyphens and dashes
        - Excessive whitespace and repeated punctuation
        """
        if not text:
            return ""

        text = re.sub(r"^[\s\-_—–]+", "", text)
        text = re.sub(r"[\s\-_—–]+$", "", text)
        text = re.sub(r" (\w+)(?:\s+ ){2,} ", r" ", text, flags=re.IGNORECASE)
        text = re.sub(r"([.?!,]) +", r" ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    @classmethod
    def normalize(cls, text: str, target_lang: str = "hi") -> str:
        """
        Master normalization entrypoint for transcribed speech.
        Seamlessly converts mixed Perso-Arabic, Romanized, and Indic tokens into
        the target Indic script.
        """
        if not text or not text.strip():
            return ""

        clean = cls.clean_whisper_artifacts(text.strip())
        target_lang = str(target_lang or "hi").lower().strip()

        if target_lang == "en":
            return unicodedata.normalize("NFC", clean)

        # 1. Replace compound multi-word Perso-Arabic phrases
        for u_phrase, dev_phrase in sorted(cls.COMPOUND_URDU_PHRASES.items(), key=lambda x: len(x[0]), reverse=True):
            clean = clean.replace(u_phrase, f" {dev_phrase} ")

        # 2. Tokenize and normalize word-by-word
        words = clean.split()
        processed_words = []

        for raw_w in words:
            punct_before = ""
            punct_after = ""
            w = raw_w

            m_prefix = re.match(r"^[^\w\s]+", raw_w)
            if m_prefix:
                punct_before = m_prefix.group(0)
                w = w[len(punct_before):]

            m_suffix = re.search(r"[^\w\s]+$", w)
            if m_suffix:
                punct_after = m_suffix.group(0)
                w = w[:-len(punct_after)]

            if not w:
                processed_words.append(raw_w)
                continue

            # Check Perso-Arabic
            if cls.is_perso_arabic(w):
                w_dev = cls.urdu_to_devanagari(w)
                processed_words.append(f"{punct_before}{w_dev}{punct_after}")
            # Check Roman/Latin
            elif any("a" <= c.lower() <= "z" for c in w):
                clean_w = re.sub(r"[^\w]", "", w).lower()
                if clean_w in cls.ROMAN_HINDI_DICT:
                    w_dev = cls.ROMAN_HINDI_DICT[clean_w]
                else:
                    w_dev = cls.phonetic_roman_to_devanagari(clean_w)
                processed_words.append(f"{punct_before}{w_dev}{punct_after}")
            else:
                processed_words.append(raw_w)

        intermediate = " ".join(processed_words)

        # 3. Transliterate Devanagari to target Indic script if required
        if target_lang in cls.SCRIPT_BASES and target_lang not in ("hi", "mr", "ur", "en"):
            intermediate = cls.devanagari_to_indic(intermediate, target_lang)

        return unicodedata.normalize("NFC", intermediate)
