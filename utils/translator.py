from deep_translator import GoogleTranslator

def translate_text(text: str, target: str = 'en') -> str:
    try:
        translator = GoogleTranslator(source='auto', target=target)
        return translator.translate(text)
    except Exception as e:
        print(f"Translation error: {e}")
        return "Translation failed."