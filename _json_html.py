"""Serialize JSON for an HTML script raw-text element, preserving its values."""
import json


def script_json(value) -> str:
    # HTML parsers recognize </script> even inside JSON strings. Escaping the
    # opening bracket also protects legacy <!-- / <script parsing states.
    return json.dumps(value, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c')
