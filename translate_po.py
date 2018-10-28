import argparse
import functools
import json
import os
import sys

from google.cloud import translate

_cache_home = "."
_cache_filename = "po-translation-cache.json"
_translated_text_length = 0

service_account_json_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
translate_client = translate.Client.from_service_account_json(service_account_json_path)


def calculate_fee(text_len, dollar_per_currency=None):
    """
    https://cloud.google.com/translate/pricing?hl=en

    * Google charges on per character basis, even if the character is multiple bytes,
      where a character corresponds to a (code-point).
    * Google does not charge extra for language detection when you do not specify
      the source language for the translate method.
    """
    if dollar_per_currency is None:
        dollar_per_currency = 1  # dollar
    dollar = text_len / (10 ** 6) * 20
    return dollar_per_currency * dollar


def cache_translation(callback):
    @functools.wraps(callback)
    def decorated(*args, **kwargs):
        file_path = os.path.join(_cache_home, _cache_filename)
        key = f"{args[0]}:{args[1]}"
        cache = {}
        try:
            with open(file_path) as f:
                cache = json.load(f)
        except FileNotFoundError:
            pass
        cached = cache.get(key)
        if cached:
            return cached
        result = callback(*args, **kwargs)
        cache[key] = result
        with open(file_path, "w") as f:
            json.dump(cache, f, indent=4)
        return result
    return decorated


@cache_translation
def translate(text, target_lang):
    if text == "":
        return ""
    global _translated_text_length
    _translated_text_length += len(text)
    translation = translate_client.translate(text, target_language=target_lang)
    return translation.get('translatedText')


def parse_po(filepath, target_lang):
    with open(filepath) as f:
        for line in f:
            if line.startswith("msgstr "):
                continue
            print(line, end="")
            if line.startswith("msgid"):
                text = line[len("msgid"):].strip(' "\n')
                translation = translate(text, target_lang)
                print(f'msgstr "{translation}"')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("filepath")
    parser.add_argument('--lang', default="ja", type=str,
                        help='target language (default: "ja")')
    parser.add_argument('--currency', default=111.90, type=float,
                        help='dollar per your currency. (default currency is yen: 111.90)')
    args = parser.parse_args()
    parse_po(args.filepath, args.lang)

    fee = calculate_fee(_translated_text_length, dollar_per_currency=args.currency)
    print("Cost: {} yen".format(fee), file=sys.stderr)


if __name__ == '__main__':
    main()
