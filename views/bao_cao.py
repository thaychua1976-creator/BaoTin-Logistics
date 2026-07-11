import streamlit as st
import pandas as pd
import datetime
import io
from st_aggrid import AgGrid, GridOptionsBuilder  # 👉 Bổ sung import AgGrid đồng bộ

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

st.markdown("<h3 style='text-align: center; color: #0b5394;'>📊 TRUNG TÂM BÁO CÁO THỐNG KÊ & XUẤT DỮ LIỆU EXCEL</h3>", unsafe_allow_html=True)

# ==========================================
# 1. KHU VỰC BỘ LỌC THÔNG MINH (NGÀY & TÀI XẾ)
# ==========================================
with st.container():
    st.markdown("##### 🔍 Bộ lọc điều kiện thống kê")
    c_date1, c_date2, c_driver = st.columns([1, 1, 2])
    
    today = datetime.date.today()
    start_of_month = today.replace(day=1)
    
    tu_ngay = c_date1.date_input("Từ ngày", value=start_of_month,format="DD/MM/YYYY")
    den_ngay = c_date2.date_input("Đến ngày", value=today,format="DD/MM/YYYY")
    
    sql_tx_list = "SELECT id, ho_ten FROM nhan_vien WHERE loai_nhan_vien IN ('Tai_Chinh', 'Tai_Phu') ORDER BY ho_ten"
    df_tx_filter = db.execute_query(sql_tx_list)
    
    tx_options = {0: "✨ Tất cả tài xế (Mặc định)"}
    if isinstance(df_tx_filter, pd.DataFrame) and not df_tx_filter.empty:
        for _, r in df_tx_filter.iterrows():
            tx_options[r['id']] = r['ho_ten']
            
    tai_xe_duoc_chon = c_driver.selectbox("Chọn Tài xế thống kê", options=list(tx_options.keys()), format_func=lambda x: tx_options[x], index=0)

st.divider()

# ==========================================
# 2. KHU VỰC HIỂN THỊ: CHIA 2 TAB BÁO CÁO
# ==========================================
tab_bc1, tab_bc2 = st.tabs(["📊 Báo cáo tài chính & Quyết toán", "⚠️ Cảnh báo Xe tồn đọng / Quá hạn"])

# ---------------------------------------------------------
# TAB 1: BÁO CÁO TÀI CHÍNH (CÁC CHUYẾN ĐÃ HOÀN THÀNH)
# ---------------------------------------------------------
with tab_bc1:
    try:
        tx_clause = ""
        params_bc1 = [f"{tu_ngay.strftime('%Y-%m-%d')} 00:00:00", f"{den_ngay.strftime('%Y-%m-%d')} 23:59:59"]
        
        if tai_xe_duoc_chon != 0:
            tx_clause = "AND cdtx.tai_xe_id = %s"
            params_bc1.append(tai_xe_duoc_chon)

        sql_raw_data = f"""
            SELECT 
                cd.id AS 'Mã Chuyến', 
                cd.ngay_chuyen_di AS 'Ngày Chạy', 
                cd.ten_khach_hang AS 'Khách Hàng',
                x.bien_so_xe AS 'Biển Số Xe', 
                CAST(x.tai_trong_thiet_ke AS DECIMAL(15,2)) AS 'Tải Trọng',
                nv.ho_ten AS 'Tài Xế', 
                cd.dia_diem_giao_nhan AS 'Lộ Trình', 
                CAST(COALESCE(cd.so_km_thuc_te, 0) AS DECIMAL(15,2)) AS 'Số KM chạy', 
                CAST(COALESCE(cd.so_lit_xang, 0) AS DECIMAL(15,2)) AS 'Số Lít Dầu',
                CAST(COALESCE(cd.cong_chuyen, 0) AS DECIMAL(15,2)) AS 'Lương Chuyến Gốc',
                CAST(COALESCE(cd.tien_them, 0) AS DECIMAL(15,2)) AS 'Thưởng Thêm',
                CAST((COALESCE(cd.cong_chuyen, 0) + COALESCE(cd.tien_them, 0)) AS DECIMAL(15,2)) AS 'Tổng Lương Tài Xế',
                CAST(COALESCE(cd.phi_hai_quan, 0) AS DECIMAL(15,2)) AS 'Phí Hải Quan',
                CAST(COALESCE(cd.phi_boc_xep, 0) AS DECIMAL(15,2)) AS 'Phí Bốc Xếp',
                CAST(COALESCE(cd.phi_khac, 0) AS DECIMAL(15,2)) AS 'Phí Khác',
                cd.ghi_chu AS 'Ghi chú'
            FROM chuyen_di cd
            LEFT JOIN xe x ON cd.xe_id = x.id
            LEFT JOIN chuyen_di_tai_xe cdtx ON cd.id = cdtx.chuyen_di_id AND cdtx.loai_tai_xe = 'Tai_Chinh'
            LEFT JOIN nhan_vien nv ON cdtx.tai_xe_id = nv.id
            WHERE cd.trang_thai_chuyen = 'Hoan_Thanh' 
              AND cd.ngay_chuyen_di >= %s 
              AND cd.ngay_chuyen_di <= %s
              {tx_clause}
            ORDER BY cd.ngay_chuyen_di DESC, cd.id DESC
        """
        df_result = db.execute_query(sql_raw_data, tuple(params_bc1))

        if isinstance(df_result, pd.DataFrame) and not df_result.empty:
            df_result['Ngày hiển thị'] = pd.to_datetime(df_result['Ngày Chạy']).dt.strftime('%d/%m/%Y')
            
            tong_so_chuyen = len(df_result)
            tong_luong_tx = df_result['Tổng Lương Tài Xế'].sum()
            tong_hq_bx = df_result['Phí Hải Quan'].sum() + df_result['Phí Bốc Xếp'].sum()
            tong_phi_khac = df_result['Phí Khác'].sum()
            
            col_m1, col_m2, col_m3, col_m4 = st.columns(4)
            col_m1.metric("🚛 Tổng Số Chuyến", f"{tong_so_chuyen} chuyến")
            col_m2.metric("👨‍✈️ Tổng Lương Tài Xế", f"{tong_luong_tx:,.0f} đ")
            col_m3.metric("📦 Phí Hải Quan & Bốc Xếp", f"{tong_hq_bx:,.0f} đ")
            col_m4.metric("💸 Tổng Phí Khác", f"{tong_phi_khac:,.0f} đ")
            
            st.divider()

            # (Giữ nguyên đoạn code xuất Excel auto-fit và hiển thị AgGrid của Tab 1 ở đây)
            # ... Bạn dán tiếp phần Xuất Excel multi-sheets và AgGrid của tin nhắn trước vào đây ...
            st.markdown("##### 📥 Xuất báo cáo tài chính chuyên sâu")
            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
                cols_excel = [
                    'Mã Chuyến', 'Ngày hiển thị', 'Khách Hàng', 'Biển Số Xe', 'Tải Trọng', 'Tài Xế', 'Lộ Trình',
                    'Số KM chạy', 'Số Lít Dầu', 'Lương Chuyến Gốc', 'Thưởng Thêm', 'Tổng Lương Tài Xế',
                    'Phí Hải Quan', 'Phí Bốc Xếp', 'Phí Khác', 'Ghi chú'
                ]
                df_excel_all = df_result[cols_excel].rename(columns={'Ngày hiển thị': 'Ngày Chạy'}).copy()
                
                def auto_fit_columns(worksheet, df):
                    for idx, col in enumerate(df.columns):
                    # BƯỚC BẢO VỆ: Lấp đầy các ô trống (NaN) bằng chuỗi rỗng "", 
                    # sau đó mới ép toàn bộ cột về kiểu chữ (str)
                        series_str = df[col].fillna("").astype(str)
                    # Lúc này 100% dữ liệu đã là chữ, hàm len() sẽ chạy mượt mà
                        max_len = max(series_str.map(len).max() if not series_str.empty else 0, len(str(col))) + 2
                                    
                    # Giới hạn độ rộng cột tối đa là 50 để tránh cột bị kéo ra quá dài
                        worksheet.set_column(idx, idx, min(max_len, 50))

                
                df_excel_all.to_excel(writer, sheet_name='Tổng Hợp', index=False)
                worksheet_all = writer.sheets['Tổng Hợp']
                header_format = writer.book.add_format({'bold': True, 'font_color': 'white', 'bg_color': '#0b5394', 'border': 1})
                for col_num, col_name in enumerate(df_excel_all.columns):
                    worksheet_all.write(0, col_num, col_name, header_format)
                auto_fit_columns(worksheet_all, df_excel_all)

                for tx_name, df_group in df_excel_all.groupby('Tài Xế'):
                    clean_sheet_name = str(tx_name).replace('/', '-').replace('\\', '-').strip()[:30]
                    if not clean_sheet_name or clean_sheet_name.lower() == 'nan':
                        clean_sheet_name = "Chưa phân tài"
                    df_group.to_excel(writer, sheet_name=clean_sheet_name, index=False)
                    worksheet_tx = writer.sheets[clean_sheet_name]
                    for col_num, col_name in enumerate(df_group.columns):
                        worksheet_tx.write(0, col_num, col_name, header_format)
                    auto_fit_columns(worksheet_tx, df_group)
                        
            st.download_button(
                label="📥 TẢI FILE EXCEL BÁO CÁO",
                data=excel_buffer.getvalue(),
                file_name=f"Bao_Cao_Van_Tai_{tu_ngay.strftime('%d%m%Y')}_{den_ngay.strftime('%d%m%Y')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary"
            )
            
            st.markdown("<br><b>📊 Bảng xem trước dữ liệu Báo cáo:</b>", unsafe_allow_html=True)
            df_app_display = df_result[cols_excel].copy()
            gb = GridOptionsBuilder.from_dataframe(df_app_display)
            gb.configure_default_column(resizable=True, filter=True, sortable=True, minWidth=150)
            gb.configure_pagination(paginationAutoPageSize=False, paginationPageSize=12)
            
            money_columns = ['Lương Chuyến Gốc', 'Thưởng Thêm', 'Tổng Lương Tài Xế', 'Phí Hải Quan', 'Phí Bốc Xếp', 'Phí Khác']
            for col in money_columns:
                gb.configure_column(col, type=["numericColumn", "numberColumnFilter"], valueFormatter="Math.floor(value).toString().replace(/(\\d)(?=(\\d{3})+(?!\\d))/g, '$1,') + ' đ'")
            
            custom_css = {".ag-header-cell": {"background-color": "#0b5394 !important"}, ".ag-header-cell-text": {"color": "white !important", "font-weight": "bold !important"}}
            AgGrid(df_app_display, gridOptions=gb.build(), custom_css=custom_css, theme="streamlit", fit_columns_on_grid_load=False, width="100%", allow_unsafe_jscode=True)

        else:
            st.info("📭 Không tìm thấy chuyến đi nào hoàn thành trong khoảng thời gian này.")

    except Exception as e:
        st.error(f"⚠️ Chi tiết lỗi truy vấn Báo cáo: {e}")

# ---------------------------------------------------------
# TAB 2: CẢNH BÁO XE TỒN ĐỌNG / CHƯA HOÀN THÀNH
# ---------------------------------------------------------
with tab_bc2:
    st.markdown("##### 🚨 Danh sách Chuyến đi chưa chốt sổ (Đã qua ngày)")
    st.info("Bảng này thống kê các chuyến đi có lịch chạy trước ngày hôm nay nhưng hệ thống vẫn ghi nhận là chưa hoàn thành (có thể do tài xế chưa báo cáo hoặc lỗi treo hệ thống).")
    
    try:
        tx_clause_2 = ""
        # Điều kiện lấy: Nằm trong bộ lọc ngày, nhưng BẮT BUỘC phải nhỏ hơn ngày hiện tại (CURDATE)
        params_bc2 = [f"{tu_ngay.strftime('%Y-%m-%d')} 00:00:00", f"{den_ngay.strftime('%Y-%m-%d')} 23:59:59"]
        
        if tai_xe_duoc_chon != 0:
            tx_clause_2 = "AND cdtx.tai_xe_id = %s"
            params_bc2.append(tai_xe_duoc_chon)

        sql_canh_bao = f"""
            SELECT 
                cd.id AS 'Mã Chuyến', 
                cd.ngay_chuyen_di AS 'Ngày Chạy', 
                x.bien_so_xe AS 'Biển Số Xe', 
                nv.ho_ten AS 'Tài Xế', 
                cd.ten_khach_hang AS 'Khách Hàng',
                cd.dia_diem_giao_nhan AS 'Lộ Trình', 
                cd.trang_thai_chuyen AS 'Trạng Thái HT',
                DATEDIFF(CURDATE(), DATE(cd.ngay_chuyen_di)) AS 'Số Ngày Trễ'
            FROM chuyen_di cd
            LEFT JOIN xe x ON cd.xe_id = x.id
            LEFT JOIN chuyen_di_tai_xe cdtx ON cd.id = cdtx.chuyen_di_id AND cdtx.loai_tai_xe = 'Tai_Chinh'
            LEFT JOIN nhan_vien nv ON cdtx.tai_xe_id = nv.id
            WHERE cd.trang_thai_chuyen NOT IN ('Hoan_Thanh', 'Huy_Chuyen')
              AND cd.ngay_chuyen_di >= %s 
              AND cd.ngay_chuyen_di <= %s
              AND DATE(cd.ngay_chuyen_di) < CURDATE()
              {tx_clause_2}
            ORDER BY cd.ngay_chuyen_di ASC
        """
        
        df_canh_bao = db.execute_query(sql_canh_bao, tuple(params_bc2))
        
        if isinstance(df_canh_bao, pd.DataFrame) and not df_canh_bao.empty:
            df_canh_bao['Ngày Chạy'] = pd.to_datetime(df_canh_bao['Ngày Chạy']).dt.strftime('%d/%m/%Y')
            
            st.error(f"⚠️ PHÁT HIỆN **{len(df_canh_bao)}** CHUYẾN ĐI QUÁ HẠN CHƯA QUYẾT TOÁN!")
            
            # --- KHẮC PHỤC LỖI APPLYMAP CỦA PANDAS ---
            def highlight_tre(val):
                color = '#ffcccc' if isinstance(val, (int, float)) and val > 0 else ''
                return f'background-color: {color}'
            
            # Sử dụng map() thay vì applymap() cho Pandas phiên bản mới
            try:
                styled_df = df_canh_bao.style.map(highlight_tre, subset=['Số Ngày Trễ'])
            except AttributeError:
                # Dự phòng nếu máy chủ đang chạy Pandas phiên bản rất cũ (< 2.1.0)
                styled_df = df_canh_bao.style.applymap(highlight_tre, subset=['Số Ngày Trễ'])
                
            st.dataframe(styled_df, use_container_width=True, hide_index=True)
            
            # --- CHỨC NĂNG XUẤT EXCEL CẢNH BÁO ---
            st.markdown("##### 📥 Xuất danh sách cần xử lý gấp")
            excel_buffer_cb = io.BytesIO()
            with pd.ExcelWriter(excel_buffer_cb, engine='xlsxwriter') as writer_cb:
                df_canh_bao.to_excel(writer_cb, sheet_name='Canh_Bao_Xe_Ton', index=False)
                worksheet_cb = writer_cb.sheets['Canh_Bao_Xe_Ton']
                
                # Định dạng tiêu đề cột: Màu NỀN ĐỎ để cảnh báo sự nguy cấp
                header_format_cb = writer_cb.book.add_format({
                    'bold': True, 'font_color': 'white', 'bg_color': '#cc0000', 'border': 1
                })
                
                for col_num, col_name in enumerate(df_canh_bao.columns):
                    worksheet_cb.write(0, col_num, col_name, header_format_cb)
                
                # Tự động căn chỉnh độ rộng cột (Auto-fit)
                for idx, col in enumerate(df_canh_bao):
                    series = df_canh_bao[col].astype(str)
                    max_len = max(series.map(len).max() if not series.empty else 0, len(str(col))) + 2
                    worksheet_cb.set_column(idx, idx, min(max_len, 50))
            
            st.download_button(
                label="🚨 TẢI FILE EXCEL CẢNH BÁO TỒN ĐỌNG",
                data=excel_buffer_cb.getvalue(),
                file_name=f"Canh_Bao_Chuyen_Ton_Dong_{datetime.date.today().strftime('%d%m%Y')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary"
            )
            
        else:
            st.success("🎉 Tuyệt vời! Không có chuyến đi nào bị tồn đọng hay treo hệ thống trong khoảng thời gian này.")
            st.balloons()
            
    except Exception as e:
        st.error(f"⚠️ Chi tiết lỗi truy vấn Cảnh báo: {e}")