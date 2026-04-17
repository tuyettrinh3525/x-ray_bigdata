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
    client = MongoClient("mongodb://localhost:27017/")
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
    return [
        d["date"]
        for d in db["batch_stats"]
        .find({}, {"date": 1, "_id": 0})
        .sort("date", -1)
    ]

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
        st.info("No realtime data")
    else:
        col1, col2, col3, col4 = st.columns(4)

        col1.metric("Total", len(df))
        col2.metric("Emergency", int(df["requires_emergency"].sum()))
        col3.metric("Priority 3", int((df["priority"] == 3).sum()))
        col4.metric("Latency (ms)", f"{df['processing_time_ms'].mean():.1f}")

        st.divider()

        st.markdown("### 🚨 Emergency Cases")

        df_emg = df[df["priority"] == 3]

        if df_emg.empty:
            st.success("No emergency cases")
        else:
            for _, r in df_emg.head(5).iterrows():
                c1, c2 = st.columns([1, 3])

                with c1:
                    path = os.path.join(IMG_DIR, r.get("image_filename", ""))
                    if os.path.exists(path):
                        st.image(Image.open(path))
                    else:
                        st.image("https://via.placeholder.com/224")

                with c2:
                    st.error(f"🚨 Patient {r['patient_id']}")

                    diseases = r.get("diseases", [])
                    st.write("Disease:", ", ".join(diseases) if diseases else "None")

                    st.write("Severity:", r["severity"])

                    # 🔥 dùng processing_timestamp
                    time_ago = (
                        datetime.now(timezone.utc)
                        - r["processing_timestamp"].replace(tzinfo=timezone.utc)
                    ).seconds

                    st.caption(f"{time_ago}s ago")

# ============================================================
# 📦 BATCH TAB
# ============================================================
with tab2:
    st.subheader("📊 Daily Analytics")

    if selected_date:
        bs = load_batch(selected_date)

        if not bs:
            st.warning("No batch data")
        else:
            col1, col2, col3, col4 = st.columns(4)

            col1.metric("Total", bs["total_cases"])
            col2.metric("Abnormal", bs["abnormal_cases"])
            col3.metric("Emergency", bs["emergency_cases"])
            col4.metric("Doctors", bs["doctors_needed"])

            st.divider()

            c1, c2 = st.columns(2)

            # disease
            with c1:
                dis = bs.get("disease_distribution", {})
                if dis:
                    df_dis = pd.DataFrame(dis.items(), columns=["disease", "count"])
                    st.plotly_chart(px.bar(df_dis, x="count", y="disease"), use_container_width=True)

            # severity
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

    for d in get_dates():
        bs = load_batch(d)
        if bs:
            total_cases += bs["total_cases"]
            total_abnormal += bs["abnormal_cases"]

    normal = total_cases - total_abnormal
    saved = normal * 150_000

    c1, c2, c3 = st.columns(3)

    c1.metric("Total Cases", total_cases)
    c2.metric("Normal Cases", normal)
    c3.metric("Saved (VND)", f"{saved/1e6:.1f}M")

st.divider()
st.caption("Lambda Architecture Demo")
