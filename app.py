from fastapi import FastAPI
from pydantic import BaseModel
import requests
from bs4 import BeautifulSoup
from transformers import pipeline
import nltk
nltk.download("punkt")

app = FastAPI()

# ---- ML MODELS ----
summarizer = pipeline("summarization", model="facebook/bart-large-cnn")
ner_model = pipeline("ner", grouped_entities=True, model="dslim/bert-base-NER")

# ---- REQUEST BODY MODEL ----
class UrlRequest(BaseModel):
    url: str


# ---- HELPER FUNCTIONS ----

def extract_text_from_url(url):
    """Extract readable text from a news article URL"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    try:
        page = requests.get(url, headers=headers, timeout=15)
        print(f"[DEBUG] Fetching {url} - Status: {page.status_code}")
        
        soup = BeautifulSoup(page.text, "html.parser")

        # remove scripts, styles, nav, footer
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
            tag.decompose()

        # Strategy 1: Look for <article> tag
        article = soup.find("article")
        if article:
            text = article.get_text(" ", strip=True)
            if len(text) > 100:
                print(f"[DEBUG] Strategy 1 (article) success: {len(text)} chars")
                return text

        # Strategy 2: Look for main content divs
        main_div = soup.find("div", {"id": ["content", "main", "story-body", "article-body", "post-content"]}) or \
                   soup.find("div", {"class": ["content", "main", "story-body", "article-body", "post-content", "entry-content"]})
        if main_div:
            text = main_div.get_text(" ", strip=True)
            if len(text) > 100:
                print(f"[DEBUG] Strategy 2 (div) success: {len(text)} chars")
                return text

        # Strategy 3: Fallback - all paragraphs
        paragraphs = soup.find_all("p")
        text = " ".join([p.get_text() for p in paragraphs])
        if len(text) > 50:
             print(f"[DEBUG] Strategy 3 (paragraphs) success: {len(text)} chars")
             return text
        
        # Strategy 4: Last Resort - Whole Body Text
        if soup.body:
            text = soup.body.get_text(" ", strip=True)
            print(f"[DEBUG] Strategy 4 (body) used: {len(text)} chars")
            return text

        return ""
    except Exception as e:
        print(f"[ERROR] Extraction failed: {e}")
        return ""


def extract_publish_date(html):
    """Extract publish date from meta tags"""
    soup = BeautifulSoup(html, "html.parser")
    
    # List of common meta tags for publish date
    meta_tags = [
        {"property": "article:published_time"},
        {"property": "og:published_time"},
        {"name": "date"},
        {"name": "pubdate"},
        {"name": "publish-date"},
        {"itemprop": "datePublished"}
    ]
    
    for tag in meta_tags:
        meta = soup.find("meta", tag)
        if meta and meta.get("content"):
            return meta["content"]
            
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
    publish_date = extract_publish_date(html)

    # step 5: extract events (NER based)
    events = extract_events_from_text(article_text[:1000])

    return {
        "summary": summary,
        "events": events,
        "publish_date": publish_date
    }
