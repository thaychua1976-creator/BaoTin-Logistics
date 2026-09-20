import streamlit as st
import os
import base64

def render_header(current_page="home"):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    image_dir = os.path.join(current_dir, "image")
    logo_path = os.path.join(image_dir, "logo_baotin.jfif")

    def get_base64_image(path):
        if os.path.exists(path):
            with open(path, "rb") as f:
                return base64.b64encode(f.read()).decode()
        return None
        
    logo_b64 = get_base64_image(logo_path)

    header_html = f"""
<style>
html, body, [class*="css"], .stApp, p, span, div, label, input, button {{
    font-family: "Times New Roman", Times, serif !important;
}}

.nav-item, a, a:link, a:visited, a:hover, a:active {{
    text-decoration: none !important;
    border-bottom: none !important;
}}

.stApp {{ background-color: #f8fafc; }}

.block-container {{
    max-width: 100% !important;
    padding-top: 0rem !important;
    padding-bottom: 1rem !important;
    padding-left: 2.5rem !important;
    padding-right: 2.5rem !important;
}}

header {{ visibility: hidden; }}

.navbar-container {{
    display: flex;
    align-items: center;
    background-color: #0B2E9E;
    padding: 15px 40px;
    margin-top: 15px;
    margin-left: -2.5rem !important;
    margin-right: -2.5rem !important;
    width: calc(100% + 5rem) !important;
    box-sizing: border-box;
    border-radius: 0px !important;
    position: relative;
}}

.brand-group {{ 
    display: flex; 
    align-items: center; 
    gap: 15px; 
    text-align: left; 
    z-index: 10; 
}}

.nav-links-group {{ 
    display: flex; 
    gap: 30px; 
    align-items: center;
    position: absolute;
    left: 50%;
    transform: translateX(-50%);
}}

.nav-item {{
    font-size: 16px;
    font-weight: 600;
    transition: opacity 0.2s;
    color: #ffffff !important; 
}}

.nav-item:hover {{
    opacity: 0.7;
}}

.bottom-bar-3d {{
    background: linear-gradient(180deg, #1342c4 0%, #0B2E9E 50%, #061c63 100%); 
    color: white; 
    text-align: center; 
    padding: 8px 15px; 
    font-size: 14px; 
    font-weight: bold; 
    letter-spacing: 1px; 
    box-shadow: 0 4px 6px rgba(0,0,0,0.3); 
    border-bottom: 2px solid #FF6B00; 
    margin-bottom: 15px; 
    margin-left: -2.5rem !important;
    margin-right: -2.5rem !important;
    width: calc(100% + 5rem) !important;
    box-sizing: border-box;
}}

@media (max-width: 1050px) {{
    .navbar-container {{ justify-content: space-between; }}
    .nav-links-group {{ position: static; transform: none; }}
}}
</style>

<div class="navbar-container">
<div class="brand-group">
{f'<img src="data:image/jpeg;base64,{logo_b64}" style="width: 50px; height: 50px; border-radius: 8px; object-fit: cover; border: 1px solid rgba(255,255,255,0.2);">' if logo_b64 else '<div style="width:50px;height:50px;background:#ddd;border-radius:8px;"></div>'}
<div style="line-height: 1.2;">
<span style="color: #ffffff; font-size: 20px; font-weight: 900; display: block; letter-spacing: 1px;">BẢO TÍN LOGISTICS</span>
<span style="color: #FF6B00; font-size: 14px; font-weight: bold;">TRUCKINGBAOTIN.COM</span>
</div>
</div>
<div class="nav-links-group">
<a href="?page=home" target="_self" class="nav-item">Trang chủ</a>
<a href="?page=dich_vu" target="_self" class="nav-item">Dịch vụ</a>
<a href="?page=doi_xe" target="_self" class="nav-item">Đội xe</a>
<a href="?page=tuyen_cambodia" target="_self" class="nav-item">Tuyến Cambodia</a>
<a href="?page=lien_he" target="_self" class="nav-item">Liên hệ</a>
<a href="?page=app" target="_blank" class="nav-item">Điều hành nội bộ</a>
</div>
</div>

<div class="bottom-bar-3d">
VPDD CÔNG TY TNHH BẢO TÍN LOGISTICS | 宝信物流公司 | We truck your trust
</div>
"""
    st.markdown(header_html, unsafe_allow_html=True)