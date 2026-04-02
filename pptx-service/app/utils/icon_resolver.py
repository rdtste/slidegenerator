"""Icon hint → emoji resolver.

Converts descriptive icon_hint strings like "Monastery icon" or "Hopfenpflanze"
into actual emoji characters for slide rendering. Unknown hints get a
category-based fallback emoji instead of raw text.
"""

from __future__ import annotations

import re

# ── Direct keyword → emoji mapping ────────────────────────────────────────────

_ICON_MAP: dict[str, str] = {
    # Buildings & places
    "monastery": "\U0001F3DB",    # 🏛
    "kloster": "\U0001F3DB",
    "church": "\u26EA",           # ⛪
    "kirche": "\u26EA",
    "castle": "\U0001F3F0",       # 🏰
    "burg": "\U0001F3F0",
    "factory": "\U0001F3ED",      # 🏭
    "fabrik": "\U0001F3ED",
    "brewery": "\U0001F3ED",
    "brauerei": "\U0001F3ED",
    "house": "\U0001F3E0",        # 🏠
    "haus": "\U0001F3E0",
    "building": "\U0001F3E2",     # 🏢
    "gebaeude": "\U0001F3E2",
    "hospital": "\U0001F3E5",     # 🏥
    "school": "\U0001F3EB",       # 🏫
    "schule": "\U0001F3EB",
    "university": "\U0001F393",   # 🎓
    "universitaet": "\U0001F393",

    # Nature & agriculture
    "plant": "\U0001F33F",        # 🌿
    "pflanze": "\U0001F33F",
    "hop": "\U0001F33F",
    "hopfen": "\U0001F33F",
    "hopfenpflanze": "\U0001F33F",
    "tree": "\U0001F333",         # 🌳
    "baum": "\U0001F333",
    "flower": "\U0001F33A",       # 🌺
    "blume": "\U0001F33A",
    "wheat": "\U0001F33E",        # 🌾
    "weizen": "\U0001F33E",
    "grain": "\U0001F33E",
    "getreide": "\U0001F33E",
    "sun": "\u2600",              # ☀
    "sonne": "\u2600",
    "water": "\U0001F4A7",        # 💧
    "wasser": "\U0001F4A7",
    "earth": "\U0001F30D",        # 🌍
    "erde": "\U0001F30D",
    "globe": "\U0001F30D",

    # Food & drink
    "beer": "\U0001F37A",         # 🍺
    "bier": "\U0001F37A",
    "wine": "\U0001F377",         # 🍷
    "wein": "\U0001F377",
    "food": "\U0001F372",         # 🍲
    "coffee": "\u2615",           # ☕
    "kaffee": "\u2615",

    # Documents & knowledge
    "book": "\U0001F4D6",         # 📖
    "buch": "\U0001F4D6",
    "scroll": "\U0001F4DC",       # 📜
    "document": "\U0001F4C4",     # 📄
    "dokument": "\U0001F4C4",
    "pen": "\U0001F58A",          # 🖊
    "feder": "\U0001F58B",        # 🖋
    "quill": "\U0001F58B",
    "certificate": "\U0001F4DC",
    "zertifikat": "\U0001F4DC",
    "law": "\u2696",              # ⚖
    "gesetz": "\u2696",
    "recht": "\u2696",

    # Technology & science
    "computer": "\U0001F4BB",     # 💻
    "laptop": "\U0001F4BB",
    "phone": "\U0001F4F1",        # 📱
    "smartphone": "\U0001F4F1",
    "gear": "\u2699",             # ⚙
    "zahnrad": "\u2699",
    "settings": "\u2699",
    "microscope": "\U0001F52C",   # 🔬
    "mikroskop": "\U0001F52C",
    "science": "\U0001F52C",
    "wissenschaft": "\U0001F52C",
    "robot": "\U0001F916",        # 🤖
    "ai": "\U0001F916",
    "ki": "\U0001F916",
    "rocket": "\U0001F680",       # 🚀
    "rakete": "\U0001F680",
    "lightning": "\u26A1",        # ⚡
    "blitz": "\u26A1",
    "energy": "\u26A1",
    "energie": "\u26A1",

    # People & communication
    "people": "\U0001F465",       # 👥
    "menschen": "\U0001F465",
    "team": "\U0001F465",
    "person": "\U0001F464",       # 👤
    "handshake": "\U0001F91D",    # 🤝
    "speech": "\U0001F4AC",       # 💬
    "sprache": "\U0001F4AC",
    "mail": "\U0001F4E7",         # 📧
    "email": "\U0001F4E7",
    "heart": "\u2764",            # ❤
    "herz": "\u2764",

    # Business & finance
    "chart": "\U0001F4C8",        # 📈
    "graph": "\U0001F4C8",
    "money": "\U0001F4B0",        # 💰
    "geld": "\U0001F4B0",
    "euro": "\U0001F4B6",         # 💶
    "dollar": "\U0001F4B5",       # 💵
    "target": "\U0001F3AF",       # 🎯
    "ziel": "\U0001F3AF",
    "trophy": "\U0001F3C6",       # 🏆
    "pokal": "\U0001F3C6",
    "medal": "\U0001F3C5",        # 🏅
    "award": "\U0001F3C5",
    "key": "\U0001F511",          # 🔑
    "schluessel": "\U0001F511",

    # Symbols & abstract
    "shield": "\U0001F6E1",       # 🛡
    "schild": "\U0001F6E1",
    "check": "\u2705",            # ✅
    "checkmark": "\u2705",
    "star": "\u2B50",             # ⭐
    "stern": "\u2B50",
    "light": "\U0001F4A1",        # 💡
    "bulb": "\U0001F4A1",
    "idea": "\U0001F4A1",
    "idee": "\U0001F4A1",
    "clock": "\u23F0",            # ⏰
    "uhr": "\u23F0",
    "time": "\u23F0",
    "zeit": "\u23F0",
    "lock": "\U0001F512",         # 🔒
    "schloss": "\U0001F512",
    "arrow": "\u27A1",            # ➡
    "pfeil": "\u27A1",
    "link": "\U0001F517",         # 🔗
    "connection": "\U0001F517",
    "verbindung": "\U0001F517",
    "puzzle": "\U0001F9E9",       # 🧩
    "eye": "\U0001F441",          # 👁
    "auge": "\U0001F441",
    "map": "\U0001F5FA",          # 🗺
    "karte": "\U0001F5FA",
    "landkarte": "\U0001F5FA",
    "pin": "\U0001F4CD",          # 📍
    "location": "\U0001F4CD",
    "flag": "\U0001F3F3",         # 🏳
    "flagge": "\U0001F3F3",

    # Transport
    "car": "\U0001F697",          # 🚗
    "auto": "\U0001F697",
    "train": "\U0001F682",        # 🚂
    "zug": "\U0001F682",
    "ship": "\U0001F6A2",         # 🚢
    "schiff": "\U0001F6A2",
    "plane": "\u2708",            # ✈
    "flugzeug": "\u2708",
}

# Category fallbacks when no keyword match
_CATEGORY_FALLBACKS: list[tuple[list[str], str]] = [
    (["icon", "symbol", "zeichen"], "\U0001F4A0"),    # 💠
    (["image", "bild", "foto", "photo"], "\U0001F5BC"),  # 🖼
    (["number", "zahl", "nummer"], "\U0001F522"),      # 🔢
]

_DEFAULT_EMOJI = "\U0001F4A0"  # 💠 diamond with dot — neutral category marker


def resolve_icon_hint(hint: str) -> str:
    """Convert an icon_hint string to an emoji character.

    Tries exact keyword matching first, then fuzzy matching against
    known terms. Returns a category fallback if nothing matches.

    Examples:
        "Monastery icon" → "🏛"
        "Shield or scroll icon" → "🛡"
        "Hopfenpflanze" → "🌿"
        "Buch mit Feder" → "📖"
        "Landkarte mit Pin" → "🗺"
        "Unknown thing" → "💠"
    """
    if not hint or not hint.strip():
        return ""

    # Normalize: lowercase, strip common suffixes
    normalized = hint.lower().strip()
    normalized = re.sub(r'\s*(icon|symbol|emoji|zeichen|bild)\s*$', '', normalized).strip()

    # Direct lookup
    if normalized in _ICON_MAP:
        return _ICON_MAP[normalized]

    # Split into words and try each
    words = re.split(r'[\s,/+&-]+', normalized)
    for word in words:
        word = word.strip()
        if word in _ICON_MAP:
            return _ICON_MAP[word]

    # Try compound words (German): "hopfenpflanze" → check "hopfen", "pflanze"
    for length in range(3, len(normalized)):
        prefix = normalized[:length]
        if prefix in _ICON_MAP:
            return _ICON_MAP[prefix]

    # Category fallbacks
    for keywords, emoji in _CATEGORY_FALLBACKS:
        if any(kw in normalized for kw in keywords):
            return emoji

    return _DEFAULT_EMOJI
