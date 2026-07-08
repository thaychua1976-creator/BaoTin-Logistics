import streamlit as st
import pandas as pd
import datetime, io, time, math
#from st_aggrid import AgGrid, GridOptionsBuilder

from global_func import  save_vehicle_transaction, delete_vehicle_transaction

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

########
db = st.session_state['db']
tab1, tab2, tab3, tab4 = st.tabs(["📋 Danh sách đội xe", "➕ Thêm xe mới", "🔧 Sửa/Xoá xe", "🚨 Cảnh báo pháp lý toàn diện"])



# Tải danh sách tài xế để làm danh mục gán cố định
df_all_tx = db.execute_query("SELECT id, ho_ten FROM nhan_vien WHERE loai_nhan_vien IN ('Tai_Chinh', 'Tai_Phu') AND trang_thai='Dang_Lam_Viec'")
tx_dict = {row['id']: row['ho_ten'] for _, row in df_all_tx.iterrows()} if isinstance(df_all_tx, pd.DataFrame) and not df_all_tx.empty else {}

### Danh sách đội xe
with tab1:
    try:
        sql_xe_list = """
            SELECT 
                x.id AS 'Mã', x.nhan_hieu_xe AS 'Nhãn Hiệu', x.bien_so_xe AS 'Biển Số', 
                CAST(x.tai_trong_thiet_ke AS FLOAT) AS 'Tải Trọng (Tấn)', 
                CAST(x.dung_tich_cbm AS FLOAT) AS 'Dung Tích (CBM)',
                nv.ho_ten AS 'Tài xế cố định', x.loai_xe AS 'Loại Xe', x.trang_thai AS 'Trạng thái'
            FROM xe x LEFT JOIN nhan_vien nv ON x.tai_xe_co_dinh_id = nv.id
            WHERE x.trang_thai = 'Dang_Hoat_Dong' ORDER BY x.id ASC
        """
        df_xe = db.execute_query(sql_xe_list)
        if isinstance(df_xe, pd.DataFrame) and not df_xe.empty:
            # Tạo thanh chọn chế độ hiển thị (đặt ngang hàng để tiết kiệm diện tích)
            col_opt1, col_opt2 = st.columns([1, 7])
            with col_opt1:
                che_do_xem = st.selectbox("Hiển thị:", ["10 dòng", "Tất cả"])
            
            if che_do_xem == "Tất cả":
                # CHẾ ĐỘ 1: HIỂN THỊ TẤT CẢ (Không dùng nút phân trang)
                st.caption(f"Đang hiển thị toàn bộ {len(df_xe)} nhân viên.")
                st.dataframe(
                    df_xe,
                    use_container_width=True,
                    hide_index=True
                )
            else:
                # CHẾ ĐỘ 2: PHÂN TRANG 10 DÒNG
                rows_per_page = 10
                total_rows = len(df_xe)
                total_pages = math.ceil(total_rows / rows_per_page)
                
                if total_pages > 0:
                    # Khởi tạo và bảo vệ biến nhớ
                    if 'page_doixe' not in st.session_state:
                        st.session_state['page_doixe'] = 1
                        
                    if st.session_state['page_doixe'] < 1:
                        st.session_state['page_doixe'] = 1
                    elif st.session_state['page_doixe'] > total_pages:
                        st.session_state['page_doixe'] = total_pages
                        
                    # Dàn 3 cột cho nút bấm
                    col1, col2, col3 = st.columns([1, 2, 1])
                    
                    with col1:
                        if st.button("⬅️ Trước", key="btn_prev_dx", disabled=(st.session_state['page_doixe'] <= 1)):
                            if st.session_state['page_doixe'] > 1:
                                st.session_state['page_doixe'] -= 1
                                st.rerun()
                            
                    with col3:
                        if st.button("Sau ➡️", key="btn_next_dx", disabled=(st.session_state['page_doixe'] >= total_pages)):
                            if st.session_state['page_doixe'] < total_pages:
                                st.session_state['page_doixe'] += 1
                                st.rerun()
                            
                    with col2:
                        st.markdown(f"<div style='text-align: center; margin-top: 5px;'>Trang {st.session_state['page_doixe']} / {total_pages}</div>", unsafe_allow_html=True)

                    # Tính toán vị trí và cắt dữ liệu
                    start_idx = (st.session_state['page_doixe'] - 1) * rows_per_page
                    end_idx = start_idx + rows_per_page
                    df_page = df_xe.iloc[start_idx:end_idx]
                    
                    # In bảng 10 dòng ra màn hình
                    st.dataframe(
                        df_page,
                        use_container_width=True,
                        hide_index=True
                    )
            #gb = GridOptionsBuilder.from_dataframe(df_xe)
            #gb.configure_default_column(resizable=True, filter=True, sortable=True, minWidth=140)
            #gb.configure_pagination(paginationAutoPageSize=False, paginationPageSize=10)
            #AgGrid(df_xe, gridOptions=gb.build(), theme="streamlit", fit_columns_on_grid_load=False, width="100%")
        else:
            st.info("Chưa có dữ liệu xe hoạt động.")
    except Exception as e: st.error(f"Lỗi: {e}")

## Thêm mới xe
with tab2:
    with st.form("form_them_xe", clear_on_submit=True):
        st.subheader("Thông tin Phương tiện & Phân bổ tài xế")
        c1, c2, c3, c4 = st.columns(4)
        bien_so = c1.text_input("Biển số xe*", placeholder="70H-077.09")
        nhan_hieu = c2.text_input("Nhãn hiệu xe", placeholder="ISUZU, MITSUBISHI...")
        tai_trong = c3.number_input("Tải trọng (Tấn)", min_value=0.0, step=0.1)
        dung_tich = c4.number_input("Dung tích xe (CBM / Khối)", min_value=0.0, step=0.1)
        
        c5, c6 = st.columns(2)
        loai_xe = c5.selectbox("Loại xe", ["XE TẢI THÙNG", "ĐẦU KÉO", "SƠ MI RƠ MOOC", "Khác"])
        tx_co_dinh = c6.selectbox("Gán Tài xế cố định", options=[None] + list(tx_dict.keys()), format_func=lambda x: tx_dict[x] if x else "Chưa gán tài xế")
        
        # --- SỬ DỤNG HÀM TRANSACTION CHO THÊM MỚI ---
        if st.form_submit_button("💾 Lưu Xe Mới", type="primary"):
            if not bien_so: 
                st.error("Vui lòng nhập Biển số xe!")
            else:
                # Đóng gói dữ liệu thành Dictionary
                new_xe_data = {
                    'bien_so_xe': bien_so.strip(),
                    'nhan_hieu_xe': nhan_hieu.strip(),
                    'tai_trong_thiet_ke': tai_trong,
                    'dung_tich_cbm': dung_tich,
                    'loai_xe': loai_xe,
                    'tai_xe_co_dinh_id': tx_co_dinh
                }
                
                # Gọi hàm với xe_id = None
                is_ok, msg = save_vehicle_transaction(db.pool, new_xe_data, xe_id=None)
                
                if is_ok:
                    st.success("✅ Đã thêm xe mới thành công!")
                    #st.session_state["reset_tab2"] += 1
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(f"❌ Lỗi thêm xe. Database trả về: {msg}")

## Cập nhật xe 
with tab3:
    df_xe_active = db.execute_query("SELECT * FROM xe WHERE trang_thai = 'Dang_Hoat_Dong'")
    if isinstance(df_xe_active, pd.DataFrame) and not df_xe_active.empty:
        dict_xe = {row['id']: f"{row['bien_so_xe']} - {row['nhan_hieu_xe'] or ''}" for _, row in df_xe_active.iterrows()}
        xe_id = st.selectbox("🔍 Chọn xe cần sửa:", options=list(dict_xe.keys()), index=None, format_func=lambda x: dict_xe[x])
        
        if xe_id:
            xe_data = df_xe_active[df_xe_active['id'] == xe_id].iloc[0]
            with st.form("form_update_xe"):
                c_ed1, c_ed2, c_ed3, c_ed4 = st.columns(4)
                upd_bs = c_ed1.text_input("Biển số", value=xe_data['bien_so_xe'])
                upd_nh = c_ed2.text_input("Nhãn hiệu", value=xe_data['nhan_hieu_xe'] if pd.notna(xe_data['nhan_hieu_xe']) else "")
                upd_tt = c_ed3.number_input("Tải trọng thiết kế (Tấn)", value=float(xe_data['tai_trong_thiet_ke'] or 0.0))
                upd_dt = c_ed4.number_input("Dung tích (CBM)", value=float(xe_data['dung_tich_cbm'] or 0.0))
                
                # Sửa lỗi cú pháp danh sách Index từ code cũ
                danh_sach_tx = [None] + list(tx_dict.keys())
                current_tx_id = xe_data['tai_xe_co_dinh_id']
                default_index = danh_sach_tx.index(current_tx_id) if current_tx_id in danh_sach_tx else 0
                
                upd_tx = st.selectbox("Thay đổi Tài xế cố định", options=danh_sach_tx, index=default_index, format_func=lambda x: tx_dict[x] if x else "Chưa gán tài xế")
                
                # --- SỬ DỤNG HÀM TRANSACTION CHO CẬP NHẬT ---
                st.markdown("<br>", unsafe_allow_html=True)
                
                # Checkbox xác nhận an toàn để chống bấm nhầm (dùng cho việc Xóa)
                st.markdown("##### ⚠️ Khu vực nguy hiểm")
                xac_nhan_xoa = st.checkbox("Tôi chắc chắn muốn XÓA (Ngừng hoạt động) chiếc xe này.")
                
                # Chia cột cho 2 nút bấm
                btn1, btn2 = st.columns(2)
                
                # NÚT LƯU CẬP NHẬT
                if btn1.form_submit_button("🔄 Lưu Cập Nhật", type="primary"):
                    if not upd_bs:
                        st.error("Biển số xe không được để trống!")
                    else:
                        update_xe_data = {
                            'bien_so_xe': upd_bs.strip(),
                            'nhan_hieu_xe': upd_nh.strip(),
                            'tai_trong_thiet_ke': upd_tt,
                            'dung_tich_cbm': upd_dt,
                            'tai_xe_co_dinh_id': upd_tx
                        }
                        
                        is_ok, msg = save_vehicle_transaction(db.pool, update_xe_data, xe_id=xe_id)
                        
                        if is_ok:
                            st.success("✅ Đã cập nhật thông tin xe thành công!")
                            #st.session_state["reset_tab3"] += 1
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error(f"❌ Lỗi cập nhật. Database trả về: {msg}")
                            
                # NÚT XÓA XE
                if btn2.form_submit_button("🗑️ Xóa phương tiện xe"):
                    if not xac_nhan_xoa:
                        st.error("✋ HỆ THỐNG ĐÃ CHẶN: Vui lòng tick vào ô xác nhận trước khi thực hiện xóa xe!")
                    else:
                        # Gọi hàm Xóa mềm
                        is_ok, msg = delete_vehicle_transaction(db.pool, xe_id=xe_id)
                        if is_ok:
                            st.success("✅ " + msg)
                            #st.session_state["reset_tab3"] += 1
                            st.balloons()
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error(f"❌ Lỗi xóa xe: {msg}")


# ==========================================
# TAB 4: TRUNG TÂM CẢNH BÁO PHÁP LÝ TOÀN DIỆN
# ==========================================
with tab4:
    st.markdown("### 🔔 Bảng Điều Khiển Pháp Lý (Phương tiện & Nhân sự)")
    today = pd.Timestamp(datetime.date.today())
    
    # Hàm 1: Xét trạng thái cảnh báo (Màu sắc)
    def xet_canh_bao(ngay_han):
        if pd.isna(ngay_han): return "⚪ Chưa có"
        days_left = (pd.Timestamp(ngay_han) - today).days
        if days_left < 0: return "🔴 ĐÃ HẾT HẠN"
        if days_left <= 30: return f"🟡 Sắp hết ({days_left} ngày)"
        return "🟢 An toàn"

    # Hàm 2: Định dạng ngày tháng để hiển thị chi tiết
    def format_ngay(ngay_han):
        if pd.isna(ngay_han): return ""
        return pd.to_datetime(ngay_han).strftime('%d/%m/%Y')

    # --- KHU VỰC 1: CẢNH BÁO XE ---
    st.markdown("#### 🚛 1. Pháp lý phương tiện (Đăng kiểm, Bảo hiểm, Phù hiệu)")
    df_xe = db.execute_query("SELECT bien_so_xe AS 'Biển Số', han_dang_kiem, han_bao_hiem_ds, han_phu_hieu FROM xe WHERE trang_thai = 'Dang_Hoat_Dong'")
    
    if isinstance(df_xe, pd.DataFrame) and not df_xe.empty:
        # Xây dựng cột Trạng thái
        df_xe['Trạng thái Đăng Kiểm'] = df_xe['han_dang_kiem'].apply(xet_canh_bao)
        df_xe['Trạng thái Bảo Hiểm'] = df_xe['han_bao_hiem_ds'].apply(xet_canh_bao)
        df_xe['Trạng thái Phù Hiệu'] = df_xe['han_phu_hieu'].apply(xet_canh_bao)
        
        # Xây dựng cột Ngày tháng chi tiết
        df_xe['Hạn Đăng Kiểm'] = df_xe['han_dang_kiem'].apply(format_ngay)
        df_xe['Hạn Bảo Hiểm'] = df_xe['han_bao_hiem_ds'].apply(format_ngay)
        df_xe['Hạn Phù Hiệu'] = df_xe['han_phu_hieu'].apply(format_ngay)
        
        # Lọc ra các xe gặp vấn đề (Có cờ 🔴 hoặc 🟡)
        df_xe_danger = df_xe[(df_xe['Trạng thái Đăng Kiểm'].str.contains('🔴|🟡')) | 
                             (df_xe['Trạng thái Bảo Hiểm'].str.contains('🔴|🟡')) | 
                             (df_xe['Trạng thái Phù Hiệu'].str.contains('🔴|🟡'))]
        
        if not df_xe_danger.empty:
            st.error(f"⚠️ Chú ý: Có **{len(df_xe_danger)}** xe đang gặp vấn đề về giấy tờ cần xử lý gấp!")
            
            # Chọn lọc thứ tự cột hiển thị cho gọn gàng và logic
            cols_xe_hien_thi = [
                'Biển Số', 
                'Trạng thái Đăng Kiểm', 'Hạn Đăng Kiểm',
                'Trạng thái Bảo Hiểm', 'Hạn Bảo Hiểm',
                'Trạng thái Phù Hiệu', 'Hạn Phù Hiệu'
            ]
            df_xe_display = df_xe_danger[cols_xe_hien_thi]
            
            st.dataframe(df_xe_display, use_container_width=True, hide_index=True)
            
            # XUẤT EXCEL CẢNH BÁO XE
            excel_buffer_xe = io.BytesIO()
            with pd.ExcelWriter(excel_buffer_xe, engine='xlsxwriter') as writer:
                df_xe_display.to_excel(writer, sheet_name='Canh_Bao_Xe', index=False)
                worksheet = writer.sheets['Canh_Bao_Xe']
                
                # Format Header Excel nền Đỏ
                header_format = writer.book.add_format({'bold': True, 'font_color': 'white', 'bg_color': '#cc0000', 'border': 1})
                for col_num, col_name in enumerate(df_xe_display.columns):
                    worksheet.write(0, col_num, col_name, header_format)
                
                # Tự động căn chỉnh độ rộng cột (Auto-fit)
                for idx, col in enumerate(df_xe_display):
                    series = df_xe_display[col].astype(str)
                    max_len = max(series.map(len).max() if not series.empty else 0, len(str(col))) + 2
                    worksheet.set_column(idx, idx, min(max_len, 30))
                    
            st.download_button(
                label="🚨 TẢI FILE EXCEL DANH SÁCH XE CẦN GIA HẠN",
                data=excel_buffer_xe.getvalue(),
                file_name=f"Canh_Bao_Giay_To_Xe_{datetime.date.today().strftime('%d%m%Y')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary"
            )
        else:
            st.success("✅ Toàn bộ xe đều an toàn pháp lý.")

    st.divider()

    # --- KHU VỰC 2: CẢNH BÁO TÀI XẾ ---
    st.markdown("#### 🧑‍✈️ 2. Pháp lý nhân sự (GPLX & Thẻ tập huấn)")
    df_tx = db.execute_query("SELECT ho_ten AS 'Tài Xế', so_dien_thoai AS 'SĐT', han_gplx, han_the_tap_huan FROM nhan_vien WHERE trang_thai = 'Dang_Lam_Viec' AND loai_nhan_vien IN ('Tai_Chinh', 'Tai_Phu')")
    
    if isinstance(df_tx, pd.DataFrame) and not df_tx.empty:
        df_tx['Trạng thái GPLX'] = df_tx['han_gplx'].apply(xet_canh_bao)
        df_tx['Trạng thái Tập Huấn'] = df_tx['han_the_tap_huan'].apply(xet_canh_bao)
        
        df_tx['Hạn GPLX'] = df_tx['han_gplx'].apply(format_ngay)
        df_tx['Hạn Tập Huấn'] = df_tx['han_the_tap_huan'].apply(format_ngay)
        
        df_tx_danger = df_tx[(df_tx['Trạng thái GPLX'].str.contains('🔴|🟡')) | 
                             (df_tx['Trạng thái Tập Huấn'].str.contains('🔴|🟡'))]
                             
        if not df_tx_danger.empty:
            st.error(f"⚠️ Chú ý: Có **{len(df_tx_danger)}** tài xế đang sắp hoặc đã hết hạn giấy phép lái xe hay tập huấn!")
            
            cols_tx_hien_thi = [
                'Tài Xế', 'SĐT', 
                'Trạng thái GPLX', 'Hạn GPLX', 
                'Trạng thái Tập Huấn', 'Hạn Tập Huấn'
            ]
            df_tx_display = df_tx_danger[cols_tx_hien_thi]
            
            st.dataframe(df_tx_display, use_container_width=True, hide_index=True)
            
            # XUẤT EXCEL CẢNH BÁO TÀI XẾ
            excel_buffer_tx = io.BytesIO()
            with pd.ExcelWriter(excel_buffer_tx, engine='xlsxwriter') as writer:
                df_tx_display.to_excel(writer, sheet_name='Canh_Bao_Tai_Xe', index=False)
                worksheet_tx = writer.sheets['Canh_Bao_Tai_Xe']
                
                header_format_tx = writer.book.add_format({'bold': True, 'font_color': 'white', 'bg_color': '#cc0000', 'border': 1})
                for col_num, col_name in enumerate(df_tx_display.columns):
                    worksheet_tx.write(0, col_num, col_name, header_format_tx)
                
                for idx, col in enumerate(df_tx_display):
                    series = df_tx_display[col].astype(str)
                    max_len = max(series.map(len).max() if not series.empty else 0, len(str(col))) + 2
                    worksheet_tx.set_column(idx, idx, min(max_len, 30))
                    
            st.download_button(
                label="🚨 TẢI FILE EXCEL DANH SÁCH TÀI XẾ CẦN GIA HẠN",
                data=excel_buffer_tx.getvalue(),
                file_name=f"Canh_Bao_Giay_To_Tai_Xe_{datetime.date.today().strftime('%d%m%Y')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary"
            )
        else:
            st.success("✅ Toàn bộ tài xế đều đầy đủ giấy phép hợp lệ.")
