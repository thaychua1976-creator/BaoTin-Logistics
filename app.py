import streamlit as st
import sys
import pandas as pd
import bcrypt # Thêm ở đầu file

# =====================================================================
# BƯỚC 1: BẮT BUỘC ĐẶT LỆNH NÀY Ở DÒNG ĐẦU TIÊN CỦA FILE app.py CHÍNH
# Lệnh này sẽ tự động áp tiêu đề và icon xe tải cho MỌI TRANG CON
# =====================================================================
st.set_page_config(
    page_title="HỆ THỐNG QUẢN LÝ LOGISTICS BẢO TÍN", 
    page_icon="🚚", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# =====================================================================
# 👉 ĐÂY LÀ TIÊU ĐỀ LỚN XUẤT HIỆN TRONG NỘI DUNG TRANG CHỦ ỨNG DỤNG
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
# =====================================================================
# BƯỚC 2: TIÊM MÃ CSS ĐỂ PHÓNG TO VÀ LÀM NỔI BẬT MENU SIDEBAR BÊN TRÁI
# =====================================================================
st.markdown("""
    <style>
        /* 1. Thiết lập lại độ rộng và nền của thanh Sidebar bên trái cho sang trọng */
        [data-testid="stSidebar"] {
            background-color: #f8fafc !important; /* Nền xám nhẹ dịu mắt */
            border-right: 2px solid #e2e8f0;
            min-width: 320px !important; /* Mở rộng không gian thanh điều hướng */
            max-width: 320px !important;
        }

        /* 2. Phóng to và làm nổi bật tiêu đề phân hệ lớn (Nếu dùng st.radio hoặc widget label) */
        [data-testid="stSidebar"] [data-testid="stWidgetLabel"] p,
        [data-testid="stSidebar"] .st-emotion-cache-qsr6w9 {
            font-size: 19px !important;
            font-weight: bold !important;
            color: #0b5394 !important; /* Màu xanh Bảo Tín thương hiệu */
            letter-spacing: 0.5px !important;
            margin-bottom: 12px !important;
            border-bottom: 2px solid #0b5394;
            padding-bottom: 5px;
        }

        /* 3. Phóng to chữ của CÁC MỤC CHỨC NĂNG (Radio items, Text link, Navigation) */
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
        [data-testid="stSidebar"] span,
        [data-testid="stSidebar"] label {
            font-size: 17px !important;  /* Tăng kích cỡ chữ menu to rõ ràng */
            font-weight: 600 !important;  /* Làm chữ dày dặn, nổi bật */
            color: #1e293b !important;    /* Màu chữ xám tối thanh lịch */
        }

        /* 4. Hiệu ứng Hover phát sáng khi di chuột qua các mục chức năng */
        [data-testid="stSidebar"] [role="radiogroup"] label:hover,
        [data-testid="stSidebar"] [data-testid="stSidebarNavItems"] li:hover {
            background-color: #e2e8f0 !important; /* Đổi nền khi đưa chuột vào */
            color: #0b5394 !important;
            border-radius: 8px;
            padding-left: 10px;
            transition: all 0.3s ease; /* Hiệu ứng mượt mà */
        }
        
        /* 5. Định dạng nếu mục đó đang được Click chọn (Active state) */
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] [data-checked="true"] p {
            color: #0b5394 !important;
            font-weight: bold !important;
        }

        /* 6. Phóng to các nút bấm chức năng phụ trợ nằm trong sidebar nếu có */
        [data-testid="stSidebar"] .stButton button {
            width: 100%;
            font-size: 16px !important;
            font-weight: bold !important;
            border-radius: 6px !important;
        }
            <div class="admin-card">
                <p class="admin-card-text">👋 Chào, <b>{st.session_state['username'].upper()}</b></p>
                
            </div>
    </style>
            
""", unsafe_allow_html=True)

# 1. ÉP PYTHON QUÊN FILE CŨ TRONG RAM ĐI VÀ ĐỌC LẠI TỪ ĐẦU
if 'db_config' in sys.modules:
    del sys.modules['db_config']

# Tìm đoạn khởi tạo DB ở đầu file app.py và sửa thành như sau:

@st.cache_resource
def init_database_pool():
    # Hàm này chỉ chạy đúng 1 lần duy nhất khi bật phần mềm để tạo bể chứa kết nối"""
    from db_config import Database
    return Database()
#st.write("Đường dẫn file database mà Python đang đọc:", database.__file__)
#st.write("Các thành phần bên trong file đó:", dir(database))


# ==========================================
# CSS ẨN HƯỚNG DẪN "PRESS ENTER TO SUBMIT"
# ==========================================
hide_enter_submit_css = """
<style>
    /* Nhắm mục tiêu chính xác vào thẻ div chứa dòng chữ hướng dẫn của Streamlit */
    div[data-testid="InputInstructions"] {
        display: none !important;
        visibility: hidden !important;
    }
</style>
"""
# Thực thi CSS
st.markdown(hide_enter_submit_css, unsafe_allow_html=True)

# Gọi bể chứa ra dùng (Streamlit sẽ tự dùng lại bộ nhớ đệm, không tạo lại Pool)
db = init_database_pool()
st.session_state['db'] = db




#st.set_page_config(page_title="HỆ THỐNG QUẢN LÝ LOGISTICS BẢO TÍN", page_icon="🚚", layout="wide")

# 3. GIẢ LẬP KIỂM TRA ĐĂNG NHẬP (Giữ nguyên logic session_state đăng nhập hiện tại của bạn)
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    st.markdown("<h1 style='text-align: center;'>ĐĂNG NHẬP HỆ THỐNG</h1>", unsafe_allow_html=True)
    
    # Tạo box căn giữa màn hình cho đẹp
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        with st.form("login_form"):
            username = st.text_input("Tên đăng nhập")
            password = st.text_input("Mật khẩu", type="password")
            submit = st.form_submit_button("Đăng Nhập", use_container_width=True)
            
                        
            if submit:
                # BƯỚC 1: Chỉ tìm user theo username và lấy password (chuỗi băm) về
                sql = "SELECT id, role, password FROM users WHERE username = %s"
                result = db.execute_query(sql, (username,))
                
                # Nếu tìm thấy user trong CSDL
                if isinstance(result, pd.DataFrame) and not result.empty:
                    hashed_password_db = result.iloc[0]['password']
                    
                    # BƯỚC 2: Kiểm tra mật khẩu nhập vào với chuỗi băm trong DB
                    # (Lưu ý: cần encode string sang bytes để checkpw xử lý)
                    try:
                        is_correct = bcrypt.checkpw(
                            password.encode('utf-8'), 
                            hashed_password_db.encode('utf-8')
                        )
                    except ValueError:
                        # Bắt lỗi trong trường hợp password trong DB chưa được băm (chữ thường)
                        is_correct = False
                        
                    if is_correct:
                        st.session_state['logged_in'] = True
                        st.session_state['username'] = username
                        st.session_state['role'] = result.iloc[0]['role']
                        st.success("Đăng nhập thành công! Đang chuyển hướng...") 
                        st.rerun() 
                    else:
                        st.error("❌ Sai mật khẩu!")
                else:
                    st.error("❌ Tài khoản không tồn tại!")
else:
    # =====================================================================
# 👉 PHẦN HIỂN THỊ LỜI CHÀO USER ĐĂNG NHẬP (ĐẶT Ở ĐỈNH SIDEBAR BÊN TRÁI)
# =====================================================================
# Lấy tên tài khoản từ biến session_state sau khi login (nếu chưa có sẽ lấy tên mặc định)
    user_hien_tai = st.session_state.get('username')
    #user_hien_tai = st.session_state.get('user_name', 'PHẠM TRẦN LÊ THI')
    st.sidebar.markdown(f"""
        <div style='background-color: #f1f5f9; padding: 15px; border-radius: 8px; text-align: center; margin-bottom: 20px; border-left: 5px solid #0b5394; box-shadow: 0 1px 3px rgba(0,0,0,0.05);'>
            <p style='margin: 0; font-size: 13px; color: #64748b; font-weight: bold; text-transform: uppercase; letter-spacing: 0.5px;'>
                👋 Xin chào Thành viên,
            </p>
            <h4 style='margin: 5px 0 0 0; color: #0b5394; font-weight: 800; font-size: 17px; font-family: "Segoe UI", Arial, sans-serif;'>
                {user_hien_tai}
            </h4>
            <div style='margin-top: 5px; font-size: 11px; color: #22c55e; font-weight: bold;'>
                ● Tài khoản đang hoạt động
            </div>
        </div>
    """, unsafe_allow_html=True)   

    # 4. KHAI BÁO ĐƯỜNG DẪN ĐẾN CÁC FILE GIAO DIỆN CON

    page_chuyen_di = st.Page("views/chuyen_di.py", title="QUẢN LÝ CHUYẾN ĐI", icon="📝", default=True)
    page_bao_cao   = st.Page("views/bao_cao.py", title="BÁO CÁO & THỐNG KÊ", icon="📊")
    page_nhan_vien = st.Page("views/nhan_vien.py", title="QUẢN LÝ NHÂN VIÊN", icon="🧑‍✈️")
    page_doi_xe    = st.Page("views/doi_xe.py", title="QUẢN LÝ XE", icon="🚛")
    page_tai_khoan    = st.Page("views/tai_khoan.py", title="QUẢN LÝ TÀI KHOẢN", icon="👤")
    page_config_thuong= st.Page("views/config_thuong.py", title="CẤU HÌNH THƯỞNG", icon="👤")
    page_kinh_doanh_result= st.Page("views/kinh_doanh_result.py", title="BÁO CÁO KẾT QUẢ KINH DOANH", icon="💰")

    # 5. THUẬT TOÁN PHÂN QUYỀN (RBAC) TỰ ĐỘNG CHÈN VÀO SIDEBAR
    role = st.session_state.get('role', 'User')
    
    # Tạo cấu trúc menu có phân khu thoáng đãng giống như bạn mong muốn
    if role == 'Admin':
        pages_structure = {
            "📦 NGHIỆP VỤ HẰNG NGÀY": [page_chuyen_di, page_bao_cao],
            "⚙️ DANH MỤC QUẢN TRỊ": [page_nhan_vien, page_doi_xe,page_tai_khoan,page_config_thuong,page_kinh_doanh_result]
        }
    else:
        pages_structure = {
            "📦 NGHIỆP VỤ HẰNG NGÀY": [page_chuyen_di, page_bao_cao]
        }
        
    # Lệnh gọi thanh điều hướng Đa trang gốc của Streamlit
    pg = st.navigation(pages_structure, position="sidebar")
    
    # Bổ sung nút Đăng xuất dưới đáy thanh điều hướng
    with st.sidebar:
        st.write("") # Tạo khoảng giãn cách nhỏ
        if st.button("🚪 Đăng xuất hệ thống", type="secondary", use_container_width=True):
            st.session_state['logged_in'] = False
            st.rerun()

    # 6. KÍCH HOẠT CHẠY TRANG CON ĐƯỢC CHỌN
    pg.run()