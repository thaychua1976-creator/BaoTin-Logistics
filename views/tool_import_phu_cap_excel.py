import streamlit as st
import pandas as pd
from utils_core import import_excel_phu_cap_transaction

db = st.session_state.get('db')

# Lấy chính xác username từ phiên đăng nhập thực tế của người dùng, nếu không có mặc định là 'Admin'[cite: 3]
current_user = st.session_state.get('username') or st.session_state.get('user') or st.session_state.get('logged_in_user', 'Admin')

if not db:
    st.error("⚠️ Lỗi kết nối Cơ sở dữ liệu.")
    st.stop()

st.markdown("### 📥 TOOL NHẬP LIỆU: BẢNG PHỤ CẤP TÀI XẾ TỪ EXCEL")
st.info("💡 Tính năng này sẽ tự động phân tích file Excel `NỘI DUNG PHỤ CẤP SẢN LƯỢNG.xlsx` và bóc tách dữ liệu vào 3 bảng: Tải Trọng, Tiêu Chí và Ma Trận.")

with st.form("form_import_phu_cap"):
    uploaded_file = st.file_uploader("Kéo thả file Excel Ma Trận Phụ Cấp vào đây (.xlsx)", type=['xlsx'])
    is_submit = st.form_submit_button("🚀 Thực thi Import Dữ Liệu", type="primary", use_container_width=True)
    
    if is_submit:
        if not uploaded_file:
            st.warning("⚠️ Vui lòng tải lên một file Excel!")
        else:
            with st.spinner("Đang quét cấu trúc file và đồng bộ Database..."):
                try:
                    # Đọc dữ liệu Excel
                    df_import = pd.read_excel(uploaded_file)
                    
                    # Gọi hàm xử lý backend
                    db_pool = st.session_state['db']
                    current_user = st.session_state.get('username', 'Admin')
                    
                    success, msg = import_excel_phu_cap_transaction(db_pool, df_import, current_user)
                    
                    if success:
                        st.success(msg)
                        st.balloons()
                    else:
                        st.error(f"❌ Lỗi SQL: {msg}")
                except Exception as ex:
                    st.error(f"❌ Lỗi đọc file Excel: {ex}")
