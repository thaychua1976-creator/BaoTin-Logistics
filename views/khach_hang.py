import streamlit as st
import pandas as pd
from audit_logger import ghi_log_he_thong

# ==========================================
# HÀM HIỂN THỊ POPUP LỖI GIỮA MÀN HÌNH
# ==========================================
@st.dialog("⚠️ CẢNH BÁO HỆ THỐNG")
def show_error_popup(message):
    st.error(message, icon="🚨")
    st.info("Vui lòng kiểm tra lại danh sách hoặc sử dụng Mã số thuế khác.")
    if st.button("Đã hiểu & Đóng", type="primary", use_container_width=True):
        st.rerun()

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
            # 1. KIỂM TRA TRÙNG LẶP MÃ SỐ THUẾ TRƯỚC KHI THÊM
            ma_so_thue_input = kh_data[3]
            cursor.execute("SELECT id FROM khach_hang WHERE ma_so_thue = %s", (ma_so_thue_input,))
            if cursor.fetchone():
                raise Exception(f"Khách hàng với mã số thuế '{ma_so_thue_input}' đã tồn tại trong database.")

            # 2. THỰC HIỆN THÊM MỚI
            sql = """
                INSERT INTO khach_hang (ten_khach_hang, ma_khach_hang, so_dien_thoai, ma_so_thue, dia_chi)
                VALUES (%s, %s, %s, %s, %s)
            """
            cursor.execute(sql, kh_data)
            if cursor.rowcount <= 0:
                raise Exception("Không thể thêm mới khách hàng vào CSDL.")
            new_id = cursor.lastrowid
            
            # 3. Ghi vết hệ thống (Audit Trail)
            ghi_log_he_thong(
                cursor, 
                phan_he="QUAN_LY_KHACH_HANG", 
                record_id=new_id, 
                nguoi_thuc_hien=current_user, 
                hanh_dong="TAO_MOI", 
                chi_tiet=str(kh_data)
            )

        elif action == 'UPDATE':
            # 1. KIỂM TRA TRÙNG LẶP MÃ SỐ THUẾ (Bỏ qua ID của chính khách hàng đang sửa)
            ma_so_thue_input = kh_data[3]
            cursor.execute("SELECT id FROM khach_hang WHERE ma_so_thue = %s AND id != %s", (ma_so_thue_input, kh_id))
            if cursor.fetchone():
                raise Exception(f"Khách hàng với mã số thuế '{ma_so_thue_input}' đã tồn tại trong database.")

            # 2. THỰC HIỆN CẬP NHẬT
            sql = """
                UPDATE khach_hang 
                SET ten_khach_hang = %s, ma_khach_hang = %s, so_dien_thoai = %s, ma_so_thue = %s, dia_chi = %s
                WHERE id = %s
            """
            cursor.execute(sql, (*kh_data, kh_id))
            if cursor.rowcount <= 0:
                raise Exception(f"Không tìm thấy khách hàng ID #{kh_id} hoặc dữ liệu không có sự thay đổi.")
            
            # 3. Ghi vết hệ thống (Audit Trail)
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

    tab_danh_sach, tab_form = st.tabs(["📋 Danh sách khách hàng", "✍️ Thêm mới / Cập nhật khách hàng"])

    # ==========================================
    # TAB 1: DANH SÁCH KHÁCH HÀNG & XÓA AN TOÀN
    # ==========================================
    with tab_danh_sach:
        st.markdown("##### 📊 Bảng danh bạ khách hàng và thông tin pháp lý")
        
        sql_load = "SELECT id, ma_khach_hang, ten_khach_hang, so_dien_thoai, ma_so_thue, dia_chi FROM khach_hang ORDER BY id ASC"
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
                            show_error_popup(msg)
        else:
            st.info("ℹ️ Chưa có dữ liệu khách hàng nào trong hệ thống.")

    # ==========================================
    # TAB 2: THÊM MỚI / SỬA THÔNG TIN KHÁCH HÀNG
    # ==========================================
    with tab_form:
        st.markdown("##### 📝 Form khai báo hồ sơ đối tác khách hàng")
        
        mode = st.radio("Lựa chọn chế độ:", ["Thêm mới khách hàng", "Cập nhật khách hàng có sẵn"], horizontal=True, key="radio_mode_kh")
        
        # -------------------------------------------------------------
        # CHẾ ĐỘ 1: THÊM MỚI (Real-time Auto Generate KH_MST)
        # -------------------------------------------------------------
        if mode == "Thêm mới khách hàng":
            c1, c2 = st.columns(2)
            ten_kh_new = c1.text_input("Tên đơn vị / Tên công ty (*)", placeholder="Bắt buộc nhập")
            mst_kh_new = c2.text_input("Mã số thuế (*) (Xuất hóa đơn)", placeholder="Bắt buộc nhập")
            
            auto_ma_kh = f"KH_{mst_kh_new.strip()}" if mst_kh_new.strip() else ""
            
            c3, c4 = st.columns(2)
            ma_kh_new = c3.text_input("Mã khách hàng (*)", value=auto_ma_kh, placeholder="Hệ thống tự tạo KH_MãSốThuế")
            sdt_kh_new = c4.text_input("Số điện thoại liên hệ", placeholder="VD: 0988xxxxxx")
            
            dia_chi_kh_new = st.text_area("Địa chỉ trụ sở đầy đủ", placeholder="Nhập địa chỉ đăng ký kinh doanh...")
            
            if st.button("🚀 Thêm mới hồ sơ khách hàng", type="primary", use_container_width=True):
                missing_fields = []
                if not mst_kh_new.strip(): missing_fields.append("Mã số thuế")
                if not ten_kh_new.strip(): missing_fields.append("Tên đơn vị / Tên công ty")
                if not ma_kh_new.strip(): missing_fields.append("Mã khách hàng")
                
                if missing_fields:
                    st.error(f"⚠️ Thiếu thông tin bắt buộc! Vui lòng nhập bổ sung: **{', '.join(missing_fields)}**")
                else:
                    data_tuple = (
                        ten_kh_new.strip(), 
                        ma_kh_new.strip(), 
                        sdt_kh_new.strip() if sdt_kh_new.strip() else None, 
                        mst_kh_new.strip(), 
                        dia_chi_kh_new.strip() if dia_chi_kh_new.strip() else None
                    )
                    
                    success, msg = save_khach_hang_transaction(db.pool, 'CREATE', data_tuple, None, current_user)
                    if success:
                        st.success("✅ Thêm mới hồ sơ khách hàng thành công!")
                        st.balloons()
                        import time; time.sleep(1)
                        st.rerun()
                    else:
                        # GỌI POPUP LỖI Ở ĐÂY
                        show_error_popup(msg)

        # -------------------------------------------------------------
        # CHẾ ĐỘ 2: CẬP NHẬT (Sử dụng st.form)
        # -------------------------------------------------------------
        else:
            df_all = db.execute_query("SELECT id, ten_khach_hang, ma_khach_hang, so_dien_thoai, ma_so_thue, dia_chi FROM khach_hang ORDER BY id DESC")
            if isinstance(df_all, pd.DataFrame) and not df_all.empty:
                edit_opts = {r['id']: f"#{r['id']} - {r['ten_khach_hang']} (MST: {r['ma_so_thue']})" for _, r in df_all.iterrows()}
                target_id = st.selectbox("Chọn khách hàng cần chỉnh sửa:", options=list(edit_opts.keys()), format_func=lambda x: edit_opts[x], key="sel_edit_kh")
                
                if target_id:
                    row_data = df_all[df_all['id'] == target_id].iloc[0]
                    
                    with st.form("form_update_khach_hang"):
                        c1, c2 = st.columns(2)
                        ten_kh_edit = c1.text_input("Tên đơn vị / Tên công ty (*)", value=row_data['ten_khach_hang'] or "")
                        mst_kh_edit = c2.text_input("Mã số thuế (*) (Xuất hóa đơn)", value=row_data['ma_so_thue'] or "")
                        
                        c3, c4 = st.columns(2)
                        ma_kh_edit = c3.text_input("Mã khách hàng (*)", value=row_data['ma_khach_hang'] or "")
                        sdt_kh_edit = c4.text_input("Số điện thoại liên hệ", value=row_data['so_dien_thoai'] or "")
                        
                        dia_chi_kh_edit = st.text_area("Địa chỉ trụ sở đầy đủ", value=row_data['dia_chi'] or "")
                        
                        if st.form_submit_button("💾 Lưu thay đổi thông tin", type="primary", use_container_width=True):
                            missing_fields = []
                            if not mst_kh_edit.strip(): missing_fields.append("Mã số thuế")
                            if not ten_kh_edit.strip(): missing_fields.append("Tên đơn vị / Tên công ty")
                            if not ma_kh_edit.strip(): missing_fields.append("Mã khách hàng")
                            
                            if missing_fields:
                                st.error(f"⚠️ Thiếu thông tin bắt buộc! Vui lòng nhập bổ sung: **{', '.join(missing_fields)}**")
                            else:
                                data_tuple = (
                                    ten_kh_edit.strip(), 
                                    ma_kh_edit.strip(), 
                                    sdt_kh_edit.strip() if sdt_kh_edit.strip() else None, 
                                    mst_kh_edit.strip(), 
                                    dia_chi_kh_edit.strip() if dia_chi_kh_edit.strip() else None
                                )
                                
                                success, msg = save_khach_hang_transaction(db.pool, 'UPDATE', data_tuple, target_id, current_user)
                                if success:
                                    st.success("✅ Cập nhật hồ sơ khách hàng thành công!")
                                    import time; time.sleep(1)
                                    st.rerun()
                                else:
                                    # GỌI POPUP LỖI Ở ĐÂY
                                    show_error_popup(msg)
            else:
                st.warning("⚠️ Không có dữ liệu khách hàng để cập nhật.")

if __name__ == "__main__":
    render_quan_ly_khach_hang()
else:
    render_quan_ly_khach_hang()