"""Stage 1: turn a topic into a structured script (hook/body/outro, per-scene
narration + image prompt) using an LLM.

Provider is LLM_PROVIDER ("groq" default, or "openrouter") -- both are
OpenAI-compatible chat-completions APIs, so this is one call shape with a
different base URL/key/model per provider.
"""
import json
import re
import sys

import requests

from . import config

SYSTEM_PROMPT = """You are a scriptwriter for short-form YouTube videos.
Given a topic, write a hooking script broken into scenes.

Return ONLY valid JSON (no markdown fences, no commentary) matching exactly:
{
  "title": "string, a compelling YouTube title",
  "scenes": [
    {"narration": "string, 1-3 sentences of spoken narration for this scene",
     "image_prompt": "string, a short visual description for an image generator"}
  ]
}

Rules:
- First scene must be a strong hook (first 3-5 seconds matter most).
- 6 to 10 scenes total: hook, several body scenes, one outro/CTA scene.
- Narration should sound natural when read aloud, not like bullet points.
- image_prompt describes ONLY the visual, no camera jargon needed.
"""


def _extract_json(text: str) -> dict:
    text = text.strip()
    # Strip ```json ... ``` or ``` ... ``` fences if the model added them anyway.
    fence_match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()
    return json.loads(text)


def _call_groq(topic: str) -> str:
    if not config.GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not set in the environment.")
    resp = requests.post(
        f"{config.GROQ_BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {config.GROQ_API_KEY}", "Content-Type": "application/json"},
        json={
            "model": config.GROQ_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Topic: {topic}"},
            ],
            "temperature": 0.8,
        },
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _call_openrouter(topic: str) -> str:
    if not config.OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY is not set in the environment.")
    if not config.OPENROUTER_MODEL:
        raise RuntimeError(
            "OPENROUTER_MODEL is not set. Pick the exact free model slug from "
            "https://openrouter.ai/models (filter: free) and export it, e.g.\n"
            "  export OPENROUTER_MODEL='vendor/model-name:free'"
        )
    resp = requests.post(
        f"{config.OPENROUTER_BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {config.OPENROUTER_API_KEY}", "Content-Type": "application/json"},
        json={
            "model": config.OPENROUTER_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Topic: {topic}"},
            ],
            "temperature": 0.8,
        },
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def generate_script(topic: str) -> dict:
    if config.LLM_PROVIDER == "groq":
        content = _call_groq(topic)
    elif config.LLM_PROVIDER == "openrouter":
        content = _call_openrouter(topic)
    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {config.LLM_PROVIDER}")

    try:
        script = _extract_json(content)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"Model did not return valid JSON. Raw output was:\n{content}"
        ) from e

    if "scenes" not in script or not script["scenes"]:
        raise RuntimeError(f"Script JSON missing scenes: {script}")

    return script


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m pipeline.generate_script '<topic>'")
        sys.exit(1)
    result = generate_script(sys.argv[1])
    print(json.dumps(result, indent=2))
