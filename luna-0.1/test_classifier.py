from core.classifier import TaskClassifier


classifier = TaskClassifier()


TEST_CASES = [
    ("What is a turbocharger?", "fast"),
    ("What happened in the stock market today?", "research"),
    ("Debug this Python error for me.", "coding"),
    ("Write me a funny Instagram caption.", "creative"),
    ("What do you think about this?", "conversation"),
    ("How do I reset my router?", "general"),
    ("Calculate 25 * 17.", "fast"),
    ("Compare the BMW M3 and M4.", "research"),
    ("Come up with some hard Instagram usernames.", "creative"),
    ("Why is my Python script throwing a traceback?", "coding"),
]


def main():
    print("--- TASK CLASSIFIER TEST ---")

    passed = 0

    for prompt, expected in TEST_CASES:
        result = classifier.classify(prompt)

        status = "PASS" if result.task == expected else "FAIL"

        print(
            f"[{status}] "
            f"{prompt!r} "
            f"→ {result.task} "
            f"(expected: {expected}, "
            f"confidence: {result.confidence:.2f})"
        )

        if result.task == expected:
            passed += 1

    print(f"\n{passed}/{len(TEST_CASES)} tests passed.")

    assert passed == len(TEST_CASES)

    print("✅ TASK CLASSIFIER TEST PASSED")


if __name__ == "__main__":
    main()
