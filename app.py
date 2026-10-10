import streamlit as st
import sys, time
import pandas as pd
import bcrypt

def show_page():
    # 1. Cấu hình giao diện chuẩn cho Desktop & Mobile
    st.set_page_config(layout="wide", initial_sidebar_state="auto")
    
    with st.spinner("🔄 Đang tải chương trình và đồng bộ dữ liệu hệ thống, vui lòng đợi..."):
        time.sleep(0.3) 

    # 2. CSS TẠO THANH APP-BAR ĐỈNH CAO CHUẨN MOBILE APP
    st.markdown("""
        <style>
            /* Đẩy nội dung xuống dưới để không bị Thanh App-Bar đè lên */
            .block-container {
                padding-top: 4.5rem !important; 
                padding-bottom: 1rem !important;
                padding-left: 1rem !important;
                padding-right: 1rem !important;
                max-width: 98% !important;
            }
            
            /* ========================================================= */
            /* 🚀 1. TẠO THANH MENU NGANG TRÊN CÙNG (APP-BAR)            */
            /* ========================================================= */
            header[data-testid="stHeader"] {
                display: flex !important;
                background-color: #0B2E9E !important; /* Đổ màu Xanh đậm ERP cho thanh Menu */
                z-index: 9999999 !important; /* Ép nổi lên trên mọi trang con */
                border-bottom: 3px solid #FF6B00 !important; /* Viền Cam chân thanh Menu */
                height: 3.5rem !important; /* Chiều cao cố định chuẩn Mobile */
                width: 100% !important;
            }
            
            /* 🚀 2. CHÈN TÊN PHẦN MỀM VÀO THANH MENU */
            header[data-testid="stHeader"]::after {
                content: "ERP BẢO TÍN";
                position: absolute;
                left: 55px; /* Đẩy sang phải để nhường chỗ cho nút 3 gạch */
                top: 50%;
                transform: translateY(-50%); /* Canh giữa hoàn hảo theo chiều dọc */
                color: white;
                font-weight: 800;
                font-size: 18px;
                letter-spacing: 1px;
            }
            
            /* 🚀 3. HIỆN NÚT 3 GẠCH NẰM BÊN TRONG THANH MENU */
            header[data-testid="stHeader"] button {
                display: inline-flex !important;
                visibility: visible !important;
                opacity: 1 !important;
                background: transparent !important; 
                border: none !important;
                margin-top: auto !important;
                margin-bottom: auto !important;
            }
            
            /* Đổi màu biểu tượng 3 gạch thành Trắng để nổi trên nền Xanh */
            header[data-testid="stHeader"] svg {
                fill: white !important; 
                color: white !important;
                width: 1.8rem !important; /* Phóng to nút 3 gạch ra một xíu cho dễ bấm */
                height: 1.8rem !important;
            }
            
            /* ========================================================= */
            /* CSS GỐC CỦA THANH ĐIỀU HƯỚNG BÊN TRÁI (SIDEBAR)           */
            /* ========================================================= */
            section[data-testid="stSidebar"] {
                background-color: #f8fafc !important; 
                border-right: 2px solid #e2e8f0 !important;
            }
            [data-testid="stSidebarNav"] ul li div {
                font-size: 16px !important; font-weight: 800 !important;
                color: #0b5394 !important; text-transform: uppercase !important;
                padding-bottom: 5px; margin-top: 5px !important; 
                border-bottom: 2px solid #cbd5e1;
            }
            [data-testid="stSidebarNav"] > ul > li:nth-child(2) > div {
                color: #d32f2f !important; font-size: 17px !important;
                border-bottom: 2px solid #d32f2f !important;
                padding-bottom: 8px !important; margin-top: 15px !important; 
            }
            [data-testid="stSidebarNav"] ul li ul li {
                margin-left: 25px !important; border-left: 2px solid #e2e8f0;
            }
            [data-testid="stSidebarNav"] ul li ul li a span {
                font-size: 16px !important; font-weight: 600 !important;  
                color: #334155 !important; text-transform: none !important; border-bottom: none !important;
            }
            [data-testid="stSidebarNav"] ul li ul li:hover {
                background-color: #e2e8f0 !important; border-left: 3px solid #0b5394 !important; border-radius: 0 6px 6px 0;
            }
            [data-testid="stSidebarNav"] ul li ul li[data-checked="true"] {
                background-color: #dbeafe !important; border-left: 3px solid #0b5394 !important;
            }
            [data-testid="stSidebarNav"] ul li ul li[data-checked="true"] a span {
                color: #0b5394 !important; font-weight: 800 !important;
            }
            
            /* CHỈ ẨN CÁI ICON ĐANG CHẠY VÀ FOOTER (KHÔNG ẨN TOOLBAR TRÁNH LỖI MẠNG) */
            [data-testid="stStatusWidget"], footer {
                display: none !important;
                visibility: hidden !important;
            }
            div[data-testid="InputInstructions"] { display: none !important; }
            section[data-testid="stSidebar"] .stButton button {
                width: 100%; font-size: 15px !important; font-weight: bold !important; border-radius: 6px !important;
            }
        </style>
    """, unsafe_allow_html=True)

    # 3. Khởi tạo DB
    if 'db_config' in sys.modules: del sys.modules['db_config']
    @st.cache_resource
    def init_database_pool():
        from db_config import Database
        return Database()
    db = init_database_pool()
    st.session_state['db'] = db

    # 4. Trạng thái Đăng nhập
    if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
    if 'hien_mat_khau' not in st.session_state: st.session_state['hien_mat_khau'] = False

    def toggle_password(): st.session_state['hien_mat_khau'] = not st.session_state['hien_mat_khau']

    # 5. Giao diện Đăng nhập
    def login_ui():
        st.markdown("<h3 style='text-align: center; color: #0B2E9E;'>🔐 ĐĂNG NHẬP HỆ THỐNG ERP</h3>", unsafe_allow_html=True)
        col_l1, col_l2, col_l3 = st.columns([1, 1, 1])
        with col_l2:
            def trigger_login(): st.session_state['do_login'] = True
            username = st.text_input("Tên đăng nhập", autocomplete="off")
            
            col_pw, col_eye = st.columns([9, 2], vertical_alignment="bottom")
            with col_pw:
                if not st.session_state['hien_mat_khau']:
                    st.markdown("""<style>input[aria-label="Mật khẩu"] {-webkit-text-security: disc !important;}</style>""", unsafe_allow_html=True)
                password = st.text_input("Mật khẩu", autocomplete="off", on_change=trigger_login)
            with col_eye:
                icon = "👁️‍🗨️" if st.session_state['hien_mat_khau'] else "👁️"
                st.button(icon, on_click=toggle_password, use_container_width=True)
                
            st.markdown("<br>", unsafe_allow_html=True)
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1: submit = st.button("Đăng Nhập", type="primary", use_container_width=True)
            with col_btn2:
                if st.button("⬅️ Trở về trang chủ", use_container_width=True):
                    st.session_state['in_erp'] = False
                    st.query_params["page"] = "home"
                    st.rerun()
                    
            if submit or st.session_state.get('do_login', False):
                st.session_state['do_login'] = False
                with st.spinner("⏳ Đang xác minh..."):
                    time.sleep(1) 
                    username_clean = username.strip()
                    try:
                        sql = "SELECT id, role, password, nhan_vien_id, ho_ten FROM users WHERE username = %s"
                        result = db.execute_query(sql, (username_clean,))
                        
                        if isinstance(result, str): st.error(f"❌ Lỗi truy vấn Database: {result}")
                        elif isinstance(result, pd.DataFrame) and not result.empty:
                            hashed_password_db = result.iloc[0]['password']
                            try:
                                is_correct = bcrypt.checkpw(password.encode('utf-8'), hashed_password_db.encode('utf-8'))
                            except ValueError:
                                is_correct = False
                                
                            if is_correct:
                                st.session_state['logged_in'] = True
                                st.session_state['username'] = username_clean
                                st.session_state['role'] = result.iloc[0]['role']
                                st.session_state['nhan_vien_id'] = result.iloc[0]['nhan_vien_id'] 
                                st.session_state['ho_ten'] = result.iloc[0]['ho_ten']
                                st.success("✅ Đăng nhập thành công! Đang chuyển hướng...") 
                                time.sleep(0.5)
                                st.rerun() 
                            else: st.error("❌ Sai mật khẩu!")
                        else: st.error("❌ Tài khoản không tồn tại!")
                    except Exception as e: st.error(f"❌ Lỗi xác thực: {e}")

    # 6. Khởi tạo danh sách các trang
    page_login = st.Page(login_ui, title="Đăng nhập", icon="🔐", url_path="dang-nhap")
    page_chuyen_di = st.Page("views/chuyen_di.py", title="Quản lý Chuyến đi", icon="📝", url_path="quan-ly-chuyen-di")
    page_quyet_toan = st.Page("views/quyet_toan.py", title="Quyết toán chuyến đi", icon="📝", url_path="quyet-toan-chuyen-di")
    page_bao_cao   = st.Page("views/bao_cao.py", title="Thông kê lương & Công Nợ KH", icon="📊", url_path="thong-ke-luong")
    page_nhan_vien = st.Page("views/nhan_vien.py", title="Quản lý Nhân viên", icon="🧑‍✈️", url_path="quan-ly-nhan-vien")
    page_khach_hang = st.Page("views/khach_hang.py", title="Quản lý Khách hàng", icon="🧑", url_path="quan-ly-khach-hang")
    page_to_khai_hq = st.Page("views/khai_bao_hq.py", title="Khai báo Hải Quan", icon="🧑‍✈️", url_path="khai-bao-hai-quan")
    page_quan_ly_co = st.Page("views/quan_ly_co.py", title="Quản lý CO", icon="🧑‍✈️", url_path="quan-ly-co")
    page_doi_xe    = st.Page("views/doi_xe.py", title="Quản lý Đội xe", icon="🚛", url_path="quan-ly-doi-xe")
    page_phap_ly_xe    = st.Page("views/phap_ly_xe.py", title="Quản lý pháp lý xe", icon="🚛", url_path="quan-ly-phap-ly-xe")
    page_tai_khoan = st.Page("views/tai_khoan.py", title="Quản lý tài khoản user", icon="👤", url_path="quan-ly-tai-khoan")
    page_doi_mat_khau = st.Page("views/doi_mat_khau.py", title="Đổi mật khẩu", icon="🔑", url_path="doi-mat-khau") 
    page_kinh_doanh_result= st.Page("views/kinh_doanh_result.py", title="Kết quả Kinh doanh", icon="📈", url_path="ket-qua-kinh-doanh")
    page_app_tai_xe = st.Page("views/app_tai_xe.py", title="Cập nhật Lịch trình", icon="📱", url_path="cap-nhat-lich-trinh")
    page_tool_zalo= st.Page("views/zalo_local_processor.py", title="Lấy thông tin book từ Zalo", icon="🚛", url_path="lay-thong-tin-tu-zalo")
    page_tool_import_pricing= st.Page("views/import_pricing_ui_2.py", title="Thiết lập bảng giá", icon="📈", url_path="thiet-lap-bang-gia")
    page_tool_import_phu_cap= st.Page("views/config_phu_cap.py", title="Thiết lập phụ cấp", icon="📈", url_path="thiet-lap-phu-cap")
    page_tool_import_pricing_haiquan= st.Page("views/ui_hai_quan.py", title="Thiết lập giá HQ", icon="📈", url_path="thiet-lap-gia-hq")
    page_tool_fuel_manager= st.Page("views/fuel_manager_ui.py", title="Quản lý nhiên liệu", icon="🚛", url_path="quan-ly-nhien-lieu")
    page_tool_backup_database= st.Page("views/backup_database.py", title="Backup Database", icon="🚛", url_path="backup-database")

    # =========================================================================
    # CẤU HÌNH ĐIỀU HƯỚNG BÊN TRÁI CHUYÊN NGHIỆP CỦA ERP
    # =========================================================================
    if not st.session_state['logged_in']:
        # Mẹo: Khởi tạo 2 trang ảo để Streamlit không bao giờ xóa thanh App-Bar trên điện thoại
        def trang_cho():
            pass # Hàm rỗng hợp lệ thay cho lambda
            
        page_dummy = st.Page(trang_cho, title="Chưa đăng nhập", icon="👉", url_path="trang-cho")
        pg = st.navigation({"HỆ THỐNG ERP": [page_login, page_dummy]})
    else:
        role = st.session_state.get('role', 'User')
        
        if role == 'Admin':
            pages_structure = {
                "📦 NGHIỆP VỤ HẰNG NGÀY": [page_chuyen_di, page_to_khai_hq, page_quan_ly_co, page_tool_fuel_manager, page_phap_ly_xe],
                "📦 TÀI CHÍNH KẾ TOÁN": [page_quyet_toan, page_bao_cao],
                "📦 THIẾT LẬP CẤU HÌNH": [page_tool_import_pricing, page_tool_import_phu_cap, page_tool_import_pricing_haiquan, page_tool_zalo],
                "📦 QUẢN LÝ DANH MỤC": [page_nhan_vien, page_doi_xe, page_khach_hang, page_tai_khoan],
                "📦 BÁO CÁO QUẢN TRỊ": [page_kinh_doanh_result],
                "📦 CÁ NHÂN": [page_doi_mat_khau, page_tool_backup_database]
            }
        elif role == 'Tai_Xe':
            pages_structure = {
                "📱 NGHIỆP VỤ TÀI XẾ": [page_app_tai_xe],
                "📦 CÁ NHÂN": [page_doi_mat_khau]
            }
        elif role == 'Ke_Toan':
            pages_structure = {
                "📦 TÀI CHÍNH KẾ TOÁN": [page_quyet_toan, page_bao_cao],
                "📦 CÁ NHÂN": [page_doi_mat_khau]
            }
        else:
            pages_structure = {"CÁ NHÂN": [page_doi_mat_khau]}
            
        pg = st.navigation(pages_structure, position="sidebar")
        
        # Chèn Nút Đăng xuất vào cuối Sidebar
        with st.sidebar:
            st.divider()
            ten_hien_thi = st.session_state.get('ho_ten', st.session_state.get('username', 'Người dùng'))
            st.markdown(f"<div style='text-align: center; color: #0b5394; font-weight: bold;'>👋 Xin chào, {ten_hien_thi}</div><br>", unsafe_allow_html=True)
            if st.button("🚪 Đăng xuất", type="primary", use_container_width=True):
                st.session_state.clear()
                st.rerun()
                
    pg.run()