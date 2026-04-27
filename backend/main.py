import os
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from collections import Counter
import googleapiclient.discovery
import re
import unicodedata
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from pymongo import MongoClient
from datetime import datetime, timedelta
import bcrypt
import random

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DEVELOPER_KEY = os.getenv("DEVELOPER_KEY")
HF_API_KEY = os.getenv("HF_API_KEY")
MONGO_URL = os.getenv("MONGO_URL")

client = MongoClient(MONGO_URL)
db = client["senti"]

users_col = db["users"]
history_col = db["history"]

youtube = googleapiclient.discovery.build(
    "youtube",
    "v3",
    developerKey=DEVELOPER_KEY,
    cache_discovery=False
)

HF_URL = "https://router.huggingface.co/hf-inference/models/mdhugol/indonesia-bert-sentiment-classification"
session = requests.Session()

LABEL_INDEX = {
    "LABEL_0": "Positive",
    "LABEL_1": "Neutral",
    "LABEL_2": "Negative"
}

MAX_COMMENTS = 150
RAW_LIMIT = 500
BATCH_SIZE = 5

class URLRequest(BaseModel):
    url: str

class AuthRequest(BaseModel):
    email: str
    password: str
    username: str | None = None

class SaveRequest(BaseModel):
    user: str
    videoId: str
    result: dict

def clean(text):
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("utf-8")
    text = re.sub(r"[^a-zA-Z0-9\s]", " ", text)
    return " ".join(text.lower().split())

def truncate(text, max_words=30):
    return " ".join(text.split()[:max_words])

def get_video_id(url: str):
    try:
        if "youtu.be" in url:
            return url.split("youtu.be/")[1].split("?")[0]
        m = re.search(r"v=([0-9A-Za-z_-]{11})", url)
        if m:
            return m.group(1)
        m = re.search(r"(shorts|live)/([0-9A-Za-z_-]{11})", url)
        if m:
            return m.group(2)
    except:
        return None
    return None

def get_video_title(video_id: str):
    try:
        r = youtube.videos().list(
            part="snippet",
            id=video_id
        ).execute()
        items = r.get("items", [])
        if not items:
            return "Unknown Title"
        return items[0]["snippet"]["title"]
    except:
        return "Unknown Title"

def classify_batch(batch):
    headers = {
        "Authorization": f"Bearer {HF_API_KEY}",
        "Content-Type": "application/json"
    }
    response = session.post(
        HF_URL,
        headers=headers,
        json={"inputs": batch}
    )
    if response.status_code != 200:
        raise Exception(response.text)
    return response.json()

def conclusion(counts):
    total = sum(counts.values())
    if total == 0:
        return "There is no comment data available for analysis."
    perc = {k: (v / total) * 100 for k, v in counts.items()}
    top = max(counts, key=counts.get)
    pct = perc[top]
    if pct >= 50:
        if top == "Positive":
            return f"The majority of users express positive sentiment ({pct:.1f}%), indicating that the video is generally well received."
        if top == "Negative":
            return f"The majority of users express negative sentiment ({pct:.1f}%), suggesting dissatisfaction with the video."
        return f"The majority of users express neutral sentiment ({pct:.1f}%), indicating a generally moderate response."
    return f"The sentiment distribution is mixed, with {top} being the most common at {pct:.1f}%."

@app.post("/signup")
async def signup(req: AuthRequest):
    if users_col.find_one({"email": req.email}):
        raise HTTPException(status_code=400, detail="User already exists")
    hashed = bcrypt.hashpw(req.password.encode(), bcrypt.gensalt())
    users_col.insert_one({
        "email": req.email,
        "username": req.username,
        "password": hashed
    })
    return {
        "email": req.email,
        "username": req.username
    }

@app.post("/login")
async def login(req: AuthRequest):
    user = users_col.find_one({"email": req.email})
    if not user or not bcrypt.checkpw(req.password.encode(), user["password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {
        "email": user["email"],
        "username": user.get("username", "")
    }

@app.post("/save")
async def save(req: SaveRequest):
    title = get_video_title(req.videoId)
    history_col.insert_one({
        "user": req.user,
        "videoId": req.videoId,
        "title": title,
        "result": req.result,
        "createdAt": datetime.utcnow() + timedelta(hours=7)
    })
    return {"status": "ok"}

@app.get("/history/{email}")
async def get_history(email: str):
    data = list(
        history_col.find(
            {"user": email},
            {"_id": 0}
        ).sort("createdAt", -1)
    )
    return data

@app.post("/analyze")
async def analyze(req: URLRequest):
    vid = get_video_id(req.url)
    if not vid:
        raise HTTPException(status_code=400, detail="Invalid YouTube URL")

    try:
        comments = []
        token = None

        while True:
            r = youtube.commentThreads().list(
                part="snippet",
                videoId=vid,
                maxResults=100,
                textFormat="plainText",
                pageToken=token
            ).execute()

            for item in r.get("items", []):
                t = item["snippet"]["topLevelComment"]["snippet"]["textDisplay"]
                c = truncate(clean(t), 30)

                if c:
                    comments.append(c)

                if len(comments) >= RAW_LIMIT:
                    break

            if len(comments) >= RAW_LIMIT:
                break

            token = r.get("nextPageToken")
            if not token:
                break

        if not comments:
            return {
                "status": "NoComments",
                "message": "This video may not have accessible comments."
            }

        comments = random.sample(comments, min(MAX_COMMENTS, len(comments)))

        labels = []
        processed = []

        for i in range(0, len(comments), BATCH_SIZE):
            batch = comments[i:i+BATCH_SIZE]

            try:
                results = classify_batch(batch)

                if not isinstance(results, list) or len(results) != len(batch):
                    raise Exception("Batch mismatch")

                for j, t in enumerate(batch):
                    res = results[j]

                    if isinstance(res, dict):
                        res = [res]

                    top = max(res, key=lambda x: x["score"])
                    label = LABEL_INDEX.get(top["label"], "unknown")
                    conf = round(top["score"] * 100, 2)

                    labels.append(label)
                    processed.append({
                        "text": t,
                        "label": label,
                        "confidence": conf
                    })

            except:
                for t in batch:
                    try:
                        single = classify_batch([t])[0]

                        if isinstance(single, dict):
                            single = [single]

                        top = max(single, key=lambda x: x["score"])
                        label = LABEL_INDEX.get(top["label"], "unknown")
                        conf = round(top["score"] * 100, 2)

                    except:
                        label = "unknown"
                        conf = 0

                    labels.append(label)
                    processed.append({
                        "text": t,
                        "label": label,
                        "confidence": conf
                    })

        counts = Counter(labels)
        total = len(comments)
        overall = counts.most_common(1)[0][0]

        return {
            "video_id": vid,
            "summary": {
                "total": total,
                "overall": overall,
                "counts": dict(counts),
                "conclusion": conclusion(counts)
            },
            "results": processed
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
