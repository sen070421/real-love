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
    date_pattern = re.compile(r'^(\d{4}[/.]\d{1,2}[/.]\d{1,2})')
    
    # 2. 訊息格式 (重點修正處！)
    # 說明: 允許開頭有 "上午/下午", 且使用 Tab (\t) 分隔
    msg_pattern = re.compile(r'^((?:上午|下午|AM|PM)?\s?\d{1,2}:\d{2})\t([^\t]+)\t(.*)', re.IGNORECASE)

    for line in lines:
        line = line.strip()
        
        # 檢查是不是日期
        date_match = date_pattern.match(line)
        if date_match:
            current_date = date_match.group(1).replace('.', '/')
            continue
            
        # 檢查是不是訊息
        msg_match = msg_pattern.match(line)
        if msg_match and current_date:
            raw_time, sender, message = msg_match.groups()
            
            # 簡單清洗時間字串，把中文拿掉以便轉換
            clean_time = raw_time.replace("上午", "").replace("下午", "").replace("AM", "").replace("PM", "").strip()
            
            # 處理 12 小時轉 24 小時的簡易邏輯 (為了讓圖表時間軸正確)
            # 這裡先做簡單處理：如果原始字串有"下午"，且不是12點，就+12
            try:
                hour = int(clean_time.split(':')[0])
                minute = clean_time.split(':')[1]
                if ("下午" in raw_time or "PM" in raw_time.upper()) and hour != 12:
                    hour += 12
                elif ("上午" in raw_time or "AM" in raw_time.upper()) and hour == 12:
                    hour = 0
                time_str = f"{hour:02d}:{minute}"
            except:
                time_str = clean_time # 轉換失敗就用原值

            dt_str = f"{current_date} {time_str}"
            
            data.append({
                'date': current_date,
                'time': time_str,
                'sender': sender,
                'message': message,
                'datetime_str': dt_str
            })
            
    df = pd.DataFrame(data)
    
    # 轉成時間物件，若失敗則跳過該行
    if not df.empty:
        df['datetime'] = pd.to_datetime(df['datetime_str'], format='%Y/%m/%d %H:%M', errors='coerce')
        df = df.dropna(subset=['datetime'])
        
    return df