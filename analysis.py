import pandas as pd
import numpy as np

def calculate_daily_count(df):
    """
    Calculates daily message count for each user.
    Returns: DataFrame [datetime, sender, count]
    """
    if df.empty:
        return pd.DataFrame()
        
    daily_count = df.set_index('datetime').groupby([pd.Grouper(freq='D'), 'sender']).size().reset_index(name='count')
    return daily_count

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
        
        metrics[str(u)] = {
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

    return improvements[:3]

def calculate_match_score(simp_metrics, users, stability_scores):
    """
    Calculates Match Suitability Score (0-100).
    Factors:
    1. Balance (50%): Msg count ratio.
    2. Echo (30%): Avg length similarity.
    3. Rhythm (20%): Stability score similarity.
    """
    try:
        if len(users) < 2:
            return 0, "需兩人以上才能計算"
            
        # Ensure we are using compatible types (str) for keys
        u1 = str(users[0])
        u2 = str(users[1])
        
        # 1. Balance Score (50%)
        # Access with safe get, defaulting to 0/empty logic
        m1 = simp_metrics.get(u1)
        m2 = simp_metrics.get(u2)
        
        if not m1 or not m2:
             # Fallback: try raw keys if casting failed upstream
             return 0, "資料不足"
             
        c1 = m1['msg_count']
        c2 = m2['msg_count']
        
        total = c1 + c2
        if total == 0:
            balance_ratio = 0.5
        else:
            balance_ratio = c1 / total
        
        balance_score = (1 - (abs(0.5 - balance_ratio) * 2)) * 100
        
        # 2. Echo Score (30%)
        l1 = m1['avg_len']
        l2 = m2['avg_len']
        if max(l1, l2) == 0:
            echo_score = 100
        else:
            echo_score = (min(l1, l2) / max(l1, l2)) * 100
            
        # 3. Rhythm Score (20%)
        s1 = stability_scores.get(u1, 50)
        s2 = stability_scores.get(u2, 50)
        
        rhythm_score = 100 - abs(s1 - s2)
        
        final_score = (balance_score * 0.5) + (echo_score * 0.3) + (rhythm_score * 0.2)
        
        verdict = "🤝 相當契合 (Good Match)"
        if final_score >= 90:
            verdict = "👩‍❤️‍👨 天作之合 (Soulmates)"
        elif final_score >= 70:
            verdict = "🤝 相當契合 (Good Match)"
        elif final_score >= 40:
            verdict = "🤏 普通朋友 (Just Friends)"
        else:
            verdict = "💥 頻率不對 (Mismatch)"
            
        return final_score, verdict
    except Exception as e:
        return 0, f"計算錯誤: {str(e)}"

# Add jieba import at the top if not present, but for now we put it inside or global. 
# Better to put global import at top, but since we are appending, let's just make sure it's handled.
# Accessing file again to add import to top is best practice but appending here for tool usage efficiency for now?
# No, let's do it properly. I will use multi_replace for imports + new function if I had to, but I'll validly just add import inside function or helper if lazy, but best is top.
# Actually I will use read_file to check imports again? I did view_file before.
# I will just write the function here and assume imports will be fixed or added.
# Wait, I need to add `import jieba` at the top. I'll do a separate tool call or use `multi_replace`.
# Let's use `multi_replace` to add import at top and function at bottom.

def get_word_frequency(df, top_n=20):
    """
    Calculates word frequency using jieba.
    Returns: Dict {user: [(word, count), ...]}
    """
    import jieba # Lazy import to avoid breaking if not installed yet (though we just did)
    import re
    
    if df.empty:
        return {}
        
    frequency = {}
    users = df['sender'].unique()
    
    # Common Traditional Chinese stop words
    stop_words = set([
        "的", "了", "和", "是", "就", "都", "而", "及", "與", "著",
        "或", "一個", "沒有", "我們", "你們", "他們", "它", "是否",
        "但是", "雖然", "因此", "因為", "所以", "如果", "雖然",
        "其實", "也是", "只是", "還是", "那個", "這個", "什麼",
        "怎麼", "這裡", "那裡", "原本", "可能", "大概", "可以",
        "覺得", "比較", "感覺", "好像", "不過", "這樣", "那樣",
        "貼圖", "照片", "影片", "通話", "未接", "已讀", "收回",
        "訊息", "檔案", "相簿", "記事本", "禮物", "應該", "真的",
        "對啊", "哈哈", "哈哈哈", "呵呵", "嗯嗯", "喔喔", "就是",
        "不要", "不會", "知道", "現在", "今天", "明天", "後來",
        "一定", "看到", "有些", "這些", "那些", "然後", "有些",
        "而且", "一種", "一些", "有點", "好吧", "好喔", "好啊",
        "有點", "一點", "一下", "一次", "一直"
    ])
    
    for u in users:
        user_df = df[df['sender'] == u]
        text_content = " ".join(user_df['message'].astype(str).tolist())
        
        # Simple cleaning
        text_content = re.sub(r'[^\w\s]', '', text_content)
        
        words = jieba.cut(text_content)
        
        filtered_words = []
        for w in words:
            w = w.strip()
            if len(w) > 1 and w not in stop_words and not w.isdigit():
                filtered_words.append(w)
                
        # Count
        word_counts = pd.Series(filtered_words).value_counts().head(top_n)
        frequency[str(u)] = list(word_counts.items())
        
    return frequency

def determine_theme(word_counts_list):
    """
    Determines a 'Yearly Theme' based on top words.
    Input: List of (word, count) tuples from one or all users.
    Returns: String (Theme Name)
    """
    if not word_counts_list:
        return "👻 沉默是金 (Silence is Gold)"
        
    # Flatten just to words for easy checking
    words = [w[0] for w in word_counts_list]
    text_blob = " ".join(words)
    
    themes = {
        "🍔 吃貨搭檔 (Foodie Couple)": ["吃", "餓", "飯", "麵", "喝", "飲料", "甜點", "好想吃", "去吃", "早安", "晚安", "宵夜"],
        "💼 事業強人 (Hustle Mode)": ["忙", "開會", "加班", "累", "公司", "這週", "下班", "報告", "資料", "確認", "會議"],
        "🥰 熱戀情侶 (Lovey Dovey)": ["想你", "愛你", "抱抱", "親親", "寶貝", "早安", "晚安", "喜歡", "可愛", "想見"],
        "🎮 宅宅雙人組 (Geek Squad)": ["遊戲", "上線", "打", "看", "動漫", "番", "睡", "宅", "好笑", "影片"],
        "💰 投資理財 (Wolf of Wall St)": ["錢", "買", "賣", "貴", "便宜", "股票", "匯率", "賺", "賠", "花錢"]
    }
    
    scores = {k: 0 for k in themes}
    
    for theme, keywords in themes.items():
        for kw in keywords:
            # Simple substring match in the top words list
            for w in words:
                if kw in w:
                    scores[theme] += 1
                    
    # Find max
    best_theme = max(scores, key=scores.get)
    
    if scores[best_theme] == 0:
        return "🤖 話癆二人組 (Chatty Bots)"
        
    return best_theme
