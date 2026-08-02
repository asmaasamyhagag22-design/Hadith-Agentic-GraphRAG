import sys 
import json
from pathlib import Path
import os 
from dotenv import load_dotenv
sys.path.insert(0 , str(Path(__file__).resolve().parent))

from retrieve import retrieve_relevant_chunks
from groq import Groq
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY is not set in the environment variables.")

client = Groq(api_key=GROQ_API_KEY)

def answer_question(question, k=5):
    relevent_chunks = retrieve_relevant_chunks(question, k)
    context_text = ""
    for chunk in relevent_chunks:
        context_text += f"Hadith ID: {chunk['hadith_id']}\n"
        context_text += f"Text: {chunk['text']}\n"
        context_text += f"Metadata: {chunk['metadata']}\n\n"

        ssystem_prompt = f"""
أنت مساعد افتراضي متخصص في شرح وتفسير الأحاديث النبوية.
المهمة: ستقوم بتحليل الأحاديث النبوية التي تم توفيرها لك ** فقط **، وتقديم شرح مفصل لها.
السياق (أحاديث من صحيح مسلم): 
{context_text}

التعليمات الصارمة:
1. أجب فقط بناءً على المعلومات الموجودة في السياق.
2. إذا كانت الإجابة غير موجودة بوضوح في السياق، أجب بالجملة التالية فقط: "المصادر المتاحة لا تجيب عن هذا السؤال" — بدون أي استشهاد أو رقم حديث.
3. اكتب إجابة واضحة ومباشرة.
4. اذكر أرقام الأحاديث التي استندت إليها في نهاية إجابتك بهذا الشكل: (المصدر: صحيح مسلم، حديث رقم X)، وذلك **فقط** إذا قدمت إجابة من السياق.
"""
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question}
            ],)
        return response.choices[0].message.content.strip(), relevent_chunks



if __name__ == "__main__":

    question = input("Enter your question: ")
    answer, chunks = answer_question(question)
    print("\nAnswer:")
    print(answer)
    print("\nRelevant Chunks:")
    for chunk in chunks:
        print(f"Hadith ID: {chunk['hadith_id']}, Score: {chunk['score']}")