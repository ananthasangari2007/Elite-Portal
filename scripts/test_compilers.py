import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.code_runner import run_code, evaluate_test_cases

print("Testing Python 3:")
p = run_code("python", "print('Python 3 is working!')\n")
print(p)

print("\nTesting C (GCC):")
c = run_code("c", "#include <stdio.h>\nint main() { printf(\"C GCC is working!\\n\"); return 0; }\n")
print(c)

print("\nTesting C++ (G++):")
cpp = run_code("cpp", "#include <iostream>\nint main() { std::cout << \"C++ G++ is working!\" << std::endl; return 0; }\n")
print(cpp)

print("\nTesting Java (JDK 17):")
j = run_code("java", "public class Solution { public static void main(String[] args) { System.out.println(\"Java 17 is working!\"); } }\n")
print(j)
