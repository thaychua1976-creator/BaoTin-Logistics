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

/* Bỏ lệnh ẩn Header của Streamlit ở trang chủ để tránh lỗi liên đới */
header[data-testid="stHeader"] {{ 
    background-color: transparent !important; 
    box-shadow: none !important;
}}
[data-testid="collapsedControl"] {{
    display: none !important; 
}}

/* CẤU TRÚC LẠI THANH NAVBAR CHÍNH */
.navbar-container {{
    display: flex;
    align-items: center;
    background-color: #0B2E9E;
    padding: 12px 15px; /* Giảm padding để tối ưu Mobile */
    margin-top: 15px;
    margin-left: -2.5rem !important;
    margin-right: -2.5rem !important;
    width: calc(100% + 5rem) !important;
    box-sizing: border-box;
    border-radius: 0px !important;
    flex-wrap: wrap; /* Cho phép các nhóm phần tử tự động rớt dòng nếu thiếu chỗ */
    gap: 15px;
}}

.brand-group {{ 
    display: flex; 
    align-items: center; 
    gap: 12px; 
    text-align: left; 
    min-width: max-content;
}}

/* TỐI ƯU MENU CHO MOBILE (CHO PHÉP VUỐT NGANG) */
.nav-links-group {{ 
    display: flex; 
    gap: 12px; 
    align-items: center;
    flex: 1; /* Chiếm hết khoảng trống còn lại */
    justify-content: flex-end;
    overflow-x: auto; /* BẬT TÍNH NĂNG VUỐT NGANG TRÊN ĐIỆN THOẠI */
    -webkit-overflow-scrolling: touch; /* Trải nghiệm vuốt mượt mà trên iOS */
    white-space: nowrap; /* Không bao giờ cho các nút rớt dòng đè lên nhau */
    padding-bottom: 5px; /* Tránh cấn thanh cuộn hệ điều hành */
}}

/* Ẩn thanh cuộn vật lý đi cho đẹp */
.nav-links-group::-webkit-scrollbar {{ display: none; }}

/* LÀM TO NÚT BẤM ĐỂ DỄ CHẠM */
.nav-item {{
    font-size: 15px;
    font-weight: 600;
    transition: background-color 0.2s;
    color: #ffffff !important; 
    background-color: rgba(255, 255, 255, 0.05); /* Tạo viền nút mờ mờ */
    padding: 8px 15px;
    border-radius: 6px;
}}

.nav-item:hover, .nav-item.active {{
    background-color: rgba(255, 255, 255, 0.25);
}}

.bottom-bar-3d {{
    background: linear-gradient(180deg, #1342c4 0%, #0B2E9E 50%, #061c63 100%); 
    color: white; 
    text-align: center; 
    padding: 8px 15px; 
    font-size: 13px; 
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

/* --- ĐIỀU CHỈNH RIÊNG CHO MÀN HÌNH ĐIỆN THOẠI (< 900px) --- */
@media (max-width: 900px) {{
    .navbar-container {{ 
        flex-direction: column; /* Đẩy Logo lên trên, Menu xuống dưới */
        align-items: flex-start; /* Canh trái toàn bộ */
    }}
    .nav-links-group {{ 
        width: 100%; 
        justify-content: flex-start; /* Ép các nút sát lề trái để dễ dàng vuốt sang phải */
    }}
}}
</style>

<div class="navbar-container">
    <div class="brand-group">
        {f'<img src="data:image/jpeg;base64,{logo_b64}" style="width: 50px; height: 50px; border-radius: 8px; object-fit: cover; border: 1px solid rgba(255,255,255,0.2);">' if logo_b64 else '<div style="width:50px;height:50px;background:#ddd;border-radius:8px;"></div>'}
        <div style="line-height: 1.2;">
            <span style="color: #ffffff; font-size: 17px; font-weight: 900; display: block; letter-spacing: 1px;">BẢO TÍN LOGISTICS</span>
            <span style="color: #FF6B00; font-size: 13px; font-weight: bold;">TRUCKINGBAOTIN.COM</span>
        </div>
    </div>
    <div class="nav-links-group">
        <a href="?page=home" target="_self" class="nav-item {'active' if current_page == 'home' else ''}">Trang chủ</a>
        <a href="?page=dich_vu" target="_self" class="nav-item {'active' if current_page == 'dich_vu' else ''}">Dịch vụ</a>
        <a href="?page=doi_xe" target="_self" class="nav-item {'active' if current_page == 'doi_xe' else ''}">Đội xe</a>
        <a href="?page=tuyen_cambodia" target="_self" class="nav-item {'active' if current_page == 'tuyen_cambodia' else ''}">Tuyến Cambodia</a>
        <a href="?page=lien_he" target="_self" class="nav-item {'active' if current_page == 'lien_he' else ''}">Liên hệ</a>
        <a href="?page=app" target="_blank" class="nav-item {'active' if current_page == 'app' else ''}">Điều hành nội bộ</a>
    </div>
</div>

<div class="bottom-bar-3d">
    VPDD CÔNG TY TNHH BẢO TÍN LOGISTICS | 宝信物流公司 | We truck your trust
</div>
"""
    st.markdown(header_html, unsafe_allow_html=True)