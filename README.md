# Event Extractor ML Service

## Setup

1. Install Python 3.10+
2. Create virtual environment:
   python -m venv venv

3. Activate it:
   venv\Scripts\activate

4. Install dependencies:
   pip install -r requirements.txt

5. Install spaCy model:
   python -m spacy download en_core_web_sm

6. Run the server:
   uvicorn app:app --reload --port 8000
