"""
Tests for services/llm_service.py on the OpenRouter (Qwen) path.

No network: httpx.AsyncClient.post is monkeypatched to return a fake
OpenRouter chat-completion whose message content is whatever reply the
test wants the "model" to have sent.
"""

import asyncio
import json
import os

# Must be set before importing the service: config.py reads it at import
# time, and its presence is what selects the OpenRouter path.
os.environ["QWEN_API_KEY"] = "test-key"

import httpx  # noqa: E402
import pytest  # noqa: E402

from services import llm_service  # noqa: E402
from services.llm_service import LLMGenerationError  # noqa: E402


# --------------------------------------------------------------------------
# Fixtures / helpers
# --------------------------------------------------------------------------

@pytest.fixture
def model_reply(monkeypatch):
    """Call model_reply("...") to set what the fake OpenRouter returns."""
    sent = {}

    def set_reply(content: str):
        async def fake_post(self, url, headers=None, json=None, **kwargs):
            sent["payload"] = json
            return httpx.Response(
                200,
                json={"choices": [{"message": {"content": content}}]},
                request=httpx.Request("POST", url),
            )
        monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
        return sent

    return set_reply


def run(coro):
    return asyncio.run(coro)


QUIZ_ITEMS = [
    {"question": "What is a bucket?", "options": ["A", "B", "C", "D"],
     "correct_index": 1, "explanation": "B is right.", "difficulty": "easy"},
    {"question": "What is a key?", "options": ["A", "B", "C", "D"],
     "correct_index": 2, "explanation": "C is right.", "difficulty": "hard"},
]
FLASHCARD_ITEMS = [
    {"front": "Bucket?", "back": "A top-level container.", "hint": None, "topic": "Storage"},
    {"front": "Key?", "back": "An object's full name.", "hint": "path-like", "topic": "Storage"},
]
CONCEPT_ITEMS = [
    {"term": "Bucket", "definition": "A container.", "importance": "core", "related_terms": ["Key"]},
    {"term": "Key", "definition": "An object name.", "importance": "supporting", "related_terms": []},
]
CHAPTER_ITEMS = [
    {"start_seconds": 0, "title": "Intro", "summary": "Opening."},
    {"start_seconds": 95, "title": "Buckets", "summary": "About buckets."},
]
SEGMENTS = [
    {"start": 0, "end": 5, "text": "Welcome."},
    {"start": 95, "end": 100, "text": "Buckets hold objects."},
]

GENERATORS = {
    "quiz": (lambda: llm_service.generate_quiz("transcript", 2), QUIZ_ITEMS),
    "flashcards": (lambda: llm_service.generate_flashcards("transcript", 2), FLASHCARD_ITEMS),
    "key_concepts": (lambda: llm_service.generate_key_concepts("transcript"), CONCEPT_ITEMS),
    "chapters": (lambda: llm_service.generate_chapters(SEGMENTS), CHAPTER_ITEMS),
}


def reply_shapes(items: list) -> dict[str, str]:
    arr = json.dumps(items)
    return {
        "bare_array": arr,
        "object_wrapper": json.dumps({"items": items}),
        "think_before_array": f"<think>The user wants [a list] of {{things}}.</think>\n{arr}",
        "json_fences": f"```json\n{arr}\n```",
        "prose_around": f"Sure! Here is the JSON you asked for:\n{arr}\nLet me know if you need more.",
    }


# --------------------------------------------------------------------------
# Every structured generator x every reply shape
# --------------------------------------------------------------------------

@pytest.mark.parametrize("shape", list(reply_shapes([]).keys()))
@pytest.mark.parametrize("kind", list(GENERATORS.keys()))
def test_structured_generators_accept_reply_shapes(model_reply, kind, shape):
    call, items = GENERATORS[kind]
    model_reply(reply_shapes(items)[shape])

    result = run(call())

    assert isinstance(result, list)
    assert len(result) == len(items)


def test_quiz_fields_survive_parsing(model_reply):
    model_reply(json.dumps({"questions": QUIZ_ITEMS}))
    result = run(llm_service.generate_quiz("transcript", 2))
    assert result[0]["question"] == "What is a bucket?"
    assert result[1]["correct_index"] == 2


def test_json_mode_is_requested(model_reply):
    sent = model_reply(json.dumps(QUIZ_ITEMS))
    run(llm_service.generate_quiz("transcript", 2))
    assert sent["payload"]["response_format"] == {"type": "json_object"}


# --------------------------------------------------------------------------
# Validation and failure cases
# --------------------------------------------------------------------------

def test_invalid_quiz_items_are_dropped(model_reply):
    bad = [
        {"question": "", "options": ["A", "B"], "correct_index": 0},          # no question
        {"question": "Q?", "options": "not a list", "correct_index": 0},     # options not a list
        {"question": "Q?", "options": ["A"], "correct_index": 0},            # < 2 options
        {"question": "Q?", "options": ["A", "B"], "correct_index": 5},       # index out of range
        {"question": "Q?", "options": ["A", "B"], "correct_index": "1"},     # index not an int
        "not a dict",
    ]
    model_reply(json.dumps({"items": bad + [QUIZ_ITEMS[0]]}))

    result = run(llm_service.generate_quiz("transcript", 7))

    assert len(result) == 1
    assert result[0]["question"] == QUIZ_ITEMS[0]["question"]


def test_reply_with_no_json_raises(model_reply):
    model_reply("I'm sorry, I can't produce a quiz for this transcript.")
    with pytest.raises(LLMGenerationError):
        run(llm_service.generate_quiz("transcript", 2))


def test_unclosed_think_with_no_answer_raises(model_reply):
    model_reply('<think>Let me plan [the questions] carefully... {"question":')
    with pytest.raises(LLMGenerationError):
        run(llm_service.generate_quiz("transcript", 2))


# --------------------------------------------------------------------------
# Free-text generators: <think> must not leak into saved content
# --------------------------------------------------------------------------

def test_notes_have_think_stripped(model_reply):
    model_reply("<think>\nI should start with an overview.\n</think>\n## Overview\nBuckets and keys.")
    notes = run(llm_service.generate_notes("transcript"))
    assert "<think>" not in notes and "I should start" not in notes
    assert notes.startswith("## Overview")


def test_mindmap_has_think_stripped(model_reply):
    model_reply("<think>Plan the branches.</think>\nmindmap\n  root((Storage))\n    Buckets")
    mindmap = run(llm_service.generate_mindmap("transcript"))
    assert "<think>" not in mindmap and "Plan the branches" not in mindmap
    assert mindmap.startswith("mindmap")


def test_summary_has_think_stripped(model_reply):
    model_reply("<think>Keep it short.</think>Object storage keeps files in buckets.")
    assert run(llm_service.generate_summary("transcript")) == "Object storage keeps files in buckets."


# --------------------------------------------------------------------------
# Chapters
# --------------------------------------------------------------------------

def test_chapters_sorted_by_start_seconds(model_reply):
    shuffled = [
        {"start_seconds": 300, "title": "Wrap-up", "summary": "End."},
        {"start_seconds": 0, "title": "Intro", "summary": "Start."},
        {"start_seconds": 95, "title": "Buckets", "summary": "Middle."},
    ]
    model_reply(json.dumps({"chapters": shuffled}))

    result = run(llm_service.generate_chapters(SEGMENTS))

    assert [c["start_seconds"] for c in result] == [0, 95, 300]


# --------------------------------------------------------------------------
# Prompt templates
# --------------------------------------------------------------------------

TEMPLATES = {
    "notes": (llm_service._NOTES_PROMPT, {"transcript": "t"}, False),
    "quiz": (llm_service._QUIZ_PROMPT, {"n": 5, "transcript": "t"}, True),
    "flashcards": (llm_service._FLASHCARD_PROMPT, {"n": 10, "transcript": "t"}, True),
    "key_concepts": (llm_service._CONCEPTS_PROMPT, {"transcript": "t"}, True),
    "mindmap": (llm_service._MINDMAP_PROMPT, {"transcript": "t"}, False),
    "chapters": (llm_service._CHAPTERS_PROMPT, {"timestamped": "[00:00] t"}, True),
}


@pytest.mark.parametrize("name", list(TEMPLATES.keys()))
def test_prompt_templates_format(name):
    template, kwargs, is_json = TEMPLATES[name]
    rendered = template.format(**kwargs)

    # The only braces left after .format() should be the literal example.
    assert "{" not in rendered.replace('{"items": [...]}', "")
    if is_json:
        assert 'use {"items": [...]}) with ' in rendered
