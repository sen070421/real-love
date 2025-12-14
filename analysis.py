import pandas as pd
import numpy as np
from textblob import TextBlob
def calculate_response_time_variance(df):
    """
    Calculates the variance of response times for each user.
    Response time is defined as the time difference between a message from A 
    and the immediately preceding message from B.
    Returns: Dict {user: variance_in_minutes}
    """
    if df.empty:
        return {}
        
    response_times = {} # {user: [timedelta]}
    
    # Sort just in case, though LINE logs usually sorted
    df = df.sort_values('datetime')
    
    senders = df['sender'].unique()
    for s in senders:
        response_times[s] = []
        
    for i in range(1, len(df)):
        current_msg = df.iloc[i]
        prev_msg = df.iloc[i-1]
        
        # If sender changed, it's a response
        if current_msg['sender'] != prev_msg['sender']:
            delta = current_msg['datetime'] - prev_msg['datetime']
            # We filter out very long gaps which might be "new conversations" rather than responses
            # e.g., if > 12 hours, treat as new convo, not response time
            if delta.total_seconds() < 12 * 3600:
                response_times[current_msg['sender']].append(delta.total_seconds() / 60) # minutes
                
    variances = {}
    for user, times in response_times.items():
        if len(times) > 1:
            variances[user] = np.var(times)
        else:
            variances[user] = 0.0
            
    return variances
def calculate_initiation_ratio(df, gap_hours=1.0):
    """
    Calculates who initiates the conversation (starts a topic).
    Defined as sending a message after > gap_hours silence.
    Returns: Dict {user: ratio} (Total count, not just ratio, might be better but ratio requested)
    """
    if df.empty:
        return {}
        
    initiations = {}
    senders = df['sender'].unique()
    for s in senders:
        initiations[s] = 0
        
    # First message is an initiation
    initiations[df.iloc[0]['sender']] += 1
    
    total_initiations = 1
    
    for i in range(1, len(df)):
        current_msg = df.iloc[i]
        prev_msg = df.iloc[i-1]
        
        delta = current_msg['datetime'] - prev_msg['datetime']
        if delta.total_seconds() > gap_hours * 3600:
            initiations[current_msg['sender']] += 1
            total_initiations += 1
            
    ratios = {k: v / total_initiations if total_initiations > 0 else 0 for k,v in initiations.items()}
    return ratios
def analyze_sentiment(df):
    """
    Adds a 'sentiment' column to the dataframe using TextBlob.
    Note: TextBlob is English-native. 
    Returns: df with 'sentiment' column (-1 to 1).
    """
    if df.empty:
        return df
        
    def get_sentiment(text):
        try:
            return TextBlob(str(text)).sentiment.polarity
        except:
            return 0.0
            
    df['sentiment'] = df['message'].apply(get_sentiment)
    return df