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
    img_tag = f'<img src="data:image/jpeg;base64,{logo_b64}" class="logo-img">' if logo_b64 else '<div class="logo-placeholder">🚚</div>'

    header_html = f"""
    <style>
    html, body, [class*="css"], .stApp, p, span, div, label, input, button {{
        font-family: "Times New Roman", Times, serif !important;
    }}
    
    .stApp {{ background-color: #f8fafc; }}
    
    .block-container {{
        max-width: 100% !important;
        padding-top: 0rem !important;
        padding-bottom: 1rem !important;
        padding-left: 2.5rem !important;
        padding-right: 2.5rem !important;
    }}
    
    .main-header-wrapper {{
        background-color: #0B2E9E;
        padding: 12px 15px;
        margin-top: 15px;
        margin-left: -2.5rem !important;
        margin-right: -2.5rem !important;
        width: calc(100% + 5rem) !important;
        box-sizing: border-box;
        display: flex;
        align-items: center;
        flex-wrap: wrap; 
        gap: 15px;
    }}

    .brand-group {{ 
        display: flex; 
        align-items: center; 
        gap: 12px; 
        min-width: max-content;
    }}
    .logo-img {{ width: 50px; height: 50px; border-radius: 8px; object-fit: cover; border: 1px solid rgba(255,255,255,0.2); }}
    .logo-placeholder {{ width: 50px; height: 50px; background: #ddd; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 24px; }}
    .brand-text {{ display: flex; flex-direction: column; line-height: 1.2; }}
    .brand-title {{ color: #ffffff; font-size: 16px; font-weight: 900; letter-spacing: 1px; margin: 0; }}
    .brand-sub {{ color: #FF6B00; font-size: 12px; font-weight: bold; margin: 0; }}

    .nav-links-group {{ 
        display: flex; 
        gap: 10px; 
        flex: 1; 
        justify-content: flex-end; 
        overflow-x: auto; 
        -webkit-overflow-scrolling: touch; 
        white-space: nowrap; 
        padding-bottom: 5px; 
    }}
    .nav-links-group::-webkit-scrollbar {{ display: none; }}

    .nav-item {{
        font-size: 15px;
        font-weight: 600;
        color: #ffffff !important; 
        text-decoration: none !important;
        padding: 8px 12px;
        border-radius: 6px;
        background-color: rgba(255, 255, 255, 0.05);
        transition: 0.2s;
    }}
    .nav-item:hover, .nav-item.active {{
        background-color: rgba(255, 255, 255, 0.25);
    }}

    .bottom-bar-3d {{
        background: linear-gradient(180deg, #1342c4 0%, #0B2E9E 50%, #061c63 100%); 
        color: white; text-align: center; padding: 8px 10px; font-size: 13px; font-weight: bold; 
        letter-spacing: 1px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); border-bottom: 2px solid #FF6B00; 
        margin-bottom: 15px; margin-left: -2.5rem !important; margin-right: -2.5rem !important;
        width: calc(100% + 5rem) !important; box-sizing: border-box;
    }}

    @media (max-width: 900px) {{
        .main-header-wrapper {{ 
            flex-direction: column; 
            align-items: flex-start;
            padding: 15px;
        }}
        .nav-links-group {{ 
            width: 100%; 
            justify-content: flex-start; 
        }}
    }}
    </style>

    <div class="main-header-wrapper">
        <div class="brand-group">
            {img_tag}
            <div class="brand-text">
                <p class="brand-title">BẢO TÍN LOGISTICS</p>
                <p class="brand-sub">TRUCKINGBAOTIN.COM</p>
            </div>
        </div>
        <div class="nav-links-group">
            <a href="?page=home" target="_self" class="nav-item {'active' if current_page == 'home' else ''}">Trang chủ</a>
            <a href="?page=dich_vu" target="_self" class="nav-item {'active' if current_page == 'dich_vu' else ''}">Dịch vụ</a>
            <a href="?page=doi_xe" target="_self" class="nav-item {'active' if current_page == 'doi_xe' else ''}">Đội xe</a>
            <a href="?page=tuyen_cambodia" target="_self" class="nav-item {'active' if current_page == 'tuyen_cambodia' else ''}">Tuyến Cambodia</a>
            <a href="?page=lien_he" target="_self" class="nav-item {'active' if current_page == 'lien_he' else ''}">Liên hệ</a>
            <a href="?page=app" target="_self" class="nav-item {'active' if current_page == 'app' else ''}">Điều hành nội bộ</a>
        </div>
    </div>

    <div class="bottom-bar-3d">
        VPDD CÔNG TY TNHH BẢO TÍN LOGISTICS | 宝信物流公司 | We truck your trust
    </div>
    """
    
    st.markdown(header_html, unsafe_allow_html=True)