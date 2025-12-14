import streamlit as st
import pandas as pd
import plotly.express as px
from utils import parse_line_chat
from analysis import calculate_response_time_variance, calculate_initiation_ratio, analyze_sentiment
# Page Config
st.set_page_config(page_title="暈船測試器 (SimpDetector)", page_icon="💔")
# Title & Privacy
st.title("💔 暈船測試器 (SimpDetector)")
st.caption("透過數據量化你的暈船指數，早日下船或是勇敢衝一波！")
st.info("🔒 隱私聲明：所有運算皆在本地端進行，您的聊天記錄不會上傳到任何伺服器。")
# File Upload
uploaded_file = st.file_uploader("上傳 LINE 聊天記錄 (.txt)", type="txt")
if uploaded_file is not None:
    try:
        content = uploaded_file.read().decode("utf-8")
    except:
        # Fallback for big5 or other encodings if utf-8 fails (common in Windows TW)
        uploaded_file.seek(0)
        content = uploaded_file.read().decode("utf-16", errors="ignore") # try utf-16 usually for line export, or maybe big5?
        # Let's stick to utf-8 first, usually standard.
    with st.spinner("正在偷看你的對話... (誤) 正在分析中..."):
        df = parse_line_chat(content)
    
    if df.empty:
        st.error("無法解析檔案，請確認格式是否為 LINE 文字匯出檔 (.txt)。")
    else:
        # Pre-process
        df = analyze_sentiment(df)
        
        # User selection (who is 'me')
        users = df['sender'].unique()
        if len(users) < 2:
            st.warning("聊天記錄中似乎只有一個人... 這是個人的備忘錄嗎？😢")
        else:
            me = st.selectbox("你是誰？", users)
            target = [u for u in users if u != me][0] # Simple 1v1 for MVP
            
            # Metrics
            variances = calculate_response_time_variance(df)
            init_ratios = calculate_initiation_ratio(df)
            
            # --- Simp Index Logic (Heuristic) ---
            # 暈船指數 = (對方主動比例低 + 對方回覆變異數高) ?
            # Logic: If I initiate 90%, I am simping.
            my_init_ratio = init_ratios.get(me, 0.5)
            simp_score = my_init_ratio * 100
            
            # Tuning based on sentiment?
            # If sentiment is positive, maybe less simp, more mutual love?
            # But prompt says "SimpDetector", usually implies detecting unrequited love.
            
            st.divider()
            
            # 1. 暈船指數
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("你的暈船指數", f"{simp_score:.1f}%")
            
            verdict = ""
            if simp_score > 70:
                verdict = "💀 涼了 (下船吧)"
                st.error(verdict)
            elif simp_score > 40:
                verdict = "🤔 還有機會 (曖昧中)"
                st.warning(verdict)
            else:
                verdict = "💖 穩了 (對方比較暈)"
                st.success(verdict)
                
            with col2:
                st.metric("對方回應變異數", f"{variances.get(target, 0):.1f}")
                st.caption("數值越高代表忽冷忽熱")
            
            with col3:
                st.metric("你主動開話題比例", f"{my_init_ratio*100:.1f}%")
                
            st.divider()
            
            # 2. Charts
            st.subheader("📊 互動洞察")
            
            # Sentiment Time Series
            # Resample by day
            daily_sentiment = df.set_index('datetime').groupby([pd.Grouper(freq='D'), 'sender'])['sentiment'].mean().reset_index()
            
            fig_sentiment = px.line(daily_sentiment, x='datetime', y='sentiment', color='sender', title="情緒波動圖 (Sentiment Trend)")
            st.plotly_chart(fig_sentiment, use_container_width=True)
            
            # Active Time
            # st.bar_chart ...
            
            # Initiation 
            fig_init = px.pie(names=list(init_ratios.keys()), values=list(init_ratios.values()), title="話題主動權")
            st.plotly_chart(fig_init)
            
            # Raw Data
            with st.expander("查看原始數據"):
                st.dataframe(df)
else:
    st.write("👈 請先在左側或上方上傳檔案")