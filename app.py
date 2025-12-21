import math
import time
import streamlit as st
import pandas as pd
import plotly.express as px
from utils import parse_line_chat
from analysis import calculate_response_time_variance, calculate_initiation_ratio, calculate_daily_count, calculate_simp_metrics, generate_advice, get_specific_improvements, calculate_match_score, get_word_frequency, determine_theme

# Helper for Custom Progress Bar
def get_custom_progress_html(percent, text, color="#ff69b4", icon="❤️"):
    return f"""
    <div style="margin-bottom: 5px; font-weight: bold;">{text}</div>
    <div style="width: 100%; background-color: #e6e6e6; border-radius: 15px; padding: 3px;">
        <div style="width: {percent}%; height: 20px; background-color: {color}; border-radius: 15px; transition: width 0.5s; display: flex; align-items: center; justify-content: flex-end;">
            <span style="font-size: 20px; margin-right: -10px; animation: pulse 0.8s infinite;">{icon}</span>
        </div>
    </div>
    <style>
    @keyframes pulse {{
        0% {{ transform: scale(1); }}
        50% {{ transform: scale(1.3); }}
        100% {{ transform: scale(1); }}
    }}
    </style>
    """


# Page Config
st.set_page_config(page_title="暈船測試器 (SimpDetector)", page_icon="💔")

# --- CSS Styles ---
st.markdown("""
<style>
    /* Wavy Dreamy Background - Pinker Version */
    .stApp {
        background: linear-gradient(-45deg, #ff9a9e, #fecfef, #ffdde1, #ff9a9e);
        background-size: 400% 400%;
        animation: gradient 15s ease infinite;
    }

    @keyframes gradient {
        0% {
            background-position: 0% 50%;
        }
        50% {
            background-position: 100% 50%;
        }
        100% {
            background-position: 0% 50%;
        }
    }
    
    /* Improve Text Readability: Deep Burgundy Text to contrast with Pink */
    .stMarkdown, .stText, h1, h2, h3, p, li {
        color: #4a0e1e !important; 
        text-shadow: 1px 1px 0px rgba(255,255,255,0.4);
    }
    
    /* Fix metrics label visibility if needed */
    div[data-testid="stMetricLabel"] {
        color: #4a0e1e !important;
    }
    div[data-testid="stMetricValue"] {
        color: #4a0e1e !important;
    }
</style>
""", unsafe_allow_html=True)

# Title & Privacy
st.title("💔 暈船測試器 (SimpDetector)")
st.caption("透過數據量化你的暈船指數，早日下船或是勇敢衝一波！")
st.info("🔒 隱私聲明：所有運算皆在本地端進行，您的聊天記錄不會上傳到任何伺服器。")
# File Upload
uploaded_file = st.file_uploader("上傳 LINE 聊天記錄 (.txt)", type=["txt"])

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
                
                # --- MATCH SUITABILITY SCORE ---
                # Need stability scores for all users
                stability_scores = {}
                for u in users:
                    v = variances.get(u, 0)
                    try:
                        s = math.sqrt(v)
                    except:
                        s = 0
                    score = 100 - min(100, (s / 480) * 100)
                    stability_scores[u] = score
                    
                # --- Initiation Logic ---
                init_counts = {user: 0 for user in users} 
                last_time = None
                time_threshold = pd.Timedelta(hours=2)
                
                for index, row in df.iterrows():
                    curr_time = row['datetime']
                    sender = row['sender']
                    
                    if last_time is None:
                        init_counts[sender] += 1
                    else:
                        time_diff = curr_time - last_time
                        if time_diff > time_threshold:
                            init_counts[sender] += 1
                            
                    last_time = curr_time
                
                total_inits = sum(init_counts.values())
                if total_inits > 0:
                    my_init_ratio = init_counts.get(me, 0) / total_inits
                    init_ratios = init_counts 
                else:
                    my_init_ratio = 0
                    init_ratios = {u: 1 for u in users} 

                try:
                    match_score, match_verdict = calculate_match_score(simp_metrics, list(users), stability_scores)
                except Exception as e:
                    match_score = 0
                    match_verdict = f"Error: {str(e)}"

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
                    st.metric("配對適合度", f"{match_score:.1f}")
                    st.info(match_verdict)
                
                with col3:
                   st.metric("對方穩定度", f"{stability_score:.1f}")
                   st.caption("100=極度穩定")
                   
                st.divider()
                
                # --- Simp Detector Section (Redesigned) ---
                st.subheader("🐶 舔狗偵測機 (Simp Detector)")
                
                # Calculate Humble Scores
                target_humble_score_val = min(100, (simp_metrics[target]['simp_kw_count'] / simp_metrics[target]['msg_count'] * 100 * 20)) if simp_metrics[target]['msg_count'] > 0 else 0
                my_humble_score_val = min(100, (simp_metrics[me]['simp_kw_count'] / simp_metrics[me]['msg_count'] * 100 * 20)) if simp_metrics[me]['msg_count'] > 0 else 0

                tab1, tab2 = st.tabs(["📊 詳細數據 PK", "💌 卑微指標分析"])
                
                with tab1:
                     comp_col1, comp_col2 = st.columns(2)
                     with comp_col1:
                        st.caption(f"平均訊息長度")
                        comp_data = pd.DataFrame({
                            "User": [me, target],
                            "Avg Length": [my_len, target_len],
                            "Msg Count": [my_count, target_count]
                        })
                        fig_len = px.bar(comp_data, x='User', y='Avg Length', color='User', title="")
                        st.plotly_chart(fig_len, use_container_width=True)
                        
                     with comp_col2:
                        st.caption(f"總訊息數")
                        fig_count = px.bar(comp_data, x='User', y='Msg Count', color='User', title="")
                        st.plotly_chart(fig_count, use_container_width=True)
                        
                with tab2:
                    c1, c2 = st.columns(2)
                    with c1:
                        st.metric("你的卑微度", f"{my_humble_score_val:.1f}%")
                        st.progress(int(my_humble_score_val) / 100)
                    with c2:
                        st.metric("對方卑微度", f"{target_humble_score_val:.1f}%")
                        st.progress(int(target_humble_score_val) / 100)
                        
                    if my_humble_score_val > target_humble_score_val + 20:
                        st.warning("⚠️ 你明顯比對方卑微，注意一下！")
                    elif target_humble_score_val > my_humble_score_val + 20:
                        st.success("💪 對方比較怕你，保持住！")
                    else:
                        st.info("⚖️ 雙方勢均力敵。")

                

                
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
                
                # Daily Message Trends (Heatmap)
                daily_counts = calculate_daily_count(df)
                
                fig_heat = px.line(daily_counts, x='datetime', y='count', color='sender', title="🔥 聊天熱度 (Chat Heatmap)")
                fig_heat.update_xaxes(title_text="日期")
                fig_heat.update_yaxes(title_text="每日訊息數")
                
                st.plotly_chart(fig_heat, use_container_width=True)
                
                # Initiation 
                fig_init = px.pie(names=list(init_ratios.keys()), values=list(init_ratios.values()), title="話題主動權")
                st.plotly_chart(fig_init)
                
                # Raw Data
                with st.expander("查看原始數據"):
                    st.dataframe(df)
                    
                # --- New Section: Year in Review ---
                st.markdown("---")
                st.header("📅 年度回顧 (Year in Review)")
                st.write("看看你們這一年聊了什麼，以及最愛用的詞彙！")
                
                # Word Frequency
                word_freq = get_word_frequency(df)
                
                # --- Yearly Theme ---
                # Combine top words from both users for theme generation
                all_words = []
                for u in word_freq:
                    all_words.extend(word_freq[u])
                
                theme = determine_theme(all_words)
                st.subheader(f"🏆 年度主題：{theme}")
                
                col1, col2 = st.columns(2)
                
                users = list(word_freq.keys())
                if len(users) >= 1:
                    with col1:
                        u1 = users[0]
                        st.subheader(f"🗣️ {u1} 的常用詞")
                        if word_freq[u1]:
                            wf_df1 = pd.DataFrame(word_freq[u1], columns=['Word', 'Count'])
                            fig1 = px.bar(wf_df1, x='Count', y='Word', orientation='h', title=f"{u1} Top 20 Words")
                            fig1.update_layout(yaxis={'categoryorder':'total ascending'})
                            st.plotly_chart(fig1, use_container_width=True)
                        else:
                            st.info("詞彙量不足")
                            
                if len(users) >= 2:
                    with col2:
                        u2 = users[1]
                        st.subheader(f"🗣️ {u2} 的常用詞")
                        if word_freq[u2]:
                            wf_df2 = pd.DataFrame(word_freq[u2], columns=['Word', 'Count'])
                            fig2 = px.bar(wf_df2, x='Count', y='Word', orientation='h', title=f"{u2} Top 20 Words")
                            fig2.update_layout(yaxis={'categoryorder':'total ascending'})
                            st.plotly_chart(fig2, use_container_width=True)
                        else:
                            st.info("詞彙量不足")

                st.caption("🔍 透過斷詞分析找出你們最常提到的關鍵字（已過濾常見語助詞）。")
                st.divider()

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
                
                st.divider()
                if st.button("🔥 分析完畢，銷毀資料 (Burn after reading)", type="primary"):
                    # Burning Animation
                    progress_container = st.empty()
                    for i in range(101):
                        html = get_custom_progress_html(i, f"正在銷毀證據... {i}%", color="#ff4500", icon="🔥")
                        progress_container.markdown(html, unsafe_allow_html=True)
                        time.sleep(0.01) # Fast burn
                    
                    time.sleep(0.5) # Pause for dramatic effect
                    
                    for key in list(st.session_state.keys()):
                        del st.session_state[key]
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
            content = ""
            # Try multiple encodings
            # utf-8-sig is crucial for Windows files with BOM
            encodings = ["utf-8-sig", "utf-8", "utf-16", "cp950", "big5"] 
            success = False
            
            for enc in encodings:
                try:
                    uploaded_file.seek(0)
                    content = uploaded_file.read().decode(enc)
                    success = True
                    break
                except:
                    continue
            
            if not success:
                 st.error("❌ 無法讀取檔案編碼，目前支援 UTF-8, UTF-16, Big5 (CP950)。")
                 st.stop()
                 
            # Progress Bar Workflow
            progress_container = st.empty()
            
            def show_heart_bar(val, txt):
                html = get_custom_progress_html(val, txt) 
                progress_container.markdown(html, unsafe_allow_html=True)

            show_heart_bar(0, "正在讀取檔案中...")
            
            # 1. Parse (Fast)
            df = parse_line_chat(content)
            show_heart_bar(50, "檔案讀取完成，正在統計數據...")
            
            if df.empty:
                st.error("無法解析檔案，請確認格式是否為 LINE 文字匯出檔 (.txt)。")
                progress_container.empty()
            else:
                # 2. Done (No more slow sentiment analysis)
                time.sleep(1) # Fake delay for smooth UX
                show_heart_bar(100, "分析完成！")
                st.session_state["chat_df"] = df
                st.rerun()

else:
    st.write("👈 請先在左側或上方上傳檔案")