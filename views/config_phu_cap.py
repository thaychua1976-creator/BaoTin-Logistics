import streamlit as st
import pandas as pd
from hr_system_manager import update_phu_cap_matrix_transaction

# Giả định biến db (kết nối pool) và username đã có trong session_state
db = st.session_state['db']
current_user = st.session_state.get('username', 'Admin')

st.markdown("### 💰 BẢNG CẤU HÌNH PHỤ CẤP SẢN LƯỢNG TÀI XẾ")
st.info("💡 Hướng dẫn: Click đúp vào ô số tiền để sửa trực tiếp (như dùng Excel). Nhấn nút LƯU ở dưới cùng để chốt dữ liệu.")

# 1. Truy xuất dữ liệu từ 3 bảng
df_tt = db.execute_query("SELECT id, ten_hien_thi FROM dm_tai_trong_phu_cap ORDER BY tai_trong_min ASC")
df_tc = db.execute_query("SELECT id, ten_tieu_chi FROM dm_tieu_chi_phu_cap ORDER BY id ASC")
df_mt = db.execute_query("SELECT tai_trong_id, tieu_chi_id, so_tien FROM ma_tran_phu_cap")

if not df_tt.empty and not df_tc.empty:
    # 2. Cấu trúc lại DataFrame thành Ma Trận (Pivot)
    matrix_data = []
    for _, tt in df_tt.iterrows():
        row_dict = {"Tải Trọng Xe": tt['ten_hien_thi']}
        for _, tc in df_tc.iterrows():
            # Tìm số tiền tương ứng, nếu không có mặc định là 0
            val = df_mt[(df_mt['tai_trong_id'] == tt['id']) & (df_mt['tieu_chi_id'] == tc['id'])]
            so_tien = float(val.iloc[0]['so_tien']) if not val.empty else 0.0
            row_dict[tc['ten_tieu_chi']] = so_tien
        matrix_data.append(row_dict)

    df_matrix = pd.DataFrame(matrix_data)
    df_matrix.set_index("Tải Trọng Xe", inplace=True)

    # 3. Hiển thị UI chỉnh sửa dạng Excel
    # Dùng column_config để format tiền tệ VNĐ cực kỳ đẹp mắt
    column_config = {
        col: st.column_config.NumberColumn(col, format="%d ₫", min_value=0) 
        for col in df_matrix.columns
    }

    df_edited = st.data_editor(
        df_matrix,
        column_config=column_config,
        use_container_width=True,
        num_rows="fixed", # Không cho người dùng tự ý thêm dòng rác
        height=500
    )

    # 4. Nút bấm lưu
    if st.button("💾 LƯU BẢNG PHỤ CẤP", type="primary"):
        with st.spinner("Đang đồng bộ dữ liệu vào hệ thống..."):
            is_ok, msg = update_phu_cap_matrix_transaction(db.pool, df_edited, current_user)
            if is_ok:
                st.success(msg)
            else:
                st.error(f"Lỗi: {msg}")
else:
    st.warning("⚠️ Chưa có dữ liệu Khai báo Tải trọng hoặc Tiêu chí. Vui lòng thêm trong Cài đặt chung trước!")

# --- UI PHỤ: Thêm mới Cột (Tiêu chí) hoặc Dòng (Tải trọng) ---
with st.expander("➕ Thêm mới Tiêu chí hoặc Mức tải trọng", expanded=False):
    col1, col2 = st.columns(2)
    with col1:
        new_tieu_chi = st.text_input("Thêm Tiêu chí phụ cấp mới")
        if st.button("Thêm Tiêu Chí"):
            if new_tieu_chi.strip():
                conn = db.pool.get_connection()
                try:
                    conn.autocommit = False
                    cursor = conn.cursor()
                    cursor.execute("INSERT INTO dm_tieu_chi_phu_cap (ten_tieu_chi) VALUES (%s)", (new_tieu_chi.strip(),))
                    conn.commit()
                    st.success("✅ Thêm tiêu chí thành công!")
                    import time
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    conn.rollback()
                    st.error(f"❌ Lỗi: {e}")
                finally:
                    cursor.close()
                    conn.close()
            else:
                st.warning("⚠️ Vui lòng nhập tên tiêu chí!")

    with col2:
        new_tt_name = st.text_input("Tên Mức tải trọng (VD: 15T)")
        new_min = st.number_input("Tải trọng Min (Tấn)", min_value=0.0)
        new_max = st.number_input("Tải trọng Max (Tấn)", min_value=0.0)
        if st.button("Thêm Mức Tải Trọng"):
            if new_tt_name.strip():
                conn = db.pool.get_connection()
                try:
                    conn.autocommit = False
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT INTO dm_tai_trong_phu_cap (ten_hien_thi, tai_trong_min, tai_trong_max) VALUES (%s, %s, %s)", 
                        (new_tt_name.strip(), new_min, new_max)
                    )
                    conn.commit()
                    st.success("✅ Thêm mức tải trọng thành công!")
                    import time
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    conn.rollback()
                    st.error(f"❌ Lỗi: {e}")
                finally:
                    cursor.close()
                    conn.close()
            else:
                st.warning("⚠️ Vui lòng nhập tên mức tải trọng!")
# --- UI PHỤ: XÓA TIÊU CHÍ HOẶC TẢI TRỌNG ---
with st.expander("🗑️ Xóa Tiêu chí hoặc Mức tải trọng", expanded=False):
    st.warning("⚠️ Lưu ý: Khi xóa, toàn bộ dữ liệu tiền phụ cấp của Tiêu chí/Tải trọng này trong Ma trận sẽ bị xóa theo vĩnh viễn!")
    col_del1, col_del2 = st.columns(2)
    
    with col_del1:
        st.markdown("**1. Xóa Tiêu chí**")
        df_tc_del = db.execute_query("SELECT id, ten_tieu_chi FROM dm_tieu_chi_phu_cap ORDER BY ten_tieu_chi ASC")
        if isinstance(df_tc_del, pd.DataFrame) and not df_tc_del.empty:
            tc_del_dict = dict(zip(df_tc_del['id'], df_tc_del['ten_tieu_chi']))
            del_tc_id = st.selectbox("Chọn tiêu chí cần xóa", options=list(tc_del_dict.keys()), format_func=lambda x: tc_del_dict[x], key="del_tc_sel")
            
            if st.button("🗑️ Xác nhận Xóa Tiêu Chí", type="primary"):
                conn = db.pool.get_connection()
                try:
                    conn.autocommit = False
                    cursor = conn.cursor()
                    
                    cursor.execute("DELETE FROM dm_tieu_chi_phu_cap WHERE id = %s", (del_tc_id,))
                    
                    # Ràng buộc kiểm tra rowcount theo chuẩn dự án
                    if cursor.rowcount > 0:
                        import json
                        chi_tiet = json.dumps({"ten_tieu_chi_bi_xoa": tc_del_dict[del_tc_id]}, ensure_ascii=False)
                        
                        # Ghi Audit Log trực tiếp nếu không gọi được hàm từ audit_logger
                        cursor.execute("""
                            INSERT INTO audit_logs (phan_he, record_id, nguoi_thuc_hien, hanh_dong, chi_tiet) 
                            VALUES (%s, %s, %s, %s, %s)
                        """, ('QUAN_LY_PHU_CAP', del_tc_id, current_user, 'XOA_TIEU_CHI', chi_tiet))
                        
                        conn.commit()
                        st.success("✅ Đã xóa tiêu chí và dọn dẹp ma trận thành công!")
                        import time
                        time.sleep(1)
                        st.rerun()
                    else:
                        conn.rollback()
                        st.warning("⚠️ Không tìm thấy tiêu chí để xóa. Vui lòng thử lại!")
                        
                except Exception as e:
                    conn.rollback()
                    st.error(f"❌ Lỗi SQL: {e}")
                finally:
                    cursor.close()
                    conn.close()
        else:
            st.info("Chưa có dữ liệu tiêu chí.")

    with col_del2:
        st.markdown("**2. Xóa Mức Tải Trọng**")
        df_tt_del = db.execute_query("SELECT id, ten_hien_thi FROM dm_tai_trong_phu_cap ORDER BY tai_trong_min ASC")
        if isinstance(df_tt_del, pd.DataFrame) and not df_tt_del.empty:
            tt_del_dict = dict(zip(df_tt_del['id'], df_tt_del['ten_hien_thi']))
            del_tt_id = st.selectbox("Chọn tải trọng cần xóa", options=list(tt_del_dict.keys()), format_func=lambda x: tt_del_dict[x], key="del_tt_sel")
            
            if st.button("🗑️ Xác nhận Xóa Tải Trọng", type="primary"):
                conn = db.pool.get_connection()
                try:
                    conn.autocommit = False
                    cursor = conn.cursor()
                    
                    cursor.execute("DELETE FROM dm_tai_trong_phu_cap WHERE id = %s", (del_tt_id,))
                    
                    # Ràng buộc kiểm tra rowcount theo chuẩn dự án
                    if cursor.rowcount > 0:
                        import json
                        chi_tiet = json.dumps({"ten_tai_trong_bi_xoa": tt_del_dict[del_tt_id]}, ensure_ascii=False)
                        
                        # Ghi Audit Log
                        cursor.execute("""
                            INSERT INTO audit_logs (phan_he, record_id, nguoi_thuc_hien, hanh_dong, chi_tiet) 
                            VALUES (%s, %s, %s, %s, %s)
                        """, ('QUAN_LY_PHU_CAP', del_tt_id, current_user, 'XOA_TAI_TRONG', chi_tiet))
                        
                        conn.commit()
                        st.success("✅ Đã xóa mức tải trọng và dọn dẹp ma trận thành công!")
                        import time
                        time.sleep(1)
                        st.rerun()
                    else:
                        conn.rollback()
                        st.warning("⚠️ Không tìm thấy mức tải trọng để xóa. Vui lòng thử lại!")
                        
                except Exception as e:
                    conn.rollback()
                    st.error(f"❌ Lỗi SQL: {e}")
                finally:
                    cursor.close()
                    conn.close()
        else:
            st.info("Chưa có dữ liệu tải trọng.")