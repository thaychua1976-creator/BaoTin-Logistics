import streamlit as st
import pandas as pd

# Đảm bảo database đã được khởi tạo trong session_state
if 'db' not in st.session_state:
    st.error("Vui lòng đăng nhập hoặc khởi tạo kết nối cơ sở dữ liệu trước!")
    st.stop()

db = st.session_state['db']

st.markdown("<h3 style='text-align: center; color: #0b5394;'>🔄 CÔNG CỤ ĐỒNG BỘ TÀI XẾ CỐ ĐỊNH VÀO ĐỘI XE</h3>", unsafe_allow_html=True)
st.info("Công cụ này sẽ đọc file Excel/CSV danh sách, tự động đối chiếu Tên tài xế và Biển số xe để gán 'Tài xế cố định' cho từng xe trong Database.")

# Upload file Excel/CSV
uploaded_file = st.file_uploader("Tải lên file Danh sách Tài xế & Phương tiện (Excel/CSV)", type=['csv', 'xlsx', 'xls'])

if uploaded_file is not None:
    if st.button("🚀 Bắt đầu Đồng bộ Dữ liệu", type="primary"):
        with st.spinner("Đang xử lý đồng bộ..."):
            try:
                # Đọc file: Bỏ qua 4 dòng đầu tiên vì dòng thứ 5 mới là Tiêu đề cột (STT, NHÃN HIỆU...)
                if uploaded_file.name.endswith('.csv'):
                    df = pd.read_csv(uploaded_file, skiprows=4)
                else:
                    df = pd.read_excel(uploaded_file, skiprows=4)
                
                # Làm sạch khoảng trắng thừa ở tên cột để gọi cho chính xác
                df.columns = df.columns.str.strip()
                
                xe_thanh_cong = 0
                xe_loi = []

                # Lặp qua từng dòng dữ liệu trong file
                for index, row in df.iterrows():
                    bien_so = str(row.get('BIỂN SỐ XE', '')).strip()
                    ten_tai_xe = str(row.get('Tên tài xế', '')).strip()
                    
                    # Bỏ qua các dòng trống
                    if bien_so and bien_so.lower() != 'nan' and ten_tai_xe and ten_tai_xe.lower() != 'nan':
                        
                        # 1. Tìm ID của tài xế trong bảng nhân viên (Dùng LIKE để quét chính xác dù dư khoảng trắng)
                        sql_find_tx = "SELECT id FROM nhan_vien WHERE ho_ten LIKE %s AND trang_thai = 'Dang_Lam_Viec' LIMIT 1"
                        df_tx = db.execute_query(sql_find_tx, (f"%{ten_tai_xe}%",))
                        
                        if isinstance(df_tx, pd.DataFrame) and not df_tx.empty:
                            tx_id = int(df_tx.iloc[0]['id'])
                            
                            # 2. Cập nhật ID tài xế cố định vào bảng xe
                            sql_update_xe = "UPDATE xe SET tai_xe_co_dinh_id = %s WHERE bien_so_xe = %s"
                            db.execute_query(sql_update_xe, (tx_id, bien_so))
                            
                            xe_thanh_cong += 1
                        else:
                            # Ghi nhận lại nếu không tìm thấy tên tài xế này trong CSDL nhân viên
                            xe_loi.append(f"Biển số {bien_so}: Không tìm thấy tài xế '{ten_tai_xe}' trong hệ thống nhân sự.")

                # Hiển thị kết quả
                st.success(f"🎉 Đồng bộ hoàn tất! Đã gán tài xế cố định thành công cho **{xe_thanh_cong}** xe.")
                
                if xe_loi:
                    st.warning("⚠️ Một số xe không thể đồng bộ do sai lệch tên Tài xế:")
                    for loi in xe_loi:
                        st.write(f"- {loi}")
                
            except Exception as e:
                st.error(f"❌ Xảy ra lỗi trong quá trình đọc file: {e}")