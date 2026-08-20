import streamlit as st
import pandas as pd
import datetime
import io,re
import math
from utils_core import tao_tieu_de_kem_nut_refresh
from st_aggrid import AgGrid, GridOptionsBuilder
from trip_manager import get_cong_no_khach_hang

db = st.session_state['db']

# ==========================================
# HÀM HỖ TRỢ XỬ LÝ TÊN SHEET EXCEL DUY NHẤT & AN TOÀN
# ==========================================
def get_unique_sheet_name(name, existing_names):
    # Loại bỏ các ký tự không hợp lệ cho tên sheet Excel: [ ] : * ? / \
    clean_name = re.sub(r'[\[\]:\*\?/\\]', '-', str(name))
    clean_name = clean_name.strip()[:30]
    if not clean_name:
        clean_name = "Sheet"
    
    base_name = clean_name
    counter = 1
    # Kiểm tra trùng lặp không phân biệt hoa thường (case-insensitive)
    while clean_name.lower() in [e.lower() for e in existing_names]:
        suffix = f"_{counter}"
        clean_name = base_name[:30 - len(suffix)] + suffix
        counter += 1
    existing_names.append(clean_name)
    return clean_name
# ==========================================
# CSS ẨN HƯỚNG DẪN "PRESS ENTER TO SUBMIT"
# ==========================================
hide_enter_submit_css = """
<style>
    div[data-testid="InputInstructions"] {
        display: none !important;
        visibility: hidden !important;
    }
</style>
"""
st.markdown(hide_enter_submit_css, unsafe_allow_html=True)

st.markdown("<h3 style='text-align: center; color: #0b5394;'>📊 TRUNG TÂM BÁO CÁO THỐNG KÊ & XUẤT DỮ LIỆU EXCEL</h3>", unsafe_allow_html=True)

def render_tab_cong_no_khach_hang1(db):
    st.markdown("### 💰 ĐỐI SOÁT CÔNG NỢ KHÁCH HÀNG")
    
    col1, col2, col3 = st.columns(3)
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
    
    if st.button("🔍 Xem bảng kê đối soát", type="primary"):
        df_cong_no = get_cong_no_khach_hang(db, khach_hang_id, tu_ngay.strftime('%Y-%m-%d'), den_ngay.strftime('%Y-%m-%d'))
        
        if isinstance(df_cong_no, pd.DataFrame) and not df_cong_no.empty:
            ten_kh = df_cong_no.iloc[0]['ten_khach_hang']
            mst_kh = df_cong_no.iloc[0]['ma_so_thue'] or "Chưa cập nhật"
            dia_chi_kh = df_cong_no.iloc[0]['dia_chi'] or "Chưa cập nhật"
            
            st.info(f"**Đơn vị:** {ten_kh} | **MST:** {mst_kh} | **Địa chỉ:** {dia_chi_kh}")
            
            danh_sach_hoa_don = []
            tong_tien = 0.0
            
            for index, row in df_cong_no.iterrows():
                lo_trinh = str(row['dia_diem_giao_nhan']).replace(" ➡️ ", " đi ")
                bien_so = row['bien_so_xe'] if pd.notna(row['bien_so_xe']) else (row['bien_so_xe_ngoai'] if pd.notna(row.get('bien_so_xe_ngoai')) else "Chưa xác định")
                don_gia = float(row['doanh_thu'])
                tong_tien += don_gia
                
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
            df_display = df_export.copy()
            df_display['Đơn giá'] = df_display['Đơn giá'].apply(lambda x: f"{int(x):,}")
            df_display['Thành tiền'] = df_display['Thành tiền'].apply(lambda x: f"{int(x):,}")
            st.dataframe(df_display, use_container_width=True, hide_index=True)
            
            st.markdown(f"#### 💵 Tổng cộng tiền thanh toán: {int(tong_tien):,} VNĐ")
            
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                workbook = writer.book
                worksheet = workbook.add_worksheet('Bang_Ke_Hoa_Don')
                
                format_bold = workbook.add_format({'bold': True, 'font_size': 12})
                format_money = workbook.add_format({'num_format': '#,##0', 'valign': 'vcenter'})
                format_center = workbook.add_format({'align': 'center', 'valign': 'vcenter'})
                format_wrap = workbook.add_format({'text_wrap': True, 'valign': 'vcenter'})
                
                worksheet.write('A1', f"Tên đơn vị: {ten_kh}", format_bold)
                worksheet.write('A2', f"Mã số thuế: {mst_kh}", format_bold)
                worksheet.write('A3', f"Địa chỉ: {dia_chi_kh}", format_bold)
                
                headers = ["STT", "Tên hàng hóa, dịch vụ", "Đơn vị tính", "Số lượng", "Đơn giá", "Thành tiền"]
                for col_num, data in enumerate(headers):
                    worksheet.write(4, col_num, data, format_bold)
                
                for row_num, row_data in enumerate(danh_sach_hoa_don):
                    worksheet.write(row_num + 5, 0, row_data["STT"], format_center)
                    worksheet.write(row_num + 5, 1, row_data["Tên hàng hóa, dịch vụ"], format_wrap)
                    worksheet.write(row_num + 5, 2, row_data["Đơn vị tính"], format_center)
                    worksheet.write(row_num + 5, 3, row_data["Số lượng"], format_center)
                    worksheet.write(row_num + 5, 4, row_data["Đơn giá"], format_money)
                    worksheet.write(row_num + 5, 5, row_data["Thành tiền"], format_money)
                
                worksheet.set_column('A:A', 6)
                worksheet.set_column('B:B', 60)
                worksheet.set_column('C:C', 12)
                worksheet.set_column('D:D', 10)
                worksheet.set_column('E:F', 15)
                
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
#############################
def render_tab_cong_no_khach_hang(db):
    st.markdown("### 💰 ĐỐI SOÁT CÔNG NỢ KHÁCH HÀNG")
    
    # 1. BỘ LỌC THỜI GIAN
    col1, col2 = st.columns(2)
    with col1:
        tu_ngay = st.date_input("🗓️ Từ ngày (Khách hàng)", value=datetime.date.today().replace(day=1), key="tu_ngay_kh")
    with col2:
        den_ngay = st.date_input("🗓️ Đến ngày (Khách hàng)", value=datetime.date.today(), key="den_ngay_kh")
        
    st.divider()
    
    # 2. TRUY VẤN DỮ LIỆU CÔNG NỢ (Tuân thủ lấy khoi_luong_kg làm trọng tải và tính toán 0.15%)
    sql_kh_cong_no = """
        SELECT 
            COALESCE(kh.ten_khach_hang, cd.ten_khach_hang, 'Khách Lẻ / Khác') AS ten_khach_hang,
            COALESCE(kh.ma_so_thue, 'Chưa cập nhật') AS ma_so_thue,
            cd.id AS ma_chuyen,
            cd.ngay_chuyen_di,
            COALESCE(x.bien_so_xe, cd.bien_so_xe_ngoai, 'Chưa xác định') AS bien_so_xe,
            cd.dia_diem_giao_nhan,
            CAST(COALESCE(cd.khoi_luong_kg, 0) AS DECIMAL(15,2)) AS trong_tai,
            CAST(COALESCE(cd.doanh_thu, 0) AS DECIMAL(15,2)) AS phi_van_chuyen,
            CAST(COALESCE(cd.phi_boc_xep, 0) AS DECIMAL(15,2)) AS phi_boc_xep,
            CAST(COALESCE(cd.phi_khac, 0) AS DECIMAL(15,2)) AS phu_phi_phat_sinh,
            cd.ghi_chu
        FROM chuyen_di cd
        LEFT JOIN khach_hang kh ON cd.khach_hang_id = kh.id
        LEFT JOIN xe x ON cd.xe_id = x.id
        WHERE cd.trang_thai_chuyen = 'Hoan_Thanh'
          AND cd.ngay_chuyen_di >= %s 
          AND cd.ngay_chuyen_di <= %s
        ORDER BY ten_khach_hang ASC, cd.ngay_chuyen_di ASC
    """
    
    df_kh_raw = db.execute_query(sql_kh_cong_no, (tu_ngay.strftime('%Y-%m-%d'), den_ngay.strftime('%Y-%m-%d')))
    
    if isinstance(df_kh_raw, pd.DataFrame) and not df_kh_raw.empty:
        df_kh = df_kh_raw.copy()
        df_kh['ngay_chuyen_di'] = pd.to_datetime(df_kh['ngay_chuyen_di']).dt.strftime('%d/%m/%Y')
        
        # Tính toán các khoản phụ phí và Thành tiền ngay trên Pandas
        df_kh['phu_phi_xang_dau'] = df_kh['phi_van_chuyen'] * 0.0015
        df_kh['thanh_tien'] = df_kh['phi_van_chuyen'] + df_kh['phu_phi_xang_dau'] + df_kh['phi_boc_xep'] + df_kh['phu_phi_phat_sinh']
        
        # Thống kê tổng hợp theo từng khách hàng
        df_tong_hop_kh = df_kh.groupby(['ten_khach_hang', 'ma_so_thue']).agg(
            Tong_Chuyen=('ma_chuyen', 'count'),
            Tong_Trong_Tai=('trong_tai', 'sum'),
            Tong_Thanh_Tien=('thanh_tien', 'sum')
        ).reset_index().rename(columns={
            'ten_khach_hang': 'Tên Khách Hàng / Đơn Vị',
            'ma_so_thue': 'Mã Số Thuế',
            'Tong_Chuyen': 'Số Chuyến',
            'Tong_Trong_Tai': 'Tổng Trọng Tải (Kg)',
            'Tong_Thanh_Tien': 'Tổng Công Nợ Phải Thu (VNĐ)'
        })
        
        st.markdown("#### 📊 Bảng tổng hợp công nợ các khách hàng")
        df_th_kh_display = df_tong_hop_kh.copy()
        df_th_kh_display['Tổng Công Nợ Phải Thu (VNĐ)'] = df_th_kh_display['Tổng Công Nợ Phải Thu (VNĐ)'].apply(lambda x: f"{int(x):,}")
        st.dataframe(df_th_kh_display, use_container_width=True, hide_index=True)
        
        tong_dt_toan_bo = df_tong_hop_kh['Tổng Công Nợ Phải Thu (VNĐ)'].sum()
        st.markdown(f"##### 💵 Tổng nghĩa vụ phải thu toàn bộ khách hàng: {int(tong_dt_toan_bo):,} VNĐ")
        
        st.divider()
        st.markdown("#### 📑 Chi tiết chuyến xe theo từng khách hàng")
        selected_kh = st.selectbox("Chọn khách hàng để xem chi tiết", options=df_tong_hop_kh['Tên Khách Hàng / Đơn Vị'].tolist(), key="select_chi_tiet_kh")
        
        # Format hiển thị web
        df_chi_tiet_chon_kh = df_kh[df_kh['ten_khach_hang'] == selected_kh].drop(columns=['ma_so_thue', 'ma_chuyen'])
        st.dataframe(df_chi_tiet_chon_kh, use_container_width=True, hide_index=True)
        
        # =========================================================================
        # 3. KẾT XUẤT EXCEL THEO ĐÚNG MẪU: "DEBIT SAMPLE BAO TIN -KHACH HANG.xlsx"
        # =========================================================================
        buffer_kh = io.BytesIO()
        with pd.ExcelWriter(buffer_kh, engine='xlsxwriter') as writer:
            workbook = writer.book
            
            # --- ĐỊNH DẠNG (FORMATS) ---
            format_header = workbook.add_format({'bold': True, 'font_color': 'white', 'bg_color': '#0b5394', 'border': 1, 'align': 'center', 'valign': 'vcenter', 'text_wrap': True})
            format_bold = workbook.add_format({'bold': True, 'font_size': 11})
            format_money = workbook.add_format({'num_format': '#,##0', 'valign': 'vcenter', 'border': 1})
            format_center = workbook.add_format({'align': 'center', 'valign': 'vcenter', 'border': 1})
            format_left = workbook.add_format({'align': 'left', 'valign': 'vcenter', 'border': 1})
            format_title = workbook.add_format({'bold': True, 'font_size': 14, 'align': 'center', 'valign': 'vcenter'})
            
            # Format đặc biệt cho Header Công ty (Chứa tiếng Việt và tiếng Trung)
            format_company_header = workbook.add_format({
                'bold': True, 
                'font_size': 12, 
                'text_wrap': True, 
                'valign': 'top',
                'align': 'center'
            })
            
            # Nội dung Header chuẩn theo file mẫu
            header_text = """CÔNG TY TNHH THƯƠNG MẠI VÀ GIAO NHẬN VẬN TẢI BẢO TÍN
宝信运输贸易责任有限公司
TRỤ SỞ: Số 4, Đường Gia Tân 1, Khu phố Gia Tân, Phường Gia Lộc, Thị xã Trảng Bàng, Tỉnh Tây Ninh. 
地址： 西宁省，展鹏县，嘉绿社，嘉新丘，嘉新一路，四号
CN VP : Số 888, Quốc Lộ 22 , Khu phố Suối Sâu, Phường An Tịnh, Thị Xã Trảng Bàng, Tỉnh Tây Ninh. 
分办公司： 西宁省，展鹏县，安静社，深泉丘，22号公路，888号。
Mã số thuế/ 税号: 3901229506
Telephone: 0888039888/ 0988039888/ 0918694143                  Email: baoxnk@gmail.com"""

            # --- SHEET 1: TỔNG HỢP ---
            df_tong_hop_kh.to_excel(writer, sheet_name='Tong_Hop_Cong_No', index=False)
            ws_th_kh = writer.sheets['Tong_Hop_Cong_No']
            for col_num, col_name in enumerate(df_tong_hop_kh.columns):
                ws_th_kh.write(0, col_num, col_name, format_header)
            ws_th_kh.set_column('A:A', 40)
            ws_th_kh.set_column('B:E', 20)
            
            # --- SHEET N: BẢNG KÊ CHI TIẾT TỪNG KHÁCH HÀNG ---
            for kh_name, df_group in df_kh.groupby('ten_khach_hang'):
                # Xử lý tên sheet hợp lệ (Tối đa 30 ký tự)
                sheet_name = str(kh_name).replace('/', '-').replace('\\', '-').strip()[:30]
                if not sheet_name:
                    sheet_name = "Khach_Hang"
                
                worksheet_kh = workbook.add_worksheet(sheet_name)
                
                # Nới rộng chiều cao dòng 1 để chứa đủ Header công ty
                worksheet_kh.set_row(0, 130)
                worksheet_kh.merge_range('A1:K1', header_text, format_company_header)
                
                # Tiêu đề bảng kê
                thang_nam = tu_ngay.strftime('%m.%Y')
                worksheet_kh.merge_range('A2:K2', f"BẢNG KÊ CHI TIẾT CÔNG NỢ - {kh_name.upper()} THÁNG {thang_nam}", format_title)
                
                # Ghi tiêu đề cột theo form mẫu
                headers = [
                    "STT", "Ngày", "Biển Số Xe", "Nơi Giao Nhận", "Trọng Tải (Kg)", 
                    "Phí vận chuyển", "VC tăng 0.15%", "Phí bốc xếp", "Phụ phí phát sinh", "Thành Tiền", "Ghi Chú"
                ]
                for col_num, data in enumerate(headers):
                    worksheet_kh.write(3, col_num, data, format_header)
                
                # Ghi dữ liệu
                row_num = 4
                tong_thanh_tien = 0.0
                
                for index, row in df_group.reset_index(drop=True).iterrows():
                    thanh_tien = float(row['thanh_tien'])
                    tong_thanh_tien += thanh_tien
                    
                    worksheet_kh.write(row_num, 0, index + 1, format_center)
                    worksheet_kh.write(row_num, 1, row['ngay_chuyen_di'], format_center)
                    worksheet_kh.write(row_num, 2, row['bien_so_xe'], format_center)
                    worksheet_kh.write(row_num, 3, row['dia_diem_giao_nhan'], format_left)
                    worksheet_kh.write(row_num, 4, float(row['trong_tai']), format_center)
                    worksheet_kh.write(row_num, 5, float(row['phi_van_chuyen']), format_money)
                    worksheet_kh.write(row_num, 6, float(row['phu_phi_xang_dau']), format_money)
                    worksheet_kh.write(row_num, 7, float(row['phi_boc_xep']), format_money)
                    worksheet_kh.write(row_num, 8, float(row['phu_phi_phat_sinh']), format_money)
                    worksheet_kh.write(row_num, 9, thanh_tien, format_money)
                    worksheet_kh.write(row_num, 10, row['ghi_chu'] if pd.notna(row['ghi_chu']) else "", format_left)
                    row_num += 1
                
                # Tùy chỉnh độ rộng cột chuẩn mẫu
                worksheet_kh.set_column('A:A', 6)
                worksheet_kh.set_column('B:C', 14)
                worksheet_kh.set_column('D:D', 40)
                worksheet_kh.set_column('E:E', 12)
                worksheet_kh.set_column('F:J', 16)
                worksheet_kh.set_column('K:K', 25)
                
                # Dòng Tổng cộng
                worksheet_kh.write(row_num, 3, "TỔNG CỘNG TIỀN THANH TOÁN:", format_bold)
                worksheet_kh.write(row_num, 5, df_group['phi_van_chuyen'].sum(), format_money)
                worksheet_kh.write(row_num, 6, df_group['phu_phi_xang_dau'].sum(), format_money)
                worksheet_kh.write(row_num, 7, df_group['phi_boc_xep'].sum(), format_money)
                worksheet_kh.write(row_num, 8, df_group['phu_phi_phat_sinh'].sum(), format_money)
                worksheet_kh.write(row_num, 9, tong_thanh_tien, format_money)
                

        st.download_button(
            label="⬇️ Tải Báo Cáo Công Nợ Khách Hàng Theo Form Chuẩn (Excel)",
            data=buffer_kh.getvalue(),
            file_name=f"Cong_No_Khach_Hang_{tu_ngay.strftime('%d%m%Y')}_{den_ngay.strftime('%d%m%Y')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            use_container_width=True
        )
    else:
        st.warning("📭 Không tìm thấy chuyến đi nào đã hoàn thành cho khách hàng nào trong khoảng thời gian này.")
            
################################################


def render_tab_cong_no_nha_xe(db):
    st.markdown("### 🤝 ĐỐI SOÁT CÔNG NỢ NHÀ XE THUÊ NGOÀI")
    
    # 1. BỘ LỌC THỜI GIAN
    col1, col2 = st.columns(2)
    with col1:
        tu_ngay_nx = st.date_input("🗓️ Từ ngày (Nhà xe)", value=datetime.date.today().replace(day=1), key="tu_ngay_nx")
    with col2:
        den_ngay_nx = st.date_input("🗓️ Đến ngày (Nhà xe)", value=datetime.date.today(), key="den_ngay_nx")
        
    st.divider()
    
    # 2. TRUY VẤN DỮ LIỆU CÔNG NỢ NHÀ XE THUÊ NGOÀI (Giữ nguyên cấu trúc DB theo Source)
    sql_nx = """
        SELECT 
            COALESCE(cd.ten_doi_tac_ngoai, 'Khác / Chưa rõ') AS ten_doi_tac,
            cd.id AS ma_chuyen,
            cd.ngay_chuyen_di,
            cd.bien_so_xe_ngoai,
            cd.tai_xe_ngoai_ten,
            cd.tai_xe_ngoai_sdt,
            cd.dia_diem_giao_nhan,
            CAST(COALESCE(cd.chi_phi_thue_ngoai, 0) AS DECIMAL(15,2)) AS chi_phi_thue_ngoai,
            cd.hinh_thuc_thanh_toan_ngoai,
            cd.trang_thai_chuyen,
            cd.ghi_chu
        FROM chuyen_di cd
        WHERE (cd.is_thue_ngoai = 1 OR cd.xe_id IS NULL)
          AND cd.trang_thai_chuyen IN ('Hoan_Thanh', 'Quyet_Toan')
          AND cd.ngay_chuyen_di >= %s 
          AND cd.ngay_chuyen_di <= %s
        ORDER BY ten_doi_tac ASC, cd.ngay_chuyen_di DESC
    """
    
    df_nx_raw = db.execute_query(sql_nx, (tu_ngay_nx.strftime('%Y-%m-%d'), den_ngay_nx.strftime('%Y-%m-%d')))
    
    if isinstance(df_nx_raw, pd.DataFrame) and not df_nx_raw.empty:
        # Chuẩn hóa dữ liệu hiển thị trên Web
        df_nx = df_nx_raw.copy()
        df_nx['ngay_chuyen_di'] = pd.to_datetime(df_nx['ngay_chuyen_di']).dt.strftime('%d/%m/%Y')
        
        # Thống kê tổng hợp theo từng nhà xe để làm bảng Tổng hợp
        df_tong_hop = df_nx.groupby('ten_doi_tac').agg(
            Tong_Chuyen=('ma_chuyen', 'count'),
            Tong_Tien_Thue=('chi_phi_thue_ngoai', 'sum')
        ).reset_index().rename(columns={
            'ten_doi_tac': 'Tên Nhà Xe / Đối Tác',
            'Tong_Chuyen': 'Tổng Số Chuyến',
            'Tong_Tien_Thue': 'Tổng Tiền Cần Thanh Toán (VNĐ)'
        })
        
        st.markdown("#### 📊 Bảng tổng hợp công nợ các nhà xe")
        df_th_display = df_tong_hop.copy()
        df_th_display['Tổng Tiền Cần Thanh Toán (VNĐ)'] = df_th_display['Tổng Tiền Cần Thanh Toán (VNĐ)'].apply(lambda x: f"{int(x):,}")
        st.dataframe(df_th_display, use_container_width=True, hide_index=True)
        
        tong_cong_no_toàn_bo = df_tong_hop['Tổng Tiền Cần Thanh Toán (VNĐ)'].sum()
        st.markdown(f"##### 💵 Tổng nghĩa vụ thanh toán thuê ngoài: {int(tong_cong_no_toàn_bo):,} VNĐ")
        
        st.divider()
        st.markdown("#### 📑 Chi tiết chuyến xe theo từng nhà xe")
        selected_nha_xe = st.selectbox("Chọn nhà xe để xem chi tiết", options=df_tong_hop['Tên Nhà Xe / Đối Tác'].tolist())
        
        df_chi_tiet_chon = df_nx[df_nx['ten_doi_tac'] == selected_nha_xe]
        st.dataframe(df_chi_tiet_chon, use_container_width=True, hide_index=True)
        
        # =========================================================================
        # 3. KẾT XUẤT EXCEL THEO ĐÚNG MẪU HEADER CÔNG TY (Loại bỏ Trạng thái, Thêm STT, Thành tiền)
        # =========================================================================
        buffer_nx = io.BytesIO()
        with pd.ExcelWriter(buffer_nx, engine='xlsxwriter') as writer:
            workbook = writer.book
            
            # --- ĐỊNH DẠNG (FORMATS) ---
            format_header = workbook.add_format({'bold': True, 'font_color': 'white', 'bg_color': '#0b5394', 'border': 1, 'align': 'center', 'valign': 'vcenter', 'text_wrap': True})
            format_bold = workbook.add_format({'bold': True, 'font_size': 11})
            format_money = workbook.add_format({'num_format': '#,##0', 'valign': 'vcenter', 'border': 1})
            format_center = workbook.add_format({'align': 'center', 'valign': 'vcenter', 'border': 1})
            format_left = workbook.add_format({'align': 'left', 'valign': 'vcenter', 'border': 1})
            format_title = workbook.add_format({'bold': True, 'font_size': 14, 'align': 'center', 'valign': 'vcenter'})
            
            # Format đặc biệt cho Header Công ty (Chứa tiếng Việt và tiếng Trung)
            format_company_header = workbook.add_format({
                'bold': True, 
                'font_size': 12, 
                'text_wrap': True, 
                'valign': 'top',
                'align': 'center'
            })
            
            # Nội dung Header chuẩn theo file mẫu
            header_text = """CÔNG TY TNHH THƯƠNG MẠI VÀ GIAO NHẬN VẬN TẢI BẢO TÍN
宝信运输贸易责任有限公司
TRỤ SỞ: Số 4, Đường Gia Tân 1, Khu phố Gia Tân, Phường Gia Lộc, Thị xã Trảng Bàng, Tỉnh Tây Ninh. 
地址： 西宁省，展鹏县，嘉绿社，嘉新丘，嘉新一路，四号
CN VP : Số 888, Quốc Lộ 22 , Khu phố Suối Sâu, Phường An Tịnh, Thị Xã Trảng Bàng, Tỉnh Tây Ninh. 
分办公司： 西宁省，展鹏县，安静社，深泉丘，22号公路，888号。
Mã số thuế/ 税号: 3901229506
Telephone: 0888039888/ 0988039888/ 0918694143                  Email: baoxnk@gmail.com"""

            # Khởi tạo danh sách theo dõi tên sheet đã tạo để tránh trùng lặp
            existing_sheets_nx = []
            # --- SHEET 1: TỔNG HỢP ---
            df_tong_hop.to_excel(writer, sheet_name='Tong_Hop_Cong_No_Nha_Xe', index=False)
            ws_th = writer.sheets['Tong_Hop_Cong_No_Nha_Xe']
            for col_num, col_name in enumerate(df_tong_hop.columns):
                ws_th.write(0, col_num, col_name, format_header)
            ws_th.set_column('A:A', 35)
            ws_th.set_column('B:C', 25)
            
            # --- SHEET N: BẢNG KÊ CHI TIẾT TỪNG NHÀ XE ---
            for nha_xe_name, df_group in df_nx.groupby('ten_doi_tac'):
                # Sử dụng hàm get_unique_sheet_name để tự động xử lý ký tự đặc biệt, cắt gọn <=30 ký tự và chống trùng lặp không phân biệt hoa/thường
                sheet_name = get_unique_sheet_name(nha_xe_name, existing_sheets_nx)
                #sheet_name = str(nha_xe_name).replace('/', '-').replace('\\', '-').strip()[:30]
                if not sheet_name:
                    sheet_name = "Nha_Xe_Khac"
                
                ws_nx = workbook.add_worksheet(sheet_name)
                
                # Nới rộng chiều cao dòng 1 để chứa đủ Header công ty
                ws_nx.set_row(0, 130)
                # Ghép ô chứa Header (Tương tự file KH, kéo dài từ cột A đến cột I)
                ws_nx.merge_range('A1:I1', header_text, format_company_header)
                
                # Tiêu đề bảng kê (Bao gồm Tháng/Năm)
                thang_nam = tu_ngay_nx.strftime('%m.%Y')
                ws_nx.merge_range('A2:I2', f"BẢNG KÊ CHI TIẾT CÔNG NỢ - {str(nha_xe_name).upper()} THÁNG {thang_nam}", format_title)
                
                # Ghi tiêu đề cột: Thêm "STT", Thêm "Thành Tiền", Bỏ "Trạng Thái"
                headers = [
                    "STT", "Ngày Chạy", "Mã Chuyến", "Biển Số Xe", "Tên Tài Xế", 
                    "SĐT Tài Xế", "Nơi Giao Nhận", "Hình Thức TT", "Thành Tiền","Ghi Chú"
                ]
                for col_num, data in enumerate(headers):
                    ws_nx.write(3, col_num, data, format_header)
                
                # Ghi dữ liệu vòng lặp
                row_num = 4
                tong_thanh_tien = 0.0
                
                for index, row in df_group.reset_index(drop=True).iterrows():
                    thanh_tien = float(row['chi_phi_thue_ngoai'])
                    tong_thanh_tien += thanh_tien
                    
                    # Logic: Nếu hình thức TT trong DB là 'Tien_Mat' thì xuất chữ 'Tiền Mặt', ngược lại 'Công Nợ'
                    hinh_thuc_tt = "Tiền mặt" if row['hinh_thuc_thanh_toan_ngoai'] == 'Tien_Mat' else "Công nợ"
                    
                    ws_nx.write(row_num, 0, index + 1, format_center)  # STT
                    ws_nx.write(row_num, 1, row['ngay_chuyen_di'], format_center)
                    ws_nx.write(row_num, 2, row['ma_chuyen'], format_center)
                    ws_nx.write(row_num, 3, row['bien_so_xe_ngoai'] if pd.notna(row['bien_so_xe_ngoai']) else "", format_center)
                    ws_nx.write(row_num, 4, row['tai_xe_ngoai_ten'] if pd.notna(row['tai_xe_ngoai_ten']) else "", format_left)
                    ws_nx.write(row_num, 5, row['tai_xe_ngoai_sdt'] if pd.notna(row['tai_xe_ngoai_sdt']) else "", format_center)
                    ws_nx.write(row_num, 6, row['dia_diem_giao_nhan'] if pd.notna(row['dia_diem_giao_nhan']) else "", format_left)
                    ws_nx.write(row_num, 7, hinh_thuc_tt, format_center)
                    ws_nx.write(row_num, 8, thanh_tien, format_money)  # Thành tiền
                    ws_nx.write(row_num, 9, row['ghi_chu'] if pd.notna(row['ghi_chu']) else "", format_left)
                    row_num += 1
                
                # Tùy chỉnh độ rộng cột
                ws_nx.set_column('A:A', 6)
                ws_nx.set_column('B:D', 15)
                ws_nx.set_column('E:E', 25)
                ws_nx.set_column('F:F', 15)
                ws_nx.set_column('G:G', 45)
                ws_nx.set_column('H:H', 15)
                ws_nx.set_column('I:I', 20)
                
                # Dòng Tổng cộng
                ws_nx.write(row_num, 6, "TỔNG CỘNG TIỀN THANH TOÁN:", format_bold)
                ws_nx.write(row_num, 8, tong_thanh_tien, format_money)

        st.download_button(
            label="⬇️ Tải Báo Cáo Công Nợ Nhà Xe (Excel Multi-Sheets)",
            data=buffer_nx.getvalue(),
            file_name=f"Cong_No_Nha_Xe_{tu_ngay_nx.strftime('%d%m%Y')}_{den_ngay_nx.strftime('%d%m%Y')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            use_container_width=True
        )
    else:
        st.warning("📭 Không có dữ liệu chuyến xe thuê ngoài nào đã hoàn thành trong khoảng thời gian này.")
# ==========================================
# 1. KHU VỰC BỘ LỌC THÔNG MINH (NGÀY & TÀI XẾ)
# ==========================================
with st.container():
    st.markdown("##### 🔍 Bộ lọc điều kiện thống kê")
    c_date1, c_date2, c_driver = st.columns([1, 1, 2])
    
    today = datetime.date.today()
    start_of_month = today.replace(day=1)
    
    tu_ngay = c_date1.date_input("Từ ngày", value=start_of_month, format="DD/MM/YYYY")
    den_ngay = c_date2.date_input("Đến ngày", value=today, format="DD/MM/YYYY")
    
    sql_tx_list = "SELECT id, ho_ten FROM nhan_vien WHERE loai_nhan_vien IN ('Tai_Chinh', 'Tai_Phu') ORDER BY ho_ten"
    df_tx_filter = db.execute_query(sql_tx_list)
    
    tx_options = {0: "✨ Tất cả tài xế (Mặc định)"}
    if isinstance(df_tx_filter, pd.DataFrame) and not df_tx_filter.empty:
        for _, r in df_tx_filter.iterrows():
            tx_options[r['id']] = r['ho_ten']
            
    tai_xe_duoc_chon = c_driver.selectbox("Chọn Tài xế thống kê", options=list(tx_options.keys()), format_func=lambda x: tx_options[x], index=0)

st.divider()

# ==========================================
# 2. KHU VỰC HIỂN THỊ: CHIA CÁC TAB BÁO CÁO
# ==========================================
tab_bc1, tab_bc2, tab_bc3, tab_bc4, tab_bc5 = st.tabs(["📊 Chuyến đi trong ngày", "📊 Chuyến theo ngày chọn", "⚠️ Cảnh báo Xe tồn đọng / Quá hạn", "📊 Thống kê lương tài xế", "🏢 Đối soát Công nợ"])

# ---------------------------------------------------------
# TAB 1: DANH SÁCH CHUYẾN ĐI TRONG NGÀY (CHIA 2 BẢNG NỘI BỘ & THUÊ NGOÀI)
# ---------------------------------------------------------
with tab_bc1:
    tao_tieu_de_kem_nut_refresh("📋 Quản lý danh sách chuyến đi", "ref_ds_chuyen")
    @st.fragment
    def vung_thao_tac_quan_ly_chuyen_di():
        try:
            ngay_hom_nay = datetime.date.today().strftime('%Y-%m-%d')
            
            # 1. TRUY VẤN XE NỘI BỘ
            sql_list_noibo = """
                SELECT cd.id AS 'Mã', cd.ngay_chuyen_di AS 'Ngày', cd.ten_khach_hang AS 'Khách hàng',
                    x.bien_so_xe AS 'Biển Số', nv.ho_ten AS 'Tài Xế', cd.dia_diem_giao_nhan AS 'Lộ trình', 
                    cd.khoi_luong_kg AS 'Trọng tải (kg)', CAST(cd.cong_chuyen AS FLOAT) AS 'Lương chuyến',
                    CAST(cd.doanh_thu AS FLOAT) AS 'Doanh thu', CAST(cd.tien_them AS FLOAT) AS 'Thưởng thêm',
                    cd.ghi_chu AS 'Ghi chú', cd.trang_thai_chuyen AS 'Trạng thái'
                FROM chuyen_di cd 
                JOIN xe x ON cd.xe_id = x.id
                LEFT JOIN chuyen_di_tai_xe cdtx ON cd.id = cdtx.chuyen_di_id AND cdtx.loai_tai_xe = 'Tai_Chinh'
                LEFT JOIN nhan_vien nv ON cdtx.tai_xe_id = nv.id 
                WHERE cd.ngay_chuyen_di = %s
                ORDER BY cd.id DESC
            """
            df_noibo = db.execute_query(sql_list_noibo, (ngay_hom_nay,))

            # 2. TRUY VẤN XE THUÊ NGOÀI
            sql_list_ngoai = """
                SELECT cd.id AS 'Mã', cd.ngay_chuyen_di AS 'Ngày', cd.ten_khach_hang AS 'Khách hàng',
                    cd.bien_so_xe_ngoai AS 'Biển Số', cd.tai_xe_ngoai_ten AS 'Tài Xế', cd.dia_diem_giao_nhan AS 'Lộ trình', 
                    cd.khoi_luong_kg AS 'Trọng tải (kg)', CAST(cd.cong_chuyen AS FLOAT) AS 'Lương chuyến',
                    CAST(cd.doanh_thu AS FLOAT) AS 'Doanh thu', CAST(cd.chi_phi_thue_ngoai AS FLOAT) AS 'Phí Thuê Ngoài',
                    CAST(cd.tien_them AS FLOAT) AS 'Thưởng thêm',
                    cd.ghi_chu AS 'Ghi chú', cd.trang_thai_chuyen AS 'Trạng thái'
                FROM chuyen_di cd 
                WHERE cd.ngay_chuyen_di = %s AND (cd.xe_id IS NULL OR cd.is_thue_ngoai = 1)
                ORDER BY cd.id DESC
            """
            df_ngoai = db.execute_query(sql_list_ngoai, (ngay_hom_nay,))

            has_noibo = isinstance(df_noibo, pd.DataFrame) and not df_noibo.empty
            has_ngoai = isinstance(df_ngoai, pd.DataFrame) and not df_ngoai.empty

            if has_noibo or has_ngoai:
                # Gộp dữ liệu để tính tổng quan Dashboard chung trong ngày
                df_combined = pd.concat([df_noibo, df_ngoai], ignore_index=True) if (has_noibo and has_ngoai) else (df_noibo if has_noibo else df_ngoai)
                
                st.markdown("##### 📊 Tổng quan hoạt động trong ngày")
                so_chuyen_tao_moi = len(df_combined[df_combined['Trạng thái'] == 'Tao_Moi'])
                so_chuyen_dang_di = len(df_combined[df_combined['Trạng thái'] == 'Dang_Di'])
                so_chuyen_cho_qt = len(df_combined[df_combined['Trạng thái'] == 'Quyet_Toan'])
                so_chuyen_hoan_thanh = len(df_combined[df_combined['Trạng thái'] == 'Hoan_Thanh'])
                
                col_m1, col_m2, col_m3, col_m4 = st.columns(4)
                col_m1.metric("Tạo Mới (Chưa chạy)", f"{so_chuyen_tao_moi} Chuyến")
                col_m2.metric("Đang Đi", f"{so_chuyen_dang_di} Chuyến")
                col_m3.metric("Chờ Quyết Toán", f"{so_chuyen_cho_qt} Chuyến")
                col_m4.metric("Đã Hoàn Thành", f"{so_chuyen_hoan_thanh} Chuyến")
                
                st.divider()
                
                # --- HIỂN THỊ BẢNG 1: XE NỘI BỘ ---
                st.markdown("#### 🚛 Danh sách chuyến xe Nội bộ")
                if has_noibo:
                    df_nb_display = df_noibo.copy()
                    df_nb_display['Ngày'] = pd.to_datetime(df_nb_display['Ngày']).dt.strftime('%d/%m/%Y')
                    for col_money in ['Lương chuyến', 'Thưởng thêm', 'Doanh thu']:
                        if col_money in df_nb_display.columns:
                            df_nb_display[col_money] = df_nb_display[col_money].apply(lambda x: f"{x:,.0f}" if pd.notnull(x) else "0")
                    st.dataframe(df_nb_display, use_container_width=True, hide_index=True)
                else:
                    st.info("Không có chuyến xe nội bộ nào trong ngày hôm nay.")

                st.markdown("<br>", unsafe_allow_html=True)

                # --- HIỂN THỊ BẢNG 2: XE THUÊ NGOÀI ---
                st.markdown("#### 🤝 Danh sách chuyến xe Thuê ngoài")
                if has_ngoai:
                    df_ng_display = df_ngoai.copy()
                    df_ng_display['Ngày'] = pd.to_datetime(df_ng_display['Ngày']).dt.strftime('%d/%m/%Y')
                    for col_money in ['Lương chuyến', 'Thưởng thêm', 'Doanh thu', 'Phí Thuê Ngoài']:
                        if col_money in df_ng_display.columns:
                            df_ng_display[col_money] = df_ng_display[col_money].apply(lambda x: f"{x:,.0f}" if pd.notnull(x) else "0")
                    st.dataframe(df_ng_display, use_container_width=True, hide_index=True)
                else:
                    st.info("Không có chuyến xe thuê ngoài nào trong ngày hôm nay.")

            else:
                st.info(f"Chưa có dữ liệu chuyến đi nào trong ngày hôm nay ({ngay_hom_nay}).")
        except Exception as e:
            st.error(f"Lỗi truy xuất danh sách hôm nay: {e}")
    vung_thao_tac_quan_ly_chuyen_di()
# ---------------------------------------------------------
# TAB 2: TRA CỨU CHUYẾN ĐI THEO THỜI GIAN VÀ BỘ LỌC PHỤ (CHIA 2 BẢNG NỘI BỘ & THUÊ NGOÀI)
# ---------------------------------------------------------
with tab_bc2:
    tao_tieu_de_kem_nut_refresh("📋 Quản lý danh sách chuyến đi", "ref_ds_chuyen1")
    @st.fragment
    def vung_thao_tac_tra_cuu_chuyen_di():
        st.markdown("##### 🔍 Chọn điều kiện tra cứu")
        
        sql_tx_list = "SELECT id, ho_ten FROM nhan_vien WHERE loai_nhan_vien IN ('Tai_Chinh', 'Tai_Phu') ORDER BY ho_ten"
        df_tx_filter = db.execute_query(sql_tx_list)
        
        tx_options = {0: "✨ Tất cả Tài xế"}
        if isinstance(df_tx_filter, pd.DataFrame) and not df_tx_filter.empty:
            for _, r in df_tx_filter.iterrows():
                tx_options[r['id']] = r['ho_ten']
                
        status_mapping = {
            "Tất cả": "Tất cả",
            "Tạo Mới": "Tao_Moi",
            "Đang Đi": "Dang_Di",
            "Chờ Quyết Toán": "Quyet_Toan",
            "Đã Hoàn Thành": "Hoan_Thanh",
            "Đã Hủy": "Huy_Chuyen"
        }

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
        
        if btn_tra_cuu:
            try:
                # --- 1. TRUY VẤN NỘI BỘ ---
                sql_search_nb = """
                    SELECT cd.id AS 'Mã', cd.ngay_chuyen_di AS 'Ngày', cd.ten_khach_hang AS 'Khách hàng',
                        x.bien_so_xe AS 'Biển Số', nv.ho_ten AS 'Tài Xế', cd.dia_diem_giao_nhan AS 'Lộ trình', 
                        cd.khoi_luong_kg AS 'Trọng tải (kg)', CAST(cd.cong_chuyen AS FLOAT) AS 'Lương chuyến',
                        CAST(cd.doanh_thu AS FLOAT) AS 'Doanh thu', CAST(cd.tien_them AS FLOAT) AS 'Thưởng thêm',
                        cd.ghi_chu AS 'Ghi chú', cd.trang_thai_chuyen AS 'Trạng thái'
                    FROM chuyen_di cd 
                    JOIN xe x ON cd.xe_id = x.id
                    LEFT JOIN chuyen_di_tai_xe cdtx ON cd.id = cdtx.chuyen_di_id AND cdtx.loai_tai_xe = 'Tai_Chinh'
                    LEFT JOIN nhan_vien nv ON cdtx.tai_xe_id = nv.id 
                    WHERE cd.ngay_chuyen_di >= %s AND cd.ngay_chuyen_di <= %s
                """
                params_nb = [tu_ngay.strftime('%Y-%m-%d'), den_ngay.strftime('%Y-%m-%d')]
                
                if loc_trang_thai != "Tất cả":
                    sql_search_nb += " AND cd.trang_thai_chuyen = %s"
                    params_nb.append(status_mapping[loc_trang_thai])
                if loc_tai_xe != 0:
                    sql_search_nb += " AND cdtx.tai_xe_id = %s"
                    params_nb.append(loc_tai_xe)
                    
                sql_search_nb += " ORDER BY cd.ngay_chuyen_di DESC, cd.id DESC"
                df_search_nb = db.execute_query(sql_search_nb, tuple(params_nb))

                # --- 2. TRUY VẤN THUÊ NGOÀI ---
                sql_search_ngoai = """
                    SELECT cd.id AS 'Mã', cd.ngay_chuyen_di AS 'Ngày', cd.ten_khach_hang AS 'Khách hàng',
                        cd.bien_so_xe_ngoai AS 'Biển Số', cd.tai_xe_ngoai_ten AS 'Tài Xế', cd.dia_diem_giao_nhan AS 'Lộ trình', 
                        cd.khoi_luong_kg AS 'Trọng tải (kg)', CAST(cd.cong_chuyen AS FLOAT) AS 'Lương chuyến',
                        CAST(cd.doanh_thu AS FLOAT) AS 'Doanh thu', CAST(cd.chi_phi_thue_ngoai AS FLOAT) AS 'Phí Thuê Ngoài',
                        CAST(cd.tien_them AS FLOAT) AS 'Thưởng thêm',
                        cd.ghi_chu AS 'Ghi chú', cd.trang_thai_chuyen AS 'Trạng thái'
                    FROM chuyen_di cd 
                    WHERE cd.ngay_chuyen_di >= %s AND cd.ngay_chuyen_di <= %s AND (cd.xe_id IS NULL OR cd.is_thue_ngoai = 1)
                """
                params_ngoai = [tu_ngay.strftime('%Y-%m-%d'), den_ngay.strftime('%Y-%m-%d')]
                
                if loc_trang_thai != "Tất cả":
                    sql_search_ngoai += " AND cd.trang_thai_chuyen = %s"
                    params_ngoai.append(status_mapping[loc_trang_thai])
                
                # Lưu ý: Xe thuê ngoài không dùng tài xế nội bộ (cdtx), nếu lọc theo tài xế nội bộ thì xe thuê ngoài sẽ rỗng.
                if loc_tai_xe != 0:
                    sql_search_ngoai += " AND 1 = 0" # Khớp rỗng vì thuê ngoài không có tài xế nội bộ
                    
                sql_search_ngoai += " ORDER BY cd.ngay_chuyen_di DESC, cd.id DESC"
                df_search_ngoai = db.execute_query(sql_search_ngoai, tuple(params_ngoai))

                has_nb = isinstance(df_search_nb, pd.DataFrame) and not df_search_nb.empty
                has_ng = isinstance(df_search_ngoai, pd.DataFrame) and not df_search_ngoai.empty

                if has_nb or has_ng:
                    total_len = (len(df_search_nb) if has_nb else 0) + (len(df_search_ngoai) if has_ng else 0)
                    st.success(f"✅ Tìm thấy tổng cộng **{total_len}** chuyến đi thỏa mãn điều kiện.")

                    # Hiển thị bảng Nội bộ
                    st.markdown("#### 🚛 Danh sách chuyến xe Nội bộ")
                    if has_nb:
                        df_search_nb['Ngày'] = pd.to_datetime(df_search_nb['Ngày']).dt.strftime('%d/%m/%Y')
                        for col_money in ['Lương chuyến', 'Thưởng thêm', 'Doanh thu']:
                            if col_money in df_search_nb.columns:
                                df_search_nb[col_money] = df_search_nb[col_money].apply(lambda x: f"{x:,.0f}" if pd.notnull(x) else "0")
                        st.dataframe(df_search_nb, use_container_width=True, hide_index=True)
                    else:
                        st.info("Không tìm thấy chuyến xe nội bộ nào phù hợp bộ lọc.")

                    st.markdown("<br>", unsafe_allow_html=True)

                    # Hiển thị bảng Thuê ngoài
                    st.markdown("#### 🤝 Danh sách chuyến xe Thuê ngoài")
                    if has_ng:
                        df_search_ngoai['Ngày'] = pd.to_datetime(df_search_ngoai['Ngày']).dt.strftime('%d/%m/%Y')
                        for col_money in ['Lương chuyến', 'Thưởng thêm', 'Doanh thu', 'Phí Thuê Ngoài']:
                            if col_money in df_search_ngoai.columns:
                                df_search_ngoai[col_money] = df_search_ngoai[col_money].apply(lambda x: f"{x:,.0f}" if pd.notnull(x) else "0")
                        st.dataframe(df_search_ngoai, use_container_width=True, hide_index=True)
                    else:
                        st.info("Không tìm thấy chuyến xe thuê ngoài nào phù hợp bộ lọc.")
                else:
                    st.warning("📭 Không có dữ liệu chuyến đi nào khớp với bộ lọc bạn vừa chọn.")
                    
            except Exception as e:
                st.error(f"Lỗi hệ thống khi tra cứu dữ liệu: {e}")
    vung_thao_tac_tra_cuu_chuyen_di()
# ---------------------------------------------------------
# TAB 3: CẢNH BÁO XE TỒN ĐỌNG / CHƯA HOÀN THÀNH
# ---------------------------------------------------------
with tab_bc3:
    @st.fragment
    def vung_thao_tac_canh_bao_chuyen_di():
        st.markdown("##### 🚨 Danh sách Chuyến đi chưa chốt sổ (Đã qua ngày)")
        st.info("Bảng này thống kê các chuyến đi có lịch chạy trước ngày hôm nay nhưng hệ thống vẫn ghi nhận là chưa hoàn thành.")
        
        try:
            tx_clause_2 = ""
            params_bc2 = [f"{tu_ngay.strftime('%Y-%m-%d')} 00:00:00", f"{den_ngay.strftime('%Y-%m-%d')} 23:59:59"]
            
            if tai_xe_duoc_chon != 0:
                tx_clause_2 = "AND cdtx.tai_xe_id = %s"
                params_bc2.append(tai_xe_duoc_chon)

            sql_canh_bao = f"""
                SELECT 
                    cd.id AS 'Mã Chuyến', 
                    cd.ngay_chuyen_di AS 'Ngày Chạy', 
                    COALESCE(x.bien_so_xe, cd.bien_so_xe_ngoai) AS 'Biển Số Xe', 
                    COALESCE(nv.ho_ten, cd.tai_xe_ngoai_ten) AS 'Tài Xế', 
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
                
                def highlight_tre(val):
                    color = '#ffcccc' if isinstance(val, (int, float)) and val > 0 else ''
                    return f'background-color: {color}'
                
                try:
                    styled_df = df_canh_bao.style.map(highlight_tre, subset=['Số Ngày Trễ'])
                except AttributeError:
                    styled_df = df_canh_bao.style.applymap(highlight_tre, subset=['Số Ngày Trễ'])
                    
                st.dataframe(styled_df, use_container_width=True, hide_index=True)
                
                st.markdown("##### 📥 Xuất danh sách cần xử lý gấp")
                excel_buffer_cb = io.BytesIO()
                with pd.ExcelWriter(excel_buffer_cb, engine='xlsxwriter') as writer_cb:
                    df_canh_bao.to_excel(writer_cb, sheet_name='Canh_Bao_Xe_Ton', index=False)
                    worksheet_cb = writer_cb.sheets['Canh_Bao_Xe_Ton']
                    
                    header_format_cb = writer_cb.book.add_format({
                        'bold': True, 'font_color': 'white', 'bg_color': '#cc0000', 'border': 1
                    })
                    
                    for col_num, col_name in enumerate(df_canh_bao.columns):
                        worksheet_cb.write(0, col_num, col_name, header_format_cb)
                    
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
                
        except Exception as e:
            st.error(f"⚠️ Chi tiết lỗi truy vấn Cảnh báo: {e}")
    vung_thao_tac_canh_bao_chuyen_di()
# ---------------------------------------------------------
# TAB 4: BÁO CÁO TÀI CHÍNH (CÁC CHUYẾN ĐÃ HOÀN THÀNH)
# ---------------------------------------------------------
with tab_bc4:
    @st.fragment
    def vung_thao_tac_bao_cao_tai_chinh():
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
                    COALESCE(x.bien_so_xe, cd.bien_so_xe_ngoai) AS 'Biển Số Xe', 
                    CAST(COALESCE(x.tai_trong_thiet_ke, 0) AS DECIMAL(15,2)) AS 'Tải Trọng',
                    COALESCE(nv.ho_ten, cd.tai_xe_ngoai_ten) AS 'Tài Xế', 
                    cd.dia_diem_giao_nhan AS 'Lộ Trình', 
                    cd.khoi_luong_kg AS 'Trọng tải (kg)', 
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
                WHERE cd.trang_thai_chuyen = 'Hoan_Thanh' and cd.is_thue_ngoai = 0 
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

                st.markdown("##### 📥 Xuất báo cáo lương tài xế")
                excel_buffer = io.BytesIO()
                with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
                    cols_excel = [
                        'Mã Chuyến', 'Ngày hiển thị', 'Khách Hàng', 'Biển Số Xe', 'Tải Trọng', 'Tài Xế', 'Lộ Trình',
                        'Số Lít Dầu', 'Lương Chuyến Gốc', 'Thưởng Thêm', 'Tổng Lương Tài Xế',
                        'Phí Hải Quan', 'Phí Bốc Xếp', 'Phí Khác', 'Ghi chú'
                    ]
                    df_excel_all = df_result[cols_excel].rename(columns={'Ngày hiển thị': 'Ngày Chạy'}).copy()
                    
                    def auto_fit_columns(worksheet, df):
                        for idx, col in enumerate(df.columns):
                            series_str = df[col].fillna("").astype(str)
                            max_len = max(series_str.map(len).max() if not series_str.empty else 0, len(str(col))) + 2
                            worksheet.set_column(idx, idx, min(max_len, 50))

                    existing_sheets_tab4 = []

                    # Sheet tổng hợp
                    sheet_tong_hop_name = get_unique_sheet_name("Tổng Hợp", existing_sheets_tab4)
                    df_excel_all.to_excel(writer, sheet_name=sheet_tong_hop_name, index=False)
                    worksheet_all = writer.sheets[sheet_tong_hop_name]
                    header_format = writer.book.add_format({'bold': True, 'font_color': 'white', 'bg_color': '#0b5394', 'border': 1})
                    for col_num, col_name in enumerate(df_excel_all.columns):
                        worksheet_all.write(0, col_num, col_name, header_format)
                    auto_fit_columns(worksheet_all, df_excel_all)

                    # Sheet chi tiết từng tài xế (có chống trùng tên sheet hoa/thường)
                    for tx_name, df_group in df_excel_all.groupby('Tài Xế'):
                        clean_sheet_name = get_unique_sheet_name(tx_name, existing_sheets_tab4)
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
    vung_thao_tac_bao_cao_tai_chinh()
# ---------------------------------------------------------
# TAB 5: BÁO CÁO THỐNG KÊ CÔNG NỢ KHÁCH HÀNG
# ---------------------------------------------------------
with tab_bc5:
    @st.fragment
    def vung_thao_tac_bao_cao_cong_no_kh():
        try:
            db = st.session_state['db']
            # Chia thêm phân vùng nhỏ hoặc selectbox phụ bên trong Tab 5 nếu cần, 
            # hoặc chia thành 2 sub-tabs cho gọn gàng:
            sub_tab_cn1, sub_tab_cn2 = st.tabs(["🏢 Công Nợ Khách Hàng", "🤝 Công Nợ Nhà Xe Thuê Ngoài"])
            
            with sub_tab_cn1:
                render_tab_cong_no_khach_hang(db)
                
            with sub_tab_cn2:
                render_tab_cong_no_nha_xe(db)
        except Exception as e:
            st.error(f"⚠️ Chi tiết lỗi truy vấn Báo cáo: {e}")
    vung_thao_tac_bao_cao_cong_no_kh()