import os
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from collections import Counter
import googleapiclient.discovery
import re
import time
import unicodedata
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="YouTube Sentiment API (HF API Version)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DEVELOPER_KEY = os.getenv("DEVELOPER_KEY")
HF_API_KEY = os.getenv("HF_API_KEY")

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = ""

youtube = googleapiclient.discovery.build(
    "youtube",
    "v3",
    developerKey=DEVELOPER_KEY,
    cache_discovery=False
)

HF_URL = "https://router.huggingface.co/hf-inference/models/mdhugol/indonesia-bert-sentiment-classification"

LABEL_INDEX = {
    "LABEL_0": "positive",
    "LABEL_1": "neutral",
    "LABEL_2": "negative"
}

class URLRequest(BaseModel):
    url: str

def clean_and_normalize(text):
    if not text:
        return ""
    text = unicodedata.normalize('NFKD', text)
    text = text.encode('ascii', 'ignore').decode('utf-8')
    text = text.replace('ß', 's')
    text = re.sub(r'[^a-zA-Z0-9\s]', ' ', text)
    return " ".join(text.lower().split())

def get_video_id(url: str):
    reg = r"(?:v=|\/)([0-9A-Za-z_-]{11}).*"
    match = re.search(reg, url)
    return match.group(1) if match else None

def classify_batch(batch):
    headers = {
        "Authorization": f"Bearer {HF_API_KEY}",
        "Content-Type": "application/json"
    }

    response = requests.post(
        HF_URL,
        headers=headers,
        json={"inputs": batch}
    )

    if response.status_code != 200:
        raise Exception(f"HF API Error: {response.text}")

    return response.json()

def generate_conclusion(counts):
    total = sum(counts.values())

    if total == 0:
        return "There is no comment data available for analysis."

    percentages = {k: (v / total) * 100 for k, v in counts.items()}
    max_label = max(counts, key=counts.get)
    max_pct = percentages[max_label]

    if max_pct >= 50:
        if max_label == "positive":
            return f"The majority of users express positive sentiment ({max_pct:.1f}%), indicating that the video is generally well received."
        elif max_label == "negative":
            return f"The majority of users express negative sentiment ({max_pct:.1f}%), suggesting dissatisfaction with the video."
        else:
            return f"The majority of users express neutral sentiment ({max_pct:.1f}%), indicating a generally moderate response."
    else:
        return f"The sentiment distribution is mixed, with {max_label} being the most common at {max_pct:.1f}%."

@app.post("/analyze")
async def analyze_sentiment(request: URLRequest):
    video_id = get_video_id(request.url)
    if not video_id:
        raise HTTPException(status_code=400, detail="Invalid YouTube URL")

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
            return {"status": "Empty", "message": "No valid comments found."}

        texts = cleaned_comments
        labels = []
        processed = []

        batch_size = 5

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]

            try:
                results = classify_batch(batch)

                if not isinstance(results, list) or len(results) != len(batch):
                    raise Exception("Batch mismatch")

                for j, text in enumerate(batch):
                    res = results[j]

                    if isinstance(res, dict):
                        res = [res]

                    top = max(res, key=lambda x: x["score"])
                    label = LABEL_INDEX.get(top["label"], "unknown")
                    confidence = round(top["score"] * 100, 2)

                    labels.append(label)
                    processed.append({
                        "text": text,
                        "label": label,
                        "confidence": confidence
                    })

            except:
                for text in batch:
                    try:
                        single = classify_batch([text])[0]

                        if isinstance(single, dict):
                            single = [single]

                        top = max(single, key=lambda x: x["score"])
                        label = LABEL_INDEX.get(top["label"], "unknown")
                        confidence = round(top["score"] * 100, 2)

                    except:
                        label = "unknown"
                        confidence = 0

                    labels.append(label)
                    processed.append({
                        "text": text,
                        "label": label,
                        "confidence": confidence
                    })

        counts = Counter(labels)
        total = len(texts)

        percentages = {
            k: round((v / total) * 100, 2) for k, v in counts.items()
        }

        overall = counts.most_common(1)[0][0]
        conclusion = generate_conclusion(counts)

        return {
            "video_id": video_id,
            "summary": {
                "total": total,
                "overall": overall,
                "counts": dict(counts),
                "percentages": percentages,
                "conclusion": conclusion
            },
            "results": processed
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"API Error: {str(e)}")
