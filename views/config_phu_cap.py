import streamlit as st
import pandas as pd
import io
from hr_system_manager import update_phu_cap_matrix_transaction
from utils_core import import_excel_phu_cap_transaction

db = st.session_state.get('db')
current_user = st.session_state.get('username') or st.session_state.get('user', 'Admin')

if not db:
    st.error("⚠️ Lỗi kết nối Cơ sở dữ liệu.")
    st.stop()

st.markdown("### 💰 BẢNG CẤU HÌNH PHỤ CẤP SẢN LƯỢNG TÀI XẾ")
st.info("💡 Hướng dẫn: Click đúp vào ô số tiền để sửa trực tiếp (như dùng Excel). Nhấn nút LƯU ở dưới cùng để chốt dữ liệu.")

# 🔄 NÚT LÀM MỚI DỮ LIỆU TỔNG THỂ
col_rf1, col_rf2 = st.columns([6, 1])
with col_rf2:
    if st.button("🔄 Làm mới dữ liệu", use_container_width=True):
        st.rerun()

tab1, tab2 = st.tabs([
    "⚙️ 1. Cấu hình phụ cấp",
    "📥 2. Import file excel phụ cấp"
])

with tab1:
    @st.fragment
    def vung_thao_tac_config_phu_cap():
        try:
            df_tt = db.execute_query("SELECT id, ten_hien_thi FROM dm_tai_trong_phu_cap ORDER BY tai_trong_min ASC")
            df_tc = db.execute_query("SELECT id, ten_tieu_chi FROM dm_tieu_chi_phu_cap ORDER BY id ASC")
            df_mt = db.execute_query("SELECT tai_trong_id, tieu_chi_id, so_tien FROM ma_tran_phu_cap")
        except Exception as e:
            st.error(f"❌ Lỗi truy vấn dữ liệu từ Database: {str(e)}")
            return

        if isinstance(df_tt, pd.DataFrame) and isinstance(df_tc, pd.DataFrame) and not df_tt.empty and not df_tc.empty:
            matrix_data = []
            for _, tt in df_tt.iterrows():
                row_dict = {"Tải Trọng Xe": tt['ten_hien_thi']}
                for _, tc in df_tc.iterrows():
                    val = df_mt[(df_mt['tai_trong_id'] == tt['id']) & (df_mt['tieu_chi_id'] == tc['id'])] if isinstance(df_mt, pd.DataFrame) and not df_mt.empty else pd.DataFrame()
                    so_tien = float(val.iloc[0]['so_tien']) if not val.empty else 0.0
                    row_dict[tc['ten_tieu_chi']] = so_tien
                matrix_data.append(row_dict)

            df_matrix = pd.DataFrame(matrix_data)
            df_matrix.set_index("Tải Trọng Xe", inplace=True)
            
            # Button Download File Phụ Cấp Excel
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                df_matrix.to_excel(writer, sheet_name='Ma_Tran_Phu_Cap')
            st.download_button(
                label="⬇️ Download file phụ cấp excel",
                data=buffer.getvalue(),
                file_name="Danh_Sach_Phu_Cap.xlsx",
                mime="application/vnd.ms-excel",
                type="secondary"
            )
            
            an_dong_trong = st.checkbox("👁️ Ẩn các mức tải trọng chưa có phụ cấp (Giúp bảng gọn gàng hơn)", value=True)
            if an_dong_trong:
                df_matrix = df_matrix.loc[(df_matrix > 0).any(axis=1)]

            column_config = {
                col: st.column_config.NumberColumn(col, format="%d ₫", min_value=0)
                for col in df_matrix.columns
            }

            df_edited = st.data_editor(
                df_matrix,
                column_config=column_config,
                use_container_width=True,
                num_rows="fixed"
            )

            if st.button("💾 LƯU BẢNG PHỤ CẤP", type="primary"):
                with st.spinner("Đang đồng bộ dữ liệu vào hệ thống..."):
                    try:
                        is_ok, msg = update_phu_cap_matrix_transaction(db.pool, df_edited, current_user)
                        if is_ok:
                            st.success(msg)
                        else:
                            st.error(f"Lỗi: {msg}")
                    except Exception as ex:
                        st.error(f"❌ Lỗi hệ thống khi lưu: {str(ex)}")
        else:
            st.warning("⚠️ Chưa có dữ liệu Khai báo Tải trọng hoặc Tiêu chí. Vui lòng thêm trong Cài đặt chung trước!")

        with st.expander("➕ Thêm mới Tiêu chí hoặc Mức tải trọng", expanded=False):
            col1, col2 = st.columns(2)
            
            with col1:
                with st.form("form_add_tc", clear_on_submit=True):
                    new_tieu_chi = st.text_input("Thêm Tiêu chí phụ cấp mới*")
                    col_km1, col_km2 = st.columns(2)
                    new_km_min = col_km1.number_input("Cự ly Min (km)", min_value=0.0, value=0.0, step=1.0)
                    new_km_max = col_km2.number_input("Cự ly Max (km)", min_value=0.0, value=0.0, step=1.0)
                    
                    if st.form_submit_button("➕ Thêm Tiêu Chí", type="primary"):
                        if new_tieu_chi.strip():
                            conn = db.pool.get_connection()
                            try:
                                conn.autocommit = False
                                cursor = conn.cursor()
                                cursor.execute(
                                    "INSERT INTO dm_tieu_chi_phu_cap (ten_tieu_chi, km_min, km_max) VALUES (%s, %s, %s)",
                                    (new_tieu_chi.strip(), new_km_min, new_km_max)
                                )
                                conn.commit()
                                st.success("✅ Thêm tiêu chí thành công!")
                                import time
                                time.sleep(1.2)
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
                with st.form("form_add_tt", clear_on_submit=True):
                    new_tt_name = st.text_input("Tên Mức tải trọng (VD: 15T)*")
                    new_min = st.number_input("Tải trọng Min (Tấn)", min_value=0.0)
                    new_max = st.number_input("Tải trọng Max (Tấn)", min_value=0.0)
                    
                    if st.form_submit_button("➕ Thêm Mức Tải Trọng", type="primary"):
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
                                time.sleep(1.2)
                                st.rerun()
                            except Exception as e:
                                conn.rollback()
                                st.error(f"❌ Lỗi: {e}")
                            finally:
                                cursor.close()
                                conn.close()
                        else:
                            st.warning("⚠️ Vui lòng nhập tên mức tải trọng!")

        with st.expander("✏️ Sửa Tiêu chí hoặc Mức tải trọng", expanded=False):
            @st.fragment
            def vung_thao_tac_edit_tieu_chi():
                col_edit1, col_edit2 = st.columns(2)
                
                with col_edit1:
                    st.markdown("**1. Sửa Tiêu chí Phụ cấp**")
                    try:
                        df_tc_edit = db.execute_query("SELECT id, ten_tieu_chi, km_min, km_max FROM dm_tieu_chi_phu_cap ORDER BY ten_tieu_chi ASC")
                    except Exception:
                        df_tc_edit = pd.DataFrame()
                    
                    if isinstance(df_tc_edit, pd.DataFrame) and not df_tc_edit.empty:
                        tc_edit_dict = {int(r['id']): r for _, r in df_tc_edit.iterrows()}
                        
                        tc_format = {
                            k: f"{v['ten_tieu_chi']} ({float(v.get('km_min') or 0):.1f} - {float(v.get('km_max') or 0):.1f} km)"
                            for k, v in tc_edit_dict.items()
                        }
                        
                        edit_tc_id = st.selectbox("Chọn tiêu chí cần sửa", options=list(tc_edit_dict.keys()),
                                                  format_func=lambda x: tc_format[x], key="edit_tc_sel", index= None,placeholder="-- Vui lòng chọn tiêu chí --")
                        
                        if edit_tc_id:
                            curr_tc = tc_edit_dict[edit_tc_id]
                            edit_tc_name = st.text_input("Tên Tiêu chí mới*", value=curr_tc['ten_tieu_chi'], key="edit_tc_name")
                            
                            c_km1, c_km2 = st.columns(2)
                            edit_km_min = c_km1.number_input("Cự ly Min mới (km)", value=float(curr_tc.get('km_min') or 0.0), step=1.0, key="edit_km_min")
                            edit_km_max = c_km2.number_input("Cự ly Max mới (km)", value=float(curr_tc.get('km_max') or 0.0), step=1.0, key="edit_km_max")
                            
                            if st.button("✏️ Cập nhật Tiêu Chí", type="primary"):
                                if edit_tc_name.strip():
                                    conn = db.pool.get_connection()
                                    try:
                                        conn.autocommit = False
                                        cursor = conn.cursor()
                                        
                                        cursor.execute(
                                            "UPDATE dm_tieu_chi_phu_cap SET ten_tieu_chi = %s, km_min = %s, km_max = %s WHERE id = %s",
                                            (edit_tc_name.strip(), edit_km_min, edit_km_max, edit_tc_id)
                                        )
                                        
                                        if cursor.rowcount >= 0:
                                            import json
                                            chi_tiet = json.dumps({"id_sua": edit_tc_id, "ten_cu": curr_tc['ten_tieu_chi'], "ten_moi": edit_tc_name.strip()}, ensure_ascii=False)
                                            
                                            cursor.execute("""
                                                INSERT INTO audit_logs (phan_he, record_id, nguoi_thuc_hien, hanh_dong, chi_tiet) 
                                                VALUES (%s, %s, %s, %s, %s)
                                            """, ('QUAN_LY_PHU_CAP', edit_tc_id, current_user, 'SUA_TIEU_CHI', chi_tiet))
                                            
                                            conn.commit()
                                            st.success("✅ Cập nhật tiêu chí thành công!")
                                            for k in ["edit_tc_sel", "edit_tc_name", "edit_km_min", "edit_km_max"]:
                                                if k in st.session_state: del st.session_state[k]
                                            import time
                                            time.sleep(1)
                                            st.rerun()
                                        else:
                                            conn.rollback()
                                            st.warning("⚠️ Lỗi không xác định khi cập nhật.")
                                    except Exception as e:
                                        conn.rollback()
                                        st.error(f"❌ Lỗi SQL: {e}")
                                    finally:
                                        cursor.close()
                                        conn.close()
                                else:
                                    st.warning("⚠️ Vui lòng không để trống tên tiêu chí!")
                    else:
                        st.info("Chưa có dữ liệu tiêu chí để sửa.")
                
                with col_edit2:
                    st.markdown("**2. Sửa Mức Tải Trọng**")
                    try:
                        df_tt_edit = db.execute_query("SELECT id, ten_hien_thi, tai_trong_min, tai_trong_max FROM dm_tai_trong_phu_cap ORDER BY tai_trong_min ASC")
                    except Exception:
                        df_tt_edit = pd.DataFrame()
                    
                    if isinstance(df_tt_edit, pd.DataFrame) and not df_tt_edit.empty:
                        tt_edit_dict = {int(r['id']): r for _, r in df_tt_edit.iterrows()}
                        
                        edit_tt_id = st.selectbox("Chọn tải trọng cần sửa", options=list(tt_edit_dict.keys()),
                                                   format_func=lambda x: tt_edit_dict[x]['ten_hien_thi'], key="edit_tt_sel",index=None, placeholder="-- Vui lòng chọn tải trọng --")
                        
                        if edit_tt_id:
                            curr_tt = tt_edit_dict[edit_tt_id]
                            edit_tt_name = st.text_input("Tên Mức tải trọng mới*", value=curr_tt['ten_hien_thi'], key="edit_tt_name")
                            
                            c_tt1, c_tt2 = st.columns(2)
                            edit_tt_min = c_tt1.number_input("Tải trọng Min mới (Tấn)", value=float(curr_tt.get('tai_trong_min') or 0.0), step=0.1, key="edit_tt_min")
                            edit_tt_max = c_tt2.number_input("Tải trọng Max mới (Tấn)", value=float(curr_tt.get('tai_trong_max') or 0.0), step=0.1, key="edit_tt_max")
                            
                            if st.button("✏️ Cập nhật Tải Trọng", type="primary"):
                                if edit_tt_name.strip():
                                    conn = db.pool.get_connection()
                                    try:
                                        conn.autocommit = False
                                        cursor = conn.cursor()
                                        
                                        cursor.execute(
                                            "UPDATE dm_tai_trong_phu_cap SET ten_hien_thi = %s, tai_trong_min = %s, tai_trong_max = %s WHERE id = %s",
                                            (edit_tt_name.strip(), edit_tt_min, edit_tt_max, edit_tt_id)
                                        )
                                        
                                        if cursor.rowcount >= 0:
                                            import json
                                            chi_tiet = json.dumps({"id_sua": edit_tt_id, "ten_cu": curr_tt['ten_hien_thi'], "ten_moi": edit_tt_name.strip()}, ensure_ascii=False)
                                            
                                            cursor.execute("""
                                                INSERT INTO audit_logs (phan_he, record_id, nguoi_thuc_hien, hanh_dong, chi_tiet) 
                                                VALUES (%s, %s, %s, %s, %s)
                                            """, ('QUAN_LY_PHU_CAP', edit_tt_id, current_user, 'SUA_TAI_TRONG', chi_tiet))
                                            
                                            conn.commit()
                                            st.success("✅ Cập nhật mức tải trọng thành công!")
                                            for k in ["edit_tt_sel", "edit_tt_name", "edit_tt_min", "edit_tt_max"]:
                                                if k in st.session_state: del st.session_state[k]
                                            import time
                                            time.sleep(1)
                                            st.rerun()
                                    except Exception as e:
                                        conn.rollback()
                                        st.error(f"❌ Lỗi SQL: {e}")
                                    finally:
                                        cursor.close()
                                        conn.close()
                                else:
                                    st.warning("⚠️ Vui lòng không để trống tên mức tải trọng!")
                    else:
                        st.info("Chưa có dữ liệu tải trọng để sửa.")
            vung_thao_tac_edit_tieu_chi()

        with st.expander("🗑️ Xóa Tiêu chí hoặc Mức tải trọng", expanded=False):
            st.warning("⚠️ Lưu ý: Khi xóa, toàn bộ dữ liệu tiền phụ cấp của Tiêu chí/Tải trọng này trong Ma trận sẽ bị xóa theo vĩnh viễn!")
            @st.fragment
            def vung_thao_tac_delete_tieu_chi():
                col_del1, col_del2 = st.columns(2)
                
                with col_del1:
                    st.markdown("**1. Xóa Tiêu chí**")
                    try:
                        df_tc_del = db.execute_query("SELECT id, ten_tieu_chi, km_min, km_max FROM dm_tieu_chi_phu_cap ORDER BY ten_tieu_chi ASC")
                    except Exception:
                        df_tc_del = pd.DataFrame()
                        
                    if isinstance(df_tc_del, pd.DataFrame) and not df_tc_del.empty:
                        tc_del_dict = {
                            int(r['id']): f"{r['ten_tieu_chi']} ({float(r.get('km_min', 0)):.1f} - {float(r.get('km_max', 0)):.1f} km)"
                            for _, r in df_tc_del.iterrows()
                        }
                        
                        del_tc_id = st.selectbox("Chọn tiêu chí cần xóa", options=list(tc_del_dict.keys()),
                                                 format_func=lambda x: tc_del_dict[x], key="del_tc_sel", index=None, placeholder="-- Vui lòng chọn tiêu chí --")
                        
                        if st.button("🗑️ Xác nhận Xóa Tiêu Chí", type="primary"):
                            conn = db.pool.get_connection()
                            try:
                                conn.autocommit = False
                                cursor = conn.cursor()
                                
                                cursor.execute("DELETE FROM dm_tieu_chi_phu_cap WHERE id = %s", (del_tc_id,))
                                
                                if cursor.rowcount > 0:
                                    import json
                                    chi_tiet = json.dumps({"ten_tieu_chi_bi_xoa": tc_del_dict[del_tc_id]}, ensure_ascii=False)
                                    
                                    cursor.execute("""
                                        INSERT INTO audit_logs (phan_he, record_id, nguoi_thuc_hien, hanh_dong, chi_tiet) 
                                        VALUES (%s, %s, %s, %s, %s)
                                    """, ('QUAN_LY_PHU_CAP', del_tc_id, current_user, 'XOA_TIEU_CHI', chi_tiet))
                                    
                                    conn.commit()
                                    st.success("✅ Đã xóa tiêu chí và dọn dẹp ma trận thành công!")
                                    if "del_tc_sel" in st.session_state: del st.session_state["del_tc_sel"]
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
                    try:
                        df_tt_del = db.execute_query("SELECT id, ten_hien_thi FROM dm_tai_trong_phu_cap ORDER BY tai_trong_min ASC")
                    except Exception:
                        df_tt_del = pd.DataFrame()
                        
                    if isinstance(df_tt_del, pd.DataFrame) and not df_tt_del.empty:
                        tt_del_dict = dict(zip(df_tt_del['id'], df_tt_del['ten_hien_thi']))
                        del_tt_id = st.selectbox("Chọn tải trọng cần xóa", options=list(tt_del_dict.keys()),
                                                 format_func=lambda x: tt_del_dict[x], key="del_tt_sel", index=None, placeholder="-- Vui lòng chọn tải trọng --")
                        
                        if st.button("🗑️ Xác nhận Xóa Tải Trọng", type="primary"):
                            conn = db.pool.get_connection()
                            try:
                                conn.autocommit = False
                                cursor = conn.cursor()
                                
                                cursor.execute("DELETE FROM dm_tai_trong_phu_cap WHERE id = %s", (del_tt_id,))
                                
                                if cursor.rowcount > 0:
                                    import json
                                    chi_tiet = json.dumps({"ten_tai_trong_bi_xoa": tt_del_dict[del_tt_id]}, ensure_ascii=False)
                                    
                                    cursor.execute("""
                                        INSERT INTO audit_logs (phan_he, record_id, nguoi_thuc_hien, hanh_dong, chi_tiet) 
                                        VALUES (%s, %s, %s, %s, %s)
                                    """, ('QUAN_LY_PHU_CAP', del_tt_id, current_user, 'XOA_TAI_TRONG', chi_tiet))
                                    
                                    conn.commit()
                                    st.success("✅ Đã xóa mức tải trọng và dọn dẹp ma trận thành công!")
                                    if "del_tt_sel" in st.session_state: del st.session_state["del_tt_sel"]
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
            vung_thao_tac_delete_tieu_chi()

    vung_thao_tac_config_phu_cap()

with tab2:
    st.markdown("#### 📥 Import Bảng Phụ Cấp Sản Lượng (Excel)")
    with st.form("form_import_phu_cap_tab2", clear_on_submit=True):
        uploaded_file = st.file_uploader("Kéo thả file Excel Ma Trận Phụ Cấp vào đây (.xlsx)", type=['xlsx'])
        is_submit = st.form_submit_button("🚀 Thực thi Import Dữ Liệu", type="primary", use_container_width=True)
        
        if is_submit:
            if not uploaded_file:
                st.warning("⚠️ Vui lòng tải lên một file Excel!")
            else:
                # 📊 KHU VỰC HIỂN THỊ TIẾN TRÌNH CHO NGƯỜI DÙNG
                progress_text = st.empty()
                progress_bar = st.progress(0)
                
                try:
                    progress_text.text("⏳ Đang đọc cấu trúc file Excel...")
                    progress_bar.progress(25)
                    
                    df_import = pd.read_excel(uploaded_file)
                    
                    progress_text.text("⏳ Đang phân tích dữ liệu ma trận và kiểm tra Database...")
                    progress_bar.progress(50)
                    
                    success, msg = import_excel_phu_cap_transaction(db.pool, df_import, current_user)
                    
                    progress_bar.progress(100)
                    progress_text.text("🎉 Hoàn tất quá trình đồng bộ!")
                    
                    if success:
                        st.success(f"✅ {msg}")
                        st.balloons()
                    else:
                        st.error(f"❌ Lỗi SQL: {msg}")
                except Exception as ex:
                    progress_bar.empty()
                    progress_text.empty()
                    st.error(f"❌ Lỗi đọc file Excel hoặc xử lý dữ liệu: {str(ex)}")