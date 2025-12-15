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
def analyze_sentiment(df, progress_callback=None):
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
            
    # If no callback, just do it all at once
    if not progress_callback:
        df['sentiment'] = df['message'].apply(get_sentiment)
        return df

    # Chunk processing for progress
    chunks = np.array_split(df, 10)
    processed_chunks = []
    
    total_chunks = len(chunks)
    for i, chunk in enumerate(chunks):
        chunk = chunk.copy()
        chunk['sentiment'] = chunk['message'].apply(get_sentiment)
        processed_chunks.append(chunk)
        
        # Update progress (0.0 to 1.0)
        progress = (i + 1) / total_chunks
        progress_callback(progress)
        
    return pd.concat(processed_chunks)

def calculate_simp_metrics(df):
    """
    Calculates advanced Simp metrics:
    1. Keyword usage (Humble words)
    2. Msg Length avg
    3. Msg Count
    """
    if df.empty:
        return {}
        
    metrics = {}
    users = df['sender'].unique()
    
    # Define humble/simp keywords
    simp_keywords = ["對不起", "抱歉", "打擾了", "沒關係", "好的", "收到", "早安", "晚安", "在忙嗎", "可以嗎", "不好意思", "拜託"]
    
    for u in users:
        user_df = df[df['sender'] == u]
        
        # 1. Msg Count
        msg_count = len(user_df)
        
        # 2. Avg Length
        avg_len = user_df['message'].astype(str).str.len().mean()
        
        # 3. Keyword Count
        # Check how many messages contain at least one keyword (or total occurrences)
        # Let's count total occurrences
        kw_count = 0
        used_keywords = {}
        for msg in user_df['message'].astype(str):
            for kw in simp_keywords:
                if kw in msg:
                    kw_count += 1
                    used_keywords[kw] = used_keywords.get(kw, 0) + 1
                    
        sorted_kws = sorted(used_keywords.items(), key=lambda x: x[1], reverse=True)
        
        metrics[u] = {
            'msg_count': msg_count,
            'avg_len': avg_len if not pd.isna(avg_len) else 0,
            'simp_kw_count': kw_count,
            'top_keywords': sorted_kws[:3] # Top 3
        }
        
    return metrics

def generate_advice(metrics, simp_score, stability_score):
    """
    Generates general advice based on metrics.
    """
    advice_list = []
    
    # 1. Simp Score
    if simp_score > 60:
        advice_list.append("⚠️ **暈船警報**：你的暈船指數偏高，請記得「認真就輸了」。試著轉移注意力，不要整天守著手機。")
    elif simp_score < 30:
        advice_list.append("👍 **保持自信**：你目前掌握主導權，繼續保持這種從容的態度！")
        
    # 2. Stability
    if stability_score < 40:
        advice_list.append("🌊 **風浪太大**：对方的情緒或回覆頻率極不穩定。這通常是「養魚」的訊號，建議不要投入太多感情。")
        
    # 3. Initiation
    # metrics is {user: {data}}
    # We need to pass 'me' or just key logic in app.py to pass specific values. 
    # Let's assume input is simplified or we extract inside app.py. 
    # To keep analysis pure, let's accept specific values or handle parsing here.
    # Refactoring slightly: move decision logic to app or generic here? 
    # Generic here is better.
    return advice_list

def get_specific_improvements(df, me):
    """
    Finds specific 'humble' messages and suggests improvements.
    Returns: List of dicts {'original': str, 'reason': str, 'suggestion': str}
    """
    if df.empty:
        return []
        
    user_df = df[df['sender'] == me]
    improvements = []
    
    # Define rules: Keyword -> (Reason, Suggestion)
    rules = {
        "抱歉": ("太常道歉會顯得低姿態，像在尋求原諒。", "改說「謝謝你的耐心」或直接說重點，展現自信。"),
        "對不起": ("除非真的做錯事，否則不要一直對不起。", "試著把「對不起我遲到了」改成「謝謝你等我」。"),
        "在忙嗎": ("這句話把主導權完全交給對方，且隱含「我怕打擾你」的卑微感。", "直接分享有趣的事或開啟話題，例如「欸我剛看到...」。"),
        "打擾了": ("這預設了你的存在是種打擾。", "不需要這句，直接說事即可。"),
        "沒關係": ("如果是被拒絕後馬上回這句，會顯得太好說話。", "已讀不回一段時間，或者說「OK」就好。"),
        "可以嗎": ("過度詢問許可，顯得沒有主見。", "改用「要不要一起...」或「我們去...」，用邀請代替請求。")
    }
    
    # Scan last ~100 messages to be relevant
    recent_msgs = user_df.tail(100)
    
    for msg in recent_msgs['message'].astype(str):
        for kw, (reason, suggestion) in rules.items():
            if kw in msg:
                # Deduplicate loosely
                if not any(d['original'] == msg for d in improvements):
                    improvements.append({
                        "original": msg,
                        "keyword": kw,
                        "reason": reason,
                        "suggestion": suggestion
                    })
                break # One rule per message
                
    # Return top 3 unique suggestions
    return improvements[:3]
