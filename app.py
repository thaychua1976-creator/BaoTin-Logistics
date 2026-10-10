import streamlit as st
import sys, time
import pandas as pd
import bcrypt

def show_page():
    # Cấu hình giao diện rộng cho cả máy tính và điện thoại
    st.set_page_config(layout="wide", initial_sidebar_state="collapsed")
    
    with st.spinner("🔄 Đang tải chương trình và đồng bộ dữ liệu hệ thống, vui lòng đợi..."):
        time.sleep(0.3) 

    # 1. Hàm tùy chỉnh CSS giao diện
    def apply_custom_appearance():
        custom_css = """
        <style>
        button, input, select {
            -webkit-appearance: none;
            -moz-appearance: none;
            appearance: none;
        }
        </style>
        """
        st.markdown(custom_css, unsafe_allow_html=True)
        
    # 2. CSS Tùy chỉnh Layout Gốc (ĐÃ XÓA BÙA HỘ MỆNH GÂY LỖI)
    st.markdown("""
        <style>
            .block-container {
                padding-top: 1rem !important; /* Kéo toàn bộ app lên sát mép trên */
                padding-bottom: 1rem !important;
                padding-left: 1rem !important;
                padding-right: 1rem !important;
                max-width: 98% !important;
            }
            
            /* --- ẨN CÁC THÀNH PHẦN MẶC ĐỊNH CỦA STREAMLIT --- */
            [data-testid="stStatusWidget"], [data-testid="stToolbar"], footer {
                display: none !important;
                visibility: hidden !important;
            }
            div[data-testid="InputInstructions"] { display: none !important; }
            
            /* --- ẨN LUÔN NÚT 3 GẠCH (VÌ TA ĐÃ DÙNG TOP NAVBAR) --- */
            [data-testid="collapsedControl"] { display: none !important; }
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
        st.markdown("<h3 style='text-align: center; color: #0B2E9E;'>🔐 ĐĂNG NHẬP HỆ THỐNG ERP BẢO TÍN</h3>", unsafe_allow_html=True)
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
    page_bao_cao   = st.Page("views/bao_cao.py", title="Thông kê lương & Công Nợ", icon="📊", url_path="thong-ke-luong")
    page_nhan_vien = st.Page("views/nhan_vien.py", title="Quản lý Nhân viên", icon="🧑‍✈️", url_path="quan-ly-nhan-vien")
    page_khach_hang = st.Page("views/khach_hang.py", title="Quản lý Khách hàng", icon="🧑", url_path="quan-ly-khach-hang")
    page_to_khai_hq = st.Page("views/khai_bao_hq.py", title="Khai báo Hải Quan", icon="🧑‍✈️", url_path="khai-bao-hai-quan")
    page_quan_ly_co = st.Page("views/quan_ly_co.py", title="Quản lý CO", icon="🧑‍✈️", url_path="quan-ly-co")
    page_doi_xe    = st.Page("views/doi_xe.py", title="Quản lý Đội xe", icon="🚛", url_path="quan-ly-doi-xe")
    page_phap_ly_xe    = st.Page("views/phap_ly_xe.py", title="Quản lý pháp lý xe", icon="🚛", url_path="quan-ly-phap-ly-xe")
    page_tai_khoan = st.Page("views/tai_khoan.py", title="Quản lý tài khoản", icon="👤", url_path="quan-ly-tai-khoan")
    page_doi_mat_khau = st.Page("views/doi_mat_khau.py", title="Đổi mật khẩu", icon="🔑", url_path="doi-mat-khau") 
    page_kinh_doanh_result= st.Page("views/kinh_doanh_result.py", title="Kết quả Kinh doanh", icon="📈", url_path="ket-qua-kinh-doanh")
    page_app_tai_xe = st.Page("views/app_tai_xe.py", title="Cập nhật Lịch trình", icon="📱", url_path="cap-nhat-lich-trinh")
    page_tool_zalo= st.Page("views/zalo_local_processor.py", title="Lấy thông tin Zalo", icon="🚛", url_path="lay-thong-tin-tu-zalo")
    page_tool_import_pricing= st.Page("views/import_pricing_ui_2.py", title="Thiết lập bảng giá", icon="📈", url_path="thiet-lap-bang-gia")
    page_tool_import_phu_cap= st.Page("views/config_phu_cap.py", title="Thiết lập phụ cấp", icon="📈", url_path="thiet-lap-phu-cap")
    page_tool_import_pricing_haiquan= st.Page("views/ui_hai_quan.py", title="Thiết lập giá HQ", icon="📈", url_path="thiet-lap-gia-hq")
    page_tool_fuel_manager= st.Page("views/fuel_manager_ui.py", title="Quản lý nhiên liệu", icon="🚛", url_path="quan-ly-nhien-lieu")
    page_tool_backup_database= st.Page("views/backup_database.py", title="Backup Database", icon="🚛", url_path="backup-database")

    # =========================================================================
    # GIẢI PHÁP TỐI ƯU: THANH MENU VUỐT NGANG Y HỆT TRANG HOME PAGE
    # =========================================================================
    if not st.session_state['logged_in']:
        pg = st.navigation([page_login], position="hidden")
    else:
        role = st.session_state.get('role', 'User')
        
        danh_sach_trang = {}
        if role == 'Admin':
            danh_sach_trang = {
                "📝 Chuyến đi": page_chuyen_di, "🧑‍✈️ Hải Quan": page_to_khai_hq, "🧑‍✈️ Quản lý CO": page_quan_ly_co,
                "💰 Quyết toán": page_quyet_toan, "🚛 Nhiên liệu": page_tool_fuel_manager, "🚛 Pháp lý xe": page_phap_ly_xe,
                "📊 Thống kê": page_bao_cao, "📈 Bảng giá": page_tool_import_pricing, "📈 Phụ cấp": page_tool_import_phu_cap,
                "📈 Giá HQ": page_tool_import_pricing_haiquan, "🚛 Zalo": page_tool_zalo, "🧑‍✈️ Nhân viên": page_nhan_vien,
                "🚛 Đội xe": page_doi_xe, "🧑 Khách hàng": page_khach_hang, "👤 Tài khoản": page_tai_khoan,
                "📈 KQ Kinh doanh": page_kinh_doanh_result, "🔑 Đổi mật khẩu": page_doi_mat_khau, "🚛 Backup": page_tool_backup_database
            }
        elif role == 'Tai_Xe':
            danh_sach_trang = { "📱 Cập nhật Lịch trình": page_app_tai_xe, "🔑 Đổi mật khẩu": page_doi_mat_khau }
        elif role == 'Ke_Toan':
            danh_sach_trang = { "💰 Quyết toán": page_quyet_toan, "📊 Thống kê": page_bao_cao, "🔑 Đổi mật khẩu": page_doi_mat_khau }

        # Ẩn Sidebar gốc đi để dành đất diễn cho Top Menu
        pg = st.navigation(list(danh_sach_trang.values()), position="hidden")
        
        # --- CSS BIẾN ST.RADIO THÀNH THANH ĐIỀU HƯỚNG VUỐT NGANG Y HỆT HOME ---
        st.markdown("""
            <style>
                div[role="radiogroup"] {
                    display: flex !important;
                    flex-direction: row !important;
                    flex-wrap: nowrap !important;
                    overflow-x: auto !important;
                    overflow-y: hidden !important;
                    padding-bottom: 8px !important;
                    -webkit-overflow-scrolling: touch !important; /* Mượt trên iOS */
                }
                /* Ẩn dấu chấm tròn mặc định của Radio */
                div[role="radiogroup"] span[data-baseweb="radio"] { display: none !important; }
                
                /* Đóng khung từng Menu thành 1 Nút bấm */
                div[role="radiogroup"] > label {
                    background-color: #f1f5f9 !important;
                    color: #0B2E9E !important;
                    padding: 8px 16px !important;
                    border-radius: 20px !important; /* Bo góc tròn như nút App */
                    margin-right: 8px !important;
                    font-weight: 800 !important;
                    white-space: nowrap !important; /* Cấm xuống dòng */
                    border: 1px solid #cbd5e1 !important;
                    cursor: pointer !important;
                }
                
                /* Khi Menu đó đang được chọn (Active) */
                div[role="radiogroup"] > label[data-checked="true"] {
                    background-color: #0B2E9E !important;
                    color: white !important;
                    border: 2px solid #FF6B00 !important;
                    box-shadow: 0px 4px 6px rgba(0,0,0,0.1) !important;
                }
            </style>
        """, unsafe_allow_html=True)

        if 'current_menu_page' not in st.session_state:
            st.session_state['current_menu_page'] = list(danh_sach_trang.keys())[0]
        
        col_name, col_btn = st.columns([7, 3], vertical_alignment="center")
        with col_name:
            ten_hien_thi = st.session_state.get('ho_ten', st.session_state.get('username', 'Người dùng'))
            st.markdown(f"<span style='color: #0B2E9E; font-weight: 800; font-size: 15px;'>👋 Chào, {ten_hien_thi}</span>", unsafe_allow_html=True)
        with col_btn:
            if st.button("🚪 Đăng xuất", use_container_width=True):
                st.session_state.clear()
                st.rerun()

        # Hiển thị Thanh Vuốt ngang (Ngay dưới lời chào)
        selected_menu = st.radio(
            "ĐIỀU HƯỚNG:", 
            options=list(danh_sach_trang.keys()), 
            index=list(danh_sach_trang.keys()).index(st.session_state['current_menu_page']) if st.session_state['current_menu_page'] in danh_sach_trang else 0,
            horizontal=True,
            label_visibility="collapsed"
        )
        
        st.divider() # Đường gạch ngang phân cách Menu và Nội dung
        
        # Nhảy trang khi người dùng bấm vào Menu
        if selected_menu != st.session_state['current_menu_page']:
            st.session_state['current_menu_page'] = selected_menu
            st.switch_page(danh_sach_trang[selected_menu])

    # HÀM RUN LUÔN NẰM CUỐI CÙNG
    pg.run()