import streamlit as st
import pandas as pd
import datetime
import io
import math
from utils_core import tao_tieu_de_kem_nut_refresh
from st_aggrid import AgGrid, GridOptionsBuilder  # 👉 Bổ sung import AgGrid đồng bộ
from trip_manager import get_cong_no_khach_hang

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

def render_tab_cong_no_khach_hang(db):
    st.markdown("### 💰 ĐỐI SOÁT CÔNG NỢ KHÁCH HÀNG")
    
    # 1. BỘ LỌC TÌM KIẾM
    col1, col2, col3 = st.columns(3)
    
    # Lấy danh sách khách hàng
    df_kh = db.execute_query("SELECT id, ten_khach_hang, ma_so_thue FROM khach_hang")
    dict_kh = {}
    if isinstance(df_kh, pd.DataFrame) and not df_kh.empty:
         dict_kh = {row['id']: f"{row['ten_khach_hang']} (MST: {row['ma_so_thue']})" for _, row in df_kh.iterrows()}
    
    with col1:
        khach_hang_id = st.selectbox("🏢 Chọn Khách hàng", options=list(dict_kh.keys()), format_func=lambda x: dict_kh.get(x, "Không xác định"))
    with col2:
        tu_ngay = st.date_input("🗓️ Từ ngày", value=datetime.date.today().replace(day=1))
    with col3:
        den_ngay = st.date_input("🗓️ Đến ngày", value=datetime.date.today())
        
    st.divider()
    
    # 2. XỬ LÝ DỮ LIỆU
    if st.button("🔍 Xem bảng kê đối soát", type="primary"):
        df_cong_no = get_cong_no_khach_hang(db, khach_hang_id, tu_ngay.strftime('%Y-%m-%d'), den_ngay.strftime('%Y-%m-%d'))
        
        if isinstance(df_cong_no, pd.DataFrame) and not df_cong_no.empty:
            # Thông tin Header khách hàng
            ten_kh = df_cong_no.iloc[0]['ten_khach_hang']
            mst_kh = df_cong_no.iloc[0]['ma_so_thue'] or "Chưa cập nhật"
            dia_chi_kh = df_cong_no.iloc[0]['dia_chi'] or "Chưa cập nhật"
            
            st.info(f"**Đơn vị:** {ten_kh} | **MST:** {mst_kh} | **Địa chỉ:** {dia_chi_kh}")
            
            danh_sach_hoa_don = []
            tong_tien = 0.0
            
            # Chuẩn hóa dữ liệu theo cấu trúc cột của Hóa đơn VAT
            for index, row in df_cong_no.iterrows():
                lo_trinh = str(row['dia_diem_giao_nhan']).replace(" ➡️ ", " đi ")
                bien_so = row['bien_so_xe'] if pd.notna(row['bien_so_xe']) else "Chưa xác định"
                don_gia = float(row['doanh_thu'])
                tong_tien += don_gia
                
                # Nối chuỗi tạo tên hàng hóa chuẩn mực
                ten_hang_hoa = f"Cước vận chuyển từ {lo_trinh}, BKS: {bien_so}"
                
                danh_sach_hoa_don.append({
                    "STT": index + 1,
                    "Tên hàng hóa, dịch vụ": ten_hang_hoa,
                    "Đơn vị tính": "Chuyến",
                    "Số lượng": 1,
                    "Đơn giá": don_gia,
                    "Thành tiền": don_gia
                })
            
            df_export = pd.DataFrame(danh_sach_hoa_don)
            
            # Hiển thị xem trước trên web
            df_display = df_export.copy()
            df_display['Đơn giá'] = df_display['Đơn giá'].apply(lambda x: f"{int(x):,}")
            df_display['Thành tiền'] = df_display['Thành tiền'].apply(lambda x: f"{int(x):,}")
            st.dataframe(df_display, use_container_width=True, hide_index=True)
            
            st.markdown(f"#### 💵 Tổng cộng tiền thanh toán: {int(tong_tien):,} VNĐ")
            
            # 3. KẾT XUẤT EXCEL CHUẨN FORM
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                workbook = writer.book
                worksheet = workbook.add_worksheet('Bang_Ke_Hoa_Don')
                
                # Định dạng style
                format_bold = workbook.add_format({'bold': True, 'font_size': 12})
                format_money = workbook.add_format({'num_format': '#,##0', 'valign': 'vcenter'})
                format_center = workbook.add_format({'align': 'center', 'valign': 'vcenter'})
                format_wrap = workbook.add_format({'text_wrap': True, 'valign': 'vcenter'})
                
                # Ghi Header thông tin công ty vào Excel
                worksheet.write('A1', f"Tên đơn vị: {ten_kh}", format_bold)
                worksheet.write('A2', f"Mã số thuế: {mst_kh}", format_bold)
                worksheet.write('A3', f"Địa chỉ: {dia_chi_kh}", format_bold)
                
                # Ghi tiêu đề cột
                headers = ["STT", "Tên hàng hóa, dịch vụ", "Đơn vị tính", "Số lượng", "Đơn giá", "Thành tiền"]
                for col_num, data in enumerate(headers):
                    worksheet.write(4, col_num, data, format_bold)
                
                # Đổ dữ liệu
                for row_num, row_data in enumerate(danh_sach_hoa_don):
                    worksheet.write(row_num + 5, 0, row_data["STT"], format_center)
                    worksheet.write(row_num + 5, 1, row_data["Tên hàng hóa, dịch vụ"], format_wrap)
                    worksheet.write(row_num + 5, 2, row_data["Đơn vị tính"], format_center)
                    worksheet.write(row_num + 5, 3, row_data["Số lượng"], format_center)
                    worksheet.write(row_num + 5, 4, row_data["Đơn giá"], format_money)
                    worksheet.write(row_num + 5, 5, row_data["Thành tiền"], format_money)
                
                # Tùy chỉnh độ rộng cột
                worksheet.set_column('A:A', 6)
                worksheet.set_column('B:B', 60)
                worksheet.set_column('C:C', 12)
                worksheet.set_column('D:D', 10)
                worksheet.set_column('E:F', 15)
                
                # Dòng tổng cộng
                last_row = len(danh_sach_hoa_don) + 5
                worksheet.write(last_row, 1, "Tổng cộng tiền thanh toán:", format_bold)
                worksheet.write(last_row, 5, tong_tien, format_money)

            st.download_button(
                label="⬇️ Tải Bảng Kê (Excel)",
                data=buffer.getvalue(),
                file_name=f"Bang_Ke_Doi_Soat_{ten_kh.replace(' ', '_')}_{tu_ngay.strftime('%m%Y')}.xlsx",
                type="primary",
                use_container_width=True
            )
        else:
            st.warning("Không tìm thấy chuyến đi nào đã hoàn thành cho khách hàng này trong thời gian trên.")
            

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
tab_bc1, tab_bc2,tab_bc3,tab_bc4,tab_bc5 = st.tabs(["📊 Chuyến đi trong ngày ","📊 Chuyến theo ngày chọn ","⚠️ Cảnh báo Xe tồn đọng / Quá hạn","📊 Thống kê lương tài xế ","🏢 Đối soát Công nợ"])

# ==========================================
# KHU VỰC: DANH SÁCH CHUYẾN ĐI
# ==========================================



# ---------------------------------------------------------
# TAB 1: DANH SÁCH CHUYẾN ĐI TRONG NGÀY
# ---------------------------------------------------------
with tab_bc1:
    tao_tieu_de_kem_nut_refresh("📋 Quản lý danh sách chuyến đi", "ref_ds_chuyen")
    try:
        sql_list = """
            SELECT cd.id AS 'Mã', cd.ngay_chuyen_di AS 'Ngày', cd.ten_khach_hang AS 'Khách hàng',
                   x.bien_so_xe AS 'Biển Số', nv.ho_ten AS 'Tài Xế', cd.dia_diem_giao_nhan AS 'Lộ trình', 
                   CAST(cd.so_km_thuc_te AS FLOAT) AS 'Số KM', CAST(cd.cong_chuyen AS FLOAT) AS 'Lương chuyến',
                   CAST(cd.doanh_thu AS FLOAT) AS 'Doanh thu', CAST(cd.tien_them AS FLOAT) AS 'Thưởng thêm',
                   cd.ghi_chu AS 'Ghi chú', cd.trang_thai_chuyen AS 'Trạng thái'
            FROM chuyen_di cd 
            LEFT JOIN xe x ON cd.xe_id = x.id
            LEFT JOIN chuyen_di_tai_xe cdtx ON cd.id = cdtx.chuyen_di_id AND cdtx.loai_tai_xe = 'Tai_Chinh'
            LEFT JOIN nhan_vien nv ON cdtx.tai_xe_id = nv.id 
            WHERE cd.ngay_chuyen_di = CURDATE()
            ORDER BY cd.id DESC
        """
        df_chuyen = db.execute_query(sql_list)
        
        if isinstance(df_chuyen, pd.DataFrame) and not df_chuyen.empty:
            # Tích hợp Dashboard thống kê xe trong ngày
            st.markdown("##### 📊 Tổng quan hoạt động xe hôm nay")
            xe_chua_chay = df_chuyen[df_chuyen['Trạng thái'] == 'Tao_Moi']['Biển Số'].nunique()
            xe_dang_chay = df_chuyen[df_chuyen['Trạng thái'] == 'Dang_Di']['Biển Số'].nunique()
            xe_cho_qt = df_chuyen[df_chuyen['Trạng thái'] == 'Quyet_Toan']['Biển Số'].nunique()
            xe_hoan_thanh = df_chuyen[df_chuyen['Trạng thái'] == 'Hoan_Thanh']['Biển Số'].nunique()
            
            col_m1, col_m2, col_m3, col_m4 = st.columns(4)
            col_m1.metric("Tạo Mới (Chưa chạy)", f"{xe_chua_chay} Xe")
            col_m2.metric("Đang Đi", f"{xe_dang_chay} Xe")
            col_m3.metric("Chờ Quyết Toán", f"{xe_cho_qt} Xe")
            col_m4.metric("Đã Hoàn Thành", f"{xe_hoan_thanh} Xe")
            
            st.divider()

            df_chuyen['Ngày'] = pd.to_datetime(df_chuyen['Ngày']).dt.strftime('%d/%m/%Y')
            for col_money in ['Lương chuyến', 'Thưởng thêm','Doanh thu']:
                df_chuyen[col_money] = df_chuyen[col_money].apply(lambda x: f"{x:,.0f}" if pd.notnull(x) else "0")
    
            col_opt1, col_opt2 = st.columns([1, 7]) 
            with col_opt1:
                che_do_xem_chuyen = st.selectbox("Hiển thị:", ["20 dòng", "Tất cả"], key="xem_chuyen_t1")
            
            if che_do_xem_chuyen == "Tất cả":
                st.caption(f"Đang hiển thị toàn bộ {len(df_chuyen)} chuyến đi.")
                st.dataframe(df_chuyen, use_container_width=True, hide_index=True)
            else:
                rows_per_page = 20
                total_rows = len(df_chuyen)
                total_pages = math.ceil(total_rows / rows_per_page)
                
                if total_pages > 0:
                    if 'page_chuyen_t1' not in st.session_state:
                        st.session_state['page_chuyen_t1'] = 1
                        
                    if st.session_state['page_chuyen_t1'] < 1: st.session_state['page_chuyen_t1'] = 1
                    elif st.session_state['page_chuyen_t1'] > total_pages: st.session_state['page_chuyen_t1'] = total_pages
                        
                    col1, col2, col3 = st.columns([1, 2, 1])
                    with col1:
                        if st.button("⬅️ Trước", key="prev_t1", disabled=(st.session_state['page_chuyen_t1'] <= 1)):
                            st.session_state['page_chuyen_t1'] -= 1
                            st.rerun()
                    with col3:
                        if st.button("Sau ➡️", key="next_t1", disabled=(st.session_state['page_chuyen_t1'] >= total_pages)):
                            st.session_state['page_chuyen_t1'] += 1
                            st.rerun()
                    with col2:
                        st.markdown(f"<div style='text-align: center; margin-top: 5px;'>Trang {st.session_state['page_chuyen_t1']} / {total_pages}</div>", unsafe_allow_html=True)

                    start_idx = (st.session_state['page_chuyen_t1'] - 1) * rows_per_page
                    st.dataframe(df_chuyen.iloc[start_idx:start_idx + rows_per_page], use_container_width=True, hide_index=True)
        else:
            st.info("Chưa có dữ liệu chuyến đi nào trong ngày hôm nay.")
    except Exception as e:
        st.error(f"Lỗi truy xuất danh sách hôm nay: {e}")

# ---------------------------------------------------------
# TAB 2: TRA CỨU CHUYẾN ĐI THEO THỜI GIAN VÀ BỘ LỌC PHỤ
# ---------------------------------------------------------
with tab_bc2:
    tao_tieu_de_kem_nut_refresh("📋 Quản lý danh sách chuyến đi", "ref_ds_chuyen1")
    st.markdown("##### 🔍 Chọn điều kiện tra cứu")
    
    # --- 1. LẤY DANH SÁCH TÀI XẾ TỪ DATABASE ĐỂ ĐƯA VÀO BỘ LỌC ---
    sql_tx_list = "SELECT id, ho_ten FROM nhan_vien WHERE loai_nhan_vien IN ('Tai_Chinh', 'Tai_Phu') ORDER BY ho_ten"
    df_tx_filter = db.execute_query(sql_tx_list)
    
    tx_options = {0: "✨ Tất cả Tài xế"}
    if isinstance(df_tx_filter, pd.DataFrame) and not df_tx_filter.empty:
        for _, r in df_tx_filter.iterrows():
            tx_options[r['id']] = r['ho_ten']
            
    # Dictionary map trạng thái thân thiện sang đúng chuẩn ENUM trong Database
    status_mapping = {
        "Tất cả": "Tất cả",
        "Tạo Mới": "Tao_Moi",
        "Đang Đi": "Dang_Di",
        "Chờ Quyết Toán": "Quyet_Toan",
        "Đã Hoàn Thành": "Hoan_Thanh",
        "Đã Hủy": "Huy_Chuyen"
    }

    # --- 2. XÂY DỰNG GIAO DIỆN BỘ LỌC TÙY CHỈNH ---
    col_d1, col_d2 = st.columns(2)
    today = datetime.date.today()
    start_of_week = today - datetime.timedelta(days=7)
    
    with col_d1:
        tu_ngay = st.date_input("Từ ngày", value=start_of_week, format="DD/MM/YYYY", key="tu_ngay_tc")
        loc_tai_xe = st.selectbox("Lọc theo Tài xế", options=list(tx_options.keys()), format_func=lambda x: tx_options[x], key="loc_tx_tc")
    with col_d2:
        den_ngay = st.date_input("Đến ngày", value=today, format="DD/MM/YYYY", key="den_ngay_tc")
        loc_trang_thai = st.selectbox("Lọc theo Trạng thái", options=list(status_mapping.keys()), key="loc_tt_tc")
        
    st.markdown("<br>", unsafe_allow_html=True)
    btn_tra_cuu = st.button("🚀 Thực thi tra cứu", type="primary", use_container_width=True)
        
    st.divider()
    
    # --- 3. XỬ LÝ TRUY VẤN DỮ LIỆU ---
    if btn_tra_cuu:
        try:
            # Câu lệnh cơ sở
            sql_search = """
                SELECT cd.id AS 'Mã', cd.ngay_chuyen_di AS 'Ngày', cd.ten_khach_hang AS 'Khách hàng',
                       x.bien_so_xe AS 'Biển Số', nv.ho_ten AS 'Tài Xế', cd.dia_diem_giao_nhan AS 'Lộ trình', 
                       CAST(cd.so_km_thuc_te AS FLOAT) AS 'Số KM', CAST(cd.cong_chuyen AS FLOAT) AS 'Lương chuyến',
                       CAST(cd.doanh_thu AS FLOAT) AS 'Doanh thu', CAST(cd.tien_them AS FLOAT) AS 'Thưởng thêm',
                       cd.ghi_chu AS 'Ghi chú', cd.trang_thai_chuyen AS 'Trạng thái'
                FROM chuyen_di cd 
                LEFT JOIN xe x ON cd.xe_id = x.id
                LEFT JOIN chuyen_di_tai_xe cdtx ON cd.id = cdtx.chuyen_di_id AND cdtx.loai_tai_xe = 'Tai_Chinh'
                LEFT JOIN nhan_vien nv ON cdtx.tai_xe_id = nv.id 
                WHERE cd.ngay_chuyen_di >= %s AND cd.ngay_chuyen_di <= %s
            """
            
            # Khởi tạo mảng tham số với 2 ngày mặc định
            params_search = [tu_ngay.strftime('%Y-%m-%d'), den_ngay.strftime('%Y-%m-%d')]
            
            # Điều kiện phụ 1: Nếu có chọn lọc trạng thái cụ thể
            if loc_trang_thai != "Tất cả":
                sql_search += " AND cd.trang_thai_chuyen = %s"
                params_search.append(status_mapping[loc_trang_thai])
                
            # Điều kiện phụ 2: Nếu có chọn lọc đích danh tài xế
            if loc_tai_xe != 0:
                sql_search += " AND cdtx.tai_xe_id = %s"
                params_search.append(loc_tai_xe)
                
            # Chốt câu lệnh SQL bằng ORDER BY
            sql_search += " ORDER BY cd.ngay_chuyen_di DESC, cd.id DESC"
            
            # Truy vấn DB
            df_search = db.execute_query(sql_search, tuple(params_search))
            
            # --- 4. HIỂN THỊ KẾT QUẢ ---
            if isinstance(df_search, pd.DataFrame) and not df_search.empty:
                st.success(f"✅ Tìm thấy **{len(df_search)}** chuyến đi thỏa mãn điều kiện.")
                
                # Format định dạng tiền tệ và ngày tháng
                df_search['Ngày'] = pd.to_datetime(df_search['Ngày']).dt.strftime('%d/%m/%Y')
                for col_money in ['Lương chuyến', 'Thưởng thêm','Doanh thu']:
                    df_search[col_money] = df_search[col_money].apply(lambda x: f"{x:,.0f}" if pd.notnull(x) else "0")
                
                # In bảng
                st.dataframe(df_search, use_container_width=True, hide_index=True)
            else:
                st.warning("📭 Không có dữ liệu chuyến đi nào khớp với bộ lọc bạn vừa chọn.")
                
        except Exception as e:
            st.error(f"Lỗi hệ thống khi tra cứu dữ liệu: {e}")
# ---------------------------------------------------------
# TAB 3: CẢNH BÁO XE TỒN ĐỌNG / CHƯA HOÀN THÀNH
# ---------------------------------------------------------
with tab_bc3:
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
            #st.balloons()
            
    except Exception as e:
        st.error(f"⚠️ Chi tiết lỗi truy vấn Cảnh báo: {e}")
# ---------------------------------------------------------
# TAB 4: BÁO CÁO TÀI CHÍNH (CÁC CHUYẾN ĐÃ HOÀN THÀNH)
# ---------------------------------------------------------
with tab_bc4:
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
            st.markdown("##### 📥 Xuất báo cáo lương tài xế")
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
##################### báo cáo thống kế công nợ khách hàng
with tab_bc5:
    try:
        # Gọi hàm đã định nghĩa ở trên (nhớ lấy db từ session_state)
        db = st.session_state['db']
        render_tab_cong_no_khach_hang(db)
    except Exception as e:
            st.error(f"⚠️ Chi tiết lỗi truy vấn Báo cáo: {e}")    



