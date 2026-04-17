# ============================================================
# DASHBOARD — Real-time Decision Support (Lambda Architecture)
# ============================================================

import streamlit as st
import pandas as pd
import plotly.express as px
from pymongo import MongoClient
from datetime import datetime, timezone
import os
from PIL import Image

# ── 1. PAGE CONFIG & STYLING ───────────────────────────────────────────────

st.set_page_config(page_title="Smart X-Ray Analytics", page_icon="🫁", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #FAFAFA; }
    .alert-box { background:#FFF3E0; border-left:5px solid #E53935; border-radius:8px; padding:10px 14px; margin:4px 0; }
    .success-box { background:#E8F5E9; border-left:5px solid #43A047; border-radius:8px; padding:10px 14px; margin:4px 0; }
    .metric-card { background:#fff; border-radius:8px; padding:15px; box-shadow:0 2px 5px rgba(0,0,0,0.05); text-align:center;}
</style>
""", unsafe_allow_html=True)

# Cấu hình đường dẫn thư mục chứa ảnh X-quang
IMG_DIR = "/content/images-224/images-224"

# ── 2. DATABASE CONNECTION ─────────────────────────────────────────────────

@st.cache_resource
def get_db():
    try:
        mongo_uri = st.secrets["MONGO_URI"]
    except:
        mongo_uri = "mongodb+srv://tuyettrinh3525:Trinh3005@clusterbigdata.ubhpjjc.mongodb.net/?appName=ClusterBigData"
    
    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000, tls=True, tlsAllowInvalidCertificates=True)
    return client["chestxray_db"]

db = get_db()

# ── 3. DATA LOADING FUNCTIONS ──────────────────────────────────────────────

# SPEED LAYER: Lấy các luồng ảnh vừa được xử lý gần nhất (Real-time)
def load_live_predictions(limit=50):
    docs = list(db["predictions"].find(
        {}, {"_id": 0}
    ).sort("processing_timestamp", -1).limit(limit))
    return pd.DataFrame(docs) if docs else pd.DataFrame()

# BATCH LAYER: Lấy thống kê lịch sử theo ngày
@st.cache_data(ttl=60)
def load_batch_stats_by_date(date_str):
    return db["batch_stats"].find_one({"date": date_str}, {"_id": 0, "computed_at": 0})

@st.cache_data(ttl=60)
def get_available_dates():
    dates = list(db["batch_stats"].find({}, {"date": 1, "_id": 0}).sort("date", -1))
    return [d["date"] for d in dates]

# ── 4. UI: SIDEBAR ─────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("### ⚙️ Bảng Điều Khiển")
    
    # Nút làm mới dữ liệu Live
    if st.button("🔄 Cập nhật Live Feed", use_container_width=True, type="primary"):
        st.cache_data.clear()
        
    st.divider()
    
    st.markdown("### 📅 Bộ lọc Batch Layer")
    available_dates = get_available_dates()
    if available_dates:
        selected_date_str = st.selectbox("Chọn ngày xem báo cáo:", available_dates)
    else:
        st.warning("Chưa có dữ liệu Batch")
        selected_date_str = datetime.now().strftime("%Y-%m-%d")

    st.divider()
    st.markdown("**ℹ️ Kiến trúc Lambda**\n- ⚡ **Speed:** Live predictions\n- 📦 **Batch:** Daily aggregated stats")

# ── 5. UI: HEADER ──────────────────────────────────────────────────────────

st.markdown('<h1 style="text-align:center;color:#1565C0;">🫁 Smart X-Ray Analytics</h1>', unsafe_allow_html=True)
st.markdown('<p style="text-align:center;color:#757575;">DenseNet121 · AUC=0.8380 · Real-time Decision Support</p>', unsafe_allow_html=True)
st.divider()

# Phân chia Dashboard thành các Tab theo Kiến trúc Lambda
tab_speed, tab_batch, tab_roi = st.tabs(["⚡ LIVE MONITOR (Speed Layer)", "📦 BÁO CÁO NGÀY (Batch Layer)", "💰 TÁC ĐỘNG KINH TẾ"])

# ── TAB 1: SPEED LAYER (LIVE) ──────────────────────────────────────────────
with tab_speed:
    st.subheader("🔴 Giám sát luồng dữ liệu trực tiếp (50 ca gần nhất)")
    
    df_live = load_live_predictions(limit=50)
    
    if df_live.empty:
        st.info("Đang chờ dữ liệu từ luồng máy quét...")
    else:
        n_emg = int(df_live["requires_emergency"].sum())
        n_pri3 = int((df_live["priority"]==3).sum())
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("🏥 Đang chờ xử lý", len(df_live))
        c2.metric("🔴 Cần cấp cứu", n_emg)
        c3.metric("⚠️ Priority 3", n_pri3)
        c4.metric("⏱️ Tốc độ xử lý (TB)", f"{df_live['processing_time_ms'].mean():.0f} ms")

        # Cảnh báo các ca Emergency có kèm hình ảnh X-quang
        st.markdown("### 🚨 Danh sách ưu tiên cao")
        df_emg = df_live[df_live["priority"] == 3]
        
        if df_emg.empty:
            st.markdown('<div class="success-box"><b>✅ Hiện không có ca bệnh nguy hiểm nào.</b></div>', unsafe_allow_html=True)
        else:
            for _, r in df_emg.head(5).iterrows():
                with st.container():
                    col1, col2 = st.columns([1, 3])
                    
                    with col1:
                        # Load và hiển thị ảnh X-quang
                        image_name = r.get("image_filename", "unknown.png")
                        img_path = os.path.join(IMG_DIR, image_name)
                        
                        if os.path.exists(img_path):
                            st.image(Image.open(img_path), caption=f"ID: {r.get('patient_id', 'N/A')}", use_container_width=True)
                        else:
                            st.image("https://via.placeholder.com/224x224.png?text=No+Image+Found", caption="Image Missing", use_container_width=True)
                    
                    with col2:
                        st.markdown(f"#### 🚨 CẢNH BÁO KHẨN CẤP: BỆNH NHÂN `{r.get('patient_id', 'Unknown')}`")
                        
                        diseases = r.get("diseases", [])
                        if not diseases or diseases == ["No Finding"]:
                            diseases_str = "Hồ sơ y lệnh khẩn"
                        else:
                            diseases_str = ", ".join(diseases)
                            
                        st.error(f"**Phát hiện bệnh:** {diseases_str}")
                        st.write(f"- **Độ tuổi:** {r.get('age', 'N/A')} ({r.get('age_group', 'N/A')})")
                        st.write(f"- **Mức độ nghiêm trọng nền:** {str(r.get('severity', 'N/A')).upper()}")
                        
                        time_ago = (datetime.now(timezone.utc) - r["processing_timestamp"].replace(tzinfo=timezone.utc)).seconds
                        ms = r.get("processing_time_ms", 0)
                        st.caption(f"⏱️ *AI Inference Time: {ms:.2f} ms* | 🕒 *Phát hiện {time_ago} giây trước*")
                        
                st.markdown("---")

# ── TAB 2: BATCH LAYER (HISTORY) ───────────────────────────────────────────
with tab_batch:
    st.subheader(f"📊 Báo cáo tổng hợp ngày: {selected_date_str}")
    bs = load_batch_stats_by_date(selected_date_str)
    
    if not bs:
        st.warning("Dữ liệu ngày này chưa được Batch Layer tổng hợp.")
    else:
        # Overview KPIs
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Tổng ca quét", f"{bs.get('total_cases', 0):,}")
        col2.metric("Ca bất thường", f"{bs.get('is_abnormal_count', 0):,}")
        col3.metric("Tỷ lệ bất thường", f"{bs.get('abnormal_rate_pct', 0):.1f}%")
        col4.metric("Ca khẩn cấp", f"{bs.get('emergency_cases', 0):,}")
        
        st.markdown("---")
        
        c_chart1, c_chart2 = st.columns(2)
        
        # Biểu đồ loại bệnh
        with c_chart1:
            diseases = bs.get("disease_distribution", {})
            if diseases:
                df_dis = pd.DataFrame(list(diseases.items()), columns=["Disease", "Count"]).sort_values("Count", ascending=True)
                fig_dis = px.bar(df_dis, x="Count", y="Disease", orientation='h', title="Phân bố bệnh lý")
                st.plotly_chart(fig_dis, use_container_width=True)
        
        # Biểu đồ độ tuổi
        with c_chart2:
            ages = bs.get("age_group_distribution", {})
            if ages:
                df_age = pd.DataFrame(list(ages.items()), columns=["Age Group", "Count"])
                fig_age = px.pie(df_age, values="Count", names="Age Group", hole=0.4, title="Phân bố nhóm tuổi")
                st.plotly_chart(fig_age, use_container_width=True)

# ── TAB 3: ECONOMIC IMPACT ─────────────────────────────────────────────────
with tab_roi:
    st.subheader("💰 Đánh giá Tác động Kinh tế & Hiệu suất")
    st.info("Giả định: Chi phí cho bác sĩ đọc 1 tấm ảnh X-quang thủ công là 150,000 VNĐ.")
    
    all_batch_dates = get_available_dates()
    total_scans = 0
    total_abnormal = 0
    
    for d in all_batch_dates:
        day_stats = load_batch_stats_by_date(d)
        if day_stats:
            total_scans += day_stats.get("total_cases", 0)
            total_abnormal += day_stats.get("is_abnormal_count", 0)
            
    total_normal = total_scans - total_abnormal
    saved_vnd = total_normal * 150_000
    
    e1, e2, e3 = st.columns(3)
    e1.metric("Tổng ảnh đã quét (Lịch sử)", f"{total_scans:,}")
    e2.metric("Ảnh bình thường (AI tự động lọc)", f"{total_normal:,}", delta="Không cần BS đọc", delta_color="normal")
    e3.metric("Tổng tiền tiết kiệm ước tính", f"{saved_vnd/1e6:.1f} Triệu VNĐ")

# ── FOOTER ─────────────────────────────────────────────────────────────────
st.divider()
st.markdown('<p style="text-align:center;color:#9E9E9E;font-size:.8rem">Hệ thống mô phỏng phục vụ Đồ Án | MongoDB + Streamlit</p>', unsafe_allow_html=True)
