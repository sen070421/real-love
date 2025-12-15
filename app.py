import math
import streamlit as st
import pandas as pd
import plotly.express as px
from utils import parse_line_chat
from analysis import calculate_response_time_variance, calculate_initiation_ratio, analyze_sentiment, calculate_simp_metrics, generate_advice, get_specific_improvements


# Page Config
st.set_page_config(page_title="暈船測試器 (SimpDetector)", page_icon="💔")
# Title & Privacy
st.title("💔 暈船測試器 (SimpDetector)")
st.caption("透過數據量化你的暈船指數，早日下船或是勇敢衝一波！")
st.info("🔒 隱私聲明：所有運算皆在本地端進行，您的聊天記錄不會上傳到任何伺服器。")
# File Upload
uploaded_file = st.file_uploader("上傳 LINE 聊天記錄 (.txt)", type="txt")

if uploaded_file is not None:
    # Unique ID for the file to handle re-uploads/changes
    file_details = {"filename": uploaded_file.name, "size": uploaded_file.size}
    
    # Reset state if new file is uploaded
    if "file_details" not in st.session_state or st.session_state["file_details"] != file_details:
        st.session_state["file_details"] = file_details
        if "chat_df" in st.session_state:
            del st.session_state["chat_df"]
        if "selected_user" in st.session_state:
            del st.session_state["selected_user"]
            
    # Main logic
    if "chat_df" in st.session_state:
        # --- SHOW DASHBOARD (Data is ready) ---
        df = st.session_state["chat_df"]
        
        # User selection (who is 'me')
        users = df['sender'].unique()
        if len(users) < 2:
            st.warning("聊天記錄中似乎只有一個人... 這是個人的備忘錄嗎？😢")
        else:
            if "selected_user" in st.session_state:
                me = st.session_state["selected_user"]
                target = [u for u in users if u != me][0] # Simple 1v1 for MVP
                
                # Metrics Calculation
                variances = calculate_response_time_variance(df)
                init_ratios = calculate_initiation_ratio(df, gap_hours=2.0)
                simp_metrics = calculate_simp_metrics(df)
                
                # --- Advanced Simp Index Logic (Score 2.0) ---
                # Factors:
                # 1. Initiation (30%): Higher is simpler
                init_score = init_ratios.get(me, 0.5) * 100
                
                # 2. Length Disparity (30%): If I speak more than target, I am simp.
                my_len = simp_metrics[me]['avg_len']
                target_len = simp_metrics[target]['avg_len']
                len_ratio = my_len / (my_len + target_len) if (my_len + target_len) > 0 else 0.5
                len_score = len_ratio * 100
                
                # 3. Count Disparity (20%)
                my_count = simp_metrics[me]['msg_count']
                target_count = simp_metrics[target]['msg_count']
                count_ratio = my_count / (my_count + target_count) if (my_count + target_count) > 0 else 0.5
                count_score = count_ratio * 100
                
                # 4. Keyword Usage (20%)
                my_kw = simp_metrics[me]['simp_kw_count']
                # Normalized against msg count to get density
                kw_density = my_kw / my_count if my_count > 0 else 0
                # Arbitrary scaling: 5 keywords per 100 msgs = 100 score? 
                # Let's say 1% keywords is max score.
                kw_score = min(100, kw_density * 100 * 10) 
                
                # Weighted Sum
                simp_score = (init_score * 0.3) + (len_score * 0.3) + (count_score * 0.2) + (kw_score * 0.2) 
                
                # --- Hot & Cold Index Logic ---
                target_variance = variances.get(target, 0)
                try:
                    std_dev_minutes = math.sqrt(target_variance)
                except:
                    std_dev_minutes = 0
                
                hot_cold_score = min(100, (std_dev_minutes / 480) * 100)
                stability_score = 100 - hot_cold_score
                
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
                    st.metric("對方穩定度", f"{stability_score:.1f}")
                    st.caption("100=極度穩定, 0=忽冷忽熱")
                
                with col3:
                    st.metric("你主動開話題比例", f"{init_ratios.get(me, 0)*100:.1f}%")
                    
                st.divider()
                
                # --- Simp Detector Section ---
                st.subheader("🐶 舔狗偵測機 (Simp Detector)")
                sd_col1, sd_col2 = st.columns(2)
                
                with sd_col1:
                    st.markdown("**💌 卑微關鍵字分析**")
                    if simp_metrics[me]['top_keywords']:
                        st.write("你最常說的卑微詞：")
                        for kw, count in simp_metrics[me]['top_keywords']:
                             st.write(f"- {kw}: {count} 次")
                    else:
                        st.write("你沒有使用卑微關鍵字！👍")
                        
                    st.divider()
                    st.markdown("**對方的卑微詞**")
                    if simp_metrics[target]['top_keywords']:
                         for kw, count in simp_metrics[target]['top_keywords']:
                             st.write(f"- {kw}: {count} 次")
                    else:
                        st.write("對方很強勢，沒在道歉的。")

                with sd_col2:
                    st.markdown("**📏 長度與頻率大PK**")
                    # Prepare data for bar chart
                    # --- 🚑 補上這段：計算話題主動權邏輯 ---
# 邏輯：如果兩則訊息間隔超過 2 小時，視為「新話題」的開始

                    # 1. 初始化計數器
                    init_counts = {user: 0 for user in users} 
                    last_time = None
                    time_threshold = pd.Timedelta(hours=2) # 設定間隔 2 小時算新話題
                    
                    # 2. 跑迴圈計算
                    for index, row in df.iterrows():
                        curr_time = row['datetime']
                        sender = row['sender']
                        
                        if last_time is None:
                            init_counts[sender] += 1 # 第一則訊息算主動
                        else:
                            time_diff = curr_time - last_time
                            if time_diff > time_threshold:
                                init_counts[sender] += 1 # 間隔太久才講話，算主動開啟
                                
                        last_time = curr_time
                    
                    # 3. 算出比例 (解決 NameError)
                    total_inits = sum(init_counts.values())
                    if total_inits > 0:
                        my_init_ratio = init_counts.get(me, 0) / total_inits
                        init_ratios = init_counts # 這個變數給後面的圓餅圖用
                    else:
                        my_init_ratio = 0
                        init_ratios = {u: 1 for u in users} # 避免分母為 0
                    comp_data = pd.DataFrame({
                        "User": [me, target],
                        "Avg Length": [my_len, target_len],
                        "Msg Count": [my_count, target_count]
                    })
                    
                    st.caption(f"平均訊息長度：你 {my_len:.1f} 字 VS 對方 {target_len:.1f} 字")
                    fig_len = px.bar(comp_data, x='User', y='Avg Length', color='User', title="平均訊息長度 (字數)")
                    st.plotly_chart(fig_len, use_container_width=True)
                    
                    st.caption(f"總訊息數：你 {my_count} 則 VS 對方 {target_count} 則")
                    fig_count = px.bar(comp_data, x='User', y='Msg Count', color='User', title="總訊息數量")
                    st.plotly_chart(fig_count, use_container_width=True)

                

                
                # --- Love Guru Advice Section ---
                st.subheader("💡 戀愛軍師建議 (Love Guru Advice)")
                
                # 1. General Advice
                advice = generate_advice(simp_metrics, simp_score, stability_score)
                if advice:
                    for tip in advice:
                        st.info(tip)
                else:
                    st.success("✨ 目前看起來一切都很穩，你是戀愛高手！")
                    
                # 2. Specific Feedback
                improvements = get_specific_improvements(df, me)
                if improvements:
                    st.markdown("**🚑 實戰修改 (Rescue Mission)**")
                    st.caption("以下是你最近傳送的一些訊息，軍師覺得可以修得更好：")
                    
                    for item in improvements:
                        with st.expander(f"NG 訊息：{item['original'][:20]}..."):
                            st.markdown(f"**為什麼 NG？**\n{item['reason']}")
                            st.markdown(f"**✨ 建議改法**\n{item['suggestion']}")
                            st.caption(f"關鍵字：{item['keyword']}")
                else:
                    st.caption("找不到明顯的「卑微」訊息，做得好！")
                
                st.divider()
                
                # 2. Charts
                st.subheader("📊 互動洞察")
                
                # Sentiment Time Series
                daily_sentiment = df.set_index('datetime').groupby([pd.Grouper(freq='D'), 'sender'])['sentiment'].mean().reset_index()
                
                # Smooth the lines
                daily_sentiment['sentiment'] = daily_sentiment.groupby('sender')['sentiment'].transform(lambda x: x.rolling(window=3, min_periods=1).mean())

                fig_sentiment = px.line(daily_sentiment, x='datetime', y='sentiment', color='sender', title="🌡️ 感情溫度計 (Vibe Check)")
                
                # Custom Y-Axis with Emojis
                fig_sentiment.update_yaxes(
                    range=[-1.1, 1.1],
                    tickvals=[-1, -0.5, 0, 0.5, 1],
                    ticktext=["😡 火大", "😒 冷淡", "😐 平常", "😊 開心", "😍 愛死"],
                    zeroline=True, zerolinewidth=2, zerolinecolor='LightGray'
                )
                
                st.plotly_chart(fig_sentiment, use_container_width=True)
                
                # Initiation 
                fig_init = px.pie(names=list(init_ratios.keys()), values=list(init_ratios.values()), title="話題主動權")
                st.plotly_chart(fig_init)
                
                # Raw Data
                with st.expander("查看原始數據"):
                    st.dataframe(df)
                    
                col_actions_1, col_actions_2 = st.columns(2)
                with col_actions_1:
                    if st.button("重新分析 (Re-Analyze)"):
                        del st.session_state["chat_df"]
                        if "selected_user" in st.session_state:
                           del st.session_state["selected_user"]
                        st.rerun()
                with col_actions_2:
                    if st.button("更換使用者 (Change User)"):
                         del st.session_state["selected_user"]
                         st.rerun()
            else:
                # Selection Stage
                st.info("分析完成！請選擇你的身分以查看結果。")
                selected = st.selectbox("你是誰？", users)
                if st.button("確定 (Confirm)"):
                    st.session_state["selected_user"] = selected
                    st.rerun()

    else:
        # --- SHOW START BUTTON (Data not processed yet) ---
        st.info(f"已上傳檔案：{uploaded_file.name}，準備就緒。")
        if st.button("🚀 開始分析 (Start Analysis)"):
            try:
                content = uploaded_file.read().decode("utf-8")
            except:
                uploaded_file.seek(0)
                content = uploaded_file.read().decode("utf-16", errors="ignore")
                
            # Progress Bar Workflow
            progress_bar = st.progress(0, text="正在讀取檔案中...")
            
            # 1. Parse (Fast)
            df = parse_line_chat(content)
            progress_bar.progress(30, text="檔案讀取完成，正在分析情感...")
            
            if df.empty:
                st.error("無法解析檔案，請確認格式是否為 LINE 文字匯出檔 (.txt)。")
                progress_bar.empty()
            else:
                # 2. Sentiment Analysis (Slow) with callback
                def update_progress(p):
                    # Map p (0.0-1.0) to 30-100 range
                    val = 30 + int(p * 70)
                    progress_bar.progress(val, text=f"正在分析情感... {int(p*100)}%")
                    
                df = analyze_sentiment(df, progress_callback=update_progress)
                
                # Done
                progress_bar.progress(100, text="分析完成！")
                st.session_state["chat_df"] = df
                st.rerun()
else:
    st.write("👈 請先在左側或上方上傳檔案")
