from pathlib import Path
import sys


MIDDLEWARE_PATH = Path("/app/backend/open_webui/utils/middleware.py")
MARKER = "default_feature_ids = []"


def patch_feature_fallback() -> None:
    text = MIDDLEWARE_PATH.read_text()
    if MARKER in text:
        print("open-webui patch already present")
        return

    old = "    features = form_data.pop('features', None) or {}\n    extra_params['__features__'] = features\n"
    new = (
        "    features = form_data.pop('features', None) or {}\n"
        "    if not features:\n"
        "        model_info = form_data.get('model_info')\n"
        "        default_feature_ids = []\n"
        "        if model_info and getattr(model_info, 'meta', None):\n"
        "            default_feature_ids = getattr(model_info.meta, 'defaultFeatureIds', []) or []\n"
        "        if not default_feature_ids:\n"
        "            db_model = Models.get_model_by_id(form_data.get('model'))\n"
        "            if db_model and getattr(db_model, 'meta', None):\n"
        "                default_feature_ids = getattr(db_model.meta, 'defaultFeatureIds', []) or []\n"
        "        if default_feature_ids:\n"
        "            features = {feature_id: True for feature_id in default_feature_ids}\n"
        "    extra_params['__features__'] = features\n"
    )

    if old not in text:
        raise RuntimeError("Expected feature block not found in middleware.py")

    MIDDLEWARE_PATH.write_text(text.replace(old, new, 1))
    print("patched open-webui middleware feature fallback")


if __name__ == "__main__":
    try:
        patch_feature_fallback()
    except Exception as exc:
        print(f"failed to patch open-webui: {exc}", file=sys.stderr)
        raise
