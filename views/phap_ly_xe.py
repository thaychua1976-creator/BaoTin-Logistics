import streamlit as st
import pandas as pd
import datetime, io, time, math
#from st_aggrid import AgGrid, GridOptionsBuilder
import plotly.express as px
import plotly.graph_objects as go
from fleet_manager import  save_vehicle_transaction, delete_vehicle_transaction, get_canh_bao_bao_duong, save_lich_su_bao_duong,get_thong_ke_hoat_dong_xe,get_chi_tiet_bao_duong_xe,get_bieu_do_hoat_dong,get_bang_ke_tong_hop_xe
from utils_core import  kiem_tra_va_gui_bao_cao_telegram

# --- HỆ THỐNG CACHE BỘ NHỚ ĐỆM ---
@st.cache_data(ttl=1800, show_spinner=False)
def get_cached_master_data(_db_instance, query, params=None):
    return _db_instance.execute_query(query, params)

def clear_master_cache():
    get_cached_master_data.clear()
# ---------------------------------

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

tab1, tab2,tab3 = st.tabs(["📋 Danh sách đội xe", "🚨 Cảnh báo pháp lý toàn diện","🛠️ Cảnh báo/Lập phiếu bảo dưỡng "])

# Tải danh sách tài xế để làm danh mục gán cố định (Sử dụng Cache)
df_all_tx = get_cached_master_data(db, "SELECT id, ho_ten FROM nhan_vien WHERE loai_nhan_vien IN ('Tai_Chinh', 'Tai_Phu') AND trang_thai='Dang_Lam_Viec'")
tx_dict = {row['id']: row['ho_ten'] for _, row in df_all_tx.iterrows()} if isinstance(df_all_tx, pd.DataFrame) and not df_all_tx.empty else {}

### Danh sách đội xe
with tab1:
    try:
        sql_xe_list = """
            SELECT 
                x.id AS 'Mã', x.nhan_hieu_xe AS 'Nhãn Hiệu', x.bien_so_xe AS 'Biển Số', 
                CAST(x.tai_trong_thiet_ke AS FLOAT) AS 'Tải Trọng (Tấn)', 
                CAST(x.dung_tich_cbm AS FLOAT) AS 'Dung Tích (CBM)',
                CAST(x.dinh_muc_bao_duong AS FLOAT) AS 'Định mức BD (Km)',
                x.ghi_chu AS 'Ghi chú',
                nv.ho_ten AS 'Tài xế cố định', x.loai_xe AS 'Loại Xe', x.trang_thai AS 'Trạng thái'
            FROM xe x LEFT JOIN nhan_vien nv ON x.tai_xe_co_dinh_id = nv.id
            WHERE x.trang_thai = 'Dang_Hoat_Dong' ORDER BY x.id ASC
        """
        # Sử dụng Cache cho danh sách xe
        df_xe = get_cached_master_data(db, sql_xe_list)
        
        if isinstance(df_xe, pd.DataFrame) and not df_xe.empty:
            col_opt1, col_opt2 = st.columns([1, 7])
            with col_opt1:
                che_do_xem = st.selectbox("Hiển thị:", ["10 dòng", "Tất cả"])
            
            if che_do_xem == "Tất cả":
                st.caption(f"Đang hiển thị toàn bộ {len(df_xe)} xe.")
                st.dataframe(
                    df_xe,
                    use_container_width=True,
                    hide_index=True
                )
            else:
                rows_per_page = 10
                total_rows = len(df_xe)
                total_pages = math.ceil(total_rows / rows_per_page)
                
                if total_pages > 0:
                    if 'page_doixe' not in st.session_state:
                        st.session_state['page_doixe'] = 1
                        
                    if st.session_state['page_doixe'] < 1:
                        st.session_state['page_doixe'] = 1
                    elif st.session_state['page_doixe'] > total_pages:
                        st.session_state['page_doixe'] = total_pages
                        
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

                    start_idx = (st.session_state['page_doixe'] - 1) * rows_per_page
                    end_idx = start_idx + rows_per_page
                    df_page = df_xe.iloc[start_idx:end_idx]
                    
                    st.dataframe(
                        df_page,
                        use_container_width=True,
                        hide_index=True
                    )
        else:
            st.info("Chưa có dữ liệu xe hoạt động.")
    except Exception as e: st.error(f"Lỗi: {e}")

# ==========================================
# TAB 2: TRUNG TÂM CẢNH BÁO PHÁP LÝ TOÀN DIỆN
# ==========================================
with tab2:
    st.markdown("### 🔔 Bảng Điều Khiển Pháp Lý (Phương tiện & Nhân sự)")
    today = pd.Timestamp(datetime.date.today())
    
    def xet_canh_bao(ngay_han):
        if pd.isna(ngay_han): return "⚪ Chưa có"
        days_left = (pd.Timestamp(ngay_han) - today).days
        if days_left < 0: return "🔴 ĐÃ HẾT HẠN"
        if days_left <= 30: return f"🟡 Sắp hết ({days_left} ngày)"
        return "🟢 An toàn"

    def format_ngay(ngay_han):
        if pd.isna(ngay_han): return ""
        return pd.to_datetime(ngay_han).strftime('%d/%m/%Y')

    # --- KHU VỰC 1: CẢNH BÁO XE ---
    st.markdown("#### 🚛 1. Pháp lý phương tiện (Đăng kiểm, Bảo hiểm, Phù hiệu)")
    
    # Sử dụng Cache
    df_xe = get_cached_master_data(db, "SELECT bien_so_xe AS 'Biển Số', han_dang_kiem, han_bao_hiem_ds, han_phu_hieu FROM xe WHERE trang_thai = 'Dang_Hoat_Dong'")
    
    if isinstance(df_xe, pd.DataFrame) and not df_xe.empty:
        df_xe['Trạng thái Đăng Kiểm'] = df_xe['han_dang_kiem'].apply(xet_canh_bao)
        df_xe['Trạng thái Bảo Hiểm'] = df_xe['han_bao_hiem_ds'].apply(xet_canh_bao)
        df_xe['Trạng thái Phù Hiệu'] = df_xe['han_phu_hieu'].apply(xet_canh_bao)
        
        df_xe['Hạn Đăng Kiểm'] = df_xe['han_dang_kiem'].apply(format_ngay)
        df_xe['Hạn Bảo Hiểm'] = df_xe['han_bao_hiem_ds'].apply(format_ngay)
        df_xe['Hạn Phù Hiệu'] = df_xe['han_phu_hieu'].apply(format_ngay)
        
        df_xe_danger = df_xe[(df_xe['Trạng thái Đăng Kiểm'].str.contains('🔴|🟡')) | 
                             (df_xe['Trạng thái Bảo Hiểm'].str.contains('🔴|🟡')) | 
                             (df_xe['Trạng thái Phù Hiệu'].str.contains('🔴|🟡'))]
        
        if not df_xe_danger.empty:
            st.error(f"⚠️ Chú ý: Có **{len(df_xe_danger)}** xe đang gặp vấn đề về giấy tờ cần xử lý gấp!")
            
            cols_xe_hien_thi = [
                'Biển Số', 
                'Trạng thái Đăng Kiểm', 'Hạn Đăng Kiểm',
                'Trạng thái Bảo Hiểm', 'Hạn Bảo Hiểm',
                'Trạng thái Phù Hiệu', 'Hạn Phù Hiệu'
            ]
            df_xe_display = df_xe_danger[cols_xe_hien_thi]
            
            st.dataframe(df_xe_display, use_container_width=True, hide_index=True)
            
            excel_buffer_xe = io.BytesIO()
            with pd.ExcelWriter(excel_buffer_xe, engine='xlsxwriter') as writer:
                df_xe_display.to_excel(writer, sheet_name='Canh_Bao_Xe', index=False)
                worksheet = writer.sheets['Canh_Bao_Xe']
                
                header_format = writer.book.add_format({'bold': True, 'font_color': 'white', 'bg_color': '#cc0000', 'border': 1})
                for col_num, col_name in enumerate(df_xe_display.columns):
                    worksheet.write(0, col_num, col_name, header_format)
                
                for idx, col in enumerate(df_xe_display):
                    series = df_xe_display[col].astype(str)
                    max_len = max(series.map(len).max() if not series.empty else 0, len(str(col))) + 2
                    worksheet.set_column(idx, idx, min(max_len, 30))
            excel_buffer_xe.seek(0)        
            
            col_btn1, col_btn2 = st.columns([1, 1])
            with col_btn1:
                st.download_button(
                    label="🚨 TẢI EXCEL ",
                    data=excel_buffer_xe.getvalue(),
                    file_name=f"Canh_Bao_Giay_To_Xe_{datetime.date.today().strftime('%d%m%Y')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary"
                )
            with col_btn2:
                if st.button("🚀 Gửi File lên Telegram", key='btn_gui_telegram_xe', type="primary", use_container_width=True):
                    with st.spinner("Đang kiểm tra và gửi..."):
                        success, message = kiem_tra_va_gui_bao_cao_telegram(
                          df_xe_danger, 
                          "XE", 
                          excel_buffer_xe
                        )
                        if success:
                            st.success("✅ Đã gửi danh sách tới hạn lên Telegram!")
                        else:
                            st.warning(f"Thông tin: {message}")
        else:
            st.success("✅ Toàn bộ xe đều an toàn pháp lý.")

    st.divider()

    # --- KHU VỰC 2: CẢNH BÁO TÀI XẾ ---
    st.markdown("#### 🧑‍✈️ 2. Pháp lý nhân sự (GPLX & Thẻ tập huấn)")
    
    # Sử dụng Cache
    df_tx = get_cached_master_data(db, "SELECT ho_ten AS 'Tài Xế', so_dien_thoai AS 'SĐT', han_gplx, han_the_tap_huan FROM nhan_vien WHERE trang_thai = 'Dang_Lam_Viec' AND loai_nhan_vien IN ('Tai_Chinh', 'Tai_Phu')")
    
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
            excel_buffer_tx.seek(0)        
            
            col_btn4, col_btn5 = st.columns([1, 1])
            with col_btn4:
                    st.download_button(
                        label="🚨 TẢI FILE EXCEL ",
                        data=excel_buffer_tx.getvalue(),
                        file_name=f"Canh_Bao_Giay_To_Tai_Xe_{datetime.date.today().strftime('%d%m%Y')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        type="primary",
                        use_container_width=True
                    )

            with col_btn5:
                    if st.button("🚀 GỬI FILE LÊN TELEGRAM", key='btn_gui_telegram_tx', type="primary", use_container_width=True):
                        with st.spinner("Đang kiểm tra và gửi..."):
                            success, message = kiem_tra_va_gui_bao_cao_telegram(
                                df_tx_danger, 
                                "TAIXE", 
                                excel_buffer_tx 
                            )
                            if success:
                                st.success("✅ Đã gửi danh sách tới hạn lên Telegram!")
                            else:
                                st.warning(f"Thông tin: {message}")
            
        else:
            st.success("✅ Toàn bộ tài xế đều đầy đủ giấy phép hợp lệ.")

###############################
with tab3:
    try:
            st.markdown("### 🛠️ Hệ thống Cảnh báo Bảo dưỡng Phương tiện")

            # Không dùng Cache vì Odometer của phương tiện thay đổi liên tục
            df_bao_duong = get_canh_bao_bao_duong(db.pool)

            if df_bao_duong is not None and not df_bao_duong.empty:
                df_bao_duong['km_da_chay'] = pd.to_numeric(df_bao_duong['km_da_chay'], errors='coerce').fillna(0.0)
                df_bao_duong['dinh_muc_km'] = pd.to_numeric(df_bao_duong['dinh_muc_km'], errors='coerce').fillna(5000.0)
                
                df_bao_duong['dinh_muc_km'] = df_bao_duong['dinh_muc_km'].replace(0, 5000)
                df_bao_duong['ty_le'] = (df_bao_duong['km_da_chay'] / df_bao_duong['dinh_muc_km']) * 100
                
                xe_qua_han = df_bao_duong[df_bao_duong['ty_le'] >= 100]
                xe_sap_den_han = df_bao_duong[(df_bao_duong['ty_le'] >= 85) & (df_bao_duong['ty_le'] < 100)]
                
                col1, col2, col3 = st.columns(3)
                col1.metric("🚨 CẦN BẢO DƯỠNG GẤP", len(xe_qua_han))
                col2.metric("⚠️ SẮP ĐẾN HẠN (Trên 85%)", len(xe_sap_den_han))
                col3.metric("✅ HOẠT ĐỘNG ỔN ĐỊNH", len(df_bao_duong) - len(xe_qua_han) - len(xe_sap_den_han))
                
                st.divider()
                
                df_hien_thi = df_bao_duong[['bien_so_xe', 'ngay_bd_cuoi', 'km_da_chay', 'dinh_muc_km', 'ty_le']].copy()
                df_hien_thi.columns = ['Biển Số Xe', 'Ngày BD Gần Nhất', 'KM Đã Chạy', 'Định Mức KM', 'Tỷ Lệ (%)']
                df_hien_thi['Ngày BD Gần Nhất'] = df_hien_thi['Ngày BD Gần Nhất'].fillna("Chưa từng BD")
                
                def color_status(val):
                    try:
                        v = float(val)
                        if v >= 100: return 'color: red; font-weight: bold'
                        if v >= 85: return 'color: orange; font-weight: bold'
                        return 'color: green; font-weight: bold'
                    except:
                        return 'color: green; font-weight: bold'
                    
                def format_status(val):
                    try:
                        v = float(val)
                        if v >= 100: return "Quá hạn 🔴"
                        if v >= 85: return "Sắp đến hạn 🟡"
                        return "Tốt 🟢"
                    except:
                        return "Tốt 🟢"

                df_hien_thi['Đánh Giá Cảnh Báo'] = df_hien_thi['Tỷ Lệ (%)'].apply(format_status)
                
                st.dataframe(
                    df_hien_thi.style.map(color_status, subset=['Đánh Giá Cảnh Báo'])\
                                    .format({"KM Đã Chạy": "{:,.1f} km", "Định Mức KM": "{:,.0f} km", "Tỷ Lệ (%)": "{:.1f}%"}),
                    use_container_width=True,
                    hide_index=True
                )
                
                st.markdown("<br>", unsafe_allow_html=True)
                buffer_export_bd = io.BytesIO()
                with pd.ExcelWriter(buffer_export_bd, engine='xlsxwriter') as writer:
                    df_export = df_hien_thi.copy()
                    df_export.to_excel(writer, index=False, sheet_name="Bao_Duong")
                    worksheet = writer.sheets['Bao_Duong']
                    
                    header_format = writer.book.add_format({'bold': True, 'font_color': 'white', 'bg_color': '#d9534f', 'border': 1})
                    for col_num, col_name in enumerate(df_export.columns):
                        worksheet.write(0, col_num, col_name, header_format)
                        
                    for idx, col in enumerate(df_export.columns):
                        series_str = df_export[col].fillna("").astype(str)
                        max_len = max(series_str.map(len).max() if not series_str.empty else 0, len(str(col))) + 2
                        worksheet.set_column(idx, idx, min(max_len, 50))

                col_dl1, col_dl2 = st.columns([1, 2])
                with col_dl1:
                    st.download_button(
                        label="📥 TẢI FILE EXCEL CẢNH BÁO",
                        data=buffer_export_bd.getvalue(),
                        file_name=f"Canh_Bao_Bao_Duong_{datetime.date.today().strftime('%d_%m_%Y')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        type="primary",
                        use_container_width=True
                    )
            else:
                st.info("Chưa có dữ liệu xe để hiển thị.")

            st.divider()

            # ==========================================
            # FORM NHẬP LỊCH SỬ BẢO DƯỠNG
            # ==========================================
            st.markdown("### 📝 Lập Phiếu Ghi Nhận Bảo Dưỡng / Sửa Chữa")

            # Sử dụng Cache
            sql_get_xe = "SELECT id, bien_so_xe FROM xe WHERE trang_thai = 'Dang_Hoat_Dong'"
            df_xe = get_cached_master_data(db, sql_get_xe)

            if df_xe is not None and not df_xe.empty:
                xe_dict = dict(zip(df_xe['id'], df_xe['bien_so_xe']))
                
                with st.form("form_nhap_bao_duong", clear_on_submit=True):
                    c1, c2, c3 = st.columns(3)
                    xe_duoc_chon = c1.selectbox("🚛 Chọn xe", options=list(xe_dict.keys()), format_func=lambda x: xe_dict[x])
                    ngay_bd = c2.date_input("📅 Ngày thực hiện", format="DD/MM/YYYY")
                    loai_bd = c3.selectbox("Loại sửa chữa", options=['Dinh_Ky', 'Sua_Chua_Dot_Xuat', 'Thay_Lop', 'Khac'], 
                                        format_func=lambda x: "Bảo dưỡng định kỳ" if x == 'Dinh_Ky' else ("Sửa chữa đột xuất" if x == 'Sua_Chua_Dot_Xuat' else ("Thay lốp" if x == 'Thay_Lop' else "Khác")))
                    
                    c4, c5 = st.columns(2)
                    km_luc_bd = c4.number_input("Tốc độ kế (Số KM trên đồng hồ xe hiện tại)", min_value=0.0, step=10.0, 
                                                help="Đồng hồ phần mềm sẽ được đồng bộ lại với con số này (nếu chọn Bảo dưỡng định kỳ).")
                    chi_phi_bd = c5.text_input("Tổng chi phí (VNĐ)", placeholder="VD: 5,500,000")
                    
                    hang_muc = st.text_area("🔧 Hạng mục thực hiện", placeholder="VD: Thay nhớt máy, lọc gió, đảo lốp...")
                    
                    c6, c7 = st.columns(2)
                    don_vi = c6.text_input("🏭 Đơn vị Garage", placeholder="Tên Garage")
                    ghi_chu = c7.text_input("Ghi chú thêm")
                    
                    if st.form_submit_button("💾 Lưu Phiếu", type="primary"):
                        try:
                            tien_clean = float(chi_phi_bd.replace(",", "").replace(".", "").strip()) if chi_phi_bd else 0.0
                        except:
                            tien_clean = 0.0
                            
                        if not hang_muc.strip():
                            st.error("⚠️ Vui lòng nhập chi tiết hạng mục!")
                        else:
                            data_bd = {
                                'xe_id': xe_duoc_chon,
                                'ngay_bao_duong': ngay_bd.strftime('%Y-%m-%d'),
                                'km_thuc_te': km_luc_bd,
                                'loai_bao_duong': loai_bd,
                                'hang_muc_sua_chua': hang_muc.strip(),
                                'chi_phi': tien_clean,
                                'don_vi_thuc_hien': don_vi.strip(),
                                'ghi_chu': ghi_chu.strip()
                            }
                            
                            with st.spinner("Đang lưu dữ liệu..."):
                                is_ok, msg = save_lich_su_bao_duong(db.pool, data_bd)
                            
                            if is_ok:
                                clear_master_cache() # Gọi xóa cache để làm mới lại trạng thái bảo dưỡng và thông tin CSDL
                                st.success(msg)
                                import time; time.sleep(1)
                                st.rerun() 
                            else:
                                st.error(msg)
    except Exception as e: st.error(f"Lỗi: {e}")