import os
import time
import random
import sqlite3
import requests
from openai import OpenAI
import tweepy
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# === Config ===
XAI_API_KEY = os.getenv("XAI_API_KEY")

# Twitter Credentials
TW_BEARER = os.getenv("TW_BEARER_TOKEN")
TW_API_KEY = os.getenv("TW_CONSUMER_KEY")
TW_API_SECRET = os.getenv("TW_CONSUMER_SECRET")
TW_ACCESS_TOKEN = os.getenv("TW_ACCESS_TOKEN")
TW_ACCESS_SECRET = os.getenv("TW_ACCESS_TOKEN_SECRET")

# Initialize xAI Client
client = OpenAI(api_key=XAI_API_KEY, base_url="https://api.x.ai/v1")

# Initialize Twitter Clients
# Client v2 for posting tweets
client_v2 = tweepy.Client(
    bearer_token=TW_BEARER,
    consumer_key=TW_API_KEY,
    consumer_secret=TW_API_SECRET,
    access_token=TW_ACCESS_TOKEN,
    access_token_secret=TW_ACCESS_SECRET,
)

# API v1.1 for media upload (Required for images)
auth = tweepy.OAuth1UserHandler(
    TW_API_KEY, TW_API_SECRET, TW_ACCESS_TOKEN, TW_ACCESS_SECRET
)
api_v1 = tweepy.API(auth)

# === Database Setup ===
conn = sqlite3.connect('topics.db')
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS used_topics (topic TEXT PRIMARY KEY, date INTEGER)''')
conn.commit()

c.execute("SELECT topic FROM used_topics")
used_topics = {row[0] for row in c.fetchall()}

# Topic Pool
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
]

def pick_topic():
    available = [t for t in topic_pool if t not in used_topics]
    if not available:
        # Fallback if all topics used
        return "EV + AI + Datacenter news roundup — fresh insights from the frontier"
    
    topic = random.choice(available)
    c.execute("INSERT OR IGNORE INTO used_topics (topic, date) VALUES (?, ?)", (topic, int(time.time())))
    conn.commit()
    return topic

def generate_thread_content(topic):
    print(f"Generating text for: {topic}")
    prompt = f"""
    Write a viral 7–10 tweet X/Twitter thread about this exact topic:
    "{topic}"

    Tone: technical but exciting, for engineers + investors.
    Rules:
    - Separate each tweet with the string "|||" so I can split them easily.
    - Start with a bold hook tweet.
    - Use real numbers and recent facts.
    - End with a question to drive replies.
    - Add 2–3 relevant emojis max per tweet.
    - Do NOT number them (e.g. don't write "1/").
    """
    
    try:
        resp = client.chat.completions.create(
            model="grok-3", 
            messages=[{"role": "user", "content": prompt}],
            temperature=0.9,
            max_tokens=2500,
        )
        content = resp.choices[0].message.content.strip()
        # Split by the separator defined in prompt
        tweets = [t.strip() for t in content.split("|||") if t.strip()]
        return tweets
    except Exception as e:
        print(f"Error generating text: {e}")
        return []

def generate_image_url(topic):
    print("Generating image...")
    prompt = f"Ultra-realistic cinematic scene: {topic}, datacenter racks, EVs, AI chips, liquid cooling, neon lights, highly detailed, dramatic lighting"
    
    # Simple retry logic
    for i in range(2):
        try:
            # Note: Ensure your xAI account has access to image models
            resp = client.images.generate(
                model="grok-2-vision-1212", # Or "grok-beta" depending on your access
                prompt=prompt,
                n=1,
                size="1024x1024"
            )
            return resp.data[0].url
        except Exception as e:
            print(f"Image gen attempt {i+1} failed: {e}")
            time.sleep(2)
            
    print("Skipping image generation.")
    return None

def post_thread():
    # 1. Get Topic
    topic = pick_topic()
    
    # 2. Generate Content
    tweets = generate_thread_content(topic)
    if not tweets:
        print("No tweets generated. Exiting.")
        return

    # 3. Generate Image
    image_url = generate_image_url(topic)
    media_id = None

    # 4. Handle Image Upload (if successful)
    if image_url:
        try:
            print("Downloading image...")
            img_data = requests.get(image_url, timeout=20).content
            filename = 'temp_image.jpg'
            
            with open(filename, 'wb') as f:
                f.write(img_data)
            
            # Use v1 API for media upload
            print("Uploading media...")
            media = api_v1.media_upload(filename)
            media_id = media.media_id_string
            
            # Clean up file
            if os.path.exists(filename):
                os.remove(filename)
        except Exception as e:
            print(f"Image upload failed: {e}")
            media_id = None

    # 5. Post Thread
    print("Posting thread...")
    previous_id = None
    
    for i, tweet_text in enumerate(tweets):
        try:
            if i == 0:
                # First tweet (Hook) gets the image
                response = client_v2.create_tweet(
                    text=tweet_text,
                    media_ids=[media_id] if media_id else None
                )
            else:
                # Subsequent tweets are replies
                response = client_v2.create_tweet(
                    text=tweet_text, 
                    in_reply_to_tweet_id=previous_id
                )
            
            previous_id = response.data['id']
            print(f"Posted tweet {i+1}/{len(tweets)}")
            time.sleep(3) # Stay within rate limits
            
        except Exception as e:
            print(f"Error posting tweet {i+1}: {e}")
            break

    print("Thread posted successfully!")

if __name__ == "__main__":
    post_thread()
