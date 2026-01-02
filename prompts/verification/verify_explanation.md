You are verifying that explanations correctly support the marked answers.

## Questions to Verify:
{{QUESTIONS_JSON}}

## Verification Criteria - ALL must pass:

1. **Logical Consistency**
   - Explanation logic leads to the marked correct answer
   - No contradictions between explanation and answer
   - Steps in explanation are valid

2. **Completeness**
   - Explains WHY the correct answer is correct
   - Ideally mentions why at least one wrong answer is wrong
   - Provides educational value

3. **Accuracy**
   - Facts stated in explanation are correct
   - Mathematical or logical steps are valid
   - No errors in reasoning

## Output Format (JSON array):
[
  {
    "question_index": 0,
    "logic_consistent": true,
    "complete": true,
    "accurate": true,
    "all_passed": true,
    "issues": []
  },
  {
    "question_index": 1,
    "logic_consistent": false,
    "complete": true,
    "accurate": false,
    "all_passed": false,
    "issues": [
      "Logic: Explanation says answer is B but marked answer is C",
      "Accuracy: Step 2 claims 5+7=13, which is incorrect (should be 12)"
    ]
  }
]

CRITICAL:
- Explanation MUST match the marked correct answer
- If explanation leads to different answer, this is a critical failure
- Be specific about what's inconsistent or inaccurate
