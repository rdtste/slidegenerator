"""Audience and image style profile text blocks for V2 pipeline prompts."""

from __future__ import annotations


AUDIENCE_PROFILES: dict[str, str] = {
    "management": (
        "Zielgruppe Management: Executive-Level. "
        "Kurze, verdichtete Aussagen. Jeder Bullet braucht Bold-Prefix. "
        "Zahlen und KPIs priorisieren. Wenig Text, viel Weissraum. "
        "Maximal 4 Bullets pro Folie. Headline muss die Kernaussage enthalten."
    ),
    "team": (
        "Zielgruppe Team: Intern, handlungsorientiert. "
        "Klare Anweisungen, konkrete naechste Schritte. Moderate Textdichte. "
        "Bis zu 5 Bullets erlaubt. Verantwortlichkeiten und Deadlines benennen."
    ),
    "customer": (
        "Zielgruppe Kunde/Extern: Professionell, ueberzeugend. "
        "Hochwertige Sprache, keine internen Begriffe. Visuell ansprechend. "
        "Nutzen und Mehrwert in den Vordergrund stellen. "
        "Maximal 4 Bullets pro Folie."
    ),
    "workshop": (
        "Zielgruppe Workshop: Offen, kollaborativ, fragend. "
        "Raum fuer Diskussion lassen. Interaktive Elemente. "
        "Offene Fragen als Headlines. Weniger Content pro Folie, "
        "mehr Denkraum."
    ),
}

IMAGE_STYLE_PROFILES: dict[str, str] = {
    "photo": (
        "Bildstil Fotografie: Realistische Business-Fotos. "
        "Mindestens 20% der Folien mit Bild. "
        "image_fullbleed und image_text_split bevorzugt einsetzen."
    ),
    "illustration": (
        "Bildstil Illustration: Moderne Flat-Illustrationen. "
        "Icons in Cards und Prozessen. "
        "Passende icon_hint Werte in CardBlocks setzen."
    ),
    "minimal": (
        "Bildstil Minimal: Keine Fotos. "
        "Nur geometrische Formen und Line-Icons. Viel Weissraum. "
        "Keine image_fullbleed verwenden."
    ),
    "data_visual": (
        "Bildstil Data Visual: Charts und Diagramme bevorzugt. "
        "Mindestens 2 chart_insight pro Deck. "
        "Daten visuell aufbereiten wo moeglich."
    ),
    "none": (
        "Kein Bildstil: Reine Typografie. "
        "Keine Bilder, keine image_fullbleed, keine image_text_split. "
        "Visual.type muss immer 'none' sein."
    ),
}


def get_audience_profile(audience: str) -> str:
    """Return audience profile text, falling back to management."""
    return AUDIENCE_PROFILES.get(audience, AUDIENCE_PROFILES["management"])


def get_image_style_profile(image_style: str) -> str:
    """Return image style profile text, falling back to minimal."""
    return IMAGE_STYLE_PROFILES.get(image_style, IMAGE_STYLE_PROFILES["minimal"])
