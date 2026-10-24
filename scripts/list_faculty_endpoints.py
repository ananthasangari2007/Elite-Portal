import json

with open("scripts/endpoints_manifest.json") as f:
    eps = json.load(f)

for e in eps:
    if e["module"] == "faculty":
        print(f"{e['method']:<7} {e['path']:<65} {e['func']}({e['args']})")
