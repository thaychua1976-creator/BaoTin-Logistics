import streamlit as st
import pandas as pd
import datetime, io, time, math
from fleet_manager import get_canh_bao_bao_duong, save_lich_su_bao_duong
from utils_core import kiem_tra_va_gui_bao_cao_telegram

db = st.session_state.get('db')
if not db:
    st.error("⚠️ Lỗi kết nối Cơ sở dữ liệu.")
    st.stop()


# --- HỆ THỐNG CACHE BỘ NHỚ ĐỆM ---
@st.cache_data(ttl=1800, show_spinner=False)
def get_cached_master_data(_db_instance, query, params=None):
    return _db_instance.execute_query(query, params)


def clear_master_cache():
    get_cached_master_data.clear()
# ---------------------------------


if 'bd_add_counter_pl' not in st.session_state:
    st.session_state['bd_add_counter_pl'] = 0

hide_enter_submit_css = """
<style>
    div[data-testid="InputInstructions"] {
        display: none !important;
        visibility: hidden !important;
    }
</style>
"""
st.markdown(hide_enter_submit_css, unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["📋 Danh sách đội xe", "🚨 Cảnh báo pháp lý toàn diện", "🛠️ Cảnh báo/Lập phiếu bảo dưỡng"])

# ==========================================
# TAB 1: DANH SÁCH ĐỘI XE
# ==========================================
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
        df_xe = get_cached_master_data(db, sql_xe_list)

        if isinstance(df_xe, pd.DataFrame) and not df_xe.empty:
            df_xe['Nhãn Hiệu'] = df_xe['Nhãn Hiệu'].fillna('').apply(lambda x: str(x).strip() if str(x).strip().lower() not in ('nan', 'none') else '')
            df_xe['Ghi chú'] = df_xe['Ghi chú'].fillna('').apply(lambda x: str(x).strip() if str(x).strip().lower() not in ('nan', 'none') else '')
            df_xe['Tài xế cố định'] = df_xe['Tài xế cố định'].fillna('Chưa gán tài xế')

            col_opt1, _ = st.columns([1, 7])
            with col_opt1:
                che_do_xem = st.selectbox("Hiển thị:", ["10 dòng", "Tất cả"], key="sel_view_pl_xe")

            if che_do_xem == "Tất cả":
                st.caption(f"Đang hiển thị toàn bộ {len(df_xe)} xe.")
                st.dataframe(df_xe, use_container_width=True, hide_index=True)
            else:
                rows_per_page = 10
                total_rows = len(df_xe)
                total_pages = math.ceil(total_rows / rows_per_page)

                if total_pages > 0:
                    if 'page_doixe' not in st.session_state:
                        st.session_state['page_doixe'] = 1

                    st.session_state['page_doixe'] = max(1, min(st.session_state['page_doixe'], total_pages))

                    col1, col2, col3 = st.columns([1, 2, 1])
                    with col1:
                        if st.button("⬅️ Trước", key="btn_prev_dx", disabled=(st.session_state['page_doixe'] <= 1)):
                            st.session_state['page_doixe'] -= 1
                            st.rerun()
                    with col3:
                        if st.button("Sau ➡️", key="btn_next_dx", disabled=(st.session_state['page_doixe'] >= total_pages)):
                            st.session_state['page_doixe'] += 1
                            st.rerun()
                    with col2:
                        st.markdown(f"<div style='text-align: center; margin-top: 5px;'>Trang {st.session_state['page_doixe']} / {total_pages}</div>", unsafe_allow_html=True)

                    start_idx = (st.session_state['page_doixe'] - 1) * rows_per_page
                    df_page = df_xe.iloc[start_idx:start_idx + rows_per_page]
                    st.dataframe(df_page, use_container_width=True, hide_index=True)
        else:
            st.info("Chưa có dữ liệu xe hoạt động.")
    except Exception as e:
        st.error(f"Lỗi: {e}")

# ==========================================
# TAB 2: TRUNG TÂM CẢNH BÁO PHÁP LÝ TOÀN DIỆN
# ==========================================
with tab2:
    st.markdown("### 🔔 Bảng Điều Khiển Pháp Lý (Phương tiện & Nhân sự)")
    today = pd.Timestamp(datetime.date.today())

    def xet_canh_bao(ngay_han):
        if pd.isna(ngay_han) or str(ngay_han).strip().lower() in ('', 'nat', 'nan', 'none'):
            return "⚪ Chưa có"
        try:
            days_left = (pd.Timestamp(ngay_han) - today).days
            if days_left < 0:
                return "🔴 ĐÃ HẾT HẠN"
            if days_left <= 30:
                return f"🟡 Sắp hết ({days_left} ngày)"
            return "🟢 An toàn"
        except Exception:
            return "⚪ Chưa có"

    def format_ngay(ngay_han):
        if pd.isna(ngay_han) or str(ngay_han).strip().lower() in ('', 'nat', 'nan', 'none'):
            return ""
        try:
            return pd.to_datetime(ngay_han).strftime('%d/%m/%Y')
        except Exception:
            return ""

    st.markdown("#### 🚛 1. Pháp lý phương tiện (Đăng kiểm, Bảo hiểm, Phù hiệu)")
    df_xe_pl = get_cached_master_data(db, "SELECT bien_so_xe AS 'Biển Số', han_dang_kiem, han_bao_hiem_ds, han_phu_hieu FROM xe WHERE trang_thai = 'Dang_Hoat_Dong'")

    if isinstance(df_xe_pl, pd.DataFrame) and not df_xe_pl.empty:
        df_xe_pl['Trạng thái Đăng Kiểm'] = df_xe_pl['han_dang_kiem'].apply(xet_canh_bao)
        df_xe_pl['Trạng thái Bảo Hiểm'] = df_xe_pl['han_bao_hiem_ds'].apply(xet_canh_bao)
        df_xe_pl['Trạng thái Phù Hiệu'] = df_xe_pl['han_phu_hieu'].apply(xet_canh_bao)

        df_xe_pl['Hạn Đăng Kiểm'] = df_xe_pl['han_dang_kiem'].apply(format_ngay)
        df_xe_pl['Hạn Bảo Hiểm'] = df_xe_pl['han_bao_hiem_ds'].apply(format_ngay)
        df_xe_pl['Hạn Phù Hiệu'] = df_xe_pl['han_phu_hieu'].apply(format_ngay)

        df_xe_danger = df_xe_pl[
            (df_xe_pl['Trạng thái Đăng Kiểm'].str.contains('🔴|🟡')) |
            (df_xe_pl['Trạng thái Bảo Hiểm'].str.contains('🔴|🟡')) |
            (df_xe_pl['Trạng thái Phù Hiệu'].str.contains('🔴|🟡'))
        ]

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
                    label="🚨 TẢI EXCEL",
                    data=excel_buffer_xe.getvalue(),
                    file_name=f"Canh_Bao_Giay_To_Xe_{datetime.date.today().strftime('%d%m%Y')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary",
                    use_container_width=True
                )
            with col_btn2:
                if st.button("🚀 Gửi File lên Telegram", key='btn_gui_telegram_xe', type="primary", use_container_width=True):
                    with st.spinner("Đang kiểm tra và gửi..."):
                        excel_buffer_xe.seek(0)
                        success, message = kiem_tra_va_gui_bao_cao_telegram(df_xe_danger, "XE", excel_buffer_xe)
                        if success:
                            st.success("✅ Đã gửi danh sách tới hạn lên Telegram!")
                        else:
                            st.warning(f"Thông tin: {message}")
        else:
            st.success("✅ Toàn bộ xe đều an toàn pháp lý.")

    st.divider()

    st.markdown("#### 🧑‍✈️ 2. Pháp lý nhân sự (GPLX & Thẻ tập huấn)")
    df_tx = get_cached_master_data(db, "SELECT ho_ten AS 'Tài Xế', so_dien_thoai AS 'SĐT', han_gplx, han_the_tap_huan FROM nhan_vien WHERE trang_thai = 'Dang_Lam_Viec' AND loai_nhan_vien IN ('Tai_Chinh', 'Tai_Phu')")

    if isinstance(df_tx, pd.DataFrame) and not df_tx.empty:
        df_tx['Trạng thái GPLX'] = df_tx['han_gplx'].apply(xet_canh_bao)
        df_tx['Trạng thái Tập Huấn'] = df_tx['han_the_tap_huan'].apply(xet_canh_bao)
        df_tx['Hạn GPLX'] = df_tx['han_gplx'].apply(format_ngay)
        df_tx['Hạn Tập Huấn'] = df_tx['han_the_tap_huan'].apply(format_ngay)

        df_tx_danger = df_tx[
            (df_tx['Trạng thái GPLX'].str.contains('🔴|🟡')) |
            (df_tx['Trạng thái Tập Huấn'].str.contains('🔴|🟡'))
        ]

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
                    label="🚨 TẢI FILE EXCEL",
                    data=excel_buffer_tx.getvalue(),
                    file_name=f"Canh_Bao_Giay_To_Tai_Xe_{datetime.date.today().strftime('%d%m%Y')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary",
                    use_container_width=True
                )
            with col_btn5:
                if st.button("🚀 GỬI FILE LÊN TELEGRAM", key='btn_gui_telegram_tx', type="primary", use_container_width=True):
                    with st.spinner("Đang kiểm tra và gửi..."):
                        excel_buffer_tx.seek(0)
                        success, message = kiem_tra_va_gui_bao_cao_telegram(df_tx_danger, "TAIXE", excel_buffer_tx)
                        if success:
                            st.success("✅ Đã gửi danh sách tới hạn lên Telegram!")
                        else:
                            st.warning(f"Thông tin: {message}")
        else:
            st.success("✅ Toàn bộ tài xế đều đầy đủ giấy phép hợp lệ.")

# ==========================================
# TAB 3: BẢO DƯỠNG XE
# ==========================================
with tab3:
    try:
        st.markdown("### 🛠️ Hệ thống Cảnh báo Bảo dưỡng Phương tiện")
        df_bao_duong = get_canh_bao_bao_duong(db.pool)

        if df_bao_duong is not None and not df_bao_duong.empty:
            df_bao_duong['km_da_chay'] = pd.to_numeric(df_bao_duong['km_da_chay'], errors='coerce').fillna(0.0)
            df_bao_duong['dinh_muc_km'] = pd.to_numeric(df_bao_duong['dinh_muc_km'], errors='coerce').fillna(5000.0).replace(0, 5000.0)
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
            df_hien_thi['Ngày BD Gần Nhất'] = df_hien_thi['Ngày BD Gần Nhất'].fillna("Chưa từng BD").apply(
                lambda x: str(x).strip() if str(x).strip().lower() not in ('nan', 'none', '') else "Chưa từng BD"
            )

            def color_status(val):
                try:
                    v = float(val)
                    if v >= 100:
                        return 'color: red; font-weight: bold'
                    if v >= 85:
                        return 'color: orange; font-weight: bold'
                    return 'color: green; font-weight: bold'
                except Exception:
                    return 'color: green; font-weight: bold'

            def format_status(val):
                try:
                    v = float(val)
                    if v >= 100:
                        return "Quá hạn 🔴"
                    if v >= 85:
                        return "Sắp đến hạn 🟡"
                    return "Tốt 🟢"
                except Exception:
                    return "Tốt 🟢"

            df_hien_thi['Đánh Giá Cảnh Báo'] = df_hien_thi['Tỷ Lệ (%)'].apply(format_status)

            st.dataframe(
                df_hien_thi.style.map(color_status, subset=['Đánh Giá Cảnh Báo'])
                                 .format({"KM Đã Chạy": "{:,.1f} km", "Định Mức KM": "{:,.0f} km", "Tỷ Lệ (%)": "{:.1f}%"}),
                use_container_width=True,
                hide_index=True
            )

            st.markdown("<br>", unsafe_allow_html=True)
            buffer_export_bd = io.BytesIO()
            with pd.ExcelWriter(buffer_export_bd, engine='xlsxwriter') as writer:
                df_hien_thi.to_excel(writer, index=False, sheet_name="Bao_Duong")
                worksheet = writer.sheets['Bao_Duong']
                header_format = writer.book.add_format({'bold': True, 'font_color': 'white', 'bg_color': '#d9534f', 'border': 1})
                for col_num, col_name in enumerate(df_hien_thi.columns):
                    worksheet.write(0, col_num, col_name, header_format)
                for idx, col in enumerate(df_hien_thi.columns):
                    series_str = df_hien_thi[col].fillna("").astype(str)
                    max_len = max(series_str.map(len).max() if not series_str.empty else 0, len(str(col))) + 2
                    worksheet.set_column(idx, idx, min(max_len, 50))

            col_dl1, _ = st.columns([1, 2])
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
        st.markdown("### 📝 Lập Phiếu Ghi Nhận Bảo Dưỡng / Sửa Chữa")

        df_xe_bd = get_cached_master_data(db, "SELECT id, bien_so_xe FROM xe WHERE trang_thai = 'Dang_Hoat_Dong'")
        if df_xe_bd is not None and not df_xe_bd.empty:
            xe_dict = dict(zip(df_xe_bd['id'], df_xe_bd['bien_so_xe']))
            bc = st.session_state['bd_add_counter_pl']

            c1, c2, c3 = st.columns(3)
            xe_duoc_chon = c1.selectbox("🚛 Chọn xe", options=list(xe_dict.keys()), format_func=lambda x: xe_dict[x], key=f"pl_bd_xe_{bc}")
            ngay_bd = c2.date_input("📅 Ngày thực hiện", format="DD/MM/YYYY", key=f"pl_bd_ngay_{bc}")
            loai_bd = c3.selectbox(
                "Loại sửa chữa",
                options=['Dinh_Ky', 'Sua_Chua_Dot_Xuat', 'Thay_Lop', 'Khac'],
                format_func=lambda x: "Bảo dưỡng định kỳ" if x == 'Dinh_Ky' else ("Sửa chữa đột xuất" if x == 'Sua_Chua_Dot_Xuat' else ("Thay lốp" if x == 'Thay_Lop' else "Khác")),
                key=f"pl_bd_loai_{bc}"
            )

            c4, c5 = st.columns(2)
            km_luc_bd = c4.number_input(
                "Tốc độ kế (Số KM trên đồng hồ xe hiện tại)",
                min_value=0.0,
                value=None,
                placeholder="0",
                format="%g",
                step=10.0,
                help="Đồng hồ phần mềm sẽ được đồng bộ lại với con số này (nếu chọn Bảo dưỡng định kỳ).",
                key=f"pl_bd_km_{bc}"
            )
            chi_phi_bd = c5.text_input("Tổng chi phí (VNĐ)", placeholder="VD: 5,500,000", key=f"pl_bd_tien_{bc}")

            hang_muc = st.text_area("🔧 Hạng mục thực hiện", placeholder="VD: Thay nhớt máy, lọc gió, đảo lốp...", key=f"pl_bd_hm_{bc}")

            c6, c7 = st.columns(2)
            don_vi = c6.text_input("🏭 Đơn vị Garage", placeholder="Tên Garage", key=f"pl_bd_dv_{bc}")
            ghi_chu = c7.text_input("Ghi chú thêm", key=f"pl_bd_gc_{bc}")

            if st.button("💾 Lưu Phiếu", type="primary", use_container_width=True, key=f"pl_btn_bd_{bc}"):
                try:
                    tien_clean = float(chi_phi_bd.replace(",", "").replace(".", "").strip()) if chi_phi_bd else 0.0
                except Exception:
                    tien_clean = 0.0

                if not hang_muc.strip():
                    st.error("⚠️ Vui lòng nhập chi tiết hạng mục!")
                else:
                    data_bd = {
                        'xe_id': xe_duoc_chon,
                        'ngay_bao_duong': ngay_bd.strftime('%Y-%m-%d'),
                        'km_thuc_te': km_luc_bd or 0.0,
                        'loai_bao_duong': loai_bd,
                        'hang_muc_sua_chua': hang_muc.strip(),
                        'chi_phi': tien_clean,
                        'don_vi_thuc_hien': don_vi.strip(),
                        'ghi_chu': ghi_chu.strip()
                    }
                    with st.spinner("Đang lưu dữ liệu..."):
                        is_ok, msg = save_lich_su_bao_duong(db.pool, data_bd)
                    if is_ok:
                        clear_master_cache()
                        st.success(msg)
                        st.session_state['bd_add_counter_pl'] += 1
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(msg)
    except Exception as e:
        st.error(f"Lỗi: {e}")