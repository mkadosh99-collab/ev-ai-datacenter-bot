import os
import time
import random
import sqlite3
import requests
from openai import OpenAI
import tweepy
from dotenv import load_dotenv

load_dotenv()

# === Config ===
XAI_API_KEY = os.getenv("XAI_API_KEY")
TW_BEARER = os.getenv("TW_BEARER_TOKEN")
TW_API_KEY = os.getenv("TW_CONSUMER_KEY")
TW_API_SECRET = os.getenv("TW_CONSUMER_SECRET")
TW_ACCESS_TOKEN = os.getenv("TW_ACCESS_TOKEN")
TW_ACCESS_SECRET = os.getenv("TW_ACCESS_TOKEN_SECRET")

client = OpenAI(api_key=XAI_API_KEY, base_url="https://api.x.ai/v1")

twitter = tweepy.Client(
    bearer_token=TW_BEARER,
    consumer_key=TW_API_KEY,
    consumer_secret=TW_API_SECRET,
    access_token=TW_ACCESS_TOKEN,
    access_token_secret=TW_ACCESS_SECRET,
)

# Simple SQLite DB for used topics
conn = sqlite3.connect('topics.db')
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS used_topics (topic TEXT PRIMARY KEY, date INTEGER)''')
conn.commit()

c.execute("SELECT topic FROM used_topics")
used_topics = {row[0] for row in c.fetchall()}

# 50 starter topic ideas (expandable)
topic_pool = [
    "Why Tesla’s new 800V Cybercab pack is a datacenter cooling breakthrough in disguise",
    "How xAI’s Memphis supercluster is forcing utilities to rethink EV-scale demand response",
    "Liquid immersion cooling is coming to robotaxis — here’s the 2026 roadmap",
    "Training Grok-5 on 100k H100s will consume as much power as 40,000 homes",
    "The hidden 1.21 GW datacenter inside Tesla’s Cortex cluster in Austin",
    "Why NVIDIA GB200 racks are pushing datacenters toward direct 800V DC power",
    "Edge AI in EVs: How Tesla's HW5 is turning cars into mini datacenters",
    "The power crisis: Why AI training clusters need nuclear co-location by 2027",
    "From FSD data to Grok fine-tuning: Tesla's secret EV-AI feedback loop",
    "Datacenter heat reuse for EV charging stations — the $10B opportunity",
    # Add more here as needed...
]

def pick_topic():
    available = [t for t in topic_pool if t not in used_topics]
    if not available:
        return "EV + AI + Datacenter news roundup — fresh insights from the frontier"
    topic = random.choice(available)
    c.execute("INSERT OR IGNORE INTO used_topics (topic, date) VALUES (?, ?)", (topic, int(time.time())))
    conn.commit()
    return topic

def generate_thread(topic):
    prompt = f"""
    Write a viral 7–10 tweet X/Twitter thread about this exact topic:
    "{topic}"

    Tone: technical but exciting, for engineers + investors.
    Rules:
    - Start with a bold hook tweet (<270 chars for image)
    - Use real numbers and recent facts when possible
    - End with a question to drive replies
    - Add 2–3 relevant emojis max
    - Number tweets like 1/ , 2/ , etc.
    """
    resp = client.chat.completions.create(
        model="grok-3",  # Use "grok-4" if you have access; cheaper with grok-3
        messages=[{"role": "user", "content": prompt}],
        temperature=0.92,
        max_tokens=2500,
    )
    return resp.choices[0].message.content.strip()

def generate_image(topic):
    resp = client.images.generate(
        model="grok",  # xAI's image gen
        prompt=f"Ultra-realistic futuristic scene: {topic}, cinematic lighting, highly detailed, 16:9 aspect ratio",
        n=1,
        size="1024x1024"
    )
    return resp.data[0].url

def post_thread():
    topic = pick_topic()
    print(f"Generating thread for: {topic}")
    thread = generate_thread(topic)
    image_url = generate_image(topic)
    
    # Download image temporarily
    img_data = requests.get(image_url).content
    with open('temp_image.jpg', 'wb') as f:
        f.write(img_data)
    
    # Parse tweets (split by lines with numbers)
    tweets = [t.strip() for t in thread.split('\n') if t.strip() and any(char.isdigit() for char in t if char != '/') and '/' in t]
    
    # Auth for v1 API (needed for media upload)
    auth = tweepy.OAuth1UserHandler(TW_API_KEY, TW_API_SECRET, TW_ACCESS_TOKEN, TW_ACCESS_SECRET)
    api_v1 = tweepy.API(auth)
    
    # Upload image
    media = api_v1.media_upload('temp_image.jpg')
    media_id = media.media_id_string
    
    previous_id = None
    for i, tweet in enumerate(tweets[:10]):  # Limit to 10 tweets
        if i == 0:
            # First tweet with image
            response = twitter.create_tweet(text=tweet, media_ids=[media_id])
        else:
            # Replies
            response = twitter.create_tweet(text=tweet, in_reply_to_tweet_id=previous_id)
        previous_id = response.data['id']
        print(f"Posted tweet {i+1}: {tweet[:50]}...")
        time.sleep(3)  # Rate limit buffer
    
    # Cleanup
    os.remove('temp_image.jpg')
    print("Thread posted successfully!")

if __name__ == "__main__":
    post_thread()
