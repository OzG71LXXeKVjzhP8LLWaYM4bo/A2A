## QUESTION TYPES for Deduction (generate {{COUNT}} questions):

Create "Whose reasoning is correct?" questions matching NSW Selective exam format.

**EXACT LAYOUT (MATCHES PRACTICE TEST - see Question 5):**
1. **Content field** contains (in order):
   - Premise in HTML box with inline border styling
   - Character statements as HTML `<p><strong>Name:</strong> "quote"</p>`
2. **Image** (if enabled) = Two character portraits side-by-side with names ONLY (NO quotes in image)
3. **Question field** = ONLY "If the information in the box is true, whose reasoning is correct?"

**ANSWER OPTIONS (ALWAYS EXACTLY THESE 4):**
- A. [Person1] only
- B. [Person2] only
- C. Both [Person1] and [Person2]
- D. Neither [Person1] nor [Person2]

**CHARACTER NAMES TO USE (varied and diverse):**
Use pairs like: Sara & Mila, Will & Evie, Jack & Amelia, Yifan & Ria, Alex & Jordan, Marcus & Leila, Kai & Nina, Tom & Aisha, Finn & Zoe, etc.

**CONTENT FIELD FORMAT (CRITICAL):**
The content field contains the premise box followed by character statements.

Format:
```html
<div style="border: 1px solid black; padding: 12px; margin-bottom: 12px;"><p>Premise text here...</p></div>

<p><strong>[Name1]:</strong> "[Their exact quoted statement]"</p>
<p><strong>[Name2]:</strong> "[Their exact quoted statement]"</p>
```

**QUESTION FIELD:**
The question field contains ONLY the standard question:
```
If the information in the box is true, whose reasoning is correct?
```

**IMAGE DESCRIPTION FORMAT (PORTRAITS ONLY - NO QUOTES):**
The image_description specifies character portraits with names ONLY. NO statements/quotes in the image.

```
image_type: character_portrait_dual
person1_name: [Name1]
person1_appearance: [brief description - e.g., girl with curly dark hair]
person2_name: [Name2]
person2_appearance: [brief description - e.g., boy with short hair and glasses]
```

**KEY LOGIC PATTERNS TO TEST:**

1. **Contrapositive Reasoning** - If A then B. Testing if character correctly states contrapositive (If not B then not A)
   - Premise: "Monotremes are the only type of mammal that lay eggs"
   - Correct: "If mammal lays egg, must be monotreme" AND "Not monotreme + lays egg = not mammal"
   - Incorrect: Affirming consequent or denying antecedent

2. **Conditional Logic with Sums** - If X+Y = constant, different X means different Y
   - Premise: "Reading + Writing = Total. Both got same total"
   - Correct: "Different writing = different reading" AND "Same reading = same writing"

3. **Necessary vs Sufficient Conditions** - Meeting a requirement doesn't guarantee outcome
   - Premise: "To succeed, you need X AND Y"
   - Flawed: "Has X and Y, so definitely will succeed" (treats necessary as sufficient)
   - Correct: "Lacks X, so probably won't succeed"

4. **Signal Interpretation** - What a signal indicates vs doesn't indicate
   - Premise: "Red flashing light means processor is overheating"
   - Correct: "Flashing = overheating"
   - Incorrect: "Not flashing = not overheating" (light could be on solid, or off for other reasons)

5. **Probability Language** - "Likely" vs "must" vs "might"

**EXAMPLE OUTPUT:**
```json
{
  "content": "<div style=\"border: 1px solid black; padding: 12px; margin-bottom: 12px;\"><p>At the end of each term, Mr Chen gives scores in reading and writing to each student in his English class. These two scores are then added together to give an overall score in English for the term. Last term, Sara and Mila got the same overall score in English.</p></div>\n\n<p><strong>Sara:</strong> \"If our scores in writing were different from each other, then our scores in reading must have been different too.\"</p>\n<p><strong>Mila:</strong> \"And if our scores in reading were the same, then our scores in writing must have been the same too.\"</p>",
  "question": "If the information in the box is true, whose reasoning is correct?",
  "choices": [
    {"id": "1", "text": "Sara only", "is_correct": false},
    {"id": "2", "text": "Mila only", "is_correct": false},
    {"id": "3", "text": "Both Sara and Mila", "is_correct": true},
    {"id": "4", "text": "Neither Sara nor Mila", "is_correct": false}
  ],
  "explanation": "<strong>Both are correct.</strong> Since Total = Reading + Writing is the same: If Writing differs, Reading must differ to keep the sum equal. Conversely, if Reading is the same, Writing must be the same. Both are valid contrapositives.",
  "difficulty": "2",
  "requires_image": true,
  "image_description": "image_type: character_portrait_dual\nperson1_name: Sara\nperson1_appearance: friendly girl with wavy dark hair and warm smile\nperson2_name: Mila\nperson2_appearance: girl with straight blonde hair in ponytail, thoughtful expression"
}
```

**CRITICAL RULES:**
1. Content = Premise box + Character statements (NO placeholders like {{IMAGE}})
2. Image (if enabled) = Character portraits with names ONLY (NO quotes/statements in the image)
3. Question = ONLY "If the information in the box is true, whose reasoning is correct?"
4. Answer options ALWAYS: "[Name] only" or "Both..." or "Neither..."
5. Use diverse character pairs - vary genders, ethnicities, names
6. NEVER include {{IMAGE}} or any placeholder text in the content field
