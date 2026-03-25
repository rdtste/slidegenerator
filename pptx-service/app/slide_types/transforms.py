"""Transform mappings — theme, beat, audience and image-style modifiers for
slide-type selection during storyline-to-plan conversion."""

from __future__ import annotations

from app.schemas.models import Audience, BeatType, ImageStyleType, SlideType

# ---------------------------------------------------------------------------
# Content-theme to preferred slide types
# ---------------------------------------------------------------------------

THEME_TO_SLIDE_TYPE: dict[str, list[SlideType]] = {
    "introduction": [SlideType.TITLE_HERO, SlideType.KEY_STATEMENT],
    "overview": [SlideType.AGENDA, SlideType.BULLETS_FOCUSED],
    "problem": [SlideType.KEY_STATEMENT, SlideType.IMAGE_TEXT_SPLIT],
    "solution": [SlideType.THREE_CARDS, SlideType.BULLETS_FOCUSED, SlideType.IMAGE_TEXT_SPLIT],
    "data": [SlideType.CHART_INSIGHT, SlideType.KPI_DASHBOARD],
    "metrics": [SlideType.KPI_DASHBOARD, SlideType.CHART_INSIGHT],
    "comparison": [SlideType.COMPARISON, SlideType.THREE_CARDS],
    "timeline": [SlideType.TIMELINE],
    "process": [SlideType.PROCESS_FLOW, SlideType.TIMELINE],
    "vision": [SlideType.IMAGE_FULLBLEED, SlideType.KEY_STATEMENT],
    "benefits": [SlideType.THREE_CARDS, SlideType.BULLETS_FOCUSED],
    "risks": [SlideType.BULLETS_FOCUSED, SlideType.COMPARISON],
    "next_steps": [SlideType.PROCESS_FLOW, SlideType.BULLETS_FOCUSED],
    "summary": [SlideType.BULLETS_FOCUSED, SlideType.CLOSING],
    "quote": [SlideType.KEY_STATEMENT],
    "team": [SlideType.THREE_CARDS, SlideType.IMAGE_TEXT_SPLIT],
    "results": [SlideType.KPI_DASHBOARD, SlideType.CHART_INSIGHT, SlideType.BULLETS_FOCUSED],
    "strategy": [SlideType.BULLETS_FOCUSED, SlideType.THREE_CARDS, SlideType.PROCESS_FLOW],
    "closing": [SlideType.CLOSING, SlideType.KEY_STATEMENT],
}

# ---------------------------------------------------------------------------
# Beat type to preferred slide types
# ---------------------------------------------------------------------------

BEAT_TO_SLIDE_TYPE: dict[BeatType, list[SlideType]] = {
    BeatType.OPENING: [
        SlideType.TITLE_HERO,
        SlideType.IMAGE_FULLBLEED,
        SlideType.KEY_STATEMENT,
    ],
    BeatType.CONTEXT: [
        SlideType.BULLETS_FOCUSED,
        SlideType.AGENDA,
        SlideType.IMAGE_TEXT_SPLIT,
    ],
    BeatType.EVIDENCE: [
        SlideType.CHART_INSIGHT,
        SlideType.KPI_DASHBOARD,
        SlideType.COMPARISON,
        SlideType.IMAGE_TEXT_SPLIT,
    ],
    BeatType.INSIGHT: [
        SlideType.KEY_STATEMENT,
        SlideType.THREE_CARDS,
        SlideType.BULLETS_FOCUSED,
    ],
    BeatType.ACTION: [
        SlideType.PROCESS_FLOW,
        SlideType.BULLETS_FOCUSED,
        SlideType.THREE_CARDS,
        SlideType.TIMELINE,
    ],
    BeatType.TRANSITION: [
        SlideType.SECTION_DIVIDER,
        SlideType.KEY_STATEMENT,
    ],
    BeatType.CLOSING: [
        SlideType.CLOSING,
        SlideType.KEY_STATEMENT,
        SlideType.IMAGE_FULLBLEED,
    ],
}

# ---------------------------------------------------------------------------
# Audience modifiers
# ---------------------------------------------------------------------------

AUDIENCE_MODIFIERS: dict[Audience, dict[str, list[SlideType]]] = {
    Audience.MANAGEMENT: {
        "prefer": [
            SlideType.KPI_DASHBOARD,
            SlideType.KEY_STATEMENT,
            SlideType.CHART_INSIGHT,
        ],
        "avoid": [
            SlideType.PROCESS_FLOW,
            SlideType.TIMELINE,
        ],
        "require_one_of": [
            SlideType.KPI_DASHBOARD,
            SlideType.CHART_INSIGHT,
        ],
    },
    Audience.TEAM: {
        "prefer": [
            SlideType.BULLETS_FOCUSED,
            SlideType.PROCESS_FLOW,
            SlideType.TIMELINE,
        ],
        "avoid": [],
        "require_one_of": [],
    },
    Audience.CUSTOMER: {
        "prefer": [
            SlideType.IMAGE_FULLBLEED,
            SlideType.THREE_CARDS,
            SlideType.KEY_STATEMENT,
            SlideType.IMAGE_TEXT_SPLIT,
        ],
        "avoid": [
            SlideType.KPI_DASHBOARD,
        ],
        "require_one_of": [
            SlideType.IMAGE_FULLBLEED,
            SlideType.IMAGE_TEXT_SPLIT,
        ],
    },
    Audience.WORKSHOP: {
        "prefer": [
            SlideType.BULLETS_FOCUSED,
            SlideType.COMPARISON,
            SlideType.THREE_CARDS,
            SlideType.PROCESS_FLOW,
        ],
        "avoid": [
            SlideType.IMAGE_FULLBLEED,
        ],
        "require_one_of": [],
    },
}

# ---------------------------------------------------------------------------
# Image-style modifiers
# ---------------------------------------------------------------------------

IMAGE_STYLE_MODIFIERS: dict[ImageStyleType, dict] = {
    ImageStyleType.PHOTO: {
        "allow_image_slides": True,
        "prefer": [
            SlideType.IMAGE_FULLBLEED,
            SlideType.IMAGE_TEXT_SPLIT,
        ],
        "forbid": [],
    },
    ImageStyleType.ILLUSTRATION: {
        "allow_image_slides": True,
        "prefer": [
            SlideType.IMAGE_TEXT_SPLIT,
            SlideType.THREE_CARDS,
        ],
        "forbid": [
            SlideType.IMAGE_FULLBLEED,
        ],
    },
    ImageStyleType.MINIMAL: {
        "allow_image_slides": False,
        "prefer": [
            SlideType.BULLETS_FOCUSED,
            SlideType.KEY_STATEMENT,
            SlideType.KPI_DASHBOARD,
        ],
        "forbid": [
            SlideType.IMAGE_FULLBLEED,
            SlideType.IMAGE_TEXT_SPLIT,
        ],
    },
    ImageStyleType.DATA_VISUAL: {
        "allow_image_slides": False,
        "prefer": [
            SlideType.CHART_INSIGHT,
            SlideType.KPI_DASHBOARD,
            SlideType.COMPARISON,
        ],
        "forbid": [
            SlideType.IMAGE_FULLBLEED,
            SlideType.IMAGE_TEXT_SPLIT,
        ],
    },
    ImageStyleType.NONE: {
        "allow_image_slides": False,
        "prefer": [
            SlideType.BULLETS_FOCUSED,
            SlideType.KEY_STATEMENT,
        ],
        "forbid": [
            SlideType.IMAGE_FULLBLEED,
            SlideType.IMAGE_TEXT_SPLIT,
            SlideType.TITLE_HERO,
        ],
    },
}

# ---------------------------------------------------------------------------
# Sequence rules — validated after slide-type list is assembled
# ---------------------------------------------------------------------------

SEQUENCE_RULES: list[dict] = [
    {
        "id": "first_slide_must_be_title",
        "description": "The first slide must be a title_hero.",
        "position": "first",
        "required_type": SlideType.TITLE_HERO,
    },
    {
        "id": "last_slide_must_be_closing",
        "description": "The last slide must be a closing slide.",
        "position": "last",
        "required_type": SlideType.CLOSING,
    },
    {
        "id": "no_consecutive_section_dividers",
        "description": "Two section_divider slides must not be adjacent.",
        "constraint": "no_consecutive",
        "type": SlideType.SECTION_DIVIDER,
    },
    {
        "id": "no_consecutive_key_statements",
        "description": "Two key_statement slides must not be adjacent.",
        "constraint": "no_consecutive",
        "type": SlideType.KEY_STATEMENT,
    },
    {
        "id": "no_consecutive_image_fullbleed",
        "description": "Two image_fullbleed slides must not be adjacent.",
        "constraint": "no_consecutive",
        "type": SlideType.IMAGE_FULLBLEED,
    },
    {
        "id": "agenda_in_first_three",
        "description": "If an agenda slide exists it should appear within the first three slides.",
        "constraint": "max_position",
        "type": SlideType.AGENDA,
        "max_position": 3,
    },
    {
        "id": "max_two_kpi_dashboards",
        "description": "At most two KPI dashboard slides per deck.",
        "constraint": "max_count",
        "type": SlideType.KPI_DASHBOARD,
        "max_count": 2,
    },
    {
        "id": "max_three_image_slides",
        "description": "At most three image-heavy slides (fullbleed + text_split) per deck.",
        "constraint": "max_count_combined",
        "types": [SlideType.IMAGE_FULLBLEED, SlideType.IMAGE_TEXT_SPLIT],
        "max_count": 3,
    },
]
