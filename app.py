import streamlit as st
import sys
import pandas as pd
import bcrypt

# =====================================================================
# BƯỚC 1: KHỞI TẠO PAGE CONFIG (BẮT BUỘC ĐỂ ĐẦU TIÊN)
# =====================================================================
st.set_page_config(
    page_title="HỆ THỐNG QUẢN LÝ LOGISTICS BẢO TÍN", 
    page_icon="🚚", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# =====================================================================
# BƯỚC 2: CSS TÙY CHỈNH GIAO DIỆN (SỬ DỤNG CSS :has() ĐỂ TRỊ TẬN GỐC)
# =====================================================================
# =====================================================================
# BƯỚC 2: CSS TÙY CHỈNH GIAO DIỆN (ĐÃ NÂNG CẤP MENU & ẨN HƯỚNG DẪN)
# =====================================================================
st.markdown("""
    <style>
        /* Ẩn dòng chữ hướng dẫn Press Enter to submit */
        div[data-testid="InputInstructions"] {
            display: none !important;
            visibility: hidden !important;
        }

        /* Thiết lập thanh Sidebar */
        [data-testid="stSidebar"] {
            background-color: #f8fafc !important; 
            border-right: 2px solid #e2e8f0;
            min-width: 330px !important; 
            max-width: 330px !important;
        }

        /* ===================================================== */
        /* CSS PHÂN CẤP MENU: MỤC CHÍNH CHỮ NỔI, MỤC CON LÙI VÀO */
        /* ===================================================== */
        
        /* 1. Tiêu đề Mục chính (Category Headers - Cài đặt mặc định) */
        [data-testid="stSidebarNav"] span[data-testid="stSidebarNavSeparator"] + span,
        [data-testid="stSidebarNav"] ul li div {
            font-size: 16px !important;
            font-weight: 800 !important;
            color: #0b5394 !important;
            text-transform: uppercase !important;
            letter-spacing: 0.5px !important;
            padding-bottom: 5px;
            margin-top: 15px;
            border-bottom: 2px solid #cbd5e1;
        }
        
        /* 1.1 TÙY CHỈNH RIÊNG CHO MỤC "DANH MỤC QUẢN TRỊ" (Màu đỏ + Hiệu ứng nổi 3D) */
        /* Giả định "DANH MỤC QUẢN TRỊ" là mục lớn thứ 2 trong navigation list */
        [data-testid="stSidebarNav"] > ul > li:nth-child(2) > div {
            color: #d32f2f !important; /* Màu đỏ đậm */
            font-size: 17px !important;
            text-shadow: 1px 1px 0 #999, 
                         2px 2px 0 #777, 
                         3px 3px 2px rgba(0,0,0,0.4) !important; /* Hiệu ứng chữ nổi 3D */
            border-bottom: 2px solid #d32f2f !important;
            padding-bottom: 8px !important;
            margin-top: 25px !important;
        }

        /* 2. Mục con (Sub-items - Các trang chức năng) - Lùi vào trong */
        [data-testid="stSidebarNav"] ul li ul li {
            margin-left: 25px !important; /* Đẩy lùi vào trong 25px */
            border-left: 2px solid #e2e8f0;
        }

        /* 3. Định dạng chữ của Mục con */
        [data-testid="stSidebarNav"] ul li ul li a span {
            font-size: 16px !important; 
            font-weight: 600 !important;  
            color: #334155 !important;
            text-transform: none !important;
            border-bottom: none !important;
            margin-top: 0px !important;
        }

        /* Hiệu ứng Hover cho Mục con */
        [data-testid="stSidebarNav"] ul li ul li:hover {
            background-color: #e2e8f0 !important; 
            border-left: 3px solid #0b5394 !important;
            border-radius: 0 6px 6px 0;
            transition: all 0.2s ease-in-out; 
        }
        
        /* Khi Mục con đang được chọn (Active) */
        [data-testid="stSidebarNav"] ul li ul li[data-checked="true"] {
            background-color: #dbeafe !important;
            border-left: 3px solid #0b5394 !important;
        }
        [data-testid="stSidebarNav"] ul li ul li[data-checked="true"] a span {
            color: #0b5394 !important;
            font-weight: 800 !important;
        }

        /* Định dạng nút bấm trong Sidebar */
        [data-testid="stSidebar"] .stButton button {
            width: 100%;
            font-size: 15px !important;
            font-weight: bold !important;
            border-radius: 6px !important;
        }
    </style>
""", unsafe_allow_html=True)

# =====================================================================
# BƯỚC 3: TIÊU ĐỀ TRANG CHỦ & KHỞI TẠO DATABASE
# =====================================================================
st.markdown("""
    <div style='margin-top: -30px; margin-bottom: 20px;'>
        <h1 style='text-align: center; color: #0b5394; font-family: "Segoe UI", Arial, sans-serif; font-weight: 800; font-size: 34px; letter-spacing: 1px;'>
            🚚 HỆ THỐNG QUẢN LÝ LOGISTICS BẢO TÍN
        </h1>
        <p style='text-align: center; color: #64748b; font-size: 15px; font-weight: 500; margin-top: 5px; margin-bottom: 15px;'>
            Trung tâm điều hành vận tải đường bộ • Dữ liệu số hóa thời gian thực
        </p>
        <hr style='border: 0; height: 2px; background-image: linear-gradient(to right, rgba(11, 83, 148, 0), rgba(11, 83, 148, 0.75), rgba(11, 83, 148, 0));'>
    </div>
""", unsafe_allow_html=True)
# Trong file app.py
#from apscheduler.schedulers.background import BackgroundScheduler
#from scheduler_tasks import task_gui_bao_cao_phap_ly_tu_dong


if 'db_config' in sys.modules:
    del sys.modules['db_config']

@st.cache_resource
def init_database_pool():
    from db_config import Database
    return Database()

#def start_scheduler(db_pool):
#    scheduler = BackgroundScheduler()
    # Chạy vào 8:00 sáng mỗi ngày
#    scheduler.add_job(
#        task_gui_bao_cao_phap_ly_tu_dong, 
#        'cron', 
#        hour=8, 
#        minute=0, 
#        args=[db_pool]
#    )
#    scheduler.start()
#    return scheduler

db = init_database_pool()
st.session_state['db'] = db
# Khởi tạo ngay sau khi có db_pool
#scheduler = start_scheduler(db)

# =====================================================================
# BƯỚC 4: XỬ LÝ TRẠNG THÁI ĐĂNG NHẬP (GIAO DIỆN & LOGIC)
# =====================================================================
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

# Khởi tạo trạng thái ẩn/hiện mật khẩu
if 'hien_mat_khau' not in st.session_state:
    st.session_state['hien_mat_khau'] = False

def toggle_password():
    st.session_state['hien_mat_khau'] = not st.session_state['hien_mat_khau']

if not st.session_state['logged_in']:
    st.markdown("<h3 style='text-align: center;'>🔐 ĐĂNG NHẬP HỆ THỐNG</h3>", unsafe_allow_html=True)
    
    col_l1, col_l2, col_l3 = st.columns([1, 1, 1])
    with col_l2:
        # Bỏ st.form để nút mắt hoạt động Real-time
        username = st.text_input("Tên đăng nhập", autocomplete="off")
        
        col_pw, col_eye = st.columns([9, 2])
        with col_pw:
            if not st.session_state['hien_mat_khau']:
                css_masking = """
                <style>
                    input[aria-label="Mật khẩu"] {
                        -webkit-text-security: disc !important;
                    }
                </style>
                """
                st.markdown(css_masking, unsafe_allow_html=True)
            password = st.text_input("Mật khẩu", autocomplete="off")
            
        with col_eye:
            st.markdown("<br>", unsafe_allow_html=True) 
            icon = "👁️‍🗨️" if st.session_state['hien_mat_khau'] else "👁️"
            st.button(icon, on_click=toggle_password, help="Ẩn/Hiện mật khẩu", use_container_width=True)
            
        st.markdown("<br>", unsafe_allow_html=True)
        submit = st.button("Đăng Nhập", type="primary", use_container_width=True)
        
        if submit:
            # Truy vấn thêm trường ho_ten từ bảng users
            sql = "SELECT id, role, password, nhan_vien_id, ho_ten FROM users WHERE username = %s"
            result = db.execute_query(sql, (username,))
            
            if isinstance(result, pd.DataFrame) and not result.empty:
                hashed_password_db = result.iloc[0]['password']
                try:
                    is_correct = bcrypt.checkpw(
                        password.encode('utf-8'), 
                        hashed_password_db.encode('utf-8')
                    )
                except ValueError:
                    is_correct = False
                    
                if is_correct:
                    st.session_state['logged_in'] = True
                    st.session_state['username'] = username
                    st.session_state['role'] = result.iloc[0]['role']
                    st.session_state['nhan_vien_id'] = result.iloc[0]['nhan_vien_id'] 
                    # Lưu trữ Tên Hiển Thị (Họ tên) vào Session State
                    st.session_state['ho_ten'] = result.iloc[0]['ho_ten']
                    
                    st.success("Đăng nhập thành công! Đang chuyển hướng...") 
                    st.rerun() 
                else:
                    st.error("❌ Sai mật khẩu!")
            else:
                st.error("❌ Tài khoản không tồn tại!")
else:
    # =====================================================================
    # BƯỚC 5: HIỂN THỊ MENU & ROUTING (SAU KHI ĐĂNG NHẬP THÀNH CÔNG)
    # =====================================================================
    
    # Sử dụng `ho_ten` lấy từ cơ sở dữ liệu làm lời chào thay vì `username`
    ten_hien_thi = st.session_state.get('ho_ten', st.session_state.get('username', 'Người dùng'))
    
    st.sidebar.markdown(f"""
        <div style='background-color: #f1f5f9; padding: 15px; border-radius: 8px; text-align: center; margin-bottom: 20px; border-left: 5px solid #0b5394; box-shadow: 0 1px 3px rgba(0,0,0,0.05);'>
            <p style='margin: 0; font-size: 13px; color: #64748b; font-weight: bold; text-transform: uppercase; letter-spacing: 0.5px;'>
                👋 Xin chào,
            </p>
            <h4 style='margin: 5px 0 0 0; color: #0b5394; font-weight: 800; font-size: 17px; font-family: "Segoe UI", Arial, sans-serif;'>
                {ten_hien_thi}
            </h4>
            <div style='margin-top: 5px; font-size: 11px; color: #22c55e; font-weight: bold;'>
                ● Tài khoản đang hoạt động
            </div>
        </div>
    """, unsafe_allow_html=True)   

    # Khai báo đường dẫn đến các trang chức năng
    page_chuyen_di = st.Page("views/chuyen_di.py", title="Quản lý Chuyến đi", icon="📝", default=True)
    page_bao_cao   = st.Page("views/bao_cao.py", title="Báo cáo & Thống kê", icon="📊")
    page_nhan_vien = st.Page("views/nhan_vien.py", title="Quản lý Nhân viên", icon="🧑‍✈️")
    page_doi_xe    = st.Page("views/doi_xe.py", title="Quản lý Đội xe", icon="🚛")
    page_tai_khoan = st.Page("views/tai_khoan.py", title="Quản lý Tài khoản", icon="👤")
    page_config_thuong= st.Page("views/config_thuong.py", title="Cấu hình Thưởng", icon="💰")
    page_kinh_doanh_result= st.Page("views/kinh_doanh_result.py", title="Kết quả Kinh doanh", icon="📈")
    page_app_tai_xe = st.Page("views/app_tai_xe.py", title="Cập nhật Lịch trình", icon="📱", default=True)
    page_tool_zalo= st.Page("views/tool_send_zalo.py", title="Gửi Group Zalo", icon="🚛")
    page_tool_fuel_manager= st.Page("views/fuel_manager_ui.py", title="Quản lý nhiên liệu/Hiệu suất", icon="🚛")

    # Phân quyền (RBAC) cấu trúc danh mục
    role = st.session_state.get('role', 'User')
    
    if role == 'Admin':
        pages_structure = {
            "📦 NGHIỆP VỤ HẰNG NGÀY": [page_chuyen_di, page_bao_cao,page_tool_fuel_manager],
            "📦 TOOL TIỆN ÍCH": [page_tool_zalo],
            "⚙️ DANH MỤC QUẢN TRỊ": [page_nhan_vien, page_doi_xe, page_tai_khoan, page_config_thuong, page_kinh_doanh_result]
        }
    elif role == 'Tai_Xe':
        pages_structure = {
            "📱 ỨNG DỤNG TÀI XẾ": [page_app_tai_xe]
        }
    else:
        pages_structure = {
            "📦 NGHIỆP VỤ HẰNG NGÀY": [page_chuyen_di, page_bao_cao,page_tool_fuel_manager],
            "📦 TOOL TIỆN ÍCH": [page_tool_zalo]
        }
        
    pg = st.navigation(pages_structure, position="sidebar")
    
    with st.sidebar:
        st.write("") 
        if st.button("🚪 Đăng xuất hệ thống", type="secondary", use_container_width=True):
            st.session_state.clear()
            st.rerun()

    pg.run()