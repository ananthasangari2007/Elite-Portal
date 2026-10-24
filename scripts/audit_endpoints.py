import re
import glob

endpoints = []
for file in sorted(glob.glob("app/api/*.py")):
    if file.endswith("__init__.py") or file.endswith("utils.py"):
        continue
    with open(file, "r", encoding="utf-8") as f:
        content = f.read()

    prefix_match = re.search(r'url_prefix\s*=\s*["\']([^"\']+)["\']', content)
    prefix = prefix_match.group(1) if prefix_match else ""

    for m in re.finditer(r'@(\w+)\.(get|post|put|patch|delete|route)\(\s*["\']([^"\']*)["\'](?:,\s*methods=\[([^\]]+)\])?', content):
        bp, method, path, methods = m.groups()
        if method == "route":
            method_str = methods.replace('"', '').replace("'", '').strip() if methods else "GET"
        else:
            method_str = method.upper()
        full_path = prefix + path
        endpoints.append((file, method_str, full_path))

for ep in endpoints:
    print(f"{ep[1]:<7} {ep[2]:<60} ({ep[0]})")
print(f"\nTotal endpoints found: {len(endpoints)}")
