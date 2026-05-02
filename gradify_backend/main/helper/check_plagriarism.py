from difflib import SequenceMatcher


def literal_similarity(text1, text2):
    return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()


def check_plagiarism(student_embeddings, submission_id_to_student):
    plagiarism_results = []
    student_files = list(student_embeddings.keys())
    for i, file1 in enumerate(student_files):
        for file2 in student_files[i + 1:]:
            # student_embeddings here should now be raw text, not embeddings
            sim = literal_similarity(student_embeddings[file1], student_embeddings[file2])
            if sim > 0.80:
                student1_name = submission_id_to_student.get(file1, "Unknown")
                student2_name = submission_id_to_student.get(file2, "Unknown")
                plagiarism_results.append((student1_name, student2_name, round(sim * 100, 2)))
    return plagiarism_results