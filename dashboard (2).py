# ============================================================
# DASHBOARD — FINAL (SYNC SPEED + BATCH LAYER)
# ============================================================

import streamlit as st
import pandas as pd
import plotly.express as px
from pymongo import MongoClient
from datetime import datetime, timezone
import os
from PIL import Image

# ── 1. CONFIG ───────────────────────────────────────────────
st.set_page_config(page_title="Smart X-Ray Analytics", layout="wide")

IMG_DIR = "images"

# ── 2. DB CONNECTION ───────────────────────────────────────
@st.cache_resource
def get_db():
    # ⚠️ LƯU Ý: Tốt nhất nên dùng st.secrets["MONGO_URI"] khi deploy
    # Mình đã giữ lại chuỗi kết nối của bạn nhưng hãy cẩn thận khi public code này
    MONGO_URI = "mongodb+srv://tuyettrinh3525:Trinh3005@clusterbigdata.ubhpjjc.mongodb.net/?appName=ClusterBigData"
    client = MongoClient(MONGO_URI)
    return client["chestxray_db"]

db = get_db()

# ── 3. LOAD DATA ───────────────────────────────────────────

# 🔥 SPEED: dùng processing_timestamp (realtime đúng)
def load_live(limit=50):
    docs = list(
        db["predictions"]
        .find({}, {"_id": 0})
        .sort("processing_timestamp", -1)
        .limit(limit)
    )
    return pd.DataFrame(docs) if docs else pd.DataFrame()

# 🔥 BATCH
@st.cache_data(ttl=60)
def load_batch(date):
    return db["batch_stats"].find_one({"date": date}, {"_id": 0})

@st.cache_data(ttl=60)
def get_dates():
    # Thêm check an toàn nếu collection rỗng
    cursor = db["batch_stats"].find({}, {"date": 1, "_id": 0}).sort("date", -1)
    return [d["date"] for d in cursor if "date" in d]

# ── 4. SIDEBAR ─────────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ Control")

    if st.button("🔄 Refresh"):
        st.cache_data.clear()

    st.divider()

    dates = get_dates()
    selected_date = st.selectbox("📅 Batch Date", dates) if dates else None

# ── 5. HEADER ──────────────────────────────────────────────
st.title("🫁 Smart X-Ray Analytics")
st.caption("Lambda Architecture: Speed + Batch")
st.divider()

tab1, tab2, tab3 = st.tabs(["⚡ Speed", "📦 Batch", "💰 Economic"])

# ============================================================
# ⚡ SPEED TAB
# ============================================================
with tab1:
    st.subheader("🔴 Realtime Monitoring")

    df = load_live()

    if df.empty:
        st.info("No realtime data available in the database.")
    else:
        # Bắt lỗi nếu column không tồn tại
        req_emg_sum = int(df["requires_emergency"].sum()) if "requires_emergency" in df.columns else 0
        prio_sum = int((df["priority"] == 3).sum()) if "priority" in df.columns else 0
        latency_mean = df['processing_time_ms'].mean() if "processing_time_ms" in df.columns else 0

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total", len(df))
        col2.metric("Emergency", req_emg_sum)
        col3.metric("Priority 3", prio_sum)
        col4.metric("Latency (ms)", f"{latency_mean:.1f}")

        st.divider()

        st.markdown("### 🚨 Emergency Cases")

        df_emg = df[df["priority"] == 3] if "priority" in df.columns else pd.DataFrame()

        if df_emg.empty:
            st.success("No emergency cases at the moment.")
        else:
            for _, r in df_emg.head(5).iterrows():
                c1, c2 = st.columns([1, 3])

                with c1:
                    # Xử lý an toàn khi không tìm thấy ảnh trên web server
                    img_filename = r.get("image_filename", "")
                    path = os.path.join(IMG_DIR, img_filename) if img_filename else ""
                    
                    try:
                        if os.path.exists(path):
                            st.image(Image.open(path))
                        else:
                            st.image("https://via.placeholder.com/224?text=No+Image")
                    except Exception:
                        st.image("https://via.placeholder.com/224?text=Error")

                with c2:
                    st.error(f"🚨 Patient {r.get('patient_id', 'Unknown')}")

                    diseases = r.get("diseases", [])
                    st.write("Disease:", ", ".join(diseases) if diseases else "None")

                    st.write("Severity:", r.get("severity", "Unknown"))

                    # 🔥 Xử lý Timestamp an toàn chống lỗi crash web
                    try:
                        ts = r.get("processing_timestamp")
                        if ts:
                            ts_pd = pd.to_datetime(ts)
                            if ts_pd.tzinfo is None:
                                ts_pd = ts_pd.tz_localize('UTC')
                            time_ago = int((pd.Timestamp.utcnow() - ts_pd).total_seconds())
                            st.caption(f"{time_ago}s ago")
                        else:
                            st.caption("Timestamp missing")
                    except Exception as e:
                        st.caption("Time calc error")

# ============================================================
# 📦 BATCH TAB
# ============================================================
with tab2:
    st.subheader("📊 Daily Analytics")

    if selected_date:
        bs = load_batch(selected_date)

        if not bs:
            st.warning("No batch data for this date.")
        else:
            col1, col2, col3, col4 = st.columns(4)

            col1.metric("Total", bs.get("total_cases", 0))
            col2.metric("Abnormal", bs.get("abnormal_cases", 0))
            col3.metric("Emergency", bs.get("emergency_cases", 0))
            col4.metric("Doctors", bs.get("doctors_needed", 0))

            st.divider()

            c1, c2 = st.columns(2)

            with c1:
                dis = bs.get("disease_distribution", {})
                if dis:
                    df_dis = pd.DataFrame(dis.items(), columns=["disease", "count"])
                    st.plotly_chart(px.bar(df_dis, x="count", y="disease", orientation='h'), use_container_width=True)

            with c2:
                sev = bs.get("severity_distribution", {})
                if sev:
                    df_sev = pd.DataFrame(sev.items(), columns=["severity", "count"])
                    st.plotly_chart(px.pie(df_sev, values="count", names="severity"), use_container_width=True)

# ============================================================
# 💰 ECONOMIC TAB
# ============================================================
with tab3:
    st.subheader("💰 Economic Impact")

    total_cases = 0
    total_abnormal = 0

    dates_list = get_dates()
    if dates_list:
        for d in dates_list:
            bs = load_batch(d)
            if bs:
                total_cases += bs.get("total_cases", 0)
                total_abnormal += bs.get("abnormal_cases", 0)

    normal = total_cases - total_abnormal
    saved = normal * 150_000

    c1, c2, c3 = st.columns(3)

    c1.metric("Total Historical Cases", total_cases)
    c2.metric("Normal Cases Triaged", normal)
    c3.metric("Estimated Cost Saved (VND)", f"{saved/1e6:.1f}M")

st.divider()
st.caption("Lambda Architecture Demo")
