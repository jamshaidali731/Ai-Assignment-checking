from sentence_transformers import SentenceTransformer, util

#model = SentenceTransformer('paraphrase-MiniLM-L3-v2',device='cpu')




def evaluate_submission(student_text, correct_embedding, min_words, required_keywords, max_marks):
    try:
        word_count = len(student_text.split())
        if word_count < min_words:
            return 0, f"0% semantically similar (Too short: {word_count} words < {min_words})"

        
        student_embedding = model.encode(student_text, convert_to_tensor=True)
        
        similarity = util.cos_sim(correct_embedding, student_embedding).item()

    
        kw_score = sum(kw.lower() in student_text.lower() for kw in required_keywords) / len(required_keywords)

        
        marks = round((similarity * 0.9 + kw_score * 0.1) * max_marks, 2)
        if similarity < 0.30:
            # Reduce marks more aggressively, e.g., scale down to make marks "more low"
            marks = marks * 0.4  # Scale down by 70% when similarity > 30%

        marks = round(marks, 2)
        # Generate similarity text
        sim_text = f"{round(similarity * 100, 2)}% semantically similar"
        if similarity > 0.80:
            sim_text += " ⚠️ Possible copy"
        if word_count < min_words:
            sim_text += " (Too short)"

        return marks, sim_text
    except Exception as e:
        print(f"Error evaluating submission: {e}")
        return 0, f"Error: {e}"