import motor.motor_asyncio
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
from collections import Counter
from transformers import pipeline, AutoTokenizer, AutoModelForSequenceClassification
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import asyncio
import googleapiclient.discovery
import re
import time
import unicodedata
from fastapi.middleware.cors import CORSMiddleware

client = motor.motor_asyncio.AsyncIOMotorClient("mongodb://localhost:27017")
db = client.thesis_sentiment 
raw_collection = db.raw_comments
analysis_collection = db.analyzed_results

app = FastAPI(title="YouTube Sentiment API (Clean Storage Version)")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Konfigurasi YouTube API
DEVELOPER_KEY = "AIzaSyB0NqKUD6O-P9dmNXx_klgZDkCHzWfPmI0" 
youtube = googleapiclient.discovery.build("youtube", "v3", developerKey=DEVELOPER_KEY)

# Konfigurasi IndoBERT
PRETRAINED_MODEL = "mdhugol/indonesia-bert-sentiment-classification"
LABEL_INDEX = {'LABEL_0': 'positive', 'LABEL_1': 'neutral', 'LABEL_2': 'negative'}
classifier = None
generator_model = None
generator_tokenizer = None


def clean_and_normalize(text):
    if not text:
        return ""
    text = unicodedata.normalize('NFKD', text)
    text = text.encode('ascii', 'ignore').decode('utf-8')
    text = text.replace('ß', 's') 
    text = re.sub(r'[^a-zA-Z0-9\s]', ' ', text)
    text = " ".join(text.lower().split())
    return text

def get_video_id(url: str):
    reg = r"(?:v=|\/)([0-9A-Za-z_-]{11}).*"
    match = re.search(reg, url)
    if match:
        return match.group(1)
    return None

def load_model():
    global classifier
    print("--- Memuat Model IndoBERT... ---")
    model = AutoModelForSequenceClassification.from_pretrained(PRETRAINED_MODEL)
    tokenizer = AutoTokenizer.from_pretrained(PRETRAINED_MODEL)
    classifier = pipeline("sentiment-analysis", model=model, tokenizer=tokenizer)
    print("--- Model Siap! ---")

 #def load_generator():
  #  global generator_model, generator_tokenizer
   # print("--- Memuat Model Conclusion (FLAN-T5)... ---")
    #generator_tokenizer = AutoTokenizer.from_pretrained("google/flan-t5-base")
    #generator_model = AutoModelForSeq2SeqLM.from_pretrained("google/flan-t5-base")
    #print("--- Model Conclusion Siap! ---")

def generate_conclusion(counts):
    total = sum(counts.values())

    if total == 0:
        return "There is no comment data available for analysis."

    percentages = {
        k: (v / total) * 100 for k, v in counts.items()
    }

    pos_pct = percentages.get("positive", 0)
    neg_pct = percentages.get("negative", 0)
    neu_pct = percentages.get("neutral", 0)

    max_label = max(counts, key=counts.get)
    max_pct = percentages[max_label]

    if max_pct >= 50:
        if max_label == "positive":
            return f"The majority of users express positive sentiment ({max_pct:.1f}%), indicating that the video is generally well received."
        elif max_label == "negative":
            return f"The majority of users express negative sentiment ({max_pct:.1f}%), suggesting dissatisfaction with the video."
        else:
            return f"The majority of users express neutral sentiment ({max_pct:.1f}%), indicating a generally moderate or indifferent response."
    else:
        if max_label == "positive":
            return f"The sentiment tends to be positive ({max_pct:.1f}%), but it is not strongly dominant as opinions remain diverse."
        elif max_label == "negative":
            return f"The sentiment tends to be negative ({max_pct:.1f}%), but it is not dominant due to varied opinions."
        else:
            return f"The sentiment tends to be neutral ({max_pct:.1f}%), with a relatively diverse distribution of opinions."

@app.on_event("startup")
async def startup():
    await asyncio.to_thread(load_model)
    #await asyncio.to_thread(load_generator)

class URLRequest(BaseModel):
    url: str

@app.post("/scrapping")
async def scrape_youtube_api(request: URLRequest):
    video_id = get_video_id(request.url)
    if not video_id:
        raise HTTPException(status_code=400, detail="ID Video tidak ditemukan")

    try:
        cleaned_comments = [] 
        next_page_token = None

        while True:
            youtube_request = youtube.commentThreads().list(
                part="snippet",
                videoId=video_id,
                maxResults=100, 
                textFormat="plainText",
                pageToken=next_page_token 
            )
            response = youtube_request.execute()

            for item in response.get('items', []):
                comment_text = item['snippet']['topLevelComment']['snippet']['textDisplay']
                cleaned_text = clean_and_normalize(comment_text)

                if cleaned_text:
                    cleaned_comments.append(cleaned_text)

            next_page_token = response.get('nextPageToken')
            if not next_page_token:
                break

        if not cleaned_comments:
            return {"status": "Empty", "message": "Tidak ada komentar valid."}

        document = {
            "video_id": video_id,
            "url": request.url,
            "total_scraped": len(cleaned_comments),
            "comments": cleaned_comments, 
            "source": "YouTube API v3",
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }

        await raw_collection.update_one(
            {"video_id": video_id},
            {"$set": document},
            upsert=True
        )
        
        return {
            "status": "Success",
            "message": f"Berhasil mengambil {len(cleaned_comments)} komentar.",
            "data": document 
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"API Error: {str(e)}")

@app.post("/analyze")
async def analyze_sentiment(request: URLRequest):
    video_id = get_video_id(request.url)
    raw_data = await raw_collection.find_one({"video_id": video_id})

    if not raw_data:
        raise HTTPException(status_code=404, detail="Data belum di-scrape.")

    if classifier is None:
        raise HTTPException(status_code=500, detail="Model Classifier belum siap.")

    texts = raw_data.get("comments", [])
    labels = []
    processed = []

    batch_size = 32

    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]

        results = await asyncio.to_thread(
            classifier,
            batch,
            truncation=True,
            max_length=512
        )

        for res in results:
            label = LABEL_INDEX.get(res["label"], "unknown")
            labels.append(label)
            processed.append({
                "label": label,
                "confidence": f"{res['score']*100:.2f}%"
            })

    counts = Counter(labels)
    overall = counts.most_common(1)[0][0] if counts else "N/A"

    total = len(texts)

    percentages = {
        k: round((v / total) * 100, 2) for k, v in counts.items()
    } if total > 0 else {}

    conclusion = generate_conclusion(counts)

    analysis_doc = {
        "video_id": video_id,
        "summary": {
            "total": total,
            "overall": overall,
            "counts": dict(counts),
            "percentages": percentages,
            "conclusion": conclusion
        },
        "results": processed,
        "analyzed_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }

    await analysis_collection.update_one(
        {"video_id": video_id},
        {"$set": analysis_doc},
        upsert=True
    )

    return analysis_doc

@app.get("/all-results")
async def get_results(limit: int = 10):
    cursor = analysis_collection.find().sort("analyzed_at", -1).limit(limit)
    results = await cursor.to_list(length=limit) 
    for res in results:
        res["_id"] = str(res["_id"])
    return {"data": results}
