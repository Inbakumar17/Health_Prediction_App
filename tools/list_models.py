"""Show which Gemini models your API key can use, and test them until one answers.

Run from the project folder:
    python tools/list_models.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from google.genai import errors  # noqa: E402

from app import ai  # noqa: E402  (also loads .env)

UNSUITABLE = ("embedding", "image", "imagen", "tts", "audio", "live", "veo", "aqa", "gemma", "robotics", "computer-use")


def main() -> None:
    try:
        client = ai._get_client()
    except ai.AIServiceError as exc:
        print(f"Problem: {exc}")
        return

    names = []
    try:
        for model in client.models.list():
            name = (model.name or "").removeprefix("models/")
            actions = model.supported_actions or []
            if "gemini" in name and not any(word in name for word in UNSUITABLE) and (not actions or "generateContent" in actions):
                names.append(name)
    except errors.APIError as exc:
        print(f"Could not list models: error {exc.code} ({exc.message})")
        return

    names.sort(key=lambda n: (0 if "flash" in n else 1, "preview" in n, n))
    print(f"Text models your key can use ({len(names)}):")
    for name in names:
        print("  -", name)

    print("\nQuick test (stops at the first model that answers):")
    for name in names[:8]:
        try:
            reply = client.models.generate_content(model=name, contents="Reply with the single word: ok")
            print(f"  OK  {name}: works ({(reply.text or '').strip()[:20]})")
            print(f"\nPut this line in your .env, then restart the server:\n  GEMINI_MODEL={name}")
            return
        except errors.APIError as exc:
            print(f"  --  {name}: error {exc.code} ({(exc.message or '')[:70]})")
    print("\nNo model answered right now. If you see 503, Google is busy: try again in a few minutes.")


if __name__ == "__main__":
    main()
