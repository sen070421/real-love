import re
import pandas as pd

def parse_line_chat(file_content):
    """
    解析 LINE 聊天記錄 (.txt) - 台灣寬容版
    支援: 24小時制、12小時制 (上午/下午)
    """
    lines = file_content.splitlines()
    data = []
    
    current_date = None
    
    # 1. 日期格式：抓 2023/12/14 或 2023.12.14
    # 說明: 只要開頭是數字且包含 / 或 . 就當作日期行
    # 1. 日期格式：抓 2023/12/14, 2023.12.14, 2023/12/14 (週四)
    # 支援: YYYY/MM/DD, YYYY.MM.DD, YYYY/M/D
    date_pattern = re.compile(r'^(\d{4}[/.]\d{1,2}[/.]\d{1,2})')
    
    # 2. 訊息格式 (重點修正處！)
    # Desktop: [Time]\t[Sender]\t[Message] (Tab separated)
    # Mobile (iOS/Android): [Time] [Sender] [Message] (Space separated, sometimes)
    # 寬容模式：只抓開頭的時間，後面當作 content
    # Time Pattern: 00:00, 14:00, 上午 1:00, 下午 11:30, 9:30 PM, 9:30 AM
    msg_pattern = re.compile(r'^((?:上午|下午|AM|PM)?\s?\d{1,2}:\d{2})\s+([^\t\s]+)[\t\s]+(.*)', re.IGNORECASE)
    # 備用 Pattern (若是 System Message 或其他格式)
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # 檢查是不是日期
        date_match = date_pattern.match(line)
        if date_match:
            current_date = date_match.group(1).replace('.', '/')
            # 去除 (週X) 等雜訊，雖然 replace . / 已經夠了
            continue
            
        # 檢查是不是訊息
        msg_match = msg_pattern.match(line)
        if msg_match and current_date:
            raw_time, sender, message = msg_match.groups()
            
            # 過濾系統訊息 (Sender 為空或特殊)
            # LINE 系統訊息通常沒有明確的 Sender TAB，或者 Sender 是 "系統"
            
            # 簡單清洗時間字串
            clean_time = raw_time.replace("上午", "").replace("下午", "").replace("AM", "").replace("PM", "").strip()
            
            try:
                # 處理 12/24 小時制
                parts = clean_time.split(':')
                hour = int(parts[0])
                minute = int(parts[1])
                
                if ("下午" in raw_time or "PM" in raw_time.upper()) and hour != 12:
                    hour += 12
                elif ("上午" in raw_time or "AM" in raw_time.upper()) and hour == 12:
                    hour = 0
                time_str = f"{hour:02d}:{minute}"
            except:
                time_str = clean_time 

            dt_str = f"{current_date} {time_str}"
            
            data.append({
                'date': current_date,
                'time': time_str,
                'sender': sender,
                'message': message,
                'datetime_str': dt_str
            })
            # 如果 regex 沒對到，可能是一般換行文字，屬於上一句的延續？
            # 暫不處理多行訊息，避免複雜度爆表，MVP 先求有
            pass
            
    df = pd.DataFrame(data)
    
    # 轉成時間物件，若失敗則跳過該行
    if not df.empty:
        df['datetime'] = pd.to_datetime(df['datetime_str'], format='%Y/%m/%d %H:%M', errors='coerce')
        df = df.dropna(subset=['datetime'])
        
    return df