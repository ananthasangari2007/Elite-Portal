import re
import glob

modules = {
    "auth": "app/api/auth.py",
    "common": "app/api/common.py",
    "student": "app/api/student.py",
    "coordinator": "app/api/coordinator.py",
    "faculty": "app/api/faculty.py",
    "admin": "app/api/admin.py",
}

all_endpoints = []

for mod_name, file_path in modules.items():
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    prefix_match = re.search(r'url_prefix\s*=\s*["\']([^"\']+)["\']', content)
    prefix = prefix_match.group(1) if prefix_match else ""

    pattern = r'@(\w+)\.(get|post|put|patch|delete|route)\(\s*["\']([^"\']*)["\'](?:,\s*methods=\[([^\]]+)\])?.*?\n(?:@.*?\n)*def\s+(\w+)\s*\((.*?)\):'
    for m in re.finditer(pattern, content, re.DOTALL):
        bp, method, path, methods, func_name, args = m.groups()
        if method == "route":
            method_str = methods.replace('"', '').replace("'", '').strip() if methods else "GET"
        else:
            method_str = method.upper()
        full_path = prefix + path
        all_endpoints.append({
            "module": mod_name,
            "method": method_str,
            "path": full_path,
            "func": func_name,
            "args": args.strip()
        })

print(f"Parsed {len(all_endpoints)} endpoints across {len(modules)} modules.")
with open("scripts/endpoints_manifest.json", "w", encoding="utf-8") as out:
    import json
    json.dump(all_endpoints, out, indent=2)
print("Saved to scripts/endpoints_manifest.json")
