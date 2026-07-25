import streamlit as st
import pandas as pd
from audit_logger import ghi_log_he_thong

def save_khach_hang_transaction(db_pool, action, kh_data, kh_id, current_user):
    """
    Thực hiện Thêm / Sửa / Xóa Khách hàng với Transaction an toàn và Audit Log.
    action: 'CREATE', 'UPDATE', 'DELETE'
    kh_data: tuple chứa (ten_khach_hang, ma_khach_hang, so_dien_thoai, ma_so_thue, dia_chi)
    """
    connection = None
    cursor = None
    try:
        connection = db_pool.get_connection()
        connection.autocommit = False  # BẮT BUỘC BẬT TRANSACTION THEO QUY CHUẨN DỰ ÁN
        cursor = connection.cursor()

        if action == 'CREATE':
            sql = """
                INSERT INTO khach_hang (ten_khach_hang, ma_khach_hang, so_dien_thoai, ma_so_thue, dia_chi)
                VALUES (%s, %s, %s, %s, %s)
            """
            cursor.execute(sql, kh_data)
            if cursor.rowcount <= 0:
                raise Exception("Không thể thêm mới khách hàng vào CSDL.")
            new_id = cursor.lastrowid
            
            # Ghi vết hệ thống (Audit Trail)
            ghi_log_he_thong(
                cursor, 
                phan_he="QUAN_LY_KHACH_HANG", 
                record_id=new_id, 
                nguoi_thuc_hien=current_user, 
                hanh_dong="TAO_MOI", 
                chi_tiet=str(kh_data)
            )

        elif action == 'UPDATE':
            sql = """
                UPDATE khach_hang 
                SET ten_khach_hang = %s, ma_khach_hang = %s, so_dien_thoai = %s, ma_so_thue = %s, dia_chi = %s
                WHERE id = %s
            """
            cursor.execute(sql, (*kh_data, kh_id))
            if cursor.rowcount <= 0:
                raise Exception(f"Không tìm thấy khách hàng ID #{kh_id} hoặc dữ liệu không có sự thay đổi.")
            
            # Ghi vết hệ thống (Audit Trail)
            ghi_log_he_thong(
                cursor, 
                phan_he="QUAN_LY_KHACH_HANG", 
                record_id=kh_id, 
                nguoi_thuc_hien=current_user, 
                hanh_dong="CAP_NHAT", 
                chi_tiet=str(kh_data)
            )

        elif action == 'DELETE':
            sql = "DELETE FROM khach_hang WHERE id = %s"
            cursor.execute(sql, (kh_id,))
            if cursor.rowcount <= 0:
                raise Exception(f"Không tìm thấy khách hàng ID #{kh_id} để xóa.")
            
            # Ghi vết hệ thống (Audit Trail)
            ghi_log_he_thong(
                cursor, 
                phan_he="QUAN_LY_KHACH_HANG", 
                record_id=kh_id, 
                nguoi_thuc_hien=current_user, 
                hanh_dong="XOA", 
                chi_tiet=f"Đã xóa khách hàng ID #{kh_id}"
            )

        connection.commit()
        return True, "Thành công"

    except Exception as e:
        if connection:
            connection.rollback()  # HOÀN TÁC GIAO DỊCH KHI CÓ LỖI XẢY RA
        return False, str(e)
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def render_quan_ly_khach_hang():
    db = st.session_state.get('db')
    current_user = st.session_state.get('username', 'Admin')

    if not db:
        st.error("⚠️ Lỗi kết nối Cơ sở dữ liệu.")
        return

    st.markdown("<h3 style='text-align: center; color: #0b5394;'>🏢 PHÂN HỆ QUẢN LÝ KHÁCH HÀNG & ĐỐI TÁC VẬN TẢI</h3>", unsafe_allow_html=True)
    st.divider()

    # Tạo 2 Tab chức năng chính
    tab_danh_sach, tab_form = st.tabs(["📋 Danh sách khách hàng", "✍️ Thêm mới / Cập nhật khách hàng"])

    # ==========================================
    # TAB 1: DANH SÁCH KHÁCH HÀNG & XÓA AN TOÀN
    # ==========================================
    with tab_danh_sach:
        st.markdown("##### 📊 Bảng danh bạ khách hàng và thông tin pháp lý")
        
        sql_load = "SELECT id, ma_khach_hang, ten_khach_hang, so_dien_thoai, ma_so_thue, dia_chi FROM khach_hang ORDER BY id DESC"
        df_kh = db.execute_query(sql_load)
        
        if isinstance(df_kh, pd.DataFrame) and not df_kh.empty:
            search_query = st.text_input("🔍 Tìm kiếm nhanh theo tên hoặc mã số thuế:", placeholder="Nhập tên công ty hoặc MST...")
            
            df_hien_thi = df_kh.copy()
            if search_query:
                mask = df_hien_thi['ten_khach_hang'].str.contains(search_query, case=False, na=False) | \
                       df_hien_thi['ma_so_thue'].str.contains(search_query, case=False, na=False) | \
                       df_hien_thi['ma_khach_hang'].str.contains(search_query, case=False, na=False)
                df_hien_thi = df_hien_thi[mask]

            df_display_cols = df_hien_thi.rename(columns={
                'id': 'ID',
                'ma_khach_hang': 'Mã KH',
                'ten_khach_hang': 'Tên Đơn Vị / Khách Hàng',
                'so_dien_thoai': 'Số Điện Thoại',
                'ma_so_thue': 'Mã Số Thuế',
                'dia_chi': 'Địa Chỉ Trụ Sở'
            })
            
            st.dataframe(df_display_cols, use_container_width=True, hide_index=True)
            st.caption(f"Hiển thị tổng số {len(df_display_cols)} khách hàng.")
            
            st.divider()
            st.markdown("##### 🗑️ Thao tác xóa khách hàng")
            
            col_del1, col_del2 = st.columns([2, 1])
            with col_del1:
                kh_options = {row['id']: f"#{row['id']} - {row['ten_khach_hang']} (MST: {row['ma_so_thue'] if pd.notna(row['ma_so_thue']) else 'Trống'})" for _, row in df_kh.iterrows()}
                selected_del_id = st.selectbox("Chọn khách hàng cần xóa:", options=list(kh_options.keys()), format_func=lambda x: kh_options[x], key="select_del_kh")
            
            with col_del2:
                st.markdown("<br>", unsafe_allow_html=True)
                confirm_del = st.checkbox("Xác nhận muốn xóa", key="chk_confirm_del_kh")
                if st.button("🗑️ Xóa Khách Hàng", type="primary", use_container_width=True):
                    if not confirm_del:
                        st.error("⚠️ Vui lòng tích chọn 'Xác nhận muốn xóa'.")
                    else:
                        success, msg = save_khach_hang_transaction(db.pool, 'DELETE', None, selected_del_id, current_user)
                        if success:
                            st.success("✅ Đã xóa khách hàng thành công!")
                            import time; time.sleep(1)
                            st.rerun()
                        else:
                            st.error(f"❌ Lỗi khi xóa: {msg}")
        else:
            st.info("ℹ️ Chưa có dữ liệu khách hàng nào trong hệ thống.")

    # ==========================================
    # TAB 2: THÊM MỚI / SỬA THÔNG TIN KHÁCH HÀNG (FORM)
    # ==========================================
    with tab_form:
        st.markdown("##### 📝 Form khai báo hồ sơ đối tác khách hàng")
        
        mode = st.radio("Lựa chọn chế độ:", ["Thêm mới khách hàng", "Cập nhật khách hàng có sẵn"], horizontal=True, key="radio_mode_kh")
        
        target_id = None
        default_val = {"ten": "", "ma": "", "sdt": "", "mst": "", "diachi": ""}
        
        if mode == "Cập nhật khách hàng có sẵn":
            df_all = db.execute_query("SELECT id, ten_khach_hang, ma_khach_hang, so_dien_thoai, ma_so_thue, dia_chi FROM khach_hang ORDER BY id DESC")
            if isinstance(df_all, pd.DataFrame) and not df_all.empty:
                edit_opts = {r['id']: f"#{r['id']} - {r['ten_khach_hang']} (MST: {r['ma_so_thue']})" for _, r in df_all.iterrows()}
                target_id = st.selectbox("Chọn khách hàng cần chỉnh sửa:", options=list(edit_opts.keys()), format_func=lambda x: edit_opts[x], key="sel_edit_kh")
                
                if target_id:
                    row_data = df_all[df_all['id'] == target_id].iloc[0]
                    default_val = {
                        "ten": row_data['ten_khach_hang'] or "",
                        "ma": row_data['ma_khach_hang'] or "",
                        "sdt": row_data['so_dien_thoai'] or "",
                        "mst": row_data['ma_so_thue'] or "",
                        "diachi": row_data['dia_chi'] or ""
                    }
            else:
                st.warning("⚠️ Không có dữ liệu khách hàng để cập nhật.")
                return

        with st.form("form_action_khach_hang"):
            c1, c2 = st.columns(2)
            ten_kh = c1.text_input("Tên đơn vị / Tên công ty (*)", value=default_val["ten"], placeholder="VD: CÔNG TY TNHH ABC")
            ma_kh = c2.text_input("Mã khách hàng (Unique)", value=default_val["ma"], placeholder="VD: KH_3901234567")
            
            c3, c4 = st.columns(2)
            sdt_kh = c3.text_input("Số điện thoại liên hệ", value=default_val["sdt"], placeholder="VD: 0988xxxxxx")
            mst_kh = c4.text_input("Mã số thuế (Xuất hóa đơn)", value=default_val["mst"], placeholder="VD: 3901229506")
            
            dia_chi_kh = st.text_area("Địa chỉ trụ sở đầy đủ", value=default_val["diachi"], placeholder="Nhập địa chỉ đăng ký kinh doanh...")
            
            submit_label = "💾 Lưu thay đổi thông tin" if mode == "Cập nhật khách hàng có sẵn" else "🚀 Thêm mới hồ sơ khách hàng"
            
            if st.form_submit_button(submit_label, type="primary", use_container_width=True):
                if not ten_kh.strip():
                    st.error("⚠️ Tên đơn vị / Khách hàng không được để trống!")
                else:
                    data_tuple = (
                        ten_kh.strip(), 
                        ma_kh.strip() if ma_kh.strip() else None, 
                        sdt_kh.strip() if sdt_kh.strip() else None, 
                        mst_kh.strip() if mst_kh.strip() else None, 
                        dia_chi_kh.strip() if dia_chi_kh.strip() else None
                    )
                    
                    if mode == "Thêm mới khách hàng":
                        success, msg = save_khach_hang_transaction(db.pool, 'CREATE', data_tuple, None, current_user)
                        action_name = "Thêm mới"
                    else:
                        success, msg = save_khach_hang_transaction(db.pool, 'UPDATE', data_tuple, target_id, current_user)
                        action_name = "Cập nhật"
                        
                    if success:
                        st.success(f"✅ {action_name} hồ sơ khách hàng thành công!")
                        st.balloons()
                        import time; time.sleep(1)
                        st.rerun()
                    else:
                        st.error(f"❌ Lỗi thực thi cơ sở dữ liệu: {msg}")

# 🚀 QUAN TRỌNG: Gọi hàm thực thi trực tiếp ở ngoài cùng để Streamlit nhận diện và hiển thị giao diện
if __name__ == "__main__":
    render_quan_ly_khach_hang()
else:
    render_quan_ly_khach_hang()