"""
Turns a lecture's transcript into rich study material using Gemini.

Each function here does ONE job and returns plain data (str / dict / list) —
the router decides what to do with it (save to DB, etc). Keeping the LLM
logic isolated here means a future chat/RAG feature can reuse the same
client and prompting conventions without touching route code.

Everything that must come back as structured data uses Gemini's native
JSON mode (response_mime_type="application/json") rather than asking the
model politely and hoping. That removes almost all of the "model wrapped
it in markdown fences again" class of bug.
"""

import asyncio
import json
import os
import re

import httpx

from google.genai import types

from config import GEMINI_MODEL, QWEN_API_KEY, QWEN_MODEL
from services.gemini_client import get_client


class LLMGenerationError(Exception):
    """Raised when a model response couldn't be parsed into the expected shape."""
    pass


# Kept as an alias so existing imports/except clauses don't break.
QuizGenerationError = LLMGenerationError


# --------------------------------------------------------------------------
# Internal helpers
# --------------------------------------------------------------------------

def _strip_code_fences(raw: str) -> str:
    """
    Defensive cleanup. Even in JSON mode a model can occasionally wrap output
    in ```json fences, so strip them rather than failing the whole request.
    """
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
    return raw.strip()


def _strip_thinking(raw: str) -> str:
    raw = re.sub(r"<think>.*?</think>", "", raw or "", flags=re.DOTALL)
    if "<think>" in raw:
        raw = raw.split("<think>", 1)[0]
    return raw.strip()


def _parse_json(raw: str):
    raw = _strip_code_fences(_strip_thinking(raw))
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    for open_ch, close_ch in (("[", "]"), ("{", "}")):
        start, end = raw.find(open_ch), raw.rfind(close_ch)
        if start != -1 and end > start:
            try:
                return json.loads(raw[start:end + 1])
            except json.JSONDecodeError:
                continue
    raise LLMGenerationError(f"Model did not return valid JSON. Received: {raw[:200]}")


def _as_list(data) -> list:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        lists = [v for v in data.values() if isinstance(v, list)]
        if lists:
            return lists[0]
        return [data]
    raise LLMGenerationError("Model response was not a JSON array.")


async def _generate_text(prompt: str, temperature: float = 0.3) -> str:
    if QWEN_API_KEY:
        return _strip_thinking(await _generate_openrouter(prompt, temperature))

    client = get_client().aio
    response = await _generate_with_retry(
        client,
        prompt,
        types.GenerateContentConfig(temperature=temperature),
    )
    if not response.text:
        raise LLMGenerationError("Gemini returned an empty response (possibly blocked by safety filters).")
    return _strip_thinking(response.text)


async def _generate_json(prompt: str, temperature: float = 0.3):
    """
    Uses Gemini's JSON mode so the response is machine-parseable by contract,
    not by request. Still guarded, because a truncated response is possible.
    """
    if QWEN_API_KEY:
        raw = await _generate_openrouter(
            prompt,
            temperature,
            json_mode=True,
        )
        return _parse_json(raw)

    client = get_client().aio
    response = await _generate_with_retry(
        client,
        prompt,
        types.GenerateContentConfig(
            temperature=temperature,
            response_mime_type="application/json",
        ),
    )
    if not response.text:
        raise LLMGenerationError("Gemini returned an empty response (possibly blocked by safety filters).")
    return _parse_json(response.text)


async def _generate_with_retry(client, prompt: str, config):
    for attempt in range(3):
        try:
            return await client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=config,
            )
        except Exception as error:
            error_text = str(error)
            is_unavailable = (
                getattr(error, "status_code", None) == 503
                or "503" in error_text
                or "UNAVAILABLE" in error_text
            )
            if not is_unavailable or attempt == 2:
                raise
            await asyncio.sleep(2 ** attempt)


async def _generate_openrouter(
    prompt: str,
    temperature: float,
    json_mode: bool = False,
) -> str:
    model = QWEN_MODEL if "/" in QWEN_MODEL else f"qwen/{QWEN_MODEL}"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    headers = {
        "Authorization": f"Bearer {QWEN_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:8000",
        "X-Title": "VoicePilot AI",
    }

    async with httpx.AsyncClient(timeout=120) as client:
        for attempt in range(3):
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
            )
            if response.status_code < 400:
                data = response.json()
                try:
                    return data["choices"][0]["message"]["content"].strip()
                except (KeyError, IndexError, AttributeError) as e:
                    raise LLMGenerationError(
                        "OpenRouter returned an unexpected response."
                    ) from e

            if response.status_code not in {408, 429, 500, 502, 503, 504} or attempt == 2:
                raise LLMGenerationError(
                    f"Qwen generation failed: {response.status_code} {response.text[:300]}"
                )
            await asyncio.sleep(2 ** attempt)

    raise LLMGenerationError("Qwen generation failed after retries.")


def _format_timestamped(segments: list[dict] | None, limit: int = 400) -> str:
    """
    Renders timestamped segments for prompts that need time awareness
    (chapters, timeline). Capped so a 90-minute lecture can't blow the
    prompt size on a long tail of segments.
    """
    if not segments:
        return ""
    lines = []
    for seg in segments[:limit]:
        start = int(seg.get("start", 0))
        stamp = f"{start // 60:02d}:{start % 60:02d}"
        lines.append(f"[{stamp}] {seg.get('text', '')}")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Summary
# --------------------------------------------------------------------------

async def generate_summary(transcript: str) -> str:
    return await _generate_text(
        "You are an expert study assistant. Summarize this lecture transcript "
        "in 4-6 sentences, covering only the key concepts a student needs to "
        "remember. Write in plain prose. Do not add commentary, headings, or "
        "any mention that this is a summary.\n\n"
        f"Transcript:\n{transcript}"
    )


# --------------------------------------------------------------------------
# Rich notes (Markdown + Mermaid diagrams)
# --------------------------------------------------------------------------

_NOTES_PROMPT = """You are an expert technical note-taker producing study notes \
from a lecture transcript.

Produce **Markdown** notes with this structure:

1. `## Overview` — 2-3 sentences on what the lecture covers.
2. `## Key Concepts` — bullet points grouped under `###` subheadings by theme. \
Bold every important term the first time it appears.
3. `## Visual Breakdown` — one or more Mermaid diagrams that genuinely clarify \
the material. Choose the diagram type that actually fits the content:
   - `flowchart TD` for processes, pipelines, or decision flows
   - `sequenceDiagram` for interactions between parties over time
   - `mindmap` for a topic hierarchy or taxonomy
   - `graph LR` for relationships between concepts
   - `classDiagram` for structures, entities, or type hierarchies
   Put each diagram in a fenced block marked ```mermaid. Add a one-line caption \
under each diagram explaining what it shows.
4. `## Important Details` — formulas, definitions, numbers, dates, named entities. \
Use a Markdown table where the data is tabular. Use LaTeX (`$...$`) for any math.
5. `## Common Pitfalls` — misconceptions or mistakes a student is likely to make. \
Omit this section entirely if the transcript gives no basis for it.
6. `## Quick Revision` — a compact checklist of the must-remember points.

Rules:
- Base everything strictly on the transcript. Never invent facts, figures, or \
citations that aren't supported by it.
- Mermaid node labels must be short (under 6 words) and must not contain \
parentheses, colons, or quotes, which break Mermaid parsing. Wrap labels in \
double quotes if they contain any special character.
- If the transcript is too short or sparse for a meaningful diagram, skip the \
diagram rather than forcing a trivial one.
- Output only the Markdown. No preamble, no closing commentary.

Transcript:
{transcript}
"""


async def generate_notes(transcript: str) -> str:
    return await _generate_text(_NOTES_PROMPT.format(transcript=transcript))


# --------------------------------------------------------------------------
# Quiz
# --------------------------------------------------------------------------

_QUIZ_PROMPT = """Based on this lecture transcript, write {n} multiple-choice \
quiz questions testing genuine understanding, not trivial recall.

Requirements:
- Exactly 4 options per question.
- Distractors must be plausible — wrong answers a student who half-understood \
the material might actually pick. Never use filler like "none of the above".
- Vary difficulty: roughly one third easy, one third medium, one third hard.
- `correct_index` is the 0-based index of the correct option.
- `explanation` says why the correct answer is right AND why the tempting \
distractor is wrong.
- Base everything strictly on the transcript.

Return JSON: an array of objects (if you must return an object, use {{"items": [...]}}) with exactly these keys:
"question" (string), "options" (array of 4 strings), "correct_index" (integer \
0-3), "explanation" (string), "difficulty" (one of "easy", "medium", "hard").

Transcript:
{transcript}
"""


async def generate_quiz(transcript: str, num_questions: int = 5) -> list[dict]:
    data = await _generate_json(
        _QUIZ_PROMPT.format(n=num_questions, transcript=transcript),
        temperature=0.4,
    )

    data = _as_list(data)

    # Validate each question so a malformed item can't reach the database
    # and blow up the frontend later.
    validated = []
    for item in data:
        if not isinstance(item, dict):
            continue
        options = item.get("options")
        idx = item.get("correct_index")
        if (
            not item.get("question")
            or not isinstance(options, list)
            or len(options) < 2
            or not isinstance(idx, int)
            or not (0 <= idx < len(options))
        ):
            continue
        validated.append({
            "question": item["question"],
            "options": options,
            "correct_index": idx,
            "explanation": item.get("explanation", ""),
            "difficulty": item.get("difficulty", "medium"),
        })

    if not validated:
        raise LLMGenerationError("No valid quiz questions could be parsed.")

    return validated


# --------------------------------------------------------------------------
# Flashcards
# --------------------------------------------------------------------------

_FLASHCARD_PROMPT = """Create {n} flashcards from this lecture transcript for \
spaced-repetition study.

Requirements:
- `front` is a single focused question or term — never a compound question.
- `back` is a complete but concise answer (1-3 sentences).
- Cover the breadth of the lecture, not just its opening.
- `hint` is optional; include it only when the card is genuinely hard.
- Base everything strictly on the transcript.

Return JSON: an array of objects (if you must return an object, use {{"items": [...]}}) with keys: "front" (string), "back" (string), \
"hint" (string or null), "topic" (short string naming the theme).

Transcript:
{transcript}
"""


async def generate_flashcards(transcript: str, num_cards: int = 10) -> list[dict]:
    data = await _generate_json(
        _FLASHCARD_PROMPT.format(n=num_cards, transcript=transcript),
        temperature=0.35,
    )

    data = _as_list(data)

    validated = [
        {
            "front": item["front"],
            "back": item["back"],
            "hint": item.get("hint"),
            "topic": item.get("topic", "General"),
        }
        for item in data
        if isinstance(item, dict) and item.get("front") and item.get("back")
    ]

    if not validated:
        raise LLMGenerationError("No valid flashcards could be parsed.")

    return validated


# --------------------------------------------------------------------------
# Key concepts / glossary
# --------------------------------------------------------------------------

_CONCEPTS_PROMPT = """Extract the key concepts and terminology from this \
lecture transcript, as a glossary a student can revise from.

Requirements:
- `term` is the concept name exactly as a student would look it up.
- `definition` is 1-2 sentences, in plain language.
- `importance` is one of "core", "supporting", "mentioned" — reflecting how \
central the concept is to this lecture.
- `related_terms` lists other terms from THIS glossary that connect to it \
(empty array if none).
- Extract between 5 and 15 concepts depending on the transcript's density.
- Base everything strictly on the transcript.

Return JSON: an array of objects (if you must return an object, use {{"items": [...]}}) with keys: "term", "definition", "importance", \
"related_terms" (array of strings).

Transcript:
{transcript}
"""


async def generate_key_concepts(transcript: str) -> list[dict]:
    data = await _generate_json(
        _CONCEPTS_PROMPT.format(transcript=transcript),
        temperature=0.25,
    )

    data = _as_list(data)

    validated = [
        {
            "term": item["term"],
            "definition": item["definition"],
            "importance": item.get("importance", "supporting"),
            "related_terms": item.get("related_terms", []) or [],
        }
        for item in data
        if isinstance(item, dict) and item.get("term") and item.get("definition")
    ]

    if not validated:
        raise LLMGenerationError("No valid key concepts could be parsed.")

    return validated


# --------------------------------------------------------------------------
# Mind map (standalone Mermaid diagram)
# --------------------------------------------------------------------------

_MINDMAP_PROMPT = """Create a Mermaid mindmap of this lecture's topic structure.

Rules:
- Start the output with the line `mindmap` and nothing before it.
- Root node is the lecture's main subject.
- 3-6 primary branches, each with 2-5 sub-nodes.
- Node text must be SHORT (under 5 words) and must NOT contain parentheses, \
colons, quotes, or brackets — these break Mermaid's parser.
- Indent with exactly 2 spaces per level.
- Output ONLY the Mermaid source. No fences, no explanation.

Transcript:
{transcript}
"""


async def generate_mindmap(transcript: str) -> str:
    raw = await _generate_text(_MINDMAP_PROMPT.format(transcript=transcript), 0.3)
    mermaid = _strip_code_fences(raw)

    # Guarantee the root directive is present — Mermaid fails hard without it.
    if not mermaid.lstrip().startswith("mindmap"):
        mermaid = "mindmap\n" + mermaid

    return mermaid


# --------------------------------------------------------------------------
# Chapters (timestamped outline)
# --------------------------------------------------------------------------

_CHAPTERS_PROMPT = """Below is a timestamped lecture transcript. Divide it into \
logical chapters, the way a well-produced video would be chaptered.

Requirements:
- `start_seconds` is the integer second the chapter begins, taken from the \
timestamps provided.
- `title` is a short descriptive chapter title (under 8 words).
- `summary` is one sentence on what that chapter covers.
- Produce between 3 and 10 chapters depending on length and topic shifts.
- Chapters must be in chronological order and must not overlap.
- The first chapter should start at or near 0.

Return JSON: an array of objects (if you must return an object, use {{"items": [...]}}) with keys: "start_seconds" (integer), "title" \
(string), "summary" (string).

Timestamped transcript:
{timestamped}
"""


async def generate_chapters(segments: list[dict]) -> list[dict]:
    timestamped = _format_timestamped(segments)
    if not timestamped:
        raise LLMGenerationError("No segments available to build chapters from.")

    data = await _generate_json(
        _CHAPTERS_PROMPT.format(timestamped=timestamped),
        temperature=0.3,
    )

    data = _as_list(data)

    validated = []
    for item in data:
        if not isinstance(item, dict) or not item.get("title"):
            continue
        try:
            start = int(item.get("start_seconds", 0))
        except (TypeError, ValueError):
            continue
        validated.append({
            "start_seconds": max(0, start),
            "title": item["title"],
            "summary": item.get("summary", ""),
        })

    if not validated:
        raise LLMGenerationError("No valid chapters could be parsed.")

    validated.sort(key=lambda c: c["start_seconds"])
    return validated
