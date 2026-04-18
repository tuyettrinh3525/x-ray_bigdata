# ============================================================
# DASHBOARD V4 — ANALYTICS, INSIGHTS & UI TWEAKS (FIXED)
# ============================================================
# SYNCED with Batch Layer (90 days: Jan 1 - Mar 31, 2026)
# Fixed: Load từ MongoDB batch_stats (không tính toán lại)
# Fixed: Handle NumPy types properly

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pymongo import MongoClient
from datetime import datetime, timezone, timedelta
import os
import json
import numpy as np

# ── 1. CONFIG & CSS ─────────────────────────────────────────
st.set_page_config(
    page_title="X-Ray Analytics", 
    page_icon="🫁", 
    layout="wide"
)

# CSS custom styling
st.markdown("""
<style>
    div[data-testid="metric-container"] {
        background-color: #ffffff; 
        border: 1px solid #e0e6ed;
        padding: 15px 20px; 
        border-radius: 12px;
        box-shadow: 0px 4px 6px rgba(0, 0, 0, 0.05);
    }
    div[data-testid="metric-container"] label { 
        color: #64748b !important; 
        font-weight: 600; 
    }
    div[data-testid="metric-container"] div[data-testid="stMetricValue"] { 
        color: #0f172a !important; 
        font-weight: 800; 
    }
    .stTabs [data-baseweb="tab-list"] { 
        gap: 20px; 
    }
    .stTabs [data-baseweb="tab"] { 
        height: 50px; 
        font-weight: 600; 
    }
    
    /* Alert styling */
    .alert-success {
        background-color: #d1fae5;
        border-left: 4px solid #10b981;
        padding: 12px;
        border-radius: 4px;
    }
    .alert-warning {
        background-color: #fef3c7;
        border-left: 4px solid #f59e0b;
        padding: 12px;
        border-radius: 4px;
    }
    .alert-critical {
        background-color: #fee2e2;
        border-left: 4px solid #ef4444;
        padding: 12px;
        border-radius: 4px;
    }
</style>
""", unsafe_allow_html=True)

# Image directory
IMG_DIR = r"D:\2321003619_Nguyễn Tuyết Trinh\X-RAY\images-224"

# ── 2. DB CONNECTION ───────────────────────────────────────
@st.cache_resource
def get_db():
    MONGO_URI = "mongodb+srv://tuyettrinh3525:Trinh3005@clusterbigdata.ubhpjjc.mongodb.net/?appName=ClusterBigData"
    client = MongoClient(MONGO_URI)
    return client["chestxray_db"]

db = get_db()

# ── 3. HELPER FUNCTIONS ────────────────────────────────────

def convert_numpy_types(obj):
    """Convert NumPy types to Python native types for proper display"""
    if isinstance(obj, dict):
        return {k: convert_numpy_types(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_types(v) for v in obj]
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    else:
        return obj

def load_live(limit=50):
    """Load live predictions from Speed Layer"""
    docs = list(db["predictions"].find({}, {"_id": 0})
                .sort("system_meta.timestamp", -1)
                .limit(limit))
    
    if not docs:
        return pd.DataFrame()
    
    df = pd.json_normalize(docs)
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
    """Load batch stats from Batch Layer"""
    doc = db["batch_stats"].find_one({"date": date}, {"_id": 0})
    if doc:
        doc = convert_numpy_types(doc)
    return doc

@st.cache_data(ttl=60)
def get_dates():
    """Get all available batch dates"""
    cursor = db["batch_stats"].find({}, {"date": 1, "_id": 0}).sort("date", -1)
    dates = [d["date"] for d in cursor if "date" in d]
    return sorted(dates, reverse=True)

@st.cache_data(ttl=300)
def load_economic_history(days=90):
    """Load economic data for trending"""
    cursor = db["batch_stats"].find({}, {
        "date": 1, 
        "total_cases": 1, 
        "abnormal_cases": 1,
        "normal_cases": 1,
        "daily_cost_saved_vnd": 1,
        "roi_metrics": 1,
        "_id": 0
    }).sort("date", 1)
    
    df = pd.DataFrame(list(cursor))
    
    if df.empty:
        return df
    
    # Convert NumPy types
    for col in df.columns:
        if df[col].dtype == object:
            continue
        try:
            df[col] = df[col].apply(lambda x: int(x) if isinstance(x, (np.integer, np.floating)) else x)
        except:
            pass
    
    return df

# ── 4. SIDEBAR ─────────────────────────────────────────────
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3003/3003261.png", width=60)
    st.title("Admin Control")
    
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    
    st.divider()
    
    dates = get_dates()
    if dates:
        selected_date = st.selectbox(
            "📅 Select Batch Date",
            dates,
            help="Select date to view batch statistics"
        )
    else:
        st.warning("⚠️ No batch data available")
        selected_date = None

# ── 5. HEADER ──────────────────────────────────────────────
st.title("🫁 X-Ray Analytics Dashboard")
st.caption("Powered by Lambda Architecture (Real-time Inference + Batch Aggregation)")

# Show period info
if dates:
    start_date = dates[-1] if dates else None
    end_date = dates[0] if dates else None
    num_days = len(dates)
    st.info(f"📊 Data Period: {start_date} to {end_date} ({num_days} days - Q1 2026)")

st.divider()

# Create tabs
tab1, tab2, tab3, tab4 = st.tabs([
    "⚡ Realtime Speed", 
    "📦 Daily Batch Insights", 
    "💰 Economic ROI",
    "📈 Trends & Analytics"
])

# ============================================================
# ⚡ TAB 1: SPEED (REALTIME)
# ============================================================
with tab1:
    st.subheader("🔴 Live Triage Queue")
    
    df = load_live()
    
    if df.empty:
        st.info("ℹ️ No realtime data streaming right now.")
    else:
        # Metrics
        req_emg_sum = int(df["requires_emergency"].sum()) if "requires_emergency" in df.columns else 0
        prio_sum = int((df["priority"] == 3).sum()) if "priority" in df.columns else 0
        avg_latency = float(df["processing_time_ms"].mean()) if "processing_time_ms" in df.columns else 0
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Recent Scans", len(df))
        c2.metric(
            "Emergency Flags", 
            req_emg_sum, 
            delta="🚨 High Alert" if req_emg_sum > 0 else "✅ Normal", 
            delta_color="inverse"
        )
        c3.metric("Critical Priority", prio_sum)
        c4.metric("Avg Latency", f"{avg_latency:.1f} ms")
        
        st.divider()
        st.markdown("### 🚨 High Priority Patients (Needs Immediate Review)")
        
        df_emg = df[df["priority"] == 3] if "priority" in df.columns else pd.DataFrame()
        
        if df_emg.empty:
            st.success("✅ Queue clear. No critical patients waiting.")
        else:
            for idx, (_, r) in enumerate(df_emg.head(5).iterrows()):
                with st.container():
                    col_img, col_info = st.columns([1, 4])
                    
                    with col_img:
                        img_name = r.get('image_filename', '')
                        full_path = os.path.join(IMG_DIR, img_name)
                        
                        if os.path.exists(full_path):
                            st.image(full_path, use_container_width=True)
                        else:
                            st.image(
                                "https://img.freepik.com/premium-vector/x-ray-human-chest-icon-isolated-blue-background_532867-46.jpg",
                                caption=f"Missing: {img_name}",
                                use_container_width=True
                            )
                    
                    with col_info:
                        st.error(f"**Patient ID:** {r.get('patient_id', 'N/A')}")
                        diseases = r.get('diseases', [])
                        st.write(f"**Detected:** {', '.join(diseases) if diseases else 'None'}")
                        severity = r.get('severity', 'Unknown')
                        
                        # Color-coded severity
                        if severity == "CRITICAL":
                            st.write(f"**Severity:** 🔴 `{severity}`")
                        elif severity == "ABNORMAL":
                            st.write(f"**Severity:** 🟡 `{severity}`")
                        else:
                            st.write(f"**Severity:** 🟢 `{severity}`")
                        
                        # Confidence score (if available)
                        confidence = r.get('confidence_score', None)
                        if confidence:
                            conf_val = float(confidence)
                            st.write(f"**AI Confidence:** {conf_val*100:.1f}% {'🟢' if conf_val > 0.8 else '🟡' if conf_val > 0.6 else '🔴'}")
                    
                    st.write("")  # Spacing

# ============================================================
# 📦 TAB 2: BATCH INSIGHTS
# ============================================================
with tab2:
    if selected_date:
        bs = load_batch(selected_date)
        
        if bs:
            st.subheader(f"📊 Analytics for {selected_date}")
            
            # Operational Insight
            emg_rate = float(bs.get('emergency_rate_pct', 0))
            abnormal_rate = float(bs.get('abnormal_rate_pct', 0))
            
            if emg_rate > 10:
                st.warning(
                    f"⚠️ **Operational Insight:** Tỷ lệ ca cấp cứu cao ({emg_rate:.1f}%). "
                    f"Đề xuất điều phối thêm Bác sĩ trực!"
                )
            else:
                st.success(
                    f"✅ **Operational Insight:** Lượng ca bệnh ổn định. "
                    f"Cần {int(bs.get('doctors_needed', 0))} bác sĩ để xử lý khối lượng hôm nay."
                )
            
            # KPIs
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total Scans", f"{int(bs.get('total_cases', 0)):,}")
            c2.metric("Abnormal Findings", f"{int(bs.get('abnormal_cases', 0)):,} ({abnormal_rate:.1f}%)")
            c3.metric("Emergency Cases", f"{int(bs.get('emergency_cases', 0)):,} ({emg_rate:.1f}%)")
            c4.metric("Doctors Required", int(bs.get('doctors_needed', 0)))
            
            st.divider()
            
            c_left, c_right = st.columns(2)
            
            # Left: Top Diseases
            with c_left:
                st.markdown("**🦠 Top Abnormal Diseases** *(Filtered 'No Finding')*")
                dis = bs.get("disease_distribution", {})
                
                if dis:
                    # Remove "No Finding" and sort
                    dis_filtered = {k: v for k, v in dis.items() if k != "No Finding"}
                    df_dis = pd.DataFrame(
                        sorted(dis_filtered.items(), key=lambda x: x[1], reverse=True)[:10],
                        columns=["Disease", "Count"]
                    )
                    
                    if not df_dis.empty:
                        df_dis["Count"] = df_dis["Count"].astype(int)
                        fig_bar = px.bar(
                            df_dis,
                            x="Count",
                            y="Disease",
                            orientation='h',
                            color="Count",
                            color_continuous_scale="Reds"
                        )
                        fig_bar.update_layout(
                            margin=dict(l=0, r=0, t=0, b=0),
                            height=400
                        )
                        st.plotly_chart(fig_bar, use_container_width=True)
            
            # Right: Severity Distribution
            with c_right:
                st.markdown("**⚠️ Severity Distribution**")
                sev = bs.get("severity_distribution", {})
                
                if sev:
                    df_sev = pd.DataFrame(sev.items(), columns=["Severity", "Count"])
                    df_sev["Count"] = df_sev["Count"].astype(int)
                    
                    color_map = {
                        'critical': '#7f1d1d',
                        'high': '#dc2626',
                        'moderate': '#f59e0b',
                        'mild': '#3b82f6',
                        'none': '#94a3b8'
                    }
                    
                    fig_pie = px.pie(
                        df_sev,
                        values="Count",
                        names="Severity",
                        hole=0.4,
                        color='Severity',
                        color_discrete_map=color_map
                    )
                    fig_pie.update_layout(
                        margin=dict(l=0, r=0, t=0, b=0),
                        height=400
                    )
                    st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.warning(f"ℹ️ No batch data available for {selected_date}")
    else:
        st.info("📅 Please select a date from the sidebar")

# ============================================================
# 💰 TAB 3: ECONOMIC ROI
# ============================================================
with tab3:
    st.subheader("💰 Return on Investment (ROI) & Efficiency")
    
    if selected_date:
        bs = load_batch(selected_date)
        
        if bs:
            # Get ROI metrics
            roi = bs.get("roi_metrics", {})
            cost_breakdown = bs.get("cost_breakdown", {})
            efficiency = bs.get("efficiency", {})
            
            # Metrics
            c1, c2, c3 = st.columns(3)
            
            daily_savings = int(roi.get("daily_savings_vnd", 0))
            c1.metric(
                "Daily Savings",
                f"{daily_savings/1e6:.2f}M VND",
                delta="Cost Optimized"
            )
            
            daily_cost = int(roi.get("daily_infrastructure_cost_vnd", 0))
            c2.metric(
                "Infrastructure Cost",
                f"{daily_cost/1e6:.2f}M VND"
            )
            
            payback = float(roi.get("payback_period_days", 0))
            c3.metric(
                "Payback Period",
                f"{payback:.2f} days" if payback > 1 else f"{payback*24:.1f} hours",
                delta="Break even" if payback < 1 else "Extended"
            )
            
            st.divider()
            
            # Cost comparison
            st.markdown("### 💵 Cost Analysis")
            
            c_left, c_right = st.columns(2)
            
            with c_left:
                manual_cost = int(cost_breakdown.get("manual_workflow", {}).get("cost_per_diagnosis_vnd", 0))
                ai_cost = int(cost_breakdown.get("ai_assisted_workflow", {}).get("cost_per_diagnosis_vnd", 0))
                
                comparison_df = pd.DataFrame({
                    "Workflow": ["Manual", "AI-Assisted"],
                    "Cost per Scan (VND)": [manual_cost, ai_cost]
                })
                
                fig_comp = px.bar(
                    comparison_df,
                    x="Workflow",
                    y="Cost per Scan (VND)",
                    color="Workflow",
                    color_discrete_map={"Manual": "#ef4444", "AI-Assisted": "#10b981"},
                    text="Cost per Scan (VND)"
                )
                fig_comp.update_layout(
                    margin=dict(l=0, r=0, t=0, b=0),
                    height=350,
                    showlegend=False
                )
                st.plotly_chart(fig_comp, use_container_width=True)
            
            with c_right:
                st.markdown("**📊 Financial Metrics**")
                
                cost_saved_pct = float(bs.get("cost_saved_percentage", 0))
                annual_savings = int(roi.get("annual_savings_vnd", 0))
                annual_roi = float(roi.get("annual_roi_percentage", 0))
                
                st.metric("Cost Saved %", f"{cost_saved_pct:.1f}%")
                st.metric(
                    "Annual Savings",
                    f"{annual_savings/1e9:.2f}B VND"
                )
                st.metric("Annual ROI", f"{annual_roi:.1f}%")
            
            st.divider()
            
            # Time efficiency
            st.markdown("### ⏱️ Time Efficiency")
            
            c_time1, c_time2, c_time3 = st.columns(3)
            
            time_saved = float(efficiency.get("time_saved_doctor_hours_per_day", 0))
            equiv_days = float(efficiency.get("equivalent_radiologist_days_saved", 0))
            normal_cases = int(efficiency.get("normal_cases_fast_screened", 0))
            
            c_time1.metric(
                "Hours Saved Today",
                f"{time_saved:.1f} hours"
            )
            c_time2.metric(
                "Equivalent Days",
                f"{equiv_days:.2f} radiologist-days"
            )
            c_time3.metric(
                "Normal Cases",
                f"{normal_cases:,} (fast screened)"
            )
            
        else:
            st.warning(f"ℹ️ No batch data available for {selected_date}")
    else:
        st.info("📅 Please select a date from the sidebar")

# ============================================================
# 📈 TAB 4: TRENDS & ANALYTICS
# ============================================================
with tab4:
    st.subheader("📈 90-Day Trends & Analytics (Q1 2026)")
    
    df_eco = load_economic_history(days=90)
    
    if not df_eco.empty:
        # Convert NumPy types
        df_eco["daily_cost_saved_vnd"] = df_eco["daily_cost_saved_vnd"].apply(
            lambda x: int(x) if isinstance(x, (np.integer, np.floating)) else x
        )
        
        # Calculate cumulative metrics
        df_eco['cumulative_savings_vnd'] = df_eco['daily_cost_saved_vnd'].cumsum()
        
        # Trend analysis
        c_trend1, c_trend2 = st.columns(2)
        
        with c_trend1:
            st.markdown("### 📊 Cumulative Savings Over Time")
            
            fig_savings = go.Figure()
            fig_savings.add_trace(go.Scatter(
                x=df_eco['date'],
                y=df_eco['cumulative_savings_vnd'],
                mode='lines+markers',
                fill='tozeroy',
                line=dict(color='#10b981', width=3),
                name="Cumulative Savings",
                marker=dict(size=6)
            ))
            
            fig_savings.update_layout(
                xaxis_title="Date",
                yaxis_title="VND (Cumulative)",
                hovermode="x unified",
                height=400,
                margin=dict(l=0, r=0, t=0, b=0)
            )
            
            st.plotly_chart(fig_savings, use_container_width=True)
        
        with c_trend2:
            st.markdown("### 📈 Daily Scan Volume Trend")
            
            df_eco["total_cases"] = df_eco["total_cases"].apply(
                lambda x: int(x) if isinstance(x, (np.integer, np.floating)) else x
            )
            
            fig_volume = go.Figure()
            fig_volume.add_trace(go.Scatter(
                x=df_eco['date'],
                y=df_eco['total_cases'],
                mode='lines+markers',
                line=dict(color='#3b82f6', width=3),
                name="Daily Scans",
                marker=dict(size=6)
            ))
            
            fig_volume.update_layout(
                xaxis_title="Date",
                yaxis_title="Number of Scans",
                hovermode="x unified",
                height=400,
                margin=dict(l=0, r=0, t=0, b=0)
            )
            
            st.plotly_chart(fig_volume, use_container_width=True)
        
        st.divider()
        
        # Summary stats
        c_sum1, c_sum2, c_sum3, c_sum4 = st.columns(4)
        
        total_scans = int(df_eco['total_cases'].sum())
        total_normal = int(df_eco['normal_cases'].sum())
        total_savings = int(df_eco['cumulative_savings_vnd'].iloc[-1]) if len(df_eco) > 0 else 0
        avg_daily_savings = int(df_eco['daily_cost_saved_vnd'].mean())
        
        c_sum1.metric("Total Scans (90 days)", f"{total_scans:,}")
        c_sum2.metric("Normal Cases", f"{total_normal:,} ({(total_normal/total_scans*100):.1f}%)")
        c_sum3.metric("Total Savings", f"{total_savings/1e9:.2f}B VND")
        c_sum4.metric("Avg Daily Savings", f"{avg_daily_savings/1e6:.2f}M VND")
        
        # Anomaly detection
        st.markdown("### ⚠️ Anomaly Detection")
        
        mean_scans = df_eco['total_cases'].mean()
        std_scans = df_eco['total_cases'].std()
        threshold = mean_scans + (2 * std_scans)
        
        anomalies = df_eco[df_eco['total_cases'] > threshold]
        
        if not anomalies.empty:
            st.warning(f"🚨 Found {len(anomalies)} anomalous days (high volume):")
            for _, row in anomalies.iterrows():
                st.write(f"  • {row['date']}: {int(row['total_cases']):,} scans (avg: {mean_scans:.0f})")
        else:
            st.success(f"✅ No anomalies detected. Scan volume stable (avg: {mean_scans:.0f}/day)")
        
        st.divider()
        
        # Monthly breakdown
        st.markdown("### 📅 Monthly Breakdown (Q1 2026)")
        
        try:
            df_eco['month'] = pd.to_datetime(df_eco['date']).dt.month
            
            for month_num in [1, 2, 3]:
                month_data = df_eco[df_eco['month'] == month_num]
                
                if not month_data.empty:
                    month_name = pd.to_datetime(f"2026-{month_num:02d}-01").strftime('%B')
                    month_scans = int(month_data['total_cases'].sum())
                    month_savings = int(month_data['daily_cost_saved_vnd'].sum())
                    month_normal = int(month_data['normal_cases'].sum())
                    
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.metric(f"{month_name}", f"{month_scans:,} scans")
                    with col2:
                        st.metric(f"{month_name} Saved", f"{month_savings/1e9:.2f}B VND")
                    with col3:
                        st.metric(f"{month_name} Normal", f"{month_normal:,}")
        except Exception as e:
            st.error(f"Error in monthly breakdown: {e}")
    
    else:
        st.info("ℹ️ No historical data available yet")

# ── Footer ──────────────────────────────────────────────────
st.divider()
st.markdown(f"""
    <div style="text-align: center; color: #999; font-size: 0.85rem;">
    X-Ray Analytics Dashboard | Lambda Architecture | Q1 2026 Data | Last Updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC
    </div>
    """, unsafe_allow_html=True)
