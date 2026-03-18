# Demo Questions for AI Front Desk

These questions showcase the full range of the AI Front Desk assistant. Try them in order for the best demo experience.

---

## General Questions (No Security Code Needed)

These questions are answered from the CABQ Family Handbook and demonstrate the RAG pipeline with page-level citations.

1. **"What are your hours of operation?"**
   - Shows: handbook search, citation with page link

2. **"What is your illness policy? When can my child come back after a fever?"**
   - Shows: detailed policy lookup, multi-paragraph response with citations

3. **"How do I enroll my child?"**
   - Shows: enrollment procedure from handbook

4. **"What meals do you serve? Do you accommodate food allergies?"**
   - Shows: nutrition/meal policy from handbook

5. **"I'd like to schedule a tour. My name is Alex Johnson, my number is 505-555-0333, and I'd prefer next Tuesday."**
   - Shows: tour scheduling tool, data capture, confirmation message

6. **"What is your policy on sunscreen and outdoor play?"**
   - Shows: specific policy lookup from handbook

7. **"I need to talk to a real person about a billing issue."**
   - Shows: graceful transfer-to-human with center phone number

---

## Child-Specific Questions (Security Code Required)

Enter the security code first via the PIN modal or by typing the 4-digit code, then ask child-specific questions.

### Sofia Martinez (Butterfly Room, age 4)
**Security Code: `7291`**

8. **Enter code `7291`**, then ask: **"How was Sofia's day today?"**
   - Shows: overview — attendance, meals, activities

9. **"What did Sofia eat for lunch today?"**
   - Shows: meal query with temporal awareness (past vs. scheduled)

10. **"Does Sofia have any allergies?"**
    - Shows: allergy info with doctor confirmation status

11. **"Who are Sofia's emergency contacts?"**
    - Shows: contact list with relationships and phone numbers

12. **"What's Sofia's payment balance?"**
    - Shows: payment info with next due date, last payment

13. **"Was Sofia on any field trips recently?"**
    - Shows: field trip info linked to classroom

---

### Liam Chen (Caterpillar Room, age 1)
**Security Code: `3847`**

14. **Enter code `3847`**, then ask: **"Has Liam been checked in today?"**
    - Shows: attendance with check-in time and who recorded it

15. **"What did Liam eat today?"**
    - Shows: meals for an infant with temporal hints

---

### Noah Williams (Ladybug Room, age 3)
**Security Code: `9283`**

16. **Enter code `9283`**, then ask: **"Tell me about Noah's week."**
    - Shows: multi-day attendance overview

---

### Other Children & Codes

| Child | Classroom | Age | Security Code |
|-------|-----------|-----|---------------|
| Liam Chen | Caterpillar Room | 1 | `3847` |
| Ava Patel | Caterpillar Room | 2 | `6152` |
| Noah Williams | Ladybug Room | 3 | `9283` |
| Emma Jackson | Ladybug Room | 2 | `4716` |
| Oliver Kim | Ladybug Room | 3 | `5039` |
| Sofia Martinez | Butterfly Room | 4 | `7291` |
| Ethan Brooks | Butterfly Room | 5 | `8624` |
| Mia Thompson | Butterfly Room | 4 | `1357` |

---

## Edge Cases to Try

17. **"What happens on snow days?"** — May not be in handbook, triggers "I'm not sure" response
18. **Enter wrong code `0000` three times** — Triggers lockout after 3 failed attempts
19. **"I'm worried about my custody arrangement"** — Triggers transfer to human (sensitive topic)
20. **Ask about a child without entering a code** — AI should prompt for security code
