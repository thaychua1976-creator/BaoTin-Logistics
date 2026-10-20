import streamlit as st
import os

# 1. ĐẶT CẤU HÌNH TRANG LÊN TRÊN CÙNG
st.set_page_config(
    page_title="BẢO TÍN LOGISTICS", 
    page_icon="🚚", 
    layout="wide",
    initial_sidebar_state="auto"
)

import header
import footer
import app

# ==========================================
# CÁC HÀM RENDER TRANG PUBLIC MARKETING
# ==========================================
def show_home():
    header.render_header("home")

    st.markdown("""
    <style>
    .stat-box { 
        background: white; 
        padding: 20px 10px; 
        border-radius: 12px; 
        border: 1px solid #e2e8f0; 
        text-align: center; 
        box-shadow: 0 2px 5px rgba(0,0,0,0.02); 
        margin-bottom: 15px; 
        transition: transform 0.2s;
    }
    .stat-box:hover { transform: translateY(-3px); border-color: #0B2E9E; }
    </style>
    """, unsafe_allow_html=True)

    col_left, col_right = st.columns([1.3, 1], gap="large")

    with col_left:
        st.markdown("""
        <div style="background-color: white; padding: 30px; border-radius: 16px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); border-left: 5px solid #FF6B00; margin-bottom: 15px;">
            <div style="color: #0B2E9E; font-size: 55px; font-weight: 900; margin-bottom: 10px; line-height: 1.3;"><b> Chuyên Tuyến Nhà Máy → Sân Bay, Cảng, ICD</b> </div>
            <div style="color: #FF6B00; font-size: 18px; font-weight: bold; margin-bottom: 15px;">Lợi Thế Vận Tải Quốc Tế Việt Nam - Cambodia</div>
            <div style="color: #475569; font-size: 18px; line-height: 1.6; margin-bottom: 20px;">
                Chủ lực vận chuyển từ nhà máy đi <b>Sân bay Tân Sơn Nhất / Long Thành </b>,<b>Cảng Cát Lái / Cái Mép </b>,<b> các ICD </b>. 
                Khai báo hải quan trọn gói. Đội xe <b>1T-15T </b> + Container sẵn sàng 24/7 qua <b>Mộc Bài, Xa Mát </b>.
            </div>
        </div>
        """, unsafe_allow_html=True)   
        
        st.markdown("""
        <div style="display: flex; gap: 10px; margin-bottom: 25px; flex-wrap: wrap;">
            <div style="flex: 1; min-width: 120px; background-color: #0B2E9E; color: white; padding: 10px 8px; border-radius: 8px; text-align: center; font-weight: bold; font-size: 15px; box-shadow: 0 2px 5px rgba(0,0,0,0.1);">📞 0888 039 888</div>
            <div style="flex: 1; min-width: 120px; background-color: #ffffff; color: #0B2E9E; padding: 10px 8px; border-radius: 8px; text-align: center; font-weight: bold; font-size: 15px; border: 2px solid #0B2E9E; box-shadow: 0 2px 5px rgba(0,0,0,0.05);">📞 0988 039 888</div>
            <div style="flex: 1; min-width: 130px; background-color: #FF6B00; color: white; padding: 10px 8px; border-radius: 8px; text-align: center; font-weight: bold; font-size: 14px; box-shadow: 0 2px 5px rgba(0,0,0,0.1);">✉️ bao@truckingbaotin.com</div>
        </div>
        """, unsafe_allow_html=True) 

        stat_col1, stat_col2 = st.columns(2)
        with stat_col1:
            st.markdown("""
            <div class="stat-box">
                <div style="color: #FF6B00; font-size: 20px; font-weight: 900;">10+ Năm</div>
                <div style="color: #475569; font-size: 14px; font-weight: 600;">Kinh nghiệm</div>
            </div>
            <div class="stat-box">
                <div style="color: #FF6B00; font-size: 20px; font-weight: 900;">63 Tỉnh + Cambodia</div>
                <div style="color: #475569; font-size: 14px; font-weight: 600;">Mạng lưới</div>
            </div>
            """, unsafe_allow_html=True)
        with stat_col2:
            st.markdown("""
            <div class="stat-box">
                <div style="color: #FF6B00; font-size: 20px; font-weight: 900;">50+ Xe</div>
                <div style="color: #475569; font-size: 14px; font-weight: 600;">Đầu xe sẵn sàng</div>
            </div>
            <div class="stat-box">
                <div style="color: #FF6B00; font-size: 20px; font-weight: 900;">2000+ KH</div>
                <div style="color: #475569; font-size: 14px; font-weight: 600;">Nhà máy, KCN</div>
            </div>
            """, unsafe_allow_html=True)

    with col_right:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        image_path = os.path.join(current_dir, "image", "vpdd_bao_tin.jfif")

        if os.path.exists(image_path):
            st.image(image_path, use_container_width=True)
        else:
            st.error(f"Đang bảo trì hình ảnh. Lỗi đường dẫn: không tìm thấy {image_path}")
            
        st.markdown("""
        <div style="display: flex; gap: 10px; margin-top: 15px;">
            <div style="flex: 1; background-color: #0B2E9E; color: white; padding: 12px 8px; border-radius: 10px; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                <div style="font-size: 16px; font-weight: 900; margin-bottom: 2px;">🕒24/7</div>
                <div style="font-size: 12px; opacity: 0.9;">Điều xe xuyên đêm</div>
            </div>
            <div style="flex: 1; background-color: #ffffff; color: #0B2E9E; padding: 12px 8px; border-radius: 10px; text-align: center; border: 2px solid #0B2E9E; box-shadow: 0 4px 6px rgba(0,0,0,0.05);">
                <div style="font-size: 16px; font-weight: 900; margin-bottom: 2px;">🛡️Bảo hiểm</div>
                <div style="font-size: 12px; color: #475569; font-weight: 600;">100% giá trị</div>
            </div>
            <div style="flex: 1; background-color: #FF6B00; color: white; padding: 12px 8px; border-radius: 10px; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                <div style="font-size: 14px; font-weight: 900; margin-bottom: 2px;">Mộc Bài - Xa Mát</div>
                <div style="font-size: 12px; opacity: 0.9;">Thông quan nhanh</div>
            </div>
        </div>    
        """, unsafe_allow_html=True)

    footer.render_footer()

def show_dich_vu():
    import dich_vu
    dich_vu.show_page()

def show_doi_xe():
    import doi_xe_homepage
    doi_xe_homepage.show_page()

def show_tuyen_cambodia():
    import tuyen_cambodia
    tuyen_cambodia.show_page()

def show_lien_he():
    import lien_he
    lien_he.show_page()


# ==========================================
# CẤU HÌNH BỘ ĐỊNH TUYẾN (ROUTER)
# ==========================================
url_page = st.query_params.get("page", None)

# 1. Khai báo các trang Public
page_home = st.Page(show_home, title="Trang chủ", icon="🏠", default=True)
page_dich_vu = st.Page(show_dich_vu, title="Dịch vụ", icon="🚛", url_path="dich_vu")
page_doi_xe = st.Page(show_doi_xe, title="Đội xe", icon="🚚", url_path="doi_xe")
page_tuyen_cam = st.Page(show_tuyen_cambodia, title="Tuyến Cambodia", icon="🇰🇭", url_path="tuyen_cambodia")
page_lien_he = st.Page(show_lien_he, title="Liên hệ", icon="📞", url_path="lien_he")

# 2. Phân luồng thực thi chuẩn xác
if st.session_state.get('logged_in', False):
    # NẾU ĐÃ ĐĂNG NHẬP ERP: Nhường toàn bộ quyền điều hướng cho app.py
    app.show_page()
else:
    # NẾU CHƯA ĐĂNG NHẬP:
    # Khai báo tất cả đường dẫn ERP nội bộ để hứng các liên kết mở ở New Tab
    erp_urls = [
        "app", "quan-ly-chuyen-di", "quyet-toan-chuyen-di", "thong-ke-luong", 
        "quan-ly-nhan-vien", "quan-ly-khach-hang", "khai-bao-hai-quan", 
        "quan-ly-co", "quan-ly-doi-xe", "quan-ly-phap-ly-xe", 
        "quan-ly-tai-khoan", "doi-mat-khau", "ket-qua-kinh-doanh", 
        "cap-nhat-lich-trinh", "lay-thong-tin-tu-zalo", "thiet-lap-bang-gia", 
        "thiet-lap-phu-cap", "thiet-lap-gia-hq", "quan-ly-nhien-lieu", "backup-database"
    ]
    
    if url_page in ["dich_vu", "doi_xe", "tuyen_cambodia", "lien_he"]:
        # Người dùng click cụ thể các menu Public trên Navbar
        pg = st.navigation([page_home, page_dich_vu, page_doi_xe, page_tuyen_cam, page_lien_he], position="hidden")
        pg.run()
    else:
        # Tải bộ định tuyến tổng thể (Public + ERP URLs):
        # - Mở trang gốc "/" -> Tự động chạy page_home (Trang chủ Marketing)
        # - Mở link New Tab "/quan-ly-co" -> Tự động chạy app.show_page (Form Đăng nhập ERP trực tiếp tại URL đó)
        erp_phantom_pages = []
        for u in erp_urls:
            erp_phantom_pages.append(st.Page(app.show_page, title="Điều hành nội bộ", url_path=u))
            
        pg = st.navigation([page_home, page_dich_vu, page_doi_xe, page_tuyen_cam, page_lien_he] + erp_phantom_pages, position="hidden")
        pg.run()