import os
import tweepy

client = tweepy.Client(
    bearer_token=os.getenv("TW_BEARER_TOKEN"),
    consumer_key=os.getenv("TW_CONSUMER_KEY"),
    consumer_secret=os.getenv("TW_CONSUMER_SECRET"),
    access_token=os.getenv("TW_ACCESS_TOKEN"),
    access_token_secret=os.getenv("TW_ACCESS_TOKEN_SECRET"),
)

try:
    resp = client.create_tweet(text="Bot test from @TheVessal – posting is now working! ")
    print("SUCCESS – Tweet ID:", resp.data["id"])
except Exception as e:
    print("FAILED:", str(e))

