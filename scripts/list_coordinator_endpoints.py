import json

with open("scripts/endpoints_manifest.json") as f:
    eps = json.load(f)

for e in eps:
    if e["module"] == "coordinator":
        print(f"{e['method']:<7} {e['path']:<60} {e['func']}({e['args']})")
