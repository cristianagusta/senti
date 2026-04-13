import os
from dotenv import load_dotenv

load_dotenv()

import motor.motor_asyncio
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from collections import Counter
import googleapiclient.discovery
import re
import time
import unicodedata
import requests
from fastapi.middleware.cors import CORSMiddleware

DEVELOPER_KEY = os.getenv("DEVELOPER_KEY")
MONGO_URI = os.getenv("MONGO_URI")
HF_API_KEY = os.getenv("HF_API_KEY")

client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
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

youtube = googleapiclient.discovery.build(
    "youtube",
    "v3",
    developerKey=DEVELOPER_KEY,
    cache_discovery=False
)

HF_API_URL = "https://router.huggingface.co/hf-inference/models/mdhugol/indonesia-bert-sentiment-classification"

LABEL_INDEX = {
    "LABEL_0": "positive",
    "LABEL_1": "neutral",
    "LABEL_2": "negative"
}

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

def classify_batch(texts):
    headers = {
        "Authorization": f"Bearer {HF_API_KEY}"
    }

    response = requests.post(
        HF_API_URL,
        headers=headers,
        json={"inputs": texts}
    )

    data = response.json()

    if isinstance(data, dict) and "error" in data:
        if "loading" in data["error"].lower():
            time.sleep(5)
            return classify_batch(texts)
        raise HTTPException(status_code=500, detail=data["error"])

    return data

def generate_conclusion(counts):
    total = sum(counts.values())

    if total == 0:
        return "There is no comment data available for analysis."

    percentages = {
        k: (v / total) * 100 for k, v in counts.items()
    }

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
                top_comment = item['snippet']['topLevelComment']['snippet']['textDisplay']
                cleaned_top = clean_and_normalize(top_comment)

                if cleaned_top:
                    cleaned_comments.append(cleaned_top)

                if "replies" in item:
                    for reply in item["replies"]["comments"]:
                        reply_text = reply["snippet"]["textDisplay"]
                        cleaned_reply = clean_and_normalize(reply_text)

                        if cleaned_reply:
                            cleaned_comments.append(cleaned_reply)

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

    texts = raw_data.get("comments", [])
    labels = []
    processed = []

    batch_size = 5

    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]

        try:
            results = classify_batch(batch)

            if not isinstance(results, list) or len(results) != len(batch):
                raise Exception("Mismatch results")

        except:
            results = []
            for text in batch:
                try:
                    single_result = classify_batch([text])

                    if isinstance(single_result, list):
                        results.append(single_result[0])
                    else:
                        results.append(single_result)

                except:
                    results.append(None)

        for j, text in enumerate(batch):
            try:
                res = results[j]

                if res is None:
                    raise Exception()

                if isinstance(res, dict):
                    res = [res]

                top = max(res, key=lambda x: x["score"])
                label = LABEL_INDEX.get(top["label"], "unknown")

            except:
                label = "unknown"

            labels.append(label)
            processed.append({
                "text": text,
                "label": label,
                "confidence": round(top["score"] * 100, 2)
            })

    counts_raw = Counter(labels)

    counts = {
        "positive": counts_raw.get("positive", 0),
        "neutral": counts_raw.get("neutral", 0),
        "negative": counts_raw.get("negative", 0)
    }

    overall = max(counts, key=counts.get)

    total = len(texts)

    percentages = {
        k: round((v / total) * 100, 2) for k, v in counts.items()
    }

    conclusion = generate_conclusion(counts)

    analysis_doc = {
        "video_id": video_id,
        "summary": {
            "total": total,
            "overall": overall,
            "counts": counts,
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
