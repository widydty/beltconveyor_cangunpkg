import streamlit as st
import pandas as pd
import numpy as np
import math
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Circle, Rectangle
from fpdf import FPDF
import base64
from datetime import datetime

# --- 1. KONFIGURASI SYSTEM & STYLE ---
st.set_page_config(
    page_title="Belt Conveyor Calculation",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS Premium Dashboard
st.markdown("""
<style>
    .main-header {font-size: 36px; font-weight: 900; color: #FDB913; text-shadow: 1px 1px #00563F; margin-bottom: 5px;}
    .sub-header {font-size: 16px; color: #00563F; font-weight: bold; font-style: italic; margin-bottom: 25px;}
    .status-safe {background-color: #d1e7dd; color: #0f5132; padding: 15px; border-radius: 8px; border-left: 8px solid #198754;}
    .status-warn {background-color: #fff3cd; color: #856404; padding: 15px; border-radius: 8px; border-left: 8px solid #ffc107;}
    .status-danger {background-color: #f8d7da; color: #721c24; padding: 15px; border-radius: 8px; border-left: 8px solid #dc3545;}
    .kpi-card {background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 6px rgba(0,0,0,0.15); border-top: 4px solid #FDB913;}
    .kpi-val {font-size: 26px; font-weight: 800; color: #2c3e50;}
    .kpi-lbl {font-size: 12px; text-transform: uppercase; color: #7f8c8d; letter-spacing: 1px;}
    .stTabs [data-baseweb="tab-list"] {gap: 10px;}
    .stTabs [data-baseweb="tab"] {height: 50px; white-space: pre-wrap; border-radius: 4px 4px 0 0; font-weight: 600;}
    .theory-box {background-color: #f8f9fa; padding: 20px; border-radius: 5px; border-left: 4px solid #00563F; margin-bottom: 15px;}
</style>
""", unsafe_allow_html=True)

# --- 2. DATABASE MATERIAL ---
def get_materials():
    return {
        "Urea (Prills)": {"den": 45, "rep": 30, "sur": 20, "max_v": 600, "desc": "Produk Urea butiran kecil. Berdebu & Higroskopis.", "liner": "SS304 / UHMWPE"}, 
        "Urea (Granul)": {"den": 48, "rep": 32, "sur": 25, "max_v": 650, "desc": "Produk Urea butiran besar. Flowability baik.", "liner": "SS304"},
        "ZA (Ammonium Sulfate)": {"den": 60, "rep": 32, "sur": 25, "max_v": 550, "desc": "Kristal/Granul. Sifat Korosif Tinggi (Asam).", "liner": "SS316L"},
        "NPK (Phonska)": {"den": 62, "rep": 34, "sur": 25, "max_v": 600, "desc": "Butiran Majemuk. Korosif & Abrasif sedang.", "liner": "SS304 / AR Steel"},
        "SP-36": {"den": 70, "rep": 35, "sur": 25, "max_v": 600, "desc": "Butiran abu-abu. Debu fosfat.", "liner": "AR400 / SS304"},
        "Petroganik": {"den": 40, "rep": 35, "sur": 25, "max_v": 500, "desc": "Pupuk Organik. Ringan, berserat, bridging.", "liner": "UHMWPE"},
        "Batuan Fosfat": {"den": 85, "rep": 40, "sur": 30, "max_v": 800, "desc": "Bahan baku. Sangat Abrasif & Berat.", "liner": "Ceramic Tile"},
        "Sulfur": {"den": 65, "rep": 35, "sur": 25, "max_v": 500, "desc": "Bahaya ledakan debu & statis.", "liner": "SS304 (Spark Free)"},
        "Kapur (Limestone)": {"den": 90, "rep": 38, "sur": 30, "max_v": 800, "desc": "Penetral pH. Berat & Berdebu.", "liner": "AR400 Steel"},
        "Batu Bara": {"den": 50, "rep": 35, "sur": 25, "max_v": 900, "desc": "Fuel Boiler.", "liner": "AR400 Steel"},
    }

def get_idler_limits(width_in):
    if width_in <= 36: return {"B": 410, "C": 900, "D": 1200}
    elif width_in <= 48: return {"B": 410, "C": 900, "D": 1200}
    else: return {"C": 850, "D": 1200, "E": 1800}

def get_min_pulley(piw):
    if piw <= 150: return 315
    elif piw <= 250: return 400
    elif piw <= 400: return 500
    elif piw <= 600: return 630
    elif piw <= 800: return 800
    else: return 1000

# --- 3. CALCULATION ENGINE ---
class TitanEngine:
    def __init__(self, mat_props, cap, w_mm, v_mps, l_m, h_m, trough_deg, lump_mm):
        self.mat = mat_props
        self.Q = cap * 1.1023 
        self.W_in = w_mm / 25.4
        self.V_fpm = v_mps * 196.85
        self.L = l_m * 3.281
        self.H = h_m * 3.281
        self.trough = math.radians(trough_deg)
        self.trough_deg = trough_deg
        self.lump_mm = lump_mm
        
    def calc_geometry(self):
        edge_std = 0.055 * self.W_in + 0.9
        bw_max = self.W_in - (2 * edge_std)
        c_roll = 0.371 * self.W_in
        h_wing = ((bw_max - c_roll)/2) * math.sin(self.trough)
        area_trap = (c_roll * h_wing) + (((bw_max - c_roll)/2) * h_wing)
        area_sur = (bw_max**2 * math.tan(math.radians(self.mat['sur']))) / 6
        design_cap = ((area_trap + area_sur)/144 * self.V_fpm * 60 * self.mat['den']) / 2000
        load_pct = (self.Q / design_cap * 100) if design_cap > 0 else 0
        bw_act = bw_max * math.sqrt(load_pct/100) if load_pct > 0 else 0
        edge_act = (self.W_in - bw_act)/2
        
        # Lump Check
        max_allowed_lump = self.W_in / 3 * 25.4
        is_lump_ok = self.lump_mm <= max_allowed_lump
        
        return {"load_pct": load_pct, "edge_act": edge_act, "bw_act": bw_act, "c_roll": c_roll, "bw_max": bw_max, "lump_ok": is_lump_ok, "max_lump": max_allowed_lump}

    def calc_power_tension(self):
        Wb = 3 + (self.W_in / 4)
        Wm = (33.3 * self.Q) / self.V_fpm
        Tac = 200 + (5 * self.W_in) 
        Ky = 0.035 if self.L < 500 else 0.025
        Te = self.L * (0.2 + Ky*Wb + 0.015*Wb) + Wm*(self.L*Ky + self.H) + Tac
        T2 = max(Te * 0.35, 12.5*(Wb+Wm))
        T1 = Te + T2
        PIW = T1 / self.W_in
        HP = (Te * self.V_fpm) / 33000
        kW = HP * 0.746 / 0.90
        trac_ratio = T1/T2
        is_slip = trac_ratio > 3.0 
        return {"kW": kW, "T1": T1, "T2": T2, "Te": Te, "PIW": PIW, "Wb": Wb, "Wm": Wm, "Slip": is_slip, "Ratio": trac_ratio}

    def calc_components(self, T1, Wm, Wb):
        spacing = 4.0 if Wm < 100 else 3.0
        load = (Wb + Wm) * spacing
        limits = get_idler_limits(self.W_in)
        series = "E"
        for s, lim in limits.items():
            if load < lim:
                series = s
                break
        rec_p = get_min_pulley(T1/self.W_in)
        r_min = (1.6 * T1) / Wb * 0.3048 
        return {"Series": series, "Load": load, "RecPulley": rec_p, "Curve": r_min}

    def calc_construction_data(self, T1, PIW):
        trough_factor = 3.2 if self.trough_deg == 35 else (4.0 if self.trough_deg == 45 else 2.0)
        trans_dist_m = (trough_factor * self.W_in) * 0.0254
        takeup_len_m = self.L * 0.3048 * 0.015 
        return {"TransDist": trans_dist_m, "TakeupTravel": takeup_len_m}

    def calc_trajectory(self, p_dia_mm):
        rp = (p_dia_mm/25.4)/12/2
        r = rp + ((self.W_in*0.1)/12)
        v_fps = self.V_fpm/60
        g = 32.17
        idx = v_fps**2 / (g*r)
        gamma = 0 if idx>=1 else math.acos(idx)
        t = np.linspace(0, 1.5, 80)
        x = r * math.sin(gamma) + (v_fps*math.cos(gamma)*t)
        y = r * math.cos(gamma) + (-v_fps*math.sin(gamma)*t) - (0.5*g*t**2)
        return x*0.3048, y*0.3048, rp*0.3048, idx

# --- 4. PDF REPORT GENERATOR CLASS ---
class EngineeringReport(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 14)
        self.cell(0, 10, 'BELT CONVEYOR CALCULATION REPORT', 0, 1, 'C')
        self.set_font('Arial', 'I', 10)
        self.cell(0, 10, f'Generated on: {datetime.now().strftime("%Y-%m-%d %H:%M")}', 0, 1, 'C')
        self.line(10, 30, 200, 30)
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

    def section_title(self, title):
        self.set_font('Arial', 'B', 12)
        self.set_fill_color(230, 230, 230)
        self.cell(0, 10, title, 0, 1, 'L', True)
        self.ln(2)

    def data_row(self, label, value):
        self.set_font('Arial', '', 10)
        self.cell(90, 8, label, 1)
        self.cell(0, 8, str(value), 1, 1)

# --- 5. SIDEBAR & INPUT ---
st.sidebar.image("https://upload.wikimedia.org/wikipedia/commons/thumb/2/2f/Petrokimia_Gresik_logo.svg/1200px-Petrokimia_Gresik_logo.svg.png", width=80)
st.sidebar.title("Engineering Tools")

mode = st.sidebar.radio("Mode Pengguna:", ["👤 Operasional (Auto)", "👷 Engineering (Expert)"], horizontal=True)
st.sidebar.markdown("---")

mat_db = get_materials()
sel_mat = st.sidebar.selectbox("1. Material (Petrokimia)", list(mat_db.keys()), help="Pilih material sesuai MSDS atau data produksi.")
mat_data = mat_db[sel_mat]
st.sidebar.info(f"📋 **Sifat:** {mat_data['desc']}")

cap = st.sidebar.number_input("2. Kapasitas (TPH)", 50, 5000, 500, help="Target produksi dalam Ton per Jam.")
length = st.sidebar.number_input("3. Panjang (m)", 10, 5000, 100, help="Jarak horizontal head to tail.")
lift = st.sidebar.number_input("4. Beda Elevasi (m)", -50, 100, 10, help="Tinggi angkat vertikal.")
lump = st.sidebar.number_input("5. Max Lump Size (mm)", 0, 500, 50, help="Ukuran bongkahan terbesar yang mungkin lewat.")

trough = 35; sel_w = 800; sel_v = 2.0

if mode == "👤 Operasional (Auto)":
    st.sidebar.markdown("### ⚡ Quick Design")
    spd_opt = st.sidebar.select_slider("Target Operasi:", ["Slow (Awet)", "Normal", "Fast (High Cap)"], value="Normal")
    sel_v = 1.5 if spd_opt=="Slow (Awet)" else (2.2 if spd_opt=="Normal" else 3.0)
    
    if st.sidebar.button("✨ Cari Ukuran Ideal"):
        for w in [500,650,800,1000,1200,1400,1600,2000]:
            e = TitanEngine(mat_data, cap, w, sel_v, length, lift, 35, lump)
            g = e.calc_geometry()
            if g['load_pct'] <= 85 and g['lump_ok']:
                st.session_state['rec_w'] = w
                break
    sel_w = st.sidebar.selectbox("Lebar Belt (mm)", [500,650,800,1000,1200,1400,1600,2000], index=[500,650,800,1000,1200,1400,1600,2000].index(st.session_state.get('rec_w', 800)))
else:
    st.sidebar.markdown("### 🔧 Fine Tuning")
    trough = st.sidebar.radio("Idler Trough Angle", [20, 35, 45], index=1, horizontal=True)
    sel_w = st.sidebar.selectbox("Belt Width (mm)", [500,650,800,1000,1200,1400,1600,1800,2000], index=2)
    sel_v = st.sidebar.slider("Belt Speed (m/s)", 0.5, 6.0, 2.0, 0.1)

# --- EXECUTION ---
eng = TitanEngine(mat_data, cap, sel_w, sel_v, length, lift, trough, lump)
geo = eng.calc_geometry()
pwr = eng.calc_power_tension()
comp = eng.calc_components(pwr['T1'], pwr['Wm'], pwr['Wb'])
cons = eng.calc_construction_data(pwr['T1'], pwr['PIW'])

# --- DASHBOARD ---
st.markdown("<div class='main-header'>Belt Conveyor Calculation</div>", unsafe_allow_html=True)
st.markdown("<div class='sub-header'>Sistem Perhitungan Conveyor Terintegrasi (CEMA 6th Ed.) | Khusus Cangun PKG</div>", unsafe_allow_html=True)

# STATUS CHECK
fill = geo['load_pct']
if not geo['lump_ok']:
    st.markdown(f"<div class='status-danger'><h3>⛔ BLOCKAGE ALERT: LUMP SIZE!</h3><p>Bongkahan {lump}mm terlalu besar untuk belt {sel_w}mm. Max Allowed {int(geo['max_lump'])}mm.</p></div>", unsafe_allow_html=True)
elif fill > 100:
    st.markdown(f"<div class='status-danger'><h3>⛔ BAHAYA: OVERLOAD ({int(fill)}%)</h3><p>Material meluap! Kapasitas {cap} TPH tidak muat di belt ini.</p></div>", unsafe_allow_html=True)
elif fill > 85:
    st.markdown(f"<div class='status-warn'><h3>⚠️ WARNING: High Load ({int(fill)}%)</h3><p>Di atas standar aman industri (85%). Risiko tumpahan saat *surge*.</p></div>", unsafe_allow_html=True)
else:
    st.markdown(f"<div class='status-safe'><h3>✅ DESIGN OK ({int(fill)}%)</h3><p>Conveyor aman, efisien, dan memenuhi standar CEMA.</p></div>", unsafe_allow_html=True)

st.write("")

k1, k2, k3, k4, k5 = st.columns(5)
k1.markdown(f"<div class='kpi-card'><div class='kpi-val'>{pwr['kW']:.1f} kW</div><div class='kpi-lbl'>Power Absorbed</div></div>", unsafe_allow_html=True)
k2.markdown(f"<div class='kpi-card'><div class='kpi-val'>{int(pwr['T1'])} lbs</div><div class='kpi-lbl'>Max Tension</div></div>", unsafe_allow_html=True)
k3.markdown(f"<div class='kpi-card'><div class='kpi-val'>{int(pwr['PIW'])}</div><div class='kpi-lbl'>Belt Rating (PIW)</div></div>", unsafe_allow_html=True)
k4.markdown(f"<div class='kpi-card'><div class='kpi-val'>{comp['Series']}</div><div class='kpi-lbl'>Idler Class</div></div>", unsafe_allow_html=True)
k5.markdown(f"<div class='kpi-card'><div class='kpi-val'>{comp['RecPulley']} mm</div><div class='kpi-lbl'>Min Pulley</div></div>", unsafe_allow_html=True)

st.write("")

# --- PDF GENERATOR LOGIC ---
def create_pdf():
    pdf = EngineeringReport()
    pdf.add_page()
    
    # 1. Design Parameter
    pdf.section_title("1. DESIGN PARAMETERS")
    pdf.data_row("Material Name", sel_mat)
    pdf.data_row("Material Density", f"{mat_data['den']} lbs/ft3")
    pdf.data_row("Design Capacity", f"{cap} TPH")
    pdf.data_row("Belt Width", f"{sel_w} mm")
    pdf.data_row("Belt Speed", f"{sel_v} m/s")
    pdf.data_row("Conveyor Length", f"{length} m")
    pdf.data_row("Lift Height", f"{lift} m")
    
    # 2. Calculated Results
    pdf.ln(5)
    pdf.section_title("2. ENGINEERING RESULTS (CEMA)")
    pdf.data_row("Volumetric Loading", f"{int(geo['load_pct'])} %")
    pdf.data_row("Motor Power (Shaft)", f"{pwr['kW']:.2f} kW")
    pdf.data_row("Max Belt Tension (T1)", f"{int(pwr['T1'])} lbs")
    pdf.data_row("Belt PIW Rating", f"{int(pwr['PIW'])} PIW")
    pdf.data_row("Idler Load", f"{int(comp['Load'])} lbs")
    pdf.data_row("Drive Traction Ratio", f"{pwr['Ratio']:.2f}")
    
    # 3. BOM
    pdf.ln(5)
    pdf.section_title("3. BILL OF MATERIALS")
    pdf.data_row("Recommended Belt", f"EP-{int(pwr['PIW']*1.5)} / Grade {mat_data.get('desc','Gen')}")
    pdf.data_row("Idler Series", f"CEMA {comp['Series']} / {trough} deg")
    pdf.data_row("Head Pulley", f"Dia {comp['RecPulley']} mm / Rubber Lagged")
    pdf.data_row("Motor Spec", f"Cage Motor 4P / {pwr['kW']:.2f} kW")
    pdf.data_row("Chute Liner", mat_data['liner'])
    
    return pdf.output(dest='S').encode('latin-1', 'ignore')

# --- TABS ---
tabs = st.tabs(["📐 Cross-Section", "🚀 Trajectory & Chute", "🏗️ Layout & Sipil", "📈 Tension & Drive", "📋 BOM & Procurement", "📘 Dasar Teori"])

with tabs[0]:
    c1, c2 = st.columns([3, 1])
    with c1:
        fig, ax = plt.subplots(figsize=(10, 3.5))
        W_in = sel_w/25.4
        cr = geo['c_roll']; wr = (W_in - cr)/2; beta = math.radians(trough)
        p_belt = [(-cr/2 - wr*math.cos(beta), wr*math.sin(beta)), (-cr/2, 0), (cr/2, 0), (cr/2 + wr*math.cos(beta), wr*math.sin(beta))]
        ax.add_patch(Polygon(p_belt, closed=False, linewidth=5, edgecolor='#2c3e50', facecolor='none'))
        if fill > 0:
            scale = math.sqrt(min(fill, 120)/100)
            bw_viz = geo['bw_max'] * scale
            wf = max(0, (bw_viz/2 - cr/2))
            xr = (cr/2) + wf*math.cos(beta); yr = wf*math.sin(beta)
            xl = -xr; yp = yr + (xr * math.tan(math.radians(mat_data['sur'])))
            xc = np.linspace(xl, xr, 50); a = (yr - yp)/(xr**2) if xr>0 else 0; yc = a*xc**2 + yp
            col = '#2ecc71' if fill <= 85 else '#e74c3c'
            ax.add_patch(Polygon(list(zip(xc, yc)) + ([(xr, yr), (cr/2, 0), (-cr/2, 0), (xl, yr)] if wf>0 else [(xr, 0), (xl, 0)]), closed=True, facecolor=col, alpha=0.8))
            lump_r = lump/25.4/2
            lump_c = Circle((0, yr/2), lump_r, color='#9b59b6', alpha=0.6, label='Max Lump')
            ax.add_patch(lump_c)
        ax.set_xlim(-W_in/1.5, W_in/1.5); ax.set_ylim(-1, W_in/1.8); ax.set_aspect('equal'); ax.axis('off')
        st.pyplot(fig)
    with c2:
        st.info(f"**Analisis Dimensi:**\n\nLebar Belt: {sel_w} mm\nMaterial: {int(geo['bw_act']*25.4)} mm\nEdge Dist: {int(geo['edge_act']*25.4)} mm")
        if geo['lump_ok']: st.success(f"✅ Lump {lump}mm Aman")
        else: st.error(f"❌ Lump {lump}mm Besar!")

with tabs[1]:
    c1, c2 = st.columns([1, 3])
    with c1:
        st.markdown("#### Chute Parameters")
        p_dia = st.selectbox("Pulley Diameter (mm)", [315, 400, 500, 630, 800, 1000, 1250], index=3, help="Diameter Head Pulley (termasuk lagging).")
        with st.expander("⚙️ Custom Ukuran Chute"):
            chute_w = st.slider("Lebar Box (m)", 1.0, 3.0, 1.5)
            chute_h = st.slider("Dalam Box (m)", 1.0, 4.0, 2.5)
            hood_h = st.slider("Tinggi Hood (m)", 0.5, 1.5, 0.8)
        if p_dia < comp['RecPulley']: st.error(f"⚠️ Pulley < Min {comp['RecPulley']}mm. Risiko Fatig Belt.")
        st.success(f"**Liner Rekomendasi:**\n{mat_data['liner']}")
    with c2:
        xt, yt, rp, idx = eng.calc_trajectory(p_dia)
        fig, ax = plt.subplots(figsize=(8, 5)) 
        ax.add_patch(Circle((0, -rp), rp, color='#95a5a6', alpha=0.5))
        ax.plot([-2, 0], [-rp + rp, 0], 'k-', linewidth=4)
        ax.plot(xt, yt, 'b-', linewidth=2, alpha=0.6, label='Flow Stream')
        hood_x_start = -rp - 0.2; impact_wall_x = max(xt) + 0.5
        if impact_wall_x < chute_w: impact_wall_x = chute_w
        chute_points = [(hood_x_start, rp + hood_h), (impact_wall_x, rp + hood_h), (impact_wall_x, -chute_h), (impact_wall_x - chute_w, -chute_h), (hood_x_start, -rp)]
        ax.add_patch(Polygon(chute_points, closed=False, edgecolor='#e67e22', linewidth=3, facecolor='none', linestyle='--', label='Chute Box'))
        ax.plot([impact_wall_x, impact_wall_x], [rp, -chute_h], color='#d35400', linewidth=5, alpha=0.5, label='Impact Wall')
        ax.set_title(f"Trajectory Index: {idx:.2f} ({'High Speed/Tangent' if idx>=1 else 'Low Speed/Wrap'})")
        ax.grid(True, alpha=0.3); ax.legend(loc='upper left')
        ax.set_ylim(-chute_h - 0.5, rp + hood_h + 0.5); ax.set_xlim(-1.0, impact_wall_x + 1.0); ax.set_aspect('equal')
        st.pyplot(fig)

with tabs[2]:
    col_b1, col_b2 = st.columns(2)
    with col_b1:
        st.markdown(f"<div class='kpi-card'><div class='kpi-lbl'>Min. Jarak Transisi</div><div class='kpi-val'>{cons['TransDist']:.2f} m</div><small>Jarak dari Pulley ke Idler Trough pertama agar belt tidak sobek.</small></div>", unsafe_allow_html=True)
    with col_b2:
        st.markdown(f"<div class='kpi-card'><div class='kpi-lbl'>Min. Take-up Travel</div><div class='kpi-val'>{cons['TakeupTravel']:.2f} m</div><small>Tinggi area gerak pemberat (Counterweight) untuk kompensasi mulur belt.</small></div>", unsafe_allow_html=True)

with tabs[3]:
    fig, ax = plt.subplots(figsize=(8, 3))
    ax.plot([0, length], [pwr['T2'], pwr['T1']], 'r-o', linewidth=2)
    ax.fill_between([0, length], [pwr['T2'], pwr['T1']], alpha=0.1, color='red')
    ax.set_ylabel("Tension (lbs)"); ax.set_xlabel("Conveyor Length (m)")
    ax.set_title("Profil Tegangan Belt")
    st.pyplot(fig)
    if pwr['Slip']: st.error(f"⛔ **DRIVE SLIP!** Ratio {pwr['Ratio']:.2f} > 3.0. Tambahkan berat Counterweight.")
    else: st.success(f"✅ **Traction Aman.** Ratio {pwr['Ratio']:.2f} < 3.0.")
    st.info(f"**Vertical Curve:** Gunakan Radius cekungan min {comp['Curve']:.1f} meter.")

with tabs[4]:
    st.markdown("### 📋 Procurement Spec (BOM)")
    df_bom = pd.DataFrame([
        ["Conveyor Belt", f"EP-{int(pwr['PIW']*1.5/10)*10} Grade {mat_data.get('desc', 'Gen')}", f"{sel_w} mm", f"{int(length*2.1)} m"],
        ["Motor Drive", f"Cage Motor 4-Pole / IE3", f"{pwr['kW']:.2f} kW", "1 Unit"],
        ["Idler Sets", f"CEMA Series {comp['Series']}, {trough}°", f"{int(pwr['Wb']+pwr['Wm'])} lbs load", f"{int(length)} Sets"],
        ["Head Pulley", f"Rubber Lagged Diamond 60 Shore A", f"Dia {p_dia} mm", "1 Unit"],
        ["Chute Liner", f"{mat_data['liner']}", "Thk 10-12mm", "1 Lot"]
    ], columns=["Item", "Deskripsi", "Spec/Rating", "Qty"])
    st.table(df_bom)
    
    # PDF DOWNLOAD BUTTON
    st.markdown("---")
    st.write("**Download Report Resmi:**")
    pdf_bytes = create_pdf()
    st.download_button(label="📄 Download Datasheet (PDF)", data=pdf_bytes, file_name="PetroStream_Report.pdf", mime="application/pdf")

with tabs[5]:
    st.markdown("### 📘 Dasar Teori (CEMA 6th Ed)")
    st.markdown("<div class='theory-box'><h4>1. Kapasitas ($A_s$)</h4><p>Luas penampang material di atas belt (Trapesium + Surcharge).</p></div>", unsafe_allow_html=True)
    st.latex(r"TPH = \frac{60 \times A_s \times V \times \gamma}{2000}")
    st.markdown("<div class='theory-box'><h4>2. Tegangan Efektif ($T_e$)</h4><p>Gaya tarik total untuk melawan gesekan dan gravitasi.</p></div>", unsafe_allow_html=True)
    st.latex(r"T_e = L \cdot K_t (K_x + K_y W_b + 0.015 W_b) + W_m (L K_y + H) + T_{ac}")
    st.markdown("<div class='theory-box'><h4>3. Slip Check (Euler)</h4><p>Memastikan belt tidak selip di pulley penggerak.</p></div>", unsafe_allow_html=True)
    st.latex(r"\frac{T_1}{T_2} \le e^{\mu \theta}")

st.markdown("---")
st.caption("PetroStream™ v17.0 | Developed for PT Petrokimia Gresik | CEMA Standard")
