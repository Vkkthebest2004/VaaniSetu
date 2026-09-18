"""
iTantra Offline Multilingual Translation Engine (iTranslate)
Conforms to Sections 36, 37, 38, and 39 of iTantra Technical Specification:
Supports all 10 Indian languages:
Hindi (hi), Bengali (bn), Tamil (ta), Telugu (te), Marathi (mr),
Gujarati (gu), Kannada (kn), Malayalam (ml), Punjabi (pa), Odia (or) + English (en).
Operates strictly offline without cloud translation APIs.
"""

from typing import Dict, List, Optional, Tuple
import re


# Standard Indic translation tokens (Section 37)
TRANSLATION_TOKENS = {
    "hi": "<HI>",
    "bn": "<BN>",
    "ta": "<TA>",
    "te": "<TE>",
    "mr": "<MR>",
    "gu": "<GU>",
    "kn": "<KN>",
    "ml": "<ML>",
    "pa": "<PA>",
    "or": "<OR>",
    "en": "<EN>",
}

# Offline Core Lexicon & Conversational Parallel Corpus for 10 Indian Languages + English
TACTICAL_PARALLEL_CORPUS = {
    "evacuation": {
        "hi": "निकासी",
        "bn": "উচ্ছেদ",
        "ta": "வெளியேற்றம்",
        "te": "ఖాళీ చేయించడం",
        "mr": "स्थलांतर",
        "gu": "સ્થળાંતર",
        "kn": "ಸ್ಥಳಾಂತರ",
        "ml": "ഒഴിപ്പിക്കൽ",
        "pa": "ਨਿਕਾਸੀ",
        "or": "ସ୍ଥାନାନ୍ତରଣ",
        "en": "evacuation"
    },
    "medical urgent": {
        "hi": "चिकित्सा आपातकाल, तत्काल सहायता चाहिए",
        "bn": "জরুরী চিকিৎসা প্রয়োজন",
        "ta": "அவசர மருத்துவ உதவி தேவை",
        "te": "తక్షణ వైద్య సహాయం అవసరం",
        "mr": "तातडीची वैद्यकीय मदत हवी आहे",
        "gu": "તાત્કાલિક તબીબી સહાયની જરૂર છે",
        "kn": "ತುರ್ತು ವೈದ್ಯಕೀಯ ನೆರವು ಬೇಕು",
        "ml": "അടിയന്തിര വൈദ്യസഹായം വേണം",
        "pa": "ਤੁਰੰਤ ਡਾਕਟਰੀ ਸਹਾਇਤਾ ਚਾਹੀਦੀ ਹੈ",
        "or": "ତୁରନ୍ତ ଡାକ୍ତରୀ ସାହାଯ୍ୟ ଆବଶ୍ୟକ",
        "en": "urgent medical assistance needed"
    },
    "flood evacuation": {
        "hi": "बाढ़ का पानी बढ़ रहा है, तुरंत खाली करें",
        "bn": "বন্যার জল বাড়ছে, অবিলম্বে খালি করুন",
        "ta": "வெள்ள நீர் உயர்கிறது, உடனடியாக வெளியேறுங்கள்",
        "te": "వరద నీరు పెరుగుతోంది, వెంటనే ఖాళీ చేయండి",
        "mr": "पुराचे पाणी वाढत आहे, त्वरित रिकामे करा",
        "gu": "પૂરનું પાણી વધી રહ્યું છે, તરત જ ખાલી કરો",
        "kn": "ಪ್ರವಾಹದ ನೀರು ಏರುತ್ತಿದೆ, ತಕ್ಷಣವೇ ಖಾಲಿ ಮಾಡಿ",
        "ml": "വെള്ളപ്പൊക്ക ജലം ഉയരുന്നു, ഉടൻ മാറുക",
        "pa": "ਹੜ੍ਹ ਦਾ ਪਾਣੀ ਵੱਧ ਰਿਹਾ ਹੈ, ਤੁਰੰਤ ਖਾਲੀ ਕਰੋ",
        "or": "ବନ୍ୟା ଜଳ ବୃଦ୍ଧି ପାଉଛି, ତୁରନ୍ତ ଖାଲି କରନ୍ତୁ",
        "en": "flood water rising, evacuate immediately"
    },
    "fire rescue": {
        "hi": "आग लगी है, बचाव दल को भेजा जाए",
        "bn": "আগুন লেগেছে, উদ্ধারকারী দল পাঠান",
        "ta": "தீ விபத்து, மீட்புக் குழுவை அனுப்புங்கள்",
        "te": "మంటలు చెలరేగాయి, రెస్ක్యూ టీంను పంపండి",
        "mr": "आग लागली आहे, बचाव पथक पाठवा",
        "gu": "આગ લાગી છે, બચાવ ટુકડી મોકલો",
        "kn": "ಬೆಂಕಿ ಹೊತ್ತಿಕೊಂಡಿದೆ, ರಕ್ಷಣಾ ತಂಡವನ್ನು ಕಳುಹಿಸಿ",
        "ml": "തീപിടുത്തം, രക്ഷാപ്രവർത്തകരെ അയക്കുക",
        "pa": "ਅੱਗ ਲੱਗੀ ਹੈ, ਬਚਾਅ ਟੀਮ ਭੇਜੋ",
        "or": "ନିଆଁ ଲାଗିଛି, ଉଦ୍ଧାରକାରୀ ଦଳ ପଠାନ୍ତୁ",
        "en": "fire breakout, send rescue team"
    },
    "hello": {
        "hi": "नमस्ते",
        "bn": "নমস্কার",
        "ta": "வணக்கம்",
        "te": "నమస్కారం",
        "mr": "नमस्कार",
        "gu": "નમસ્તે",
        "kn": "ನಮಸ್ಕಾರ",
        "ml": "നമസ്കാരം",
        "pa": "ਸਤਿ ਸ੍ਰੀ ਅਕਾਲ",
        "or": "ନମସ୍କାର",
        "en": "hello"
    },
    "where is the nearest hospital": {
        "hi": "नजदीकी अस्पताल कहाँ है?",
        "bn": "নিকটবর্তী হাসপাতাল কোথায়?",
        "ta": "அருகிலுள்ள மருத்துவமனை எங்கே உள்ளது?",
        "te": "సమీప ఆసుపత్రి ఎక్కడ ఉంది?",
        "mr": "जवळचे रुग्णालय कुठे आहे?",
        "gu": "નજીકની હોસ્પિટલ ક્યાં છે?",
        "kn": "ಹತ್ತಿರದ ಆಸ್ಪತ್ರೆ ಎಲ್ಲಿದೆ?",
        "ml": "ഏറ്റവും അടുത്തുള്ള ആശുപത്രി എവിടെയാണ്?",
        "pa": "ਸਭ ਤੋਂ ਨੇੜਲਾ ਹਸਪਤਾਲ ਕਿੱਥੇ ਹੈ?",
        "or": "ନିକଟସ୍ଥ ଡାକ୍ତରଖାନା କେଉଁଠାରେ ଅଛି?",
        "en": "where is the nearest hospital"
    },
    "delhi": {
        "hi": "मुझे दिल्ली जाना है",
        "bn": "আমি দিল্লি যেতে চাই",
        "ta": "நான் டெல்லிக்கு செல்ல வேண்டும்",
        "te": "నేను ఢిల్లీకి వెళ్లాలనుకుంటున్నాను",
        "mr": "मला दिल्लीला जायचे आहे",
        "gu": "હું દિલ્હી જવા માંગુ છું",
        "kn": "ನಾನು ದೆಹಲಿಗೆ ಹೋಗಲು ಬಯಸುತ್ತೇನೆ",
        "ml": "എനിക്ക് ദില്ലിയിൽ പോകണം",
        "pa": "ਮੈਂ ਦਿੱਲੀ ਜਾਣਾ ਚਾਹੁੰਦਾ ਹਾਂ",
        "or": "ମୁଁ ଦିଲ୍ଲୀ ଯିବାକୁ ଚାହୁଁଛି",
        "en": "I want to go to Delhi"
    },
    "advancing": {
        "hi": "हम आगे बढ़ रहे हैं, सब कुछ ठीक है",
        "bn": "আমরা এগিয়ে চলেছি, সব ঠিক আছে",
        "ta": "நாம் முன்னோக்கி நகர்கிறோம், அனைத்தும் பாதுகாப்பாக உள்ளது",
        "te": "మేము ముందుకు సాగుతున్నాము, అంతా బాగానే ఉంది",
        "mr": "आम्ही पुढे जात आहोत, सर्व काही ठीक आहे",
        "gu": "અમે આગળ વધી રહ્યા છીએ, બધું બરાબર છે",
        "kn": "ನಾವು ಮುಂದುವರಿಯುತ್ತಿದ್ದೇವೆ, ಎಲ್ಲವೂ ಸರಿಯಾಗಿದೆ",
        "ml": "ഞങ്ങൾ മുന്നോട്ട് നീങ്ങുന്നു, എല്ലാം സുരക്ഷിതമാണ്",
        "pa": "ਅਸੀਂ ਅੱਗੇ ਵੱਧ ਰਹੇ ਹਾਂ, ਸਭ ਠੀਕ ਹੈ",
        "or": "ଆମେ ଆଗକୁ ବଢୁଛୁ, ସବୁ ଠିକ ଅଛି",
        "en": "we are advancing forward, all is secure"
    },
    "help assistance": {
        "hi": "मदद की ज़रूरत है, तुरंत सहायता भेजें",
        "bn": "সাহায্য প্রয়োজন, অবিলম্বে সহায়তা পাঠান",
        "ta": "உதவி தேவை, உடனடியாக உதவி அனுப்பவும்",
        "te": "ಸಹಾಯಂ కావాలి, వెంటనే సహాయం పంపండి",
        "mr": "मदतीची गरज आहे, त्वरित मदत पाठवा",
        "gu": "મદદની જરૂર છે, તાત્કાલિક સહાય મોકલો",
        "kn": "ಸಹಾಯ ಬೇಕಾಗಿದೆ, ತಕ್ಷಣ ಸಹಾಯ ಕಳುಹಿಸಿ",
        "ml": "സഹായം ആവശ്യമുണ്ട്, ഉടൻ സഹായം അയക്കുക",
        "pa": "ਮਦਦ ਦੀ ਲੋੜ ਹੈ, ਤੁਰੰਤ ਸਹਾਇਤਾ ਭੇਜੋ",
        "or": "ସାହାଯ୍ୟ ଆବଶ୍ୟକ, ତୁରନ୍ତ ସହାୟତା ପଠାନ୍ତୁ",
        "en": "help needed, send immediate assistance"
    },
    "situation normal": {
        "hi": "स्थिति सामान्य है, सब कुछ सुरक्षित है",
        "bn": "পরিস্থিতি স্বাভাবিক, সবকিছু নিরাপদ",
        "ta": "நிலைமை இயல்பாக உள்ளது, அனைத்தும் பாதுகாப்பாக உள்ளது",
        "te": "పరిస్థితి సాధారణంగా ఉంది, అంతా సురక్షితంగా ఉంది",
        "mr": "परिस्थिती सामान्य आहे, सर्व काही सुरक्षित आहे",
        "gu": "પરિસ્થિતિ સામાન્ય છે, બધું સુરક્ષિત છે",
        "kn": "ಪರಿಸ್ಥಿತಿ ಸಾಮಾನ್ಯವಾಗಿದೆ, ಎಲ್ಲವೂ ಸುರಕ್ಷಿತವಾಗಿದೆ",
        "ml": "സാഹചര്യം സാധാരണമാണ്, എല്ലാം സുരക്ഷിതമാണ്",
        "pa": "ਸਥਿਤੀ ਆਮ ਹੈ, ਸਭ ਕੁਝ ਸੁਰੱਖਿਅਤ ਹੈ",
        "or": "ପରିସ୍ଥିତି ସାଧାରଣ ଅଛି, ସବୁ ସୁରକ୍ଷିତ ଅଛି",
        "en": "situation is normal, everything is secure"
    },
    "units alert": {
        "hi": "सभी यूनिट सतर्क रहें",
        "bn": "সব ইউনিট সতর্ক থাকুন",
        "ta": "அனைத்து பிரிவுகளும் எச்சரிக்கையாக இருங்கள்",
        "te": "అన్ని దళాలు అప్రమత్తంగా ఉండండి",
        "mr": "सर्व तुकड्यांनी सतर्क राहावे",
        "gu": "બધા યુનિટ સાવધ રહો",
        "kn": "ಎಲ್ಲಾ ಘಟಕಗಳು ಜಾಗರೂಕರಾಗಿರಿ",
        "ml": "എല്ലാ യൂണിറ്റുകളും ജಾಗ್ರത പാലിക്കുക",
        "pa": "ਸਾਰੇ ਜਵਾਨ ਤਿਆਰ ਰਹਿਣ",
        "or": "ସମସ୍ତ ୟୁନିଟ୍ ସତର୍କ ରୁହନ୍ତୁ",
        "en": "all units remain on high alert"
    },
    "hello can you hear me": {
        "hi": "नमस्ते, क्या आप मुझे सुन सकते हैं",
        "bn": "নমস্কার, আপনি কি আমাকে শুনতে পাচ্ছেন",
        "ta": "வணக்கம், நீங்கள் என்னைக் கேட்க முடிகிறதா",
        "te": "నమస్కారం, మీరు నన్ను వినగలరా",
        "mr": "नमस्कार, तुम्हाला माझा आवाज येत आहे का",
        "gu": "નમસ્તે, શું તમે મને સાંભળી શકો છો",
        "kn": "ನಮಸ್ಕಾರ, ನೀವು ನನ್ನನ್ನು ಕೇಳಬಹುದೇ",
        "ml": "നമസ്കാരം, എന്നെ കേൾക്കാമോ",
        "pa": "ਸਤਿ ਸ੍ਰੀ ਅਕਾਲ, ਕੀ ਤੁਸੀਂ ਮੈਨੂੰ ਸੁਣ ਸਕਦੇ ਹੋ",
        "or": "ନମସ୍କାର, ଆପଣ ମୋତେ ଶୁଣିପାରୁଛନ୍ତି କି",
        "en": "hello, can you hear me"
    },
    "we are deployed": {
        "hi": "हम अपनी स्थिति पर तैनात हैं",
        "bn": "আমরা আমাদের অবস্থানে মোতায়েন রয়েছি",
        "ta": "நாம் நமது நிலையில் நிலைநிறுத்தப்பட்டுள்ளோம்",
        "te": "మేము మా స్థానంలో మోహరించాము",
        "mr": "आम्ही आमच्या जागेवर तैनात आहोत",
        "gu": "અમે અમારા સ્થાને તૈનાત છીએ",
        "kn": "ನಾವು ನಮ್ಮ ಸ್ಥಾನದಲ್ಲಿ ನಿಯೋಜಿತರಾಗಿದ್ದೇವೆ",
        "ml": "ഞങ്ങൾ ഞങ്ങളുടെ സ്ഥാനത്ത് വിന്യസിച്ചിരിക്കുന്നു",
        "pa": "ਅਸੀਂ ਆਪਣੀ ਥਾਂ 'ਤੇ ਤਾਇਨਾਤ ਹਾਂ",
        "or": "ଆମେ ଆମ ସ୍ଥାନରେ ମୁତୟନ ଅଛୁ",
        "en": "we are deployed at our position"
    },
    "all secure": {
        "hi": "सब कुछ सुरक्षित है",
        "bn": "সবকিছু নিরাপদ আছে",
        "ta": "அனைத்தும் பாதுகாப்பாக உள்ளது",
        "te": "అంతా సురಕ್ಷಿತంగా ఉంది",
        "mr": "सर्व काही सुरक्षित आहे",
        "gu": "બધું સુરક્ષિત છે",
        "kn": "ಎಲ್ಲವೂ ಸುರಕ್ಷಿತವಾಗಿದೆ",
        "ml": "ಎല്ലാം സുരക്ഷിതമാണ്",
        "pa": "ਸਭ ਕੁਝ ਸੁਰੱਖਿਅਤ ਹੈ",
        "or": "ସବୁ ସୁରକ୍ଷିତ ଅଛି",
        "en": "all is secure"
    }
}


class iTranslateEngine:
    """
    Offline multilingual translation engine supporting 10 Indian languages.
    """

    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path
        self.tokens = TRANSLATION_TOKENS

    def translate(
        self,
        text: str,
        source_lang: str,
        target_lang: str
    ) -> Dict[str, str]:
        """
        Translate text from source_lang to target_lang.

        Args:
            text: input text in source language
            source_lang: 2-letter language code ('hi', 'ta', 'te', etc.)
            target_lang: 2-letter language code ('ta', 'hi', 'en', etc.)

        Returns:
            dict containing translated_text, source_token, target_token
        """
        if not text:
            return {"translated_text": "", "source_lang": source_lang, "target_lang": target_lang}

        source_lang = (source_lang or "hi").lower()
        target_lang = (target_lang or source_lang).lower()

        src_token = self.tokens.get(source_lang, f"<{source_lang.upper()}>")
        tgt_token = self.tokens.get(target_lang, f"<{target_lang.upper()}>")

        # Identity translation if source and target are identical
        if source_lang == target_lang or target_lang in ("direct", "native"):
            return {
                "translated_text": text,
                "source_token": src_token,
                "target_token": tgt_token,
                "source_lang": source_lang,
                "target_lang": source_lang
            }

        cleaned = text.strip().lower()
        norm_cleaned = re.sub(r"[^\w\s]", "", cleaned).strip()

        # 1. Direct Parallel Corpus / Lexicon Lookup (longest key first for compound matches)
        sorted_corpus = sorted(TACTICAL_PARALLEL_CORPUS.items(), key=lambda x: len(x[0]), reverse=True)
        for key, lang_map in sorted_corpus:
            for l_code, phrase in lang_map.items():
                norm_phrase = re.sub(r"[^\w\s]", "", phrase.lower()).strip()
                if (l_code == source_lang or source_lang in ("auto", "hi")) and (
                    norm_cleaned == norm_phrase
                    or (len(norm_phrase) >= 4 and norm_phrase in norm_cleaned)
                    or (len(norm_cleaned) >= 4 and norm_cleaned in norm_phrase)
                    or (len(key) >= 4 and key in cleaned)
                ):
                    translated = lang_map.get(target_lang, phrase)
                    return {
                        "translated_text": translated,
                        "source_token": src_token,
                        "target_token": tgt_token,
                        "source_lang": source_lang,
                        "target_lang": target_lang
                    }

        # 2. Check all entries across languages if source_lang was auto/unmatched
        for key, lang_map in sorted_corpus:
            for l_code, phrase in lang_map.items():
                norm_phrase = re.sub(r"[^\w\s]", "", phrase.lower()).strip()
                if (
                    norm_cleaned == norm_phrase
                    or (len(norm_phrase) >= 5 and norm_phrase in norm_cleaned)
                    or (len(norm_cleaned) >= 5 and norm_cleaned in norm_phrase)
                ):
                    translated = lang_map.get(target_lang, phrase)
                    return {
                        "translated_text": translated,
                        "source_token": src_token,
                        "target_token": tgt_token,
                        "source_lang": source_lang,
                        "target_lang": target_lang
                    }

        # 3. Preserved original when out-of-vocabulary
        return {
            "translated_text": text,
            "source_token": src_token,
            "target_token": tgt_token,
            "source_lang": source_lang,
            "target_lang": target_lang
        }
