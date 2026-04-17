# ============================================================
# DASHBOARD V2 — ANALYTICS, INSIGHTS & UI TWEAKS
# ============================================================

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pymongo import MongoClient
from datetime import datetime, timezone
import os

# ── 1. CONFIG & CSS ─────────────────────────────────────────
st.set_page_config(page_title="Smart X-Ray Analytics", page_icon="🫁", layout="wide")

# CSS Tiêm trực tiếp để làm đẹp giao diện
st.markdown("""
<style>
    div[data-testid="metric-container"] {
        background-color: #ffffff; border: 1px solid #e0e6ed;
        padding: 15px 20px; border-radius: 12px;
        box-shadow: 0px 4px 6px rgba(0, 0, 0, 0.05);
    }
    div[data-testid="metric-container"] label { color: #64748b !important; font-weight: 600; }
    div[data-testid="metric-container"] div[data-testid="stMetricValue"] { color: #0f172a !important; font-weight: 800; }
    .stTabs [data-baseweb="tab-list"] { gap: 20px; }
    .stTabs [data-baseweb="tab"] { height: 50px; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# Đường dẫn đến thư mục chứa ảnh trên máy tính của bạn
IMG_DIR = r"D:\2321003619_Nguyễn Tuyết Trinh\X-RAY\images-224"

# ── 2. DB CONNECTION ───────────────────────────────────────
@st.cache_resource
def get_db():
    MONGO_URI = "mongodb+srv://tuyettrinh3525:Trinh3005@clusterbigdata.ubhpjjc.mongodb.net/?appName=ClusterBigData"
    client = MongoClient(MONGO_URI)
    return client["chestxray_db"]

db = get_db()

# ── 3. DATA LOADERS ────────────────────────────────────────
def load_live(limit=50):
    # 1. Sắp xếp theo trường thời gian mới (đã lồng vào system_meta)
    docs = list(db["predictions"].find({}, {"_id": 0}).sort("system_meta.timestamp", -1).limit(limit))
    
    if not docs:
        return pd.DataFrame()
        
    # 2. Trải phẳng JSON lồng nhau thành bảng 2 chiều
    df = pd.json_normalize(docs)
    
    # 3. Đổi tên cột lại cho khớp với code giao diện (để Tab 1 không bị lỗi)
    df = df.rename(columns={
        "triage_assessment.requires_emergency": "requires_emergency",
        "triage_assessment.priority": "priority",
        "triage_assessment.severity": "severity",
        "system_meta.processing_time_ms": "processing_time_ms",
        "patient_info.patient_id": "patient_id",
        "clinical_findings.image_filename": "image_filename",
        "clinical_findings.diseases": "diseases"
    })
    
    return df

@st.cache_data(ttl=60)
def load_batch(date):
    return db["batch_stats"].find_one({"date": date}, {"_id": 0})

@st.cache_data(ttl=60)
def get_dates():
    cursor = db["batch_stats"].find({}, {"date": 1, "_id": 0}).sort("date", -1)
    return [d["date"] for d in cursor if "date" in d]

@st.cache_data(ttl=300)
def load_economic_history():
    # Lấy toàn bộ dữ liệu batch để vẽ biểu đồ xu hướng
    cursor = db["batch_stats"].find({}, {"date": 1, "total_cases": 1, "abnormal_cases": 1, "_id": 0}).sort("date", 1)
    return pd.DataFrame(list(cursor))

# ── 4. SIDEBAR ─────────────────────────────────────────────
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3003/3003261.png", width=60)
    st.title("Admin Control")
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.cache_data.clear()
    
    st.divider()
    dates = get_dates()
    selected_date = st.selectbox("📅 Select Batch Date", dates) if dates else None

# ── 5. HEADER ──────────────────────────────────────────────
st.title("🫁 Smart X-Ray Analytics Hub")
st.caption("Powered by Lambda Architecture (Realtime Inference + Batch Aggregation)")
st.divider()

tab1, tab2, tab3 = st.tabs(["⚡ Realtime Speed", "📦 Daily Batch Insights", "💰 Economic ROI"])

# ============================================================
# ⚡ TAB 1: SPEED (REALTIME)
# ============================================================
with tab1:
    st.subheader("🔴 Live Triage Queue")
    df = load_live()

    if df.empty:
        st.info("No realtime data streaming right now.")
    else:
        req_emg_sum = int(df["requires_emergency"].sum()) if "requires_emergency" in df.columns else 0
        prio_sum = int((df["priority"] == 3).sum()) if "priority" in df.columns else 0
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Recent Scans", len(df))
        c2.metric("Emergency Flags", req_emg_sum, delta="High Alert" if req_emg_sum > 0 else "Normal", delta_color="inverse")
        c3.metric("Critical Priority", prio_sum)
        c4.metric("Avg Latency", f"{df['processing_time_ms'].mean():.1f} ms")

        st.divider()
        st.markdown("### 🚨 High Priority Patients (Needs Immediate Review)")
        
        df_emg = df[df["priority"] == 3] if "priority" in df.columns else pd.DataFrame()
        
        if df_emg.empty:
            st.success("✅ Queue clear. No critical patients waiting.")
        else:
            for _, r in df_emg.head(5).iterrows():
                with st.container():
                    col_img, col_info = st.columns([1, 4])
                    
                    with col_img:
                        img_name = r.get('image_filename', '')  
                        full_path = os.path.join(IMG_DIR, img_name)
                        
                        if os.path.exists(full_path):
                            # Hiện ảnh thật từ ổ đĩa
                            st.image(full_path, use_container_width=True)
                        else:
                            # Hiện ảnh minh họa nếu chưa có file trên máy
                            st.image("https://img.freepik.com/premium-vector/x-ray-human-chest-icon-isolated-blue-background_532867-46.jpg", 
                                     caption=f"Missing: {img_name}", use_container_width=True)
                    
                    with col_info:
                        st.error(f"**Patient ID:** {r.get('patient_id', 'N/A')}")
                        diseases = r.get('diseases', [])
                        st.write(f"**Detected:** {', '.join(diseases) if diseases else 'None'}")
                        st.write(f"**Severity:** `{str(r.get('severity', 'Unknown')).upper()}`")
                
                st.write("") # Tạo khoảng trắng nhỏ giữa các bệnh nhân

# ============================================================
# 📦 TAB 2: BATCH INSIGHTS
# ============================================================
with tab2:
    if selected_date:
        bs = load_batch(selected_date)
        if bs:
            st.subheader(f"📊 Analytics for {selected_date}")
            
            # --- INSIGHT: Đánh giá Tỷ lệ Cấp cứu ---
            emg_rate = bs.get('emergency_rate_pct', 0)
            if emg_rate > 10:
                st.warning(f"⚠️ **Operational Insight:** Tỷ lệ ca cấp cứu hôm nay rất cao ({emg_rate}%). Đề xuất điều phối thêm Bác sĩ trực!")
            else:
                st.success(f"✅ **Operational Insight:** Lượng ca bệnh ổn định. Cần {bs.get('doctors_needed', 0)} bác sĩ để xử lý khối lượng hôm nay.")

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total Scans", bs.get("total_cases", 0))
            c2.metric("Abnormal Findings", bs.get("abnormal_cases", 0))
            c3.metric("Emergency Cases", bs.get("emergency_cases", 0))
            c4.metric("Doctors Required", bs.get("doctors_needed", 0))

            st.divider()
            c_left, c_right = st.columns(2)

            with c_left:
                st.markdown("**🦠 Top Abnormal Diseases** *(Filtered 'No Finding')*")
                dis = bs.get("disease_distribution", {})
                if dis:
                    df_dis = pd.DataFrame(dis.items(), columns=["Disease", "Count"])
                    df_dis = df_dis[df_dis["Disease"] != "No Finding"].sort_values("Count", ascending=True)
                    fig_bar = px.bar(df_dis, x="Count", y="Disease", orientation='h', color="Count", color_continuous_scale="Reds")
                    fig_bar.update_layout(margin=dict(l=0, r=0, t=0, b=0))
                    st.plotly_chart(fig_bar, use_container_width=True)

            with c_right:
                st.markdown("**⚠️ Severity Distribution**")
                sev = bs.get("severity_distribution", {})
                if sev:
                    df_sev = pd.DataFrame(sev.items(), columns=["Severity", "Count"])
                    color_map = {'critical':'#7f1d1d', 'high':'#dc2626', 'moderate':'#f59e0b', 'mild':'#3b82f6', 'none':'#94a3b8'}
                    fig_pie = px.pie(df_sev, values="Count", names="Severity", hole=0.4, color='Severity', color_discrete_map=color_map)
                    fig_pie.update_layout(margin=dict(l=0, r=0, t=0, b=0))
                    st.plotly_chart(fig_pie, use_container_width=True)

# ============================================================
# 💰 TAB 3: ECONOMIC ROI
# ============================================================
with tab3:
    st.subheader("💰 Return on Investment (ROI) & Efficiency")
    
    df_eco = load_economic_history()
    if not df_eco.empty:
        df_eco['normal_cases'] = df_eco['total_cases'] - df_eco['abnormal_cases']
        df_eco['cum_saved_vnd'] = (df_eco['normal_cases'] * 150000).cumsum()
        
        total_historical = df_eco['total_cases'].sum()
        total_normal = df_eco['normal_cases'].sum()
        total_saved = df_eco['cum_saved_vnd'].iloc[-1]

        c1, c2, c3 = st.columns(3)
        c1.metric("Total Scans Processed", f"{total_historical:,}")
        c2.metric("Healthy Cases Filtered", f"{total_normal:,}")
        c3.metric("Total Cost Saved", f"{total_saved/1e9:.2f} Billion VND", delta="Cost Optimized")

        st.divider()
        st.markdown("### 📈 Cumulative Savings Over Time")
        
        fig_line = go.Figure()
        fig_line.add_trace(go.Scatter(
            x=df_eco['date'], y=df_eco['cum_saved_vnd'], 
            mode='lines+markers',
            fill='tozeroy',
            line=dict(color='#10b981', width=3),
            name="VND Saved"
        ))
        fig_line.update_layout(
            xaxis_title="Date", yaxis_title="VND (Cumulative)",
            margin=dict(l=0, r=0, t=30, b=0),
            hovermode="x unified"
        )
        st.plotly_chart(fig_line, use_container_width=True)
    else:
        st.info("Not enough historical data to generate ROI trends.")
