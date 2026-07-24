import streamlit as st
import pandas as pd

# 1. Lấy kết nối Database
if 'db' not in st.session_state:
    st.error("Chưa kết nối cơ sở dữ liệu.")
    st.stop()
db_chinh = st.session_state['db']

# 2. Lấy ID tài xế
TAI_XE_ID_HIENTAI = st.session_state.get('nhan_vien_id')

st.markdown("<h3 style='text-align: center; color: #1E3A8A;'>BẢO TÍN LOGISTICS</h3>", unsafe_allow_html=True)

# ==============================================================
# BẬT CHẾ ĐỘ DEBUG MẠNH NHẤT - IN TRỰC TIẾP RA MÀN HÌNH
# ==============================================================
st.error("🛑 CHẾ ĐỘ TÌM LỖI ĐANG BẬT 🛑")

st.write(f"**1. Biến TAI_XE_ID_HIENTAI đang nhận là:** {TAI_XE_ID_HIENTAI} (Kiểu: {type(TAI_XE_ID_HIENTAI)})")

# Thử ép kiểu sang số nguyên chuẩn của Python
tx_id_chuan = int(TAI_XE_ID_HIENTAI) if TAI_XE_ID_HIENTAI else 0

# Test 1: Đọc thẳng từ bảng chuyen_di_tai_xe xem có ra ID 1 không (Không dùng %s mà ghép thẳng số vào lệnh SQL)
sql_test_1 = f"SELECT * FROM chuyen_di_tai_xe WHERE tai_xe_id = {tx_id_chuan}" 
df_test_1 = db_chinh.execute_query(sql_test_1)
st.write("**2. Dữ liệu trong bảng phân công (chuyen_di_tai_xe):**")
st.dataframe(df_test_1)

# Test 2: Đọc thẳng chuyến 149 xem trạng thái là gì
df_test_2 = db_chinh.execute_query("SELECT id, trang_thai_chuyen FROM chuyen_di WHERE id = 149")
st.write("**3. Dữ liệu chuyến đi số 149 trong bảng chuyen_di:**")
st.dataframe(df_test_2)

# Test 3: Câu lệnh JOIN hoàn chỉnh nhưng KHÔNG LỌC trạng thái
sql_test_3 = f"""
    SELECT cd.id, cd.dia_diem_giao_nhan, cd.trang_thai_chuyen, ctx.tai_xe_id 
    FROM chuyen_di cd
    JOIN chuyen_di_tai_xe ctx ON cd.id = ctx.chuyen_di_id
    WHERE ctx.tai_xe_id = {tx_id_chuan}
"""
df_test_3 = db_chinh.execute_query(sql_test_3)
st.write("**4. Kết quả câu lệnh JOIN (Chưa lọc trạng thái):**")
st.dataframe(df_test_3)

st.divider()
st.stop() # Dừng hẳn code ở đây, không chạy giao diện App bên dưới nữa