import streamlit as st
import pandas as pd
import time

from global_func import  parse_money_input, update_bonus_config_transaction

db = st.session_state['db']


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

# ==========================================
#  CẤU HÌNH PHỤ CẤP & THƯỞNG TỰ ĐỘNG
# ==========================================

st.markdown("##### ⚙️ Tham số định mức phụ cấp (Làm cơ sở gợi ý tự động)")
st.info("💡 Các thay đổi tại đây sẽ được áp dụng cho toàn bộ các chuyến đi được quyết toán sau này.")
        
df_cfg = db.execute_query("SELECT * FROM cau_hinh_thuong")
    
if isinstance(df_cfg, pd.DataFrame) and not df_cfg.empty:
        with st.form("form_cau_hinh_thuong"):
            input_values = {} # Dictionary tạm để hứng dữ liệu nhập dạng chuỗi (Text)
            
            # Hiển thị giao diện nhập liệu
            for _, row in df_cfg.iterrows():
                c_lbl, c_val = st.columns([2, 1])
                c_lbl.markdown(f"**{row['ten_tieu_chi']}**")
                
                # Lưu giá trị Text vào biến tạm
                input_values[row['ma_tieu_chi']] = c_val.text_input(
                    label=f"Mã: {row['ma_tieu_chi']}", 
                    value=f"{int(row['muc_thuong']):,}", 
                    label_visibility="collapsed"
                )
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            # Xử lý khi nhấn nút Lưu
            if st.form_submit_button("💾 Lưu Cấu hình Chính sách", type="primary"):
                
                # 1. Xóa dấu phẩy và ép kiểu về số nguyên trước khi lưu Database
                processed_values = {}
                for ma_tc, val_str in input_values.items():
                    processed_values[ma_tc] = parse_money_input(val_str)
                
                # 2. Gọi hàm Transaction để lưu và ghi Log
                # (Nếu ứng dụng có chức năng đăng nhập, bạn có thể thay "Admin" bằng biến session_state chứa tên người dùng)
                is_ok, msg = update_bonus_config_transaction(db.pool, processed_values, nguoi_dung="Admin")
                
                # 3. Hiển thị thông báo
                if is_ok:
                    st.success(f"✅ {msg}")
                    st.balloons()
                    time.sleep(1)
                    st.rerun() # Tải lại trang để cập nhật số liệu mới
                else:
                    st.error(f"❌ Lỗi lưu cấu hình. Chi tiết Database: {msg}")