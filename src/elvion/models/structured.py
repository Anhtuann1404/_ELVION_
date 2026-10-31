"""Provider-independent JSON parsing for bounded model proposals."""
import json

MAX_CONTENT_BYTES = 8 * 1024


def strict_json(value: str):
    def unique(pairs):
        result = {}
        for key, item in pairs:
            if key in result:
                raise ValueError("Duplicate key")
            result[key] = item
        return result

    def invalid_constant(value):
        raise ValueError("Invalid number")
    return json.loads(value, object_pairs_hook=unique, parse_constant=invalid_constant)
