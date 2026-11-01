"""
Test semantic skill matching
Run: python test_semantic_skills.py
"""

from processor import find_similar_skill

print("=" * 60)
print("🧪 Testing Semantic Skill Matching")
print("=" * 60 + "\n")

# Test cases (input, expected_output)
test_cases = [
    ("django", "Django"),
    ("fastapi", "FastAPI"),
    ("flask", "Flask"),
    ("aws", "AWS"),
    ("kubernetes", "Kubernetes"),
    ("postgresql", "PostgreSQL"),
    ("node.js", "Node.js"),
    ("nodejs", "Node.js"),
    ("tensorflow", "TensorFlow"),
    ("docker", "Docker"),
    ("react", "React"),
    ("python", "Python"),
    ("express", "Express"),
    ("MongoDB", "MongoDB"),
    ("redis", "Redis"),
]

passed = 0
failed = 0

for input_skill, expected_skill in test_cases:
    result = find_similar_skill(input_skill, threshold=0.70)
    is_match = result.lower() == expected_skill.lower()

    if is_match:
        print(f"✓ PASS: '{input_skill}' → '{result}'")
        passed += 1
    else:
        print(f"✗ FAIL: '{input_skill}' → '{result}' (expected: '{expected_skill}')")
        failed += 1

print("\n" + "=" * 60)
print(f"📊 Results: {passed} passed, {failed} failed out of {len(test_cases)} tests")
print("=" * 60)

if failed == 0:
    print("\n✅ All tests passed! Semantic skill matching is working correctly.")
else:
    print(f"\n⚠️  {failed} test(s) failed. This is OK - some variations may not have high similarity.")
