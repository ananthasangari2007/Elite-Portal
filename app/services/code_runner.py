"""Elite Portal — Multi-Language Code Compilation & Execution Engine
Supports Python 3, C (GCC), C++ (G++), and Java (JDK 17).
"""
import glob
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def _find_binary(name: str, fallback_patterns: list[str] = None) -> str:
    which_path = shutil.which(name)
    if which_path:
        return which_path

    if fallback_patterns:
        for pattern in fallback_patterns:
            expanded = os.path.expandvars(pattern)
            matches = glob.glob(expanded, recursive=True)
            if matches:
                for match in matches:
                    if os.path.isfile(match) and os.access(match, os.X_OK):
                        return match
                    elif os.path.isfile(match) and match.lower().endswith(".exe"):
                        return match
    return name


def get_compiler_paths():
    base_winget = "%LOCALAPPDATA%\\Microsoft\\WinGet\\Packages\\*\\**\\"
    gcc_path = _find_binary(
        "gcc",
        [
            base_winget + "gcc.exe",
            "C:\\Program Files\\mingw-w64\\*\\bin\\gcc.exe",
            "C:\\msys64\\mingw64\\bin\\gcc.exe",
            "C:\\msys64\\ucrt64\\bin\\gcc.exe",
        ],
    )
    gpp_path = _find_binary(
        "g++",
        [
            base_winget + "g++.exe",
            "C:\\Program Files\\mingw-w64\\*\\bin\\g++.exe",
            "C:\\msys64\\mingw64\\bin\\g++.exe",
            "C:\\msys64\\ucrt64\\bin\\g++.exe",
        ],
    )
    javac_path = _find_binary(
        "javac",
        [
            "C:\\Program Files\\Common Files\\Oracle\\Java\\javapath\\javac.exe",
            "C:\\Program Files\\Java\\*\\bin\\javac.exe",
        ],
    )
    java_path = _find_binary(
        "java",
        [
            "C:\\Program Files\\Common Files\\Oracle\\Java\\javapath\\java.exe",
            "C:\\Program Files\\Java\\*\\bin\\java.exe",
        ],
    )
    python_path = sys.executable or "python"
    node_path = _find_binary("node", ["C:\\Program Files\\nodejs\\node.exe"])

    return {
        "python": python_path,
        "gcc": gcc_path,
        "g++": gpp_path,
        "javac": javac_path,
        "java": java_path,
        "node": node_path,
        "rustc": _find_binary("rustc"),
        "go": _find_binary("go"),
        "php": _find_binary("php"),
        "ruby": _find_binary("ruby"),
    }


def normalize_language(lang: str) -> str:
    l = (lang or "").strip().lower()
    if l in ("python", "python3", "py"):
        return "python"
    if l in ("c", "gcc"):
        return "c"
    if l in ("cpp", "c++", "g++"):
        return "cpp"
    if l in ("java", "jdk"):
        return "java"
    if l in ("javascript", "js", "node"):
        return "javascript"
    if l in ("typescript", "ts"):
        return "typescript"
    if l in ("csharp", "c#", "cs"):
        return "csharp"
    if l in ("go", "golang"):
        return "go"
    if l in ("rust", "rs"):
        return "rust"
    if l in ("ruby", "rb"):
        return "ruby"
    if l in ("php",):
        return "php"
    if l in ("dart",):
        return "dart"
    if l in ("kotlin", "kt"):
        return "kotlin"
    if l in ("swift",):
        return "swift"
    if l in ("scala",):
        return "scala"
    if l in ("elixir", "ex"):
        return "elixir"
    if l in ("erlang", "erl"):
        return "erlang"
    if l in ("racket", "rkt"):
        return "racket"
    if l in ("web", "html", "html/css/js"):
        return "web"
    return l


def run_code(language: str, code: str, stdin: str = "", timeout_seconds: float = 5.0, compile_timeout: float = 12.0) -> dict:
    lang = normalize_language(language)
    tools = get_compiler_paths()

    with tempfile.TemporaryDirectory() as td:
        tmp_dir = Path(td)

        if lang == "python":
            script_path = tmp_dir / "solution.py"
            script_path.write_text(code, encoding="utf-8")
            cmd = [tools["python"], str(script_path)]

            start_t = time.perf_counter()
            try:
                proc = subprocess.run(
                    cmd,
                    input=stdin,
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds,
                    cwd=str(tmp_dir),
                )
                dur_ms = int((time.perf_counter() - start_t) * 1000)
                status = "success" if proc.returncode == 0 else "runtime_error"
                return {
                    "status": status,
                    "stdout": proc.stdout,
                    "stderr": proc.stderr,
                    "execution_time_ms": dur_ms,
                    "exit_code": proc.returncode,
                }
            except subprocess.TimeoutExpired:
                return {
                    "status": "time_limit_exceeded",
                    "stdout": "",
                    "stderr": f"Execution timed out after {timeout_seconds} seconds.",
                    "execution_time_ms": int(timeout_seconds * 1000),
                    "exit_code": -1,
                }
            except Exception as e:
                return {
                    "status": "runtime_error",
                    "stdout": "",
                    "stderr": str(e),
                    "execution_time_ms": 0,
                    "exit_code": -1,
                }

        elif lang == "c":
            src_path = tmp_dir / "solution.c"
            src_path.write_text(code, encoding="utf-8")
            exe_path = tmp_dir / "solution.exe"

            # Compile with static linking to prevent missing runtime DLL errors
            try:
                comp = subprocess.run(
                    [tools["gcc"], "-O2", "-static", str(src_path), "-o", str(exe_path)],
                    capture_output=True,
                    text=True,
                    timeout=compile_timeout,
                    cwd=str(tmp_dir),
                )
            except subprocess.TimeoutExpired:
                return {
                    "status": "compile_error",
                    "stdout": "",
                    "stderr": "Compilation timed out.",
                    "execution_time_ms": 0,
                    "exit_code": -1,
                }
            if comp.returncode != 0:
                return {
                    "status": "compile_error",
                    "stdout": "",
                    "stderr": comp.stderr,
                    "execution_time_ms": 0,
                    "exit_code": comp.returncode,
                }

            # Execute
            start_t = time.perf_counter()
            try:
                proc = subprocess.run(
                    [str(exe_path)],
                    input=stdin,
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds,
                    cwd=str(tmp_dir),
                )
                dur_ms = int((time.perf_counter() - start_t) * 1000)
                status = "success" if proc.returncode == 0 else "runtime_error"
                return {
                    "status": status,
                    "stdout": proc.stdout,
                    "stderr": proc.stderr,
                    "execution_time_ms": dur_ms,
                    "exit_code": proc.returncode,
                }
            except subprocess.TimeoutExpired:
                return {
                    "status": "time_limit_exceeded",
                    "stdout": "",
                    "stderr": f"Execution timed out after {timeout_seconds} seconds.",
                    "execution_time_ms": int(timeout_seconds * 1000),
                    "exit_code": -1,
                }
            except Exception as e:
                return {
                    "status": "runtime_error",
                    "stdout": "",
                    "stderr": str(e),
                    "execution_time_ms": 0,
                    "exit_code": -1,
                }

        elif lang == "cpp":
            src_path = tmp_dir / "solution.cpp"
            src_path.write_text(code, encoding="utf-8")
            exe_path = tmp_dir / "solution.exe"

            # Compile with static linking for libstdc++ and winpthreads
            try:
                comp = subprocess.run(
                    [tools["g++"], "-O2", "-static", "-std=c++17", str(src_path), "-o", str(exe_path)],
                    capture_output=True,
                    text=True,
                    timeout=compile_timeout,
                    cwd=str(tmp_dir),
                )
            except subprocess.TimeoutExpired:
                return {
                    "status": "compile_error",
                    "stdout": "",
                    "stderr": "Compilation timed out.",
                    "execution_time_ms": 0,
                    "exit_code": -1,
                }
            if comp.returncode != 0:
                return {
                    "status": "compile_error",
                    "stdout": "",
                    "stderr": comp.stderr,
                    "execution_time_ms": 0,
                    "exit_code": comp.returncode,
                }

            # Execute
            start_t = time.perf_counter()
            try:
                proc = subprocess.run(
                    [str(exe_path)],
                    input=stdin,
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds,
                    cwd=str(tmp_dir),
                )
                dur_ms = int((time.perf_counter() - start_t) * 1000)
                status = "success" if proc.returncode == 0 else "runtime_error"
                return {
                    "status": status,
                    "stdout": proc.stdout,
                    "stderr": proc.stderr,
                    "execution_time_ms": dur_ms,
                    "exit_code": proc.returncode,
                }
            except subprocess.TimeoutExpired:
                return {
                    "status": "time_limit_exceeded",
                    "stdout": "",
                    "stderr": f"Execution timed out after {timeout_seconds} seconds.",
                    "execution_time_ms": int(timeout_seconds * 1000),
                    "exit_code": -1,
                }
            except Exception as e:
                return {
                    "status": "runtime_error",
                    "stdout": "",
                    "stderr": str(e),
                    "execution_time_ms": 0,
                    "exit_code": -1,
                }

        elif lang == "java":
            # Extract or default class name
            class_name = "Solution"
            for line in code.splitlines():
                if "public class" in line:
                    parts = line.split("public class")[1].split("{")[0].strip().split()
                    if parts:
                        class_name = parts[0]
                        break

            src_path = tmp_dir / f"{class_name}.java"
            src_path.write_text(code, encoding="utf-8")

            # Compile
            try:
                comp = subprocess.run(
                    [tools["javac"], str(src_path)],
                    capture_output=True,
                    text=True,
                    timeout=compile_timeout,
                    cwd=str(tmp_dir),
                )
            except subprocess.TimeoutExpired:
                return {
                    "status": "compile_error",
                    "stdout": "",
                    "stderr": "Compilation timed out.",
                    "execution_time_ms": 0,
                    "exit_code": -1,
                }
            if comp.returncode != 0:
                return {
                    "status": "compile_error",
                    "stdout": "",
                    "stderr": comp.stderr,
                    "execution_time_ms": 0,
                    "exit_code": comp.returncode,
                }

            # Execute
            start_t = time.perf_counter()
            try:
                proc = subprocess.run(
                    [tools["java"], "-cp", str(tmp_dir), class_name],
                    input=stdin,
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds,
                    cwd=str(tmp_dir),
                )
                dur_ms = int((time.perf_counter() - start_t) * 1000)
                status = "success" if proc.returncode == 0 else "runtime_error"
                return {
                    "status": status,
                    "stdout": proc.stdout,
                    "stderr": proc.stderr,
                    "execution_time_ms": dur_ms,
                    "exit_code": proc.returncode,
                }
            except subprocess.TimeoutExpired:
                return {
                    "status": "time_limit_exceeded",
                    "stdout": "",
                    "stderr": f"Execution timed out after {timeout_seconds} seconds.",
                    "execution_time_ms": int(timeout_seconds * 1000),
                    "exit_code": -1,
                }
            except Exception as e:
                return {
                    "status": "runtime_error",
                    "stdout": "",
                    "stderr": str(e),
                    "execution_time_ms": 0,
                    "exit_code": -1,
                }

        elif lang == "javascript":
            script_path = tmp_dir / "solution.js"
            script_path.write_text(code, encoding="utf-8")
            cmd = [tools["node"], str(script_path)]

            start_t = time.perf_counter()
            try:
                proc = subprocess.run(
                    cmd,
                    input=stdin,
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds,
                    cwd=str(tmp_dir),
                )
                dur_ms = int((time.perf_counter() - start_t) * 1000)
                status = "success" if proc.returncode == 0 else "runtime_error"
                return {
                    "status": status,
                    "stdout": proc.stdout,
                    "stderr": proc.stderr,
                    "execution_time_ms": dur_ms,
                    "exit_code": proc.returncode,
                }
            except subprocess.TimeoutExpired:
                return {
                    "status": "time_limit_exceeded",
                    "stdout": "",
                    "stderr": f"Execution timed out after {timeout_seconds} seconds.",
                    "execution_time_ms": int(timeout_seconds * 1000),
                    "exit_code": -1,
                }
            except Exception as e:
                return {
                    "status": "runtime_error",
                    "stdout": "",
                    "stderr": str(e),
                    "execution_time_ms": 0,
                    "exit_code": -1,
                }

        elif lang == "typescript":
            script_path = tmp_dir / "solution.ts"
            script_path.write_text(code, encoding="utf-8")
            cmd = [tools["node"], "--experimental-strip-types", str(script_path)]

            start_t = time.perf_counter()
            try:
                proc = subprocess.run(
                    cmd,
                    input=stdin,
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds,
                    cwd=str(tmp_dir),
                )
                dur_ms = int((time.perf_counter() - start_t) * 1000)
                status = "success" if proc.returncode == 0 else "runtime_error"
                return {
                    "status": status,
                    "stdout": proc.stdout,
                    "stderr": proc.stderr,
                    "execution_time_ms": dur_ms,
                    "exit_code": proc.returncode,
                }
            except subprocess.TimeoutExpired:
                return {
                    "status": "time_limit_exceeded",
                    "stdout": "",
                    "stderr": f"Execution timed out after {timeout_seconds} seconds.",
                    "execution_time_ms": int(timeout_seconds * 1000),
                    "exit_code": -1,
                }
            except Exception as e:
                return {
                    "status": "runtime_error",
                    "stdout": "",
                    "stderr": str(e),
                    "execution_time_ms": 0,
                    "exit_code": -1,
                }

        elif lang == "web":
            # HTML/CSS/JavaScript client bundle
            return {
                "status": "success",
                "stdout": "Web payload compiled for live preview.",
                "stderr": "",
                "execution_time_ms": 1,
                "exit_code": 0,
            }

        else:
            return {
                "status": "runtime_unavailable",
                "stdout": "",
                "stderr": f"Compiler runtime for '{language}' is not installed on this evaluation worker. Please write solutions in Python 3, C, C++, Java, JavaScript, TypeScript, or Web (HTML/CSS/JS).",
                "execution_time_ms": 0,
                "exit_code": -1,
            }


def evaluate_test_cases(language: str, code: str, test_cases: list) -> dict:
    results = []
    passed = 0
    total = len(test_cases)

    for i, tc in enumerate(test_cases, start=1):
        input_data = (tc.input_data if hasattr(tc, "input_data") else tc.get("input_data")) or ""
        expected_output = (
            tc.expected_output if hasattr(tc, "expected_output") else tc.get("expected_output")
        ) or ""
        is_hidden = bool(tc.is_hidden if hasattr(tc, "is_hidden") else tc.get("is_hidden"))

        run_res = run_code(language, code, stdin=input_data, timeout_seconds=5.0)
        actual = (run_res.get("stdout") or "").strip()
        expected = expected_output.strip()

        is_passed = run_res.get("status") == "success" and actual == expected
        if is_passed:
            passed += 1

        results.append(
            {
                "case_number": i,
                "passed": is_passed,
                "status": run_res.get("status"),
                "input": "<Hidden>" if is_hidden else input_data,
                "expected": "<Hidden>" if is_hidden else expected,
                "actual": "<Hidden>" if is_hidden else actual,
                "error": run_res.get("stderr") if not is_passed else None,
                "execution_time_ms": run_res.get("execution_time_ms", 0),
            }
        )

    return {
        "passed": passed,
        "total": total,
        "all_passed": (passed == total) if total > 0 else True,
        "score_percent": int((passed / total) * 100) if total > 0 else 100,
        "results": results,
    }
