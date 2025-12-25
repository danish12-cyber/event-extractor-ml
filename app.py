from fastapi import FastAPI
from pydantic import BaseModel
import requests
from bs4 import BeautifulSoup
from transformers import pipeline
import nltk
nltk.download("punkt")
from newspaper import Article

app = FastAPI()

# ---- ML MODELS ----
summarizer = pipeline("summarization", model="facebook/bart-large-cnn")
ner_model = pipeline("ner", grouped_entities=True, model="dslim/bert-base-NER")

# ---- REQUEST BODY MODEL ----
class UrlRequest(BaseModel):
    url: str


# ---- HELPER FUNCTIONS ----

def extract_text_from_url(url):
    """Extract readable text from a news article URL using newspaper3k"""
    try:
        article = Article(url)
        article.download()
        article.parse()
        return article.text
    except Exception as e:
        print(f"Error extracting text: {e}")
        return ""


def extract_publish_date(url):
    """Extract publish date using newspaper3k"""
    try:
        article = Article(url)
        article.download()
        article.parse()
        return str(article.publish_date) if article.publish_date else "Unknown"
    except Exception:
        return "Unknown"


def extract_events_from_text(text):
    """Extract named entities as events"""
    entities = ner_model(text)
    # Expanded entities to include Organizations and Locations as they are often the 'what' and 'where' of events
    events = [e["word"] for e in entities if e["entity_group"] in ["EVENT", "MISC", "ORG", "LOC"]]
    # Deduplicate while preserving order
    seen = set()
    unique_events = []
    for ev in events:
        if ev not in seen:
            unique_events.append(ev)
            seen.add(ev)
    return unique_events[:15]


# ---- MAIN API ROUTE ----

@app.post("/extract")
async def extract_data(payload: UrlRequest):

    # step 1: fetch article HTML
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    page = requests.get(payload.url, headers=headers, timeout=10)
    html = page.text

    # step 2: extract full text
    article_text = extract_text_from_url(payload.url)

    if len(article_text) < 50:
        return {"error": "Article text too short to analyze."}

    # step 3: summarization
    summary = summarizer(article_text[:4000], max_length=130, min_length=30, do_sample=False)[0]['summary_text']

    # step 4: extract publish date
    publish_date = extract_publish_date(payload.url)

    # step 5: extract events (NER based)
    events = extract_events_from_text(article_text[:1000])

    return {
        "summary": summary,
        "events": events,
        "publish_date": publish_date
    }
