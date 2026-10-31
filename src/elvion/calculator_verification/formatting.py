"""Format-only diagnostics: counts/categories, never the displayed number."""
from collections import Counter
import re
import unicodedata


def parse_display_number(text):
    """Parse a simple ASCII number with observed edge-only LRM decoration.

    U+200E was observed in the native AX string. Do not erase format controls
    in the number, other bidi controls, signs, separators or expression syntax.
    """
    if type(text) is not str or len(text)>64:
        return None
    value=text.strip(' \u200e')
    return value if re.fullmatch(r'-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?',value) else None


def numeric_format_summary(text):
    if type(text) is not str:
        return {'text_available':False}
    sample=text[:256]
    presentation=Counter(f'U+{ord(c):04X}' for c in sample
                         if c.isspace() or unicodedata.category(c)=='Cf')
    syntax=Counter(c for c in sample if c in '+-.,/×÷=()')
    return {'text_available':True,'length':len(text),'truncated':len(text)>256,
            'ascii_digit_count':sum(c in '0123456789' for c in sample),
            'unicode_categories':dict(Counter(unicodedata.category(c) for c in sample)),
            'presentation_codepoints':dict(presentation),'syntax_counts':dict(syntax)}
