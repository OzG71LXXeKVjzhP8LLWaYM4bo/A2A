## QUESTION TYPES for Inference (generate {{COUNT}} questions):

Create "identify the reasoning mistake" questions matching NSW Selective exam format.

**EXACT LAYOUT (MATCHES PRACTICE TEST):**
1. **Content field** = The premise/context/rule in a box at the top
2. **Image** = Single character portrait with their name and quoted statement below
3. **Question** = "Which one of the following sentences shows the mistake [Name] has made?"

**ANSWER OPTIONS:**
Four different possible logical errors/mistakes - one is correct, three are wrong.

**CHARACTER NAMES TO USE (varied and diverse):**
Use names like: Sam, Ferdinand, Jarrah, Lisa, Alex, Maya, Noah, Priya, Marcus, Zara, Kai, Aiden, etc.

**CONTENT FIELD (premise box only):**
The content field contains ONLY the premise/context/rule. This is the information the character reasons about. Keep it clear and concise (1-3 sentences).

Examples:
- "In the Junior Golf Championship, prizes are given out to the players who finish first, second, and third, and to anyone who gets a hole-in-one."
- "Ferdinand has an atlas which he can use to look up any city in the world."
- "Jarrah's music teacher has promised that any students who did not have a chance to perform in the Spring concert will definitely be chosen to play in the Autumn concert."
- "There are two ways to qualify for the annual Grant County Athletics Championship: by winning at least three local events during the year, or by breaking a county record. This year, 10 students from Lisa's school have qualified."

**IMAGE DESCRIPTION FORMAT (CRITICAL):**
The image_description MUST specify the character with their name AND their flawed statement. Format:

```
image_type: character_portrait_single
person_name: [Name]
person_appearance: [brief description - e.g., boy with messy brown hair and thoughtful expression]
person_statement: "[Their exact quoted statement with the logical flaw]"
```

**MISTAKE TYPES TO TEST:**

1. **Assuming Non-Overlap** - Assuming categories are mutually exclusive when they can overlap
   - Context: "Prizes for 1st, 2nd, 3rd, AND anyone with hole-in-one"
   - Flawed: "One hole-in-one = 4 prize winners" (hole-in-one could be by top 3 finisher)
   - Correct answer: "The hole-in-one might have been scored by a player who finished first, second, or third"

2. **Affirming Consequence / Denying Antecedent** - Common conditional logic errors
   - Context: "Students who didn't perform in Spring WILL be chosen for Autumn"
   - Flawed: "I performed in Spring, so I WON'T be chosen for Autumn" (doesn't follow)
   - Correct answer: "Anyone who played in Spring will not play in Autumn" (inverse error)

3. **Uniqueness Assumption** - Assuming things are unique when duplicates exist
   - Context: "Atlas can look up any city"
   - Flawed: "Tell me city name, I can find the country"
   - Correct answer: "Some cities have the same name as each other" (e.g., Paris, Texas)

4. **Double-Counting / Overlap Error** - Counting the same item multiple ways
   - Context: "6 county records broken by our students, 10 qualifiers"
   - Flawed: "6 records = more than half are record-breakers"
   - Correct answer: "Some students may have broken more than one county record"

5. **Qualification vs Guarantee** - Confusing minimum requirements with certainty
   - Context: "You qualify by X OR Y"
   - Flawed: "I did X, so I'm selected" (qualification doesn't mean selection)

**EXAMPLE OUTPUT:**
```json
{
  "content": "In the Junior Golf Championship, prizes are given out to the players who finish first, second, and third, and to anyone who gets a hole-in-one.",
  "question": "Which one of the following sentences shows the mistake Sam has made?",
  "choices": [
    {"id": "1", "text": "Some players might deserve a prize even if they didn't score a hole-in-one.", "is_correct": false},
    {"id": "2", "text": "The hole-in-one might have been scored by a player who finished first, second, or third.", "is_correct": true},
    {"id": "3", "text": "Younger players might find it difficult to score a hole-in-one.", "is_correct": false},
    {"id": "4", "text": "We do not know the total number of players in the competition.", "is_correct": false}
  ],
  "explanation": "<strong>Sam assumes the hole-in-one scorer is a different person from the top 3.</strong> The person who got a hole-in-one could have also finished 1st, 2nd, or 3rd, meaning only 3 people get prizes, not 4.",
  "difficulty": "2",
  "requires_image": true,
  "image_description": "image_type: character_portrait_single\nperson_name: Sam\nperson_appearance: boy with short dark hair and thoughtful expression, casual clothing\nperson_statement: \"Well, I know that one player scored a hole-in-one this year. So that means that four players will get prizes.\""
}
```

**ANOTHER EXAMPLE:**
```json
{
  "content": "Jarrah's music teacher has promised that any students who did not have a chance to perform in the Spring concert will definitely be chosen to play in the Autumn concert.",
  "question": "Which one of the following sentences shows the mistake Jarrah has made?",
  "choices": [
    {"id": "1", "text": "Just because anyone who did not play in Spring will play in Autumn, it does not mean that anyone who played in Spring will not play in Autumn.", "is_correct": true},
    {"id": "2", "text": "Just because somebody is chosen for the concert, it does not mean they will actually perform.", "is_correct": false},
    {"id": "3", "text": "Just because Jarrah was chosen to perform at a concert in the past, it does not mean he will be chosen again in future.", "is_correct": false},
    {"id": "4", "text": "Just because someone did not perform in the Spring concert, it does not mean that they would not have liked to.", "is_correct": false}
  ],
  "explanation": "<strong>Jarrah confuses 'not A implies B' with 'A implies not B'.</strong> The teacher only promised that non-performers WILL play - this says nothing about whether Spring performers CANNOT play in Autumn.",
  "difficulty": "2",
  "requires_image": true,
  "image_description": "image_type: character_portrait_single\nperson_name: Jarrah\nperson_appearance: boy with curly black hair and friendly smile, wearing casual clothes\nperson_statement: \"Well, I did perform in the Spring concert. So that means I definitely won't be chosen for Autumn. I'll have to find something else to do.\""
}
```

**CRITICAL RULES:**
1. Content = ONLY the premise/rule (no character statement)
2. Image = Single character portrait WITH their name and flawed statement
3. Question format: "Which one of the following sentences shows the mistake [Name] has made?"
4. The character ALWAYS makes a FLAWED logical conclusion
5. Answer options describe different possible mistakes - only one is correct
6. ALL inference questions require images (requires_image: true)
7. Use diverse character names - vary genders, ethnicities
