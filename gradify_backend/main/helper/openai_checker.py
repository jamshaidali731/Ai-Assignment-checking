import openai
import os


def openai_checker(teacher,student):

        client = openai.OpenAI(api_key=os.environ.get("OPENAI_KEY"))

        
        
        prompt = f"Teacher: {teacher}\nStudent: {student}\nScore out of 100:"

        # Send to model
        response = client.chat.completions.create(
            model="ft:gpt-4.1-nano-2025-04-14:fyp:mrprof:C2JKUCeS",
            messages=[
                {
                    "role": "system",
                    "content": (
                                "You are a fair and precise teacher. Compare the student's answer with the teacher's reference. "
                                "Award a score out of 100 based on semantic correctness: give 100 only if all key points match in meaning. "
                                "If some points are missing or incorrect, deduct proportionally. Match every point from the teacher's answer. "
                                "Only reply with the numeric score—no explanation, no extra text."
                            )

                    #"content": "You are a fair teacher. Compare the student's answer with the teacher's reference and give a short score out of 100 if all points match semantically 100 marks else according to correctness. Match all points of teacher with student. Only reply with the numeric score."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.5,
            max_tokens=10
        )

        
        # Output score
        score = response.choices[0].message.content.strip()
        return score