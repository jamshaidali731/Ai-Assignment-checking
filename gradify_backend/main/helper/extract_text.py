import fitz
import docx
import chardet

def extract_text(file_path):
    try:
        if file_path.endswith(".pdf"):
            doc = fitz.open(file_path)
            return "\n".join(page.get_text("text") for page in doc)
        if file_path.endswith(".docx"):
            doc = docx.Document(file_path)
            return "\n".join(para.text for para in doc.paragraphs)
        elif file_path.endswith(".txt"):
            with open(file_path, "rb") as f:
                raw_data = f.read()
                encoding = chardet.detect(raw_data)['encoding'] or 'utf-8'
                return raw_data.decode(encoding, errors='ignore')
        else:
            return ""
    except Exception as e:
        print(f"Error extracting text from {file_path}: {e}")
        return ""