import requests
from pathlib import Path
from ruamel.yaml import YAML
from datetime import datetime, timezone, timedelta
from ruamel.yaml.comments import CommentedMap

yaml = YAML()

PACKAGE_YML = Path(__file__).parents[2] / "libs" / "packages.yml"

def _get_downloads(p: dict) -> int:
    url = f"https://pypistats.org/api/packages/{p['name']}/recent?period=month"
    r = requests.get(url)
    r.raise_for_status()
    return r.json()["data"]["last_month"]

current_datetime = datetime.now(timezone.utc)
yesterday = current_datetime - timedelta(days=1)

with open(PACKAGE_YML) as f:
    data = yaml.load(f)

def _reorder_keys(p):
    keys = p.keys()
    key_order = [
        # "name",
        "name_title",
        "repo",
        "type",
        "provider_page",
        "js",
        "downloads",
        "downloads_updated_at",
    ]
    if set(keys) - set(key_order):
        raise ValueError(f"Unexpected keys: {set(keys) - set(key_order)}")
    return CommentedMap((k, p[k]) for k in key_order if k in p)
data["packages"] = [CommentedMap(p) for p in data["packages"]]
for p in data["packages"]:
    downloads_updated_at = datetime.fromisoformat(p["downloads_updated_at"])

    if downloads_updated_at > yesterday:
        print(f"done: {p['name']}: {p['downloads']}")
        continue

    p["downloads"] = _get_downloads(p)
    p['downloads_updated_at'] = current_datetime.isoformat()
    with open(PACKAGE_YML, "w") as f:
        yaml.dump(data, f)
    print(f"{p['name']}: {p['downloads']}")


with open(PACKAGE_YML, "w") as f:
    yaml.dump(data, f)
