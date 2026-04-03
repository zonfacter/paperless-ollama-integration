import json
import sqlite3
import time
from pathlib import Path


DATA_ROOT = Path("/app/backend/data")
DB_PATH = DATA_ROOT / "webui.db"
USER_ID = "3d67f125-03f5-4b4f-81e9-a7dfdb993890"


def _profile(
    profile_id: str,
    name: str,
    base_model_id: str,
    description: str,
    system_prompt: str,
    tags: list[str],
    default_features: list[str],
) -> dict:
    builtin_tools = {
        "time": True,
        "memory": True,
        "chats": True,
        "notes": True,
        "knowledge": True,
        "channels": True,
        "web_search": "web_search" in default_features,
        "image_generation": "image_generation" in default_features,
        "code_interpreter": "code_interpreter" in default_features,
    }
    capabilities = {
        "file_context": True,
        "vision": True,
        "file_upload": True,
        "web_search": "web_search" in default_features,
        "image_generation": "image_generation" in default_features,
        "code_interpreter": "code_interpreter" in default_features,
        "citations": True,
        "status_updates": True,
        "usage": True,
        "builtin_tools": True,
    }
    meta = {
        "profile_image_url": "/static/favicon.png",
        "description": description,
        "capabilities": capabilities,
        "defaultFeatureIds": default_features,
        "builtinTools": builtin_tools,
        "tags": [{"name": tag} for tag in tags],
    }
    params = {
        "system": system_prompt,
        "temperature": 0.15,
        "top_k": 40,
        "top_p": 0.9,
        "function_calling": "default",
    }
    return {
        "id": profile_id,
        "user_id": USER_ID,
        "base_model_id": base_model_id,
        "name": name,
        "meta": json.dumps(meta, ensure_ascii=False),
        "params": json.dumps(params, ensure_ascii=False),
    }


PROFILES = [
    _profile(
        profile_id="local-image-assistant",
        name="LOCAL Image Assistant",
        base_model_id="qwen2.5:3b",
        description="Lokales Prompt- und Bildprofil, das Bildanfragen bevorzugt an die AMD-ComfyUI-Bildfunktion weiterreicht.",
        system_prompt=(
            "Du bist ein lokaler Bildassistent. Wenn der Nutzer ein Bild erzeugen oder bearbeiten will, "
            "nutze vorrangig das Bildgenerierungs-Tool statt nur zu erklaeren, dass du keine Bilder erzeugen kannst. "
            "Formuliere bei Bedarf den Prompt kurz um und halte Rueckfragen knapp. "
            "Nur wenn die Anfrage unklar oder unzulaessig ist, antworte rein textlich. "
            "Nach erfolgreicher Bildgenerierung antworte genau mit einem kurzen sichtbaren Ergebnissatz. "
            "Zeige niemals Denkprozess, Pruefschritte, Final-Checks oder interne Notizen."
        ),
        tags=["LOCAL", "IMAGE", "AMD", "COMFYUI"],
        default_features=["image_generation"],
    ),
    _profile(
        profile_id="local-photo-assistant",
        name="LOCAL Photo Assistant",
        base_model_id="qwen2.5:3b",
        description="Lokales Bildprofil fuer moeglichst fotorealistische Prompts ueber ComfyUI auf der AMD MI50.",
        system_prompt=(
            "Du bist ein lokaler Foto-Bildassistent. Wenn der Nutzer ein Bild erzeugen oder bearbeiten will, "
            "nutze vorrangig das Bildgenerierungs-Tool. Formuliere Bildprompts standardmaessig fotorealistisch "
            "mit natuerlicher Haut, realistischer Beleuchtung, glaubwuerdigen Proportionen und klaren Details. "
            "Vermeide Cartoon-, Anime- oder Illustrationsstil, sofern der Nutzer das nicht ausdruecklich will. "
            "Nutze bei Bedarf implizit einen negativen Stil gegen Cartoon, Anime, CGI, Plastikhaut und schlechte Anatomie. "
            "Nur wenn die Anfrage unklar oder unzulaessig ist, antworte rein textlich. "
            "Nach erfolgreicher Bildgenerierung antworte genau mit einem kurzen sichtbaren Ergebnissatz. "
            "Zeige niemals Denkprozess, Pruefschritte, Final-Checks oder interne Notizen."
        ),
        tags=["LOCAL", "IMAGE", "PHOTO", "AMD", "COMFYUI"],
        default_features=["image_generation"],
    ),
    _profile(
        profile_id="local-illustration-assistant",
        name="LOCAL Illustration Assistant",
        base_model_id="qwen2.5:3b",
        description="Lokales Bildprofil fuer bewusst stilisierte, illustrative oder comicartige Bilder ueber ComfyUI auf der AMD MI50.",
        system_prompt=(
            "Du bist ein lokaler Illustrations-Bildassistent. Wenn der Nutzer ein Bild erzeugen oder bearbeiten will, "
            "nutze vorrangig das Bildgenerierungs-Tool. Formuliere Bildprompts standardmaessig stilisiert, illustrativ "
            "oder comicartig mit klarer Farbpalette, sauberer Komposition und absichtsvoller kuenstlerischer Richtung. "
            "Nur wenn der Nutzer ausdruecklich Fotorealismus verlangt, weiche davon ab. "
            "Nur wenn die Anfrage unklar oder unzulaessig ist, antworte rein textlich. "
            "Nach erfolgreicher Bildgenerierung antworte genau mit einem kurzen sichtbaren Ergebnissatz. "
            "Zeige niemals Denkprozess, Pruefschritte, Final-Checks oder interne Notizen."
        ),
        tags=["LOCAL", "IMAGE", "ILLUSTRATION", "AMD", "COMFYUI"],
        default_features=["image_generation"],
    ),
]


def upsert_profiles() -> list[str]:
    now = int(time.time())
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    changed: list[str] = []
    for profile in PROFILES:
        cur.execute(
            """
            INSERT INTO model (id, user_id, base_model_id, name, meta, params, created_at, updated_at, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
            ON CONFLICT(id) DO UPDATE SET
                user_id=excluded.user_id,
                base_model_id=excluded.base_model_id,
                name=excluded.name,
                meta=excluded.meta,
                params=excluded.params,
                updated_at=excluded.updated_at,
                is_active=1
            """,
            (
                profile["id"],
                profile["user_id"],
                profile["base_model_id"],
                profile["name"],
                profile["meta"],
                profile["params"],
                now,
                now,
            ),
        )
        changed.append(profile["id"])
    conn.commit()
    conn.close()
    return changed


if __name__ == "__main__":
    print(json.dumps({"updated_profiles": upsert_profiles()}, ensure_ascii=False))
