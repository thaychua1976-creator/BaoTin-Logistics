import streamlit as st
import pandas as pd
import datetime
import io, math, os
from map_service import MapService
import time, requests
import streamlit.components.v1 as components
from trip_manager import delete_trip_safe, settle_trip_transaction, save_trip_full_process, update_trip_transaction, update_trip_full_process, goi_gps_theo_thoi_gian_tuy_chinh
from utils_core import parse_money_input, doc_anh_cay_xang, tao_tieu_de_kem_nut_refresh
from dotenv import load_dotenv
load_dotenv()

# Khởi tạo dịch vụ
@st.cache_resource
def get_map_service(): return MapService()

map_srv = get_map_service()
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

# 1. ĐỊNH NGHĨA ÁNH XẠ TRẠNG THÁI (Đồng bộ với ENUM dưới Database)
STATUS_MAP = {
    "Tạo Mới": "Tao_Moi",
    "Đang Đi": "Dang_Di",
    "Quyết Toán": "Quyet_Toan",
    "Hoàn Thành": "Hoan_Thanh",
    "Hủy Chuyến": "Huy_Chuyen"
}

st.markdown("<h3 style='text-align: center; color: #0b5394;'>📝 PHÂN HỆ QUẢN LÝ VÀ ĐIỀU PHỐI CHUYẾN ĐI NÂNG CAO</h3>", unsafe_allow_html=True)

# Mở rộng thành 5 Tab nghiệp vụ
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📋 Danh sách chuyến", 
    "➕ Tạo/Sửa chuyến thủ công", 
    "🏁 Quyết toán đơn chuyến",
    "🏁 Sửa chuyến đi đã quyết toán", 
    "🤖 Tạo chuyến tự động/ Excel tool" 
])

# ==========================================
# 🛠️ CHUẨN HÓA DỮ LIỆU TỪ DATABASE (KHẮC PHỤC LỖI ÉP KIỂU)
# ==========================================
# CÔNG CỤ LỌC XE TRỐNG (TỐI ƯU SQL BACKEND)
sql_xe_trong = """
    SELECT x.id, x.bien_so_xe, x.tai_trong_thiet_ke, x.dung_tich_cbm, x.tai_xe_co_dinh_id 
    FROM xe x 
    WHERE x.trang_thai = 'Dang_Hoat_Dong'
    AND NOT EXISTS (
        SELECT 1 FROM chuyen_di cd 
        WHERE cd.xe_id = x.id 
        AND cd.trang_thai_chuyen IN ('Tao_Moi', 'Dang_Di') 
    )
"""

df_xe_full = db.execute_query(sql_xe_trong)
df_tx_full = db.execute_query("SELECT id, ho_ten FROM nhan_vien WHERE loai_nhan_vien IN ('Tai_Chinh', 'Tai_Phu') AND trang_thai='Dang_Lam_Viec'")

# Đảm bảo toàn bộ ID (khóa) là kiểu số nguyên (int) gốc của Python để hàm index() chạy chính xác 100%
xe_map = {}
if isinstance(df_xe_full, pd.DataFrame) and not df_xe_full.empty:
    for _, r in df_xe_full.iterrows():
        xe_map[int(r['id'])] = r

tx_opts = {}
if isinstance(df_tx_full, pd.DataFrame) and not df_tx_full.empty:
    for _, r in df_tx_full.iterrows():
        tx_opts[int(r['id'])] = str(r['ho_ten'])

# ==========================================
# TAB 1: DANH SÁCH CHUYẾN ĐI 
# ==========================================
with tab1:
    tao_tieu_de_kem_nut_refresh("📋 Danh sách chuyến đi trong ngày", "ref_tab1")
    try:
        sql_list = """
            SELECT cd.id AS 'Mã', cd.ngay_chuyen_di AS 'Ngày', cd.ten_khach_hang AS 'Khách hàng',
                   x.bien_so_xe AS 'Biển Số', nv.ho_ten AS 'Tài Xế', cd.dia_diem_giao_nhan AS 'Lộ trình', 
                   CAST(cd.so_km_thuc_te AS FLOAT) AS 'Số KM', CAST(cd.cong_chuyen AS FLOAT) AS 'Lương chuyến',
                   CAST(cd.doanh_thu AS FLOAT) AS 'Doanh thu', CAST(cd.tien_them AS FLOAT) AS 'Thưởng thêm',cd.ghi_chu AS 'Ghi chú', cd.trang_thai_chuyen AS 'Trạng thái'
            FROM chuyen_di cd 
            LEFT JOIN xe x ON cd.xe_id = x.id
            LEFT JOIN chuyen_di_tai_xe cdtx ON cd.id = cdtx.chuyen_di_id AND cdtx.loai_tai_xe = 'Tai_Chinh'
            LEFT JOIN nhan_vien nv ON cdtx.tai_xe_id = nv.id 
            WHERE cd.ngay_chuyen_di = CURDATE()
            ORDER BY cd.id DESC
        """
        df_chuyen = db.execute_query(sql_list)
        
        if isinstance(df_chuyen, pd.DataFrame) and not df_chuyen.empty:
            
            # --- DASHBOARD THỐNG KÊ TRẠNG THÁI XE ---
            st.markdown("##### 📊 Tổng quan hoạt động xe trong ngày")
            
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
            
            # --- [TÍNH NĂNG MỚI] XỬ LÝ DỮ LIỆU XUẤT EXCEL GỬI ZALO ---
            danh_sach_zalo = []
            for _, row in df_chuyen.iterrows():
                # Tạo tên group từ biển số (Loại bỏ ký tự đặc biệt)
                bien_so = str(row['Biển Số']) if pd.notna(row['Biển Số']) else "CHUA_GAN_XE"
                ten_group = "".join([c for c in bien_so if c.isalnum()]).upper()
                
                # Xử lý ghi chú
                ghi_chu = str(row['Ghi chú']) if pd.notna(row['Ghi chú']) and str(row['Ghi chú']).strip() != "" else 'Không'
                
                # Định dạng nội dung tin nhắn Zalo chuẩn
                noi_dung_chat = (
                    f"LỆNH ĐIỀU XE BẢO TÍN \n"
                    f"- Mã chuyến: {row['Mã']}\n"
                    f"- Ngày chạy: {row['Ngày']}\n"
                    f"- Khách hàng: {row['Khách hàng']}\n"
                    f"- Lộ trình: {row['Lộ trình']}\n"
                    f"- Ghi chú: {ghi_chu}\n"
                    
                )
                
                danh_sach_zalo.append({
                    "ten_group": ten_group,
                    "noi_dung_chat": noi_dung_chat,
                    "Mã Hệ Thống (Trip ID)": row['Mã'],
                    "Ngày Chạy": row['Ngày'],
                    "Khách Hàng": row['Khách hàng'],
                    "Biển Số Xe": row['Biển Số'],
                    "Tên Tài Xế": row['Tài Xế'],
                    "Lộ Trình": row['Lộ trình'],
                    "Trạng Thái": row['Trạng thái']
                })
            
            # Ghi ra bộ nhớ đệm Buffer để tải xuống
            df_zalo_export = pd.DataFrame(danh_sach_zalo)
            buffer_zalo = io.BytesIO()
            with pd.ExcelWriter(buffer_zalo, engine='xlsxwriter') as writer:
                df_zalo_export.to_excel(writer, index=False, sheet_name="Lich_Chay_Zalo")
            # -----------------------------------------------------------

            # --- GIAO DIỆN PHÂN TRANG & NÚT XUẤT EXCEL ---
            # Chia cột lại để có khoảng trống cho nút Export Excel bên phải
            col_opt1, col_opt2, col_opt3 = st.columns([2, 5, 3]) 
            with col_opt1:
                che_do_xem_chuyen = st.selectbox("Hiển thị:", ["20 dòng", "Tất cả"], key="xem_chuyen")
                
            with col_opt3:
                st.download_button(
                    label="📥 Xuất Excel (Kèm Text Zalo)", 
                    data=buffer_zalo.getvalue(), 
                    file_name=f"Lich_Chay_Va_Zalo_HomNay_{datetime.date.today().strftime('%d_%m_%Y')}.xlsx", 
                    type="primary",
                    use_container_width=True
                )
            
            if che_do_xem_chuyen == "Tất cả":
                st.caption(f"Đang hiển thị toàn bộ {len(df_chuyen)} chuyến đi.")
                st.dataframe(
                    df_chuyen,
                    use_container_width=True,
                    hide_index=True
                )
            else:
                rows_per_page = 20
                total_rows = len(df_chuyen)
                total_pages = math.ceil(total_rows / rows_per_page)
                
                if total_pages > 0:
                    if 'page_chuyen' not in st.session_state:
                        st.session_state['page_chuyen'] = 1
                        
                    if st.session_state['page_chuyen'] < 1:
                        st.session_state['page_chuyen'] = 1
                    elif st.session_state['page_chuyen'] > total_pages:
                        st.session_state['page_chuyen'] = total_pages
                        
                    col1, col2, col3 = st.columns([1, 2, 1])
                    
                    with col1:
                        if st.button("⬅️ Trước", key="btn_prev_chuyen", disabled=(st.session_state['page_chuyen'] <= 1)):
                            if st.session_state['page_chuyen'] > 1:
                                st.session_state['page_chuyen'] -= 1
                                st.rerun()
                            
                    with col3:
                        if st.button("Sau ➡️", key="btn_next_chuyen", disabled=(st.session_state['page_chuyen'] >= total_pages)):
                            if st.session_state['page_chuyen'] < total_pages:
                                st.session_state['page_chuyen'] += 1
                                st.rerun()
                            
                    with col2:
                        st.markdown(f"<div style='text-align: center; margin-top: 5px;'>Trang {st.session_state['page_chuyen']} / {total_pages}</div>", unsafe_allow_html=True)

                    start_idx = (st.session_state['page_chuyen'] - 1) * rows_per_page
                    end_idx = start_idx + rows_per_page
                    df_page_chuyen = df_chuyen.iloc[start_idx:end_idx]
                    
                    st.dataframe(
                        df_page_chuyen,
                        use_container_width=True,
                        hide_index=True
                    )
        else:
            st.info("Chưa có dữ liệu chuyến đi nào trong ngày.")
    except Exception as e:
        st.error(f"Lỗi truy xuất danh sách: {e}")

# ==========================================
# TAB 2: ĐĂNG KÝ, SỬA CHUYẾN ĐI THỦ CÔNG
# ==========================================
with tab2:
    tao_tieu_de_kem_nut_refresh("📋 Đăng ký/ Sửa chuyến đi", "ref_tab2")
    if "reset_tab2" not in st.session_state: st.session_state["reset_tab2"] = 0
    if "api_km" not in st.session_state: st.session_state["api_km"] = 0.0
    if "editing_trip_id" not in st.session_state: st.session_state["editing_trip_id"] = None
    if "editing_trip_data" not in st.session_state: st.session_state["editing_trip_data"] = None

    col_title, col_btn = st.columns([4, 1])
    
    with col_title:
        if st.session_state["editing_trip_id"]:
            st.subheader(f"🔄 Chỉnh sửa chuyến đi #{st.session_state['editing_trip_id']}")
        else:
            st.subheader("🚀 Lên lệnh chạy đơn lẻ")
            
    with col_btn:
        if st.session_state["editing_trip_id"]:
            if st.button("➕ Tạo mới", type="secondary", use_container_width=True):
                st.session_state["editing_trip_id"] = None
                st.session_state["editing_trip_data"] = None
                st.session_state["api_km"] = 0.0
                st.rerun()

    if not st.session_state["editing_trip_id"]:
        expander_search = st.expander("🔍 Tìm chuyến đi cũ để sửa (Click để mở rộng)", expanded=False)
        with expander_search:
            df_recent_trips = db.get_recent_trips_for_edit()
            
            if isinstance(df_recent_trips, str):
                st.error(f"⚠️ Không thể tải danh sách chuyến đi. {df_recent_trips}")
            elif isinstance(df_recent_trips, pd.DataFrame):
                if not df_recent_trips.empty:
                    trip_options = df_recent_trips['id'].tolist()
                    
                    def format_trip_option(trip_id):
                        row = df_recent_trips[df_recent_trips['id'] == trip_id].iloc[0]
                        try:
                            ngay = pd.to_datetime(row['ngay_chuyen_di']).strftime('%d/%m/%Y')
                        except:
                            ngay = row['ngay_chuyen_di']
                        bien_so = row['bien_so_xe'] if pd.notna(row['bien_so_xe']) else "Chưa có xe"
                        tai_xe = row['ten_tai_xe'] if pd.notna(row['ten_tai_xe']) else "Chưa có TX"
                        khach = row['ten_khach_hang'] if pd.notna(row['ten_khach_hang']) else "Khách Lẻ"
                        return f"#{row['id']} [{ngay}] | 🚛 {bien_so} | 🧑‍✈️ {tai_xe} | 🏢 {khach}"

                    selected_trip_to_edit = st.selectbox(
                        "Chọn chuyến đi cần sửa thông tin:",
                        options=trip_options,
                        format_func=format_trip_option,
                        index=None,
                        key="sb_search_trip_edit"
                    )
                    
                    if selected_trip_to_edit and selected_trip_to_edit != st.session_state["editing_trip_id"]:
                        trip_details = df_recent_trips[df_recent_trips['id'] == selected_trip_to_edit].iloc[0].to_dict()
                        
                        st.session_state["editing_trip_id"] = selected_trip_to_edit
                        st.session_state["editing_trip_data"] = trip_details
                        st.session_state["api_km"] = float(trip_details.get('so_km_thuc_te', 0.0))
                        st.rerun()
                else:
                    st.caption("Không tìm thấy chuyến đi gần đây có thể sửa.")
            else:
                st.caption("Dữ liệu trả về không hợp lệ.")

    # XÁC ĐỊNH DỮ LIỆU HIỆN TẠI
    editing_data = st.session_state["editing_trip_data"]
    is_edit_mode = st.session_state["editing_trip_id"] is not None

    default_diem_dau = ""
    default_diem_cuoi = ""
    if is_edit_mode and editing_data and 'dia_diem_giao_nhan' in editing_data:
        lo_trinh_str = str(editing_data['dia_diem_giao_nhan'])
        if " ➡️ " in lo_trinh_str:
            parts = lo_trinh_str.split(" ➡️ ")
            default_diem_dau = parts[0]
            default_diem_cuoi = parts[1]
        else:
            default_diem_dau = lo_trinh_str 

    xe_map_clean = {int(float(k)): v for k, v in xe_map.items()}
    tx_opts_clean = {int(float(k)): v for k, v in tx_opts.items()}
    
    danh_sach_xe_id = list(xe_map_clean.keys())
    danh_sach_tx_id = list(tx_opts_clean.keys())

    old_xe_id = None
    old_tx_id = None
    if is_edit_mode and editing_data:
        if pd.notna(editing_data.get('xe_id')):
            old_xe_id = int(float(editing_data['xe_id']))
        if pd.notna(editing_data.get('tai_xe_id')):
            old_tx_id = int(float(editing_data['tai_xe_id']))

    if is_edit_mode and old_xe_id is not None and old_xe_id not in danh_sach_xe_id:
        xe_map_clean[old_xe_id] = {
            'bien_so_xe': editing_data.get('bien_so_xe', f"Xe cũ ID {old_xe_id}"),
            'tai_trong_thiet_ke': editing_data.get('khoi_luong_kg', 0) / 1000, 
            'dung_tich_cbm': editing_data.get('the_tich_cbm', 0),
            'tai_xe_co_dinh_id': old_tx_id
        }
        danh_sach_xe_id.insert(0, old_xe_id) 
        
    if is_edit_mode and old_tx_id is not None and old_tx_id not in danh_sach_tx_id:
        tx_opts_clean[old_tx_id] = editing_data.get('ten_tai_xe', f"Tài xế cũ ID {old_tx_id}")
        danh_sach_tx_id.insert(0, old_tx_id)

    default_xe_index = None
    if is_edit_mode and old_xe_id in danh_sach_xe_id:
        default_xe_index = danh_sach_xe_id.index(old_xe_id)

    c_xe_sel = st.selectbox(
        "🚛 Chọn Xe vận chuyển", 
        options=danh_sach_xe_id, 
        format_func=lambda x: f"{xe_map_clean[x]['bien_so_xe']} — ({xe_map_clean.get(x, {}).get('tai_trong_thiet_ke', 0)}T | {xe_map_clean.get(x, {}).get('dung_tich_cbm', 0)} CBM)", 
        index=default_xe_index, 
        key=f"xe_sel_{st.session_state['reset_tab2']}_{st.session_state['editing_trip_id']}" 
    )
    
    tx_of_selected_xe = None
    if c_xe_sel is not None and pd.notna(xe_map_clean[c_xe_sel].get('tai_xe_co_dinh_id')):
        tx_id_raw = int(float(xe_map_clean[c_xe_sel]['tai_xe_co_dinh_id']))
        if tx_id_raw in danh_sach_tx_id:
            tx_of_selected_xe = tx_id_raw

    default_tx_id = None
    if is_edit_mode:
        if c_xe_sel == old_xe_id:
            default_tx_id = old_tx_id
        else:
            default_tx_id = tx_of_selected_xe
    else:
        default_tx_id = tx_of_selected_xe

    tx_index = None
    if default_tx_id in danh_sach_tx_id:
        tx_index = danh_sach_tx_id.index(default_tx_id)

    dynamic_tx_key = f"tx_sel_{st.session_state['reset_tab2']}_{c_xe_sel}_{st.session_state['editing_trip_id']}"

    c_tx_sel = st.selectbox(
        "🧑‍✈️ Xác nhận Tài xế chạy", 
        options=danh_sach_tx_id, 
        index=tx_index, 
        format_func=lambda x: tx_opts_clean[x], 
        key=dynamic_tx_key
    )
    
    with st.form("form_thu_cong_chuyen", clear_on_submit=False):
        c1, c2 = st.columns(2)
        txt_khach = c1.text_input(
            "🏢 Công ty đối tác / Khách hàng", 
            value=editing_data['ten_khach_hang'] if is_edit_mode else "",
            key=f"kh_{st.session_state['reset_tab2']}_{st.session_state['editing_trip_id']}"
        )
        txt_dia_chi_kh= c2.text_input(
            "🏢 Địa chỉ khách hàng", 
            value=editing_data['dia_chi_khach_hang'] if is_edit_mode else "",
            key=f"dchikh_{st.session_state['reset_tab2']}_{st.session_state['editing_trip_id']}"
        )
        
        c3, c4, c5 = st.columns(3)
        default_date = datetime.date.today()
        if is_edit_mode and editing_data and 'ngay_chuyen_di' in editing_data:
            try:
                default_date = pd.to_datetime(editing_data['ngay_chuyen_di']).date()
            except: pass

        ngay_di = c3.date_input(
            "🗓️ Ngày khởi hành", 
            value=default_date, 
            format="DD/MM/YYYY", 
            key=f"ngay_{st.session_state['reset_tab2']}_{st.session_state['editing_trip_id']}"
        )
        diem_dau = c4.text_input("🏠 Địa chỉ kho bốc hàng", value=default_diem_dau, key=f"dau_{st.session_state['reset_tab2']}_{st.session_state['editing_trip_id']}")
        diem_cuoi = c5.text_input("🎯 Địa chỉ kho giao hàng", value=default_diem_cuoi, key=f"cuoi_{st.session_state['reset_tab2']}_{st.session_state['editing_trip_id']}")
                       
        val_km = float(st.session_state.get("api_km", 1.0))
        if val_km < 1.0: val_km = 1.0
        
        c6, c7, c8 = st.columns(3)
        so_cbm = c6.number_input(
            "Số CBM", 
            min_value=0.0, 
            value=float(editing_data['the_tich_cbm']) if is_edit_mode else 1.0,
            key=f"cbm_{st.session_state['reset_tab2']}_{st.session_state['editing_trip_id']}"
        )
        km_thuc = c7.number_input(
            "Số KM dự kiến", 
            min_value=1.0, 
            value=val_km, 
            step=0.1, 
            key=f"km_{st.session_state['reset_tab2']}_{st.session_state['editing_trip_id']}"
        )
        
        default_tien_str = ""
        if is_edit_mode and editing_data and 'cong_chuyen' in editing_data:
            try:
                default_tien_str = f"{int(editing_data['cong_chuyen']):,}" 
            except: pass

        cong_chuyen_str = c8.text_input(
            "Tạm ứng (VNĐ)", 
            value=default_tien_str,
            placeholder="VD: 200,000", 
            key=f"luong_{st.session_state['reset_tab2']}_{st.session_state['editing_trip_id']}"
        )
        
        ghi_chu_thucong= st.text_input(
            "Ghi chú", 
            value=editing_data['ghi_chu'] if is_edit_mode else "",
            key=f"gc_{st.session_state['reset_tab2']}_{st.session_state['editing_trip_id']}"
        )

        default_status_index = 0
        if is_edit_mode and editing_data and 'trang_thai_chuyen' in editing_data:
            db_status_old = editing_data['trang_thai_chuyen']
            REVERSE_STATUS_MAP = {v: k for k, v in STATUS_MAP.items()}
            status_ui_old = REVERSE_STATUS_MAP.get(db_status_old)
            status_options = list(STATUS_MAP.keys())
            if status_ui_old in status_options:
                default_status_index = status_options.index(status_ui_old)

        trang_thai_ui_value = st.selectbox(
            "Trạng thái chuyến đi", 
            options=list(STATUS_MAP.keys()),
            index=default_status_index,
            key=f"sts_{st.session_state['reset_tab2']}_{st.session_state['editing_trip_id']}"
        )
        
        if st.form_submit_button("🔍 Quét bản đồ vệ tinh", type="secondary"):
            if diem_dau and diem_cuoi and hasattr(map_srv, 'tinh_lo_trinh_duong_bo'):
                with st.spinner("Đang tính lộ trình..."):
                    c_start, c_end = map_srv.lay_toa_do(diem_dau), map_srv.lay_toa_do(diem_cuoi)
                    if c_start and c_end:
                        res = map_srv.tinh_lo_trinh_duong_bo(c_start, c_end)
                        if res: 
                            st.session_state["api_km"] = res["km"]
                            st.rerun() 
                    else:
                        st.error("❌ Không xác định được tọa độ.")

        submit_label = "💾 Cập nhật chuyến đi" if is_edit_mode else "Phát lệnh chạy thủ công"
        submit_type = "secondary" if is_edit_mode else "primary"
        
        if st.form_submit_button(submit_label, type=submit_type):
            if not c_xe_sel or not c_tx_sel or not txt_khach.strip(): 
                st.error("⚠️ Vui lòng điền đủ thông tin xe, tài xế và tên khách hàng!")
            elif is_edit_mode and editing_data['trang_thai_chuyen'] in ['Hoan_Thanh', 'Da_Huy']:
                 st.error(f"❌ Không thể sửa chuyến đi đã Hoàn thành hoặc Đã hủy.")
            else:
                ngay_db = ngay_di.strftime('%Y-%m-%d')
                cong_tien = parse_money_input(cong_chuyen_str) 
                db_status = STATUS_MAP[trang_thai_ui_value]
                
                trip_data_tuple = (
                    ngay_db,                      
                    txt_khach.strip(),            
                    txt_dia_chi_kh.strip(),       
                    c_xe_sel,                     
                    f"{diem_dau} ➡️ {diem_cuoi}", 
                    km_thuc,                      
                    0.0,                          
                    so_cbm,                       
                    cong_tien,                    
                    db_status,                    
                    ghi_chu_thucong               
                )
                
                if is_edit_mode:
                    trip_id_to_update = st.session_state["editing_trip_id"]
                    
                    with st.spinner(f"Đang cập nhật..."):
                        success, result = update_trip_full_process(db.pool, trip_id_to_update, trip_data_tuple, c_tx_sel)

                    if success:
                        st.toast(f"✅ Đã cập nhật thành công chuyến #{trip_id_to_update}!", icon="🎉")
                        st.session_state["editing_trip_id"] = None
                        st.session_state["editing_trip_data"] = None
                        st.session_state["api_km"] = 0.0
                        st.session_state["reset_tab2"] += 1 
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(f"❌ Lỗi: {result}")
                        
                else:
                    with st.spinner("Đang đăng ký chuyến đi mới..."):
                        success, result = save_trip_full_process(db.pool, trip_data_tuple, c_tx_sel)
                    
                    if success:
                        st.session_state["reset_tab2"] += 1
                        st.session_state["api_km"] = 0.0
                        st.success(f"✅ Đăng ký thành công! Mã nội bộ DB: {result}")
                        st.balloons()
                        time.sleep(1)
                        st.rerun() 
                    else:
                        st.error(f"❌ Lỗi: {result}")

# ==========================================
# TAB 3: QUYẾT TOÁN ĐƠN CHUYẾN (TÍCH HỢP TELEGRAM & AI LOGIC)
# ==========================================
bot_token = os.getenv("TELEGRAM_BOT_TOKEN")

if not bot_token:
    st.error("⚠️ HỆ THỐNG: Không tìm thấy TELEGRAM_BOT_TOKEN trong file .env. Tính năng tự động lấy ảnh sẽ bị vô hiệu hóa.")

def lay_danh_sach_anh_telegram_theo_ma_chuyen(bot_token, chuyen_di_id, danh_sach_file_id_da_tai):
    try:
        url_updates = f"https://api.telegram.org/bot{bot_token}/getUpdates"
        resp = requests.get(url_updates).json()
        
        if not resp.get('ok') or len(resp['result']) == 0:
            return [], [], "Không có tin nhắn nào mới trên Telegram."
            
        chuyen_di_id_str = str(chuyen_di_id)
        danh_sach_anh_moi = []
        danh_sach_id_moi = []
        
        for msg in resp['result']:
            message = msg.get('message', {})
            
            if 'photo' in message:
                caption = message.get('caption', '').upper()
                
                if chuyen_di_id_str in caption:
                    photo_id = message['photo'][-1]['file_id']
                    
                    if photo_id in danh_sach_file_id_da_tai:
                        continue
                        
                    url_file = f"https://api.telegram.org/bot{bot_token}/getFile?file_id={photo_id}"
                    file_path = requests.get(url_file).json()['result']['file_path']
                    
                    url_download = f"https://api.telegram.org/file/bot{bot_token}/{file_path}"
                    img_bytes = requests.get(url_download).content
                    
                    danh_sach_anh_moi.append(img_bytes)
                    danh_sach_id_moi.append(photo_id)
                    
        if danh_sach_anh_moi:
            return danh_sach_anh_moi, danh_sach_id_moi, f"✅ Đã tải thêm {len(danh_sach_anh_moi)} ảnh hóa đơn mới cho chuyến {chuyen_di_id}!"
        else:
            return [], [], f"ℹ️ Đã quét nhưng không có ảnh mới nào chứa mã chuyến '{chuyen_di_id}' trong caption."
            
    except Exception as e:
        return [], [], f"Lỗi kết nối Telegram: {e}"

with tab3:
    tao_tieu_de_kem_nut_refresh("📋 Quyết toán và cập nhật chi phí chuyến đi", "ref_tab3")

    if "reset_chuyen_form" not in st.session_state: 
        st.session_state["reset_chuyen_form"] = 0
        
    df_cfg = db.execute_query("SELECT ma_tieu_chi, muc_thuong FROM cau_hinh_thuong")
    bonus_rules = {row['ma_tieu_chi']: float(row['muc_thuong']) for _, row in df_cfg.iterrows()} if isinstance(df_cfg, pd.DataFrame) and not df_cfg.empty else {}

    sql_load = """
        SELECT cd.id, cd.ngay_chuyen_di, cd.ten_khach_hang, x.bien_so_xe, CAST(x.tai_trong_thiet_ke AS FLOAT) AS tai_trong,
               nv.ho_ten AS ten_tai_xe, cd.trang_thai_chuyen,
               cd.so_km_thuc_te, cd.so_lit_xang, cd.tien_xang, cd.cong_chuyen, cd.tien_them,
               cd.phi_hai_quan, cd.phi_boc_xep, cd.phi_khac, cd.ghi_chu_quyet_toan,
               cd.is_gop_chuyen, cd.is_ve_khuya, cd.khoi_luong_kg, cd.the_tich_cbm,
               cd.thoi_gian_bat_dau
        FROM chuyen_di cd
        LEFT JOIN xe x ON cd.xe_id = x.id
        LEFT JOIN chuyen_di_tai_xe ctx ON cd.id = ctx.chuyen_di_id AND ctx.loai_tai_xe = 'Tai_Chinh'
        LEFT JOIN nhan_vien nv ON ctx.tai_xe_id = nv.id
        WHERE cd.trang_thai_chuyen = 'Quyet_Toan'
        ORDER BY cd.ngay_chuyen_di DESC
    """
    df_cd = db.execute_query(sql_load)

    if isinstance(df_cd, pd.DataFrame) and not df_cd.empty:
        trip_options = {
            row['id']: f"Mã: {row['id']} | Ngày: {row['ngay_chuyen_di']} | Khách: {row['ten_khach_hang']} | Xe: {row['bien_so_xe']} | TX: {row['ten_tai_xe']}"
            for _, row in df_cd.iterrows()
        }
        
        cd_id = st.selectbox(
            "🔍 Chọn chuyến đi đang chờ quyết toán:", 
            options=list(trip_options.keys()), 
            format_func=lambda x: trip_options[x],
            key=f"sel_trip_{st.session_state['reset_chuyen_form']}"
        )
        
        row_sel = df_cd[df_cd['id'] == cd_id].iloc[0]
        tai_trong_xe = row_sel['tai_trong']
        
        if 'current_trip_id' not in st.session_state or st.session_state['current_trip_id'] != cd_id:
            for key in ['ai_fuel_lit', 'ai_fuel_tien', 'danh_sach_anh_tam', 'danh_sach_file_id_tam']:
                if key in st.session_state:
                    del st.session_state[key]
            st.session_state['current_trip_id'] = cd_id

        if 'danh_sach_anh_tam' not in st.session_state: st.session_state['danh_sach_anh_tam'] = []
        if 'danh_sach_file_id_tam' not in st.session_state: st.session_state['danh_sach_file_id_tam'] = []

        st.divider()

        with st.expander("🛠️ CÔNG CỤ TỰ ĐỘNG BỔ TRỢ KẾ TOÁN (GPS & AI)", expanded=True):
            st.markdown("##### 🛰️ Quét dữ liệu KM từ GPS (Hành Trình Xe)")
            ngay_cd_obj = row_sel['ngay_chuyen_di']
            if isinstance(ngay_cd_obj, str):
                ngay_cd_obj = datetime.datetime.strptime(ngay_cd_obj, '%Y-%m-%d').date()
            
            default_start = datetime.datetime.combine(ngay_cd_obj, datetime.time.min)
            if pd.notna(row_sel.get('thoi_gian_bat_dau')):
                default_start = row_sel['thoi_gian_bat_dau']
            default_end = datetime.datetime.now()

            col_gps1, col_gps2, col_gps_btn = st.columns([2, 2, 1])
            with col_gps1:
                ui_start_time = st.text_input("Thời gian Bắt đầu (YYYY-MM-DD HH:MM:SS)", value=default_start.strftime('%Y-%m-%d %H:%M:%S'))
            with col_gps2:
                ui_end_time = st.text_input("Thời gian Kết thúc (YYYY-MM-DD HH:MM:SS)", value=default_end.strftime('%Y-%m-%d %H:%M:%S'))
            with col_gps_btn:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("📡 Lấy KM GPS", type="primary", use_container_width=True):
                    try:
                        tg_bd_chuan = datetime.datetime.strptime(ui_start_time, '%Y-%m-%d %H:%M:%S')
                        tg_kt_chuan = datetime.datetime.strptime(ui_end_time, '%Y-%m-%d %H:%M:%S')
                        with st.spinner("Đang kết nối API Hành Trình Xe..."):
                            success, msg = goi_gps_theo_thoi_gian_tuy_chinh(db, cd_id, tg_bd_chuan, tg_kt_chuan)
                            if success:
                                st.success(msg)
                                time.sleep(2)
                                st.rerun()
                            else:
                                st.error(msg)
                    except ValueError:
                        st.error("Sai định dạng ngày giờ! Vui lòng nhập chuẩn YYYY-MM-DD HH:MM:SS")
            
            st.divider()

            st.markdown("##### 🤖 Thu thập & Quét biên lai nhiên liệu tự động")
            col_bot_1, col_bot_2 = st.columns([1, 1])
            
            with col_bot_1:
                st.info(f"📡 Lấy tự động hóa đơn từ Telegram cho mã chuyến **{cd_id}**.")
                if st.button("📥 Quét Telegram lấy hóa đơn xăng dầu", type="primary", use_container_width=True):
                    with st.spinner(f"Đang tìm ảnh có mã {cd_id} trên Telegram..."):
                        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
                        ds_anh_moi, ds_id_moi, msg = lay_danh_sach_anh_telegram_theo_ma_chuyen(
                            bot_token, cd_id, st.session_state['danh_sach_file_id_tam']
                        )
                        
                        if ds_anh_moi:
                            st.session_state['danh_sach_anh_tam'].extend(ds_anh_moi)
                            st.session_state['danh_sach_file_id_tam'].extend(ds_id_moi)
                            st.success(msg)
                        else:
                            st.warning(msg)
                            
            with col_bot_2:
                st.info("📂 Kế toán có thể tải lên nhiều file ảnh thủ công nếu tài xế gửi qua Zalo.")
                uploaded_fuels = st.file_uploader("Tải lên biên lai", type=['jpg', 'jpeg', 'png'], accept_multiple_files=True, key=f"up_{cd_id}_{st.session_state['reset_chuyen_form']}")
                if uploaded_fuels:
                    anh_uploads = [f.getvalue() for f in uploaded_fuels]
                    for au in anh_uploads:
                        if au not in st.session_state['danh_sach_anh_tam']:
                            st.session_state['danh_sach_anh_tam'].append(au)

            if st.session_state['danh_sach_anh_tam']:
                from io import BytesIO
                so_luong_anh = len(st.session_state['danh_sach_anh_tam'])
                st.markdown(f"**📸 Đang có {so_luong_anh} ảnh hóa đơn nhiên liệu:**")
                
                cols_img = st.columns(min(so_luong_anh, 4))
                for i, img_bytes in enumerate(st.session_state['danh_sach_anh_tam']):
                    with cols_img[i % 4]:
                        st.image(BytesIO(img_bytes), caption=f"Hóa đơn {i+1}", use_container_width=True)
                    
                if st.button("🔍 Sử dụng AI bóc tách TỔNG CỘNG dữ liệu", use_container_width=True):
                    with st.spinner("AI đang đọc và tổng hợp dữ liệu từ các hóa đơn..."):
                        tong_lit = 0.0
                        tong_tien = 0
                        loi_doc_ai = False
                        
                        for i, img_bytes in enumerate(st.session_state['danh_sach_anh_tam']):
                            ket_qua_ai = doc_anh_cay_xang(BytesIO(img_bytes))
                            if ket_qua_ai:
                                tong_lit += float(ket_qua_ai.get('so_lit', 0.0))
                                tong_tien += int(ket_qua_ai.get('tong_tien', 0))
                            else:
                                loi_doc_ai = True
                                st.warning(f"⚠️ Không thể đọc dữ liệu từ Hóa đơn {i+1}")
                        
                        st.session_state['ai_fuel_lit'] = tong_lit
                        st.session_state['ai_fuel_tien'] = tong_tien
                        
                        st.markdown("### 📊 Tổng hợp Kết quả AI trả về:")
                        st.markdown(f"- **Tổng số lít:** {tong_lit:,.2f} Lít")
                        st.markdown(f"- **Tổng tiền:** {tong_tien:,} VNĐ")
                        
                        if tong_lit > 0:
                            don_gia_tb = tong_tien / tong_lit
                            if don_gia_tb < 14000 or don_gia_tb > 40000:
                                st.error(f"🚨 **PHÁT HIỆN LỖI LOGIC:** Đơn giá trung bình là **{don_gia_tb:,.0f} VNĐ/Lít**.")
                                st.error("Mức giá này nằm ngoài vùng giá thị trường. Kế toán vui lòng kiểm tra lại từng ảnh và điền số tổng vào ô bên dưới!")
                            else:
                                st.success(f"✅ Logic hợp lệ! Đơn giá trung bình là **{don_gia_tb:,.0f} VNĐ/Lít**. Kế toán xác nhận và bấm Lưu.")
                        else:
                            st.warning("AI không đọc được số lít ở các hóa đơn, kế toán vui lòng tự tính và nhập tay.")

        st.divider()
        with st.form(key=f"form_qt_{st.session_state['reset_chuyen_form']}"):
            
            default_lit = st.session_state.get('ai_fuel_lit', float(row_sel['so_lit_xang'] or 0.0))
            default_tien_xang = st.session_state.get('ai_fuel_tien', int(row_sel['tien_xang'] or 0))

            st.markdown("##### 📍 1. Số liệu Hành trình & Xăng dầu")
            col1_1, col1_2, col1_3, col1_4, col1_5 = st.columns(5)
            
            edit_cong_ty = col1_1.text_input("Công ty", value=str(row_sel['ten_khach_hang'] or ""))
            final_km     = col1_2.number_input("KM Thực tế", min_value=0.0, value=float(row_sel['so_km_thuc_te'] or 0.0), step=1.0)
            final_lit    = col1_3.number_input("Tổng Lít Xăng", min_value=0.0, value=default_lit, step=1.0)
            tien_xang_input = col1_4.text_input("Tiền Xăng Tổng (VNĐ)", placeholder="VD: 1,500,000", value=str(default_tien_xang))
            num_cong     = col1_5.text_input("Công chuyến (VNĐ)", placeholder="VD: 200,000", value=str(row_sel['cong_chuyen'] or 0))

            st.divider()
            
            st.markdown("##### 📦 2. Thông số Hàng hóa & Phụ cấp")
            col2_1, col2_2, col2_3, col2_4 = st.columns(4)
            khoi_luong_kg = col2_1.number_input("Khối lượng (KG)", value=float(row_sel['khoi_luong_kg'] or 0.0), step=1.0)
            the_tich_cbm  = col2_2.number_input("Thể tích (CBM)", value=float(row_sel['the_tich_cbm'] or 0.0), step=1.0)
            tien_them     = col2_3.text_input("Phụ cấp / Tiền thêm", value=str(row_sel['tien_them'] or 0))
            
            with col2_4:
                st.markdown("<br>", unsafe_allow_html=True)
                chk_gop = st.checkbox("Chuyến Gộp", value=bool(row_sel['is_gop_chuyen']))
                chk_khuya = st.checkbox("Về Khuya", value=bool(row_sel['is_ve_khuya']))
            
            st.divider()

            st.markdown("##### 🧾 3. Quyết toán Phí đường bộ & Ghi chú")
            col3_1, col3_2, col3_3 = st.columns(3)
            num_hq = col3_1.text_input("Phí Hải Quan (VNĐ)", value=str(row_sel['phi_hai_quan'] or 0))
            num_bx = col3_2.text_input("Phí Bốc Xếp (VNĐ)", value=str(row_sel['phi_boc_xep'] or 0))
            num_k  = col3_3.text_input("Phí Khác (VNĐ)", value=str(row_sel['phi_khac'] or 0))
            
            gc_hien_thi = "" if pd.isna(row_sel['ghi_chu_quyet_toan']) else str(row_sel['ghi_chu_quyet_toan'])
            edit_gc = st.text_input("Ghi chú quyết toán", value=gc_hien_thi)
            
            st.markdown("##### 🛡️ Xác nhận thao tác")
            xac_nhan_chot = st.checkbox("⚠️ TÔI XÁC NHẬN SỐ LIỆU LÀ HỢP LÝ VÀ ĐỒNG Ý CHỐT SỔ CHUYẾN ĐI.")
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            b1, b2, b3 = st.columns(3)
            submit_luu  = b1.form_submit_button("💾 LƯU CẬP NHẬT TẠM", type="secondary")
            submit_chot = b2.form_submit_button("🏁 CHỐT SỔ CHUYẾN ĐI", type="primary")
            submit_xoa  = b3.form_submit_button("🗑️ XÓA CHUYẾN ĐI")

            data_dict_thu_cong = {
                'ten_khach_hang': edit_cong_ty,
                'so_km_thuc_te': final_km,
                'so_lit_xang': final_lit,
                'tien_xang': parse_money_input(tien_xang_input), 
                'cong_chuyen': parse_money_input(num_cong),
                'tien_them': parse_money_input(tien_them),
                'is_gop_chuyen': 1 if chk_gop else 0,
                'is_ve_khuya': 1 if chk_khuya else 0,
                'khoi_luong_kg': khoi_luong_kg,
                'the_tich_cbm': the_tich_cbm,
                'phi_hai_quan': parse_money_input(num_hq),
                'phi_boc_xep': parse_money_input(num_bx),
                'phi_khac': parse_money_input(num_k),
                'ghi_chu_quyet_toan': edit_gc
            }

            def clear_cache():
                keys_to_clear = ['ai_fuel_lit', 'ai_fuel_tien', 'danh_sach_anh_tam', 'danh_sach_file_id_tam', 'current_trip_id']
                for key in keys_to_clear:
                    if key in st.session_state:
                        del st.session_state[key]

            if submit_luu:
                is_ok, msg = settle_trip_transaction(db.pool, data_dict_thu_cong, row_sel['trang_thai_chuyen'], cd_id)
                if is_ok:
                    clear_cache()
                    st.session_state["reset_chuyen_form"] += 1
                    st.success("✅ Đã lưu cập nhật dữ liệu thành công!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(f"❌ Lỗi lưu chuyến: {msg}")

            if submit_chot:
                if not xac_nhan_chot:
                    st.error("✋ HỆ THỐNG ĐÃ CHẶN: Vui lòng tick vào ô 'Tôi xác nhận...' trước khi chốt sổ!")
                else:
                    is_ok, msg = settle_trip_transaction(db.pool, data_dict_thu_cong, 'Hoan_Thanh', cd_id)
                    if is_ok:
                        clear_cache()
                        st.session_state["reset_chuyen_form"] += 1
                        st.success("✅ Đã chốt chuyến đi thành công!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(f"❌ Lỗi chốt chuyến: {msg}")
                
            if submit_xoa:
                success, msg = delete_trip_safe(db.pool, cd_id)
                if success:
                    clear_cache()
                    st.session_state["reset_chuyen_form"] += 1
                    st.success("✅ Đã xóa chuyến đi và dọn dẹp sạch dữ liệu!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(f"❌ Lỗi xóa chuyến: {msg}")
    else:
        st.info("🎉 Tuyệt vời! Hiện tại không có chuyến đi nào đang chờ quyết toán.")

# ==========================================
# TAB 4: SỬA DỮ LIỆU ĐÃ QUYẾT TOÁN
# ==========================================
with tab4:
    tao_tieu_de_kem_nut_refresh("📋 Sửa dữ liệu chuyến đi đã quyết toán", "ref_tab4")
    if "reset_sqt" not in st.session_state:
        st.session_state["reset_sqt"] = 0
    st.info("Tính năng này dùng để điều chỉnh chi phí, công lương cho các chuyến đã chốt.")
    
    current_user = st.session_state.get('username', 'Admin')
    
    col_filter1, col_filter2, col_filter3 = st.columns(3)
    
    with col_filter1:
        ngay_tim_kiem = st.date_input("Chọn ngày chạy", value=datetime.date.today(), key="sqt_date")
        
    with col_filter2:
        loai_tim_kiem = st.radio("Tìm kiếm theo:", ["Theo Xe", "Theo Tài xế"], horizontal=True, key="sqt_type")
        
    with col_filter3:
        if loai_tim_kiem == "Theo Xe":
            df_xe = db.execute_query("SELECT id, bien_so_xe FROM xe WHERE trang_thai = 'Dang_Hoat_Dong'")
            if isinstance(df_xe, pd.DataFrame) and not df_xe.empty:
                dict_xe = dict(zip(df_xe['id'], df_xe['bien_so_xe']))
                doi_tuong_id = st.selectbox("Chọn Xe", options=list(dict_xe.keys()), format_func=lambda x: dict_xe[x], key="sqt_obj_xe")
            else:
                st.warning("Không có dữ liệu xe"); doi_tuong_id = None
        else:
            df_tx = db.execute_query("SELECT id, ho_ten FROM nhan_vien WHERE trang_thai = 'Dang_Lam_Viec'")
            if isinstance(df_tx, pd.DataFrame) and not df_tx.empty:
                dict_tx = dict(zip(df_tx['id'], df_tx['ho_ten']))
                doi_tuong_id = st.selectbox("Chọn Tài xế", options=list(dict_tx.keys()), format_func=lambda x: dict_tx[x], key="sqt_obj_tx")
            else:
                st.warning("Không có dữ liệu tài xế"); doi_tuong_id = None

    st.divider()

    if doi_tuong_id:
        ngay_str = ngay_tim_kiem.strftime('%Y-%m-%d')
        
        if loai_tim_kiem == "Theo Xe":
            sql_find_trips = """
                SELECT id, dia_diem_giao_nhan, ten_khach_hang, cong_chuyen,doanh_thu, so_km_thuc_te,so_lit_xang,tien_xang, 
                       tien_them, phi_hai_quan, phi_boc_xep, phi_khac, ghi_chu 
                FROM chuyen_di 
                WHERE ngay_chuyen_di = %s AND xe_id = %s 
                  AND trang_thai_chuyen = 'Hoan_Thanh'
            """
            df_trips = db.execute_query(sql_find_trips, (ngay_str, doi_tuong_id))
        else:
            sql_find_trips = """
                SELECT cd.id, cd.dia_diem_giao_nhan, cd.ten_khach_hang, cd.cong_chuyen,cd.doanh_thu, cd.so_km_thuc_te,cd.so_lit_xang,cd.tien_xang, 
                       cd.tien_them, cd.phi_hai_quan, cd.phi_boc_xep, cd.phi_khac, cd.ghi_chu 
                FROM chuyen_di cd
                JOIN chuyen_di_tai_xe ctx ON cd.id = ctx.chuyen_di_id
                WHERE cd.ngay_chuyen_di = %s AND ctx.tai_xe_id = %s 
                  AND cd.trang_thai_chuyen = 'Hoan_Thanh'
            """
            df_trips = db.execute_query(sql_find_trips, (ngay_str, doi_tuong_id))

        if isinstance(df_trips, pd.DataFrame) and not df_trips.empty:
            dict_trips = {}
            for _, row in df_trips.iterrows():
                label = f"Mã chuyến: {row['id']} | Khách: {row['ten_khach_hang']} | Lộ trình: {row['dia_diem_giao_nhan']}"
                dict_trips[row['id']] = label
                
            chuyen_can_sua = st.selectbox(
                "📌 Chọn chuyến cần sửa quyết toán:", 
                options=list(dict_trips.keys()), 
                format_func=lambda x: dict_trips[x],
                key=f"chon_chuyen_sua_{st.session_state['reset_sqt']}",
                index=None, 
                placeholder="-- Vui lòng chọn 1 chuyến đi --"
            )
            
            if chuyen_can_sua is not None:
                df_filtered = df_trips[df_trips['id'].astype(str) == str(chuyen_can_sua)]
                
                if not df_filtered.empty:
                    trip_info = df_filtered.iloc[0]
                    
                    with st.form("form_sua_quyet_toan", clear_on_submit=True):
                        st.markdown(f"**Đang sửa dữ liệu chuyến {chuyen_can_sua}**")
                        
                        def format_money(val):
                            if pd.isna(val) or val == "":
                                return "0"
                            try:
                                return f"{int(float(val)):,}" 
                            except:
                                return "0"
                                
                        def parse_money(val_str):
                            clean_str = str(val_str).replace(",", "").replace(".", "").replace(" ", "")
                            try:
                                return float(clean_str)
                            except:
                                return 0.0 

                        c1, c2, c3,c4,c5,c6 = st.columns(6)
                        
                        edit_cong_str = c1.text_input(
                            "Công tài xế (Lương)*", 
                            value=format_money(trip_info['cong_chuyen']), 
                            key=f"cong_{chuyen_can_sua}"
                        )
                        
                        edit_km = c2.number_input(
                            "Số KM thực tế*", 
                            value=0.0 if pd.isna(trip_info['so_km_thuc_te']) else float(trip_info['so_km_thuc_te']), 
                            step=1.0, 
                            key=f"km_{chuyen_can_sua}"
                        )
                        
                        edit_tien_them_str = c3.text_input(
                            "Tiền thưởng thêm", 
                            value=format_money(trip_info['tien_them']), 
                            key=f"them_{chuyen_can_sua}"
                        )
                        edit_doanh_thu_str = c4.text_input(
                            "Doanh thu chuyến", 
                            value=format_money(trip_info['doanh_thu']), 
                            key=f"doanhthu_{chuyen_can_sua}"
                        )
                        edit_so_lit_xang_str = c5.text_input(
                            "Số lít xăng", 
                            value=format_money(trip_info['so_lit_xang']), 
                            key=f"solit_{chuyen_can_sua}"
                        )
                        edit_tien_xang_str = c6.text_input(
                            "Tiền xăng", 
                            value=format_money(trip_info['tien_xang']), 
                            key=f"tienxang_{chuyen_can_sua}"
                        )

                        c7, c8, c9 = st.columns(3)
                        edit_hai_quan_str = c7.text_input(
                            "Phí hải quan", 
                            value=format_money(trip_info['phi_hai_quan']), 
                            key=f"hq_{chuyen_can_sua}"
                        )
                        
                        edit_boc_xep_str = c8.text_input(
                            "Phí bốc xếp", 
                            value=format_money(trip_info['phi_boc_xep']), 
                            key=f"bx_{chuyen_can_sua}"
                        )
                        
                        edit_khac_str = c9.text_input(
                            "Phí khác (Luật, cầu đường...)", 
                            value=format_money(trip_info['phi_khac']), 
                            key=f"khac_{chuyen_can_sua}"
                        )
                        
                        edit_ghi_chu = st.text_input(
                            "Ghi chú quyết toán (Lý do sửa)", 
                            value="" if pd.isna(trip_info['ghi_chu']) else str(trip_info['ghi_chu']),
                            key=f"gc_{chuyen_can_sua}"
                        )
                        
                        if st.form_submit_button("💾 Lưu sửa đổi quyết toán", type="primary"):
                            data_update = {
                                'cong_chuyen': parse_money(edit_cong_str),
                                'so_km_thuc_te': edit_km,
                                'so_lit_xang': parse_money(edit_so_lit_xang_str),
                                'tien_xang': parse_money(edit_tien_xang_str),
                                'tien_them': parse_money(edit_tien_them_str),
                                'doanh_thu': parse_money(edit_doanh_thu_str),
                                'phi_hai_quan': parse_money(edit_hai_quan_str),
                                'phi_boc_xep': parse_money(edit_boc_xep_str),
                                'phi_khac': parse_money(edit_khac_str),
                                'ghi_chu': edit_ghi_chu
                            }
                            
                            is_ok, msg = update_trip_transaction(db.pool, data_chuyen_di=data_update, trang_thai_enum='Hoan_Thanh', chuyen_di_id=chuyen_can_sua)
                            
                            if is_ok:
                                st.success(f"✅ Đã cập nhật thành công quyết toán cho chuyến {chuyen_can_sua}!")
                                st.session_state["reset_sqt"] += 1
                                time.sleep(2) 
                                st.rerun()
                            else:
                                st.error(f"❌ Lỗi khi lưu: {msg}")

# ==========================================
# TAB 5: 🤖 TỰ ĐỘNG ĐIỀU XE & EXCEL TOOLS
# ==========================================
with tab5:
    # --- KHỞI TẠO BỘ NHỚ TẠM ĐỂ CHỨA KẾT QUẢ ĐIỀU XE ---
    if "export_dieu_xe" not in st.session_state:
        st.session_state["export_dieu_xe"] = None
    if "export_xe_ranh" not in st.session_state: st.session_state["export_xe_ranh"] = None
    st.markdown("#### ⚙️ Trung tâm điều phối đội xe tự động & Tiện ích Excel")
    st.divider()
    
    # ---------------------------------------------------------
    # TÍNH NĂNG 1: TẢI FILE MẪU EXCEL
    # ---------------------------------------------------------
    st.markdown("##### 📥 1. Tải File Mẫu (Templates) chuẩn của hệ thống")
    col_t1, col_t2 = st.columns(2)
    with col_t1:
        df_tpl_order = pd.DataFrame([
            {
                "NGAY_CHAY": "format ô:text, dd/mm/yyyy",
                "TEN_KHACH_HANG": "Công ty TNHH ABC (Dòng Mẫu - Hãy Xóa)",
                "DIA_CHI_KHACH_HANG": "Thông tin địa chỉ khách hàng",
                "DIA_CHI_KHO_DI": "Bình Dương",
                "DIA_CHI_KHO_DEN": "Cảng Cát Lái",
                "KHOI_LUONG_KG": 1500,
                "THE_TICH_CBM": 5.5,
                "TIEN_CONG_TAI_XE":0,
                "GHI_CHU":"GHI CHÚ THÊM THÔNG TIN NẾU CẦN"
            }
        ])
        buffer_order = io.BytesIO()
        with pd.ExcelWriter(buffer_order, engine='xlsxwriter') as writer:
            df_tpl_order.to_excel(writer, index=False)
        st.download_button("⬇️ Tải mẫu Tạo chuyến tự động", data=buffer_order.getvalue(), file_name="Mau_Tao_Chuyen_Co_CBM.xlsx")
        
    with col_t2:
        df_tpl_close = pd.DataFrame(columns=["MA_CHUYEN", "KM_THUC_TE", "LIT_DAU","TIEN_XANG","TIEN_CONG_TAI_XE","DOANH_THU_CHUYEN","THUONG_THEM", "PHI_HAI_QUAN", "PHI_BOC_XEP", "PHI_KHAC", "GHI_CHU"])
        buffer_close = io.BytesIO()
        with pd.ExcelWriter(buffer_close, engine='xlsxwriter') as writer:
            df_tpl_close.to_excel(writer, index=False)
        st.download_button("⬇️ Tải mẫu Quyết toán hàng loạt", data=buffer_close.getvalue(), file_name="Mau_Quyet_Toan.xlsx")
    
    st.divider()

    # 👉 ĐÃ KHẮC PHỤC: Toàn bộ Tính năng 2 và Tính năng 3 đã được thụt lề chuẩn vào trong Tab 5

    # ---------------------------------------------------------
    # TÍNH NĂNG 2: ĐIỀU XE TỰ ĐỘNG (THUẬT TOÁN ƯU TIÊN)
    # ---------------------------------------------------------
    st.markdown("##### 🚀 2. Nạp file Excel đơn hàng chạy tự động")

    with st.form("form_auto_dispatch"):
        file_order = st.file_uploader("Chọn file Excel Tạo chuyến (Đuôi .xlsx)", type=["xlsx", "xls"])
        submit_order = st.form_submit_button("🚀 Thực thi thuật toán tự động", type="primary")
        
        if submit_order:
            if not file_order:
                st.warning("⚠️ Bạn chưa tải file Excel lên!")
            else:
                with st.spinner("⏳ Đang quét dữ liệu, ghép xe và tạo danh sách xuất file thủ công..."):
                    try:
                        df_orders = pd.read_excel(file_order)
                        df_orders.columns = [str(c).strip().upper() for c in df_orders.columns] 
                        
                        df_orders['NGAY_CHAY_CHUAN'] = pd.to_datetime(df_orders['NGAY_CHAY'], dayfirst=True, errors='coerce')
                        
                        def safe_float(val):
                            try:
                                return 0.0 if pd.isna(val) or str(val).strip() == "" else float(val)
                            except:
                                return 0.0
                        
                        df_orders['SORT_KG'] = df_orders['KHOI_LUONG_KG'].apply(safe_float)
                        df_orders['SORT_CBM'] = df_orders['THE_TICH_CBM'].apply(safe_float)
                        
                        df_orders_sorted = df_orders.sort_values(by=['SORT_KG', 'SORT_CBM'], ascending=[False, False])
                        
                        sql_xe_ranh = """
                            SELECT x.id, x.bien_so_xe, x.tai_xe_co_dinh_id, x.tai_trong_thiet_ke, x.dung_tich_cbm, 
                                nv.ho_ten as ten_tai_xe, nv.so_dien_thoai as so_dien_thoai, nv.cccd as cccd
                            FROM xe x 
                            LEFT JOIN nhan_vien nv ON x.tai_xe_co_dinh_id = nv.id
                            WHERE x.trang_thai = 'Dang_Hoat_Dong'
                            AND x.id NOT IN (
                                SELECT xe_id FROM chuyen_di 
                                WHERE trang_thai_chuyen IN ('Tao_Moi', 'Dang_Di') AND xe_id IS NOT NULL
                            )
                            ORDER BY x.tai_trong_thiet_ke ASC, x.dung_tich_cbm ASC
                        """
                        df_xe_ranh = db.execute_query(sql_xe_ranh)
                        
                        if isinstance(df_xe_ranh, str) or df_xe_ranh.empty:
                            st.error("❌ Hiện tại không có xe nào rảnh để điều phối!")
                        else:
                            success_count = 0
                            xe_list = df_xe_ranh.to_dict('records')
                            danh_sach_xuat_excel = [] 
                            
                            for xe in xe_list:
                                xe['is_used'] = False 
                            
                            for idx, row in df_orders_sorted.iterrows():
                                
                                ngay_chay_dt = row['NGAY_CHAY_CHUAN']
                                if pd.isna(ngay_chay_dt):
                                    st.error(f"❌ Dòng số {idx + 2} (Excel): Dữ liệu ngày '{row.get('NGAY_CHAY')}' không hợp lệ. Vui lòng nhập chuẩn DD/MM/YYYY.")
                                    continue
                                    
                                ngay_chay_str = ngay_chay_dt.strftime('%Y-%m-%d')       
                                ngay_chay_hien_thi = ngay_chay_dt.strftime('%d/%m/%Y')  
                                
                                req_kg = row['SORT_KG']
                                req_cbm = row['SORT_CBM']
                                khach_hang = str(row.get('TEN_KHACH_HANG', 'Khách Lẻ')).strip()
                                
                                val_cong = row.get('TIEN_CONG_TAI_XE', 0)
                                cong_tai_xe = 0.0 if pd.isna(val_cong) or str(val_cong).strip() == "" else float(val_cong)
                                
                                val_dia_chi_kh = row.get('DIA_CHI_KHACH_HANG', '')
                                dia_chi_kh = str(val_dia_chi_kh).strip() if pd.notnull(val_dia_chi_kh) else ""
                                
                                val_kho_di = row.get('DIA_CHI_KHO_DI', '')
                                kho_di = str(val_kho_di).strip() if pd.notnull(val_kho_di) else ""
                                
                                val_kho_den = row.get('DIA_CHI_KHO_DEN', '')
                                kho_den = str(val_kho_den).strip() if pd.notnull(val_kho_den) else ""
                                
                                val_ghi_chu = row.get('GHI_CHU', '')
                                ghi_chu = str(val_ghi_chu).strip() if pd.notnull(val_ghi_chu) else ""

                                xe_phu_hop = None
                                
                                for xe in xe_list:
                                    if xe['is_used'] or pd.isna(xe['tai_xe_co_dinh_id']): continue 
                                    
                                    cap_kg = float(xe['tai_trong_thiet_ke'] or 0) * 1000 
                                    cap_cbm = float(xe['dung_tich_cbm'] or 0)
                                    
                                    if (cap_kg >= req_kg) and (req_cbm == 0 or cap_cbm >= req_cbm):
                                        xe_phu_hop = xe
                                        xe['is_used'] = True
                                        break
                                
                                if xe_phu_hop:
                                    trip_data_tuple = (
                                        ngay_chay_str,                
                                        khach_hang,                   
                                        dia_chi_kh,                   
                                        xe_phu_hop['id'],             
                                        f"{kho_di} ➡️ {kho_den}",     
                                        0.0,                          
                                        req_kg,                      
                                        req_cbm,                      
                                        cong_tai_xe,                  
                                        'Tao_Moi',                    
                                        ghi_chu                       
                                    )
                                
                                    tx_id = int(float(xe_phu_hop['tai_xe_co_dinh_id']))
                                    is_ok, result_msg = save_trip_full_process(db.pool, trip_data_tuple, tx_id)
                                    
                                    if is_ok:
                                        success_count += 1
                                        
                                        raw_bien_so = str(xe_phu_hop['bien_so_xe'])
                                        ten_group = "".join([c for c in raw_bien_so if c.isalnum()]).upper()
                                        
                                        noi_dung_chat = (
                                            f"- LỆNH ĐIỀU XE BẢO TÍN -\n"
                                            f"- Mã chuyến: {result_msg}\n"
                                            f"- Ngày chạy: {ngay_chay_hien_thi}\n"
                                            f"- Khách hàng: {khach_hang}\n"
                                            f"- Lộ trình: {kho_di} ➡️ {kho_den}\n"
                                            f"- Ghi chú: {ghi_chu if ghi_chu else 'Không'}\n"
                                            
                                        )
                                        
                                        danh_sach_xuat_excel.append({
                                            "STT Dòng Excel": idx + 2,
                                            "ten_group": ten_group, 
                                            "noi_dung_chat": noi_dung_chat, 
                                            "Mã Hệ Thống (Trip ID)": result_msg,
                                            "Ngày Chạy": ngay_chay_hien_thi,
                                            "Khách Hàng": khach_hang,
                                            "Địa Chỉ KH": dia_chi_kh,
                                            "Lộ Trình": f"{kho_di} ➡️ {kho_den}",
                                            "Biển Số Xe": raw_bien_so,
                                            "Tên Tài Xế": xe_phu_hop['ten_tai_xe'],
                                            "Số điện thoại": xe_phu_hop['so_dien_thoai'],
                                            "CCCD": xe_phu_hop['cccd'],
                                            "Công tài xế": cong_tai_xe,
                                            "Khối Lượng (KG)": req_kg,
                                            "Thể Tích (CBM)": req_cbm,
                                            "Ghi Chú": ghi_chu
                                        })
                                    else:
                                        st.error(f"❌ Lỗi lưu đơn '{khach_hang}' (Dòng {idx + 2}): {result_msg}")
                                else:
                                    st.warning(f"⚠️ Dòng {idx + 2} (Excel): Đơn '{khach_hang}' ({req_kg}kg, {req_cbm} CBM) không tìm được xe phù hợp!")
                            
                            xe_con_trong = []
                            for xe in xe_list:
                                if not xe['is_used']:
                                    xe_con_trong.append({
                                        "Biển Số Xe": xe['bien_so_xe'],
                                        "Tài Xế Mặc Định": xe['ten_tai_xe'],
                                        "Số Điện Thoại": xe['so_dien_thoai'],
                                        "Tải Trọng (Tấn)": float(xe['tai_trong_thiet_ke'] or 0),
                                        "Thể Tích (CBM)": float(xe['dung_tich_cbm'] or 0)
                                    })
                            st.session_state["export_xe_ranh"] = pd.DataFrame(xe_con_trong)
                            
                            if success_count > 0:
                                st.success(f"🎉 Đã điều phối thành công {success_count} chuyến đi và tạo sẵn nội dung Zalo thủ công!")
                                st.balloons()
                                
                                df_export = pd.DataFrame(danh_sach_xuat_excel)
                                df_export = df_export.sort_values(by="STT Dòng Excel").drop(columns=["STT Dòng Excel"])
                                st.session_state["export_dieu_xe"] = df_export
                                
                                time.sleep(2)
                                st.rerun()
                                
                    except Exception as e:
                        st.error(f"❌ Lỗi xử lý thuật toán: {str(e)}")

    # ---------------------------------------------------------
    # KẾT QUẢ ĐIỀU XE: XUẤT FILE IN & GỌI TÀI XẾ
    # ---------------------------------------------------------
    if st.session_state.get("export_dieu_xe") is not None and not st.session_state["export_dieu_xe"].empty:
        st.markdown("### 🖨️ Danh sách chuyến đi vừa điều phối thành công (Hỗ trợ Zalo Thủ công)")
        st.dataframe(st.session_state["export_dieu_xe"], use_container_width=True)
        
        buffer_export = io.BytesIO()
        with pd.ExcelWriter(buffer_export, engine='xlsxwriter') as writer:
            st.session_state["export_dieu_xe"].to_excel(writer, index=False, sheet_name="Lich_Chay_Va_Zalo")
            
            df_ranh = st.session_state.get("export_xe_ranh")
            if df_ranh is not None and not df_ranh.empty:
                df_ranh.to_excel(writer, index=False, sheet_name="Xe_Con_Trong")
            else:
                pd.DataFrame([{"Thông Báo": "Tuyệt vời! Toàn bộ xe rảnh đã được điều động hết."}]).to_excel(writer, index=False, sheet_name="Xe_Con_Trong")
        
        col_btn1, col_btn2 = st.columns([1, 4])
        with col_btn1:
            if st.button("🔄 Reset Màn Hình", use_container_width=True):
                st.session_state["export_dieu_xe"] = None
                st.session_state["export_xe_ranh"] = None
                st.rerun()
        with col_btn2:
            st.download_button(
                label="⬇️ TẢI FILE EXCEL (CÓ CỘT TEN_GROUP & NỘI DUNG ZALO THỦ CÔNG)", 
                data=buffer_export.getvalue(), 
                file_name=f"Lenh_Dieu_Xe_ZaloThuCong_{datetime.date.today().strftime('%d_%m_%Y')}.xlsx", 
                type="primary",
                use_container_width=True
            )
                    
    st.divider()
        
    # ---------------------------------------------------------
    # TÍNH NĂNG 3: QUYẾT TOÁN HÀNG LOẠT BẰNG EXCEL
    # ---------------------------------------------------------
    st.markdown("##### 🏁 3. Nạp file Excel chốt chuyến / quyết toán hàng loạt")
    with st.form("form_mass_close"):
            file_close = st.file_uploader("Chọn file Excel Quyết toán (Đuôi .xlsx)", type=["xlsx", "xls"])
            submit_close = st.form_submit_button("🏁 Khóa sổ & Chốt chuyến hàng loạt", type="primary")
            
            if submit_close:
                if not file_close:
                    st.warning("⚠️ Bạn chưa tải file Excel lên!")
                else:
                    with st.spinner("⏳ Hệ thống đang xử lý quyết toán và cập nhật Database... Không đóng trình duyệt lúc này!"):
                        try:
                            df_close = pd.read_excel(file_close)
                            df_close.columns = [str(c).strip().upper() for c in df_close.columns]
                            
                            closed_count = 0
                            error_list = []
                            
                            def parse_excel_money(val):
                                if pd.isna(val) or val == "" or val is None:
                                    return 0.0
                                try:
                                    if isinstance(val, (int, float)):
                                        return float(val)
                                    clean_str = str(val).replace(",", "").replace(" ", "").strip()
                                    return float(clean_str)
                                except ValueError:
                                    return 0.0

                            for index, r in df_close.iterrows():
                                if pd.isna(r.get('MA_CHUYEN')): 
                                    continue 
                                
                                cid = int(r['MA_CHUYEN'])
                                
                                sql_check = "SELECT trang_thai_chuyen FROM chuyen_di WHERE id = %s"
                                df_check = db.execute_query(sql_check, (cid,))
                                
                                if isinstance(df_check, pd.DataFrame):
                                    if df_check.empty:
                                        error_list.append(f"❌ Dòng {index + 2} (Mã chuyến {cid}): Không tồn tại trong hệ thống.")
                                        continue
                                    else:
                                        trang_thai = df_check.iloc[0]['trang_thai_chuyen']
                                        if trang_thai == 'Hoan_Thanh':
                                            error_list.append(f"⚠️ Dòng {index + 2} (Mã chuyến {cid}): Đã khóa sổ trước đó, hệ thống tự động bỏ qua.")
                                            continue
                                else:
                                    error_list.append(f"❌ Dòng {index + 2} (Mã chuyến {cid}): Lỗi truy vấn cơ sở dữ liệu.")
                                    continue
                                
                                data_dict_excel = {
                                    'so_km_thuc_te': parse_excel_money(r.get('KM_THUC_TE')),
                                    'so_lit_xang': parse_excel_money(r.get('LIT_DAU')),
                                    'tien_xang': parse_excel_money(r.get('TIEN_XANG')),
                                    'cong_chuyen': parse_excel_money(r.get('TIEN_CONG_TAI_XE')),
                                    'doanh_thu': parse_excel_money(r.get('DOANH_THU_CHUYEN')),
                                    'tien_them': parse_excel_money(r.get('THUONG_THEM')),
                                    'phi_hai_quan': parse_excel_money(r.get('PHI_HAI_QUAN')),
                                    'phi_boc_xep': parse_excel_money(r.get('PHI_BOC_XEP')),
                                    'phi_khac': parse_excel_money(r.get('PHI_KHAC')),
                                    'ghi_chu': str(r.get('GHI_CHU', '')).strip() if pd.notna(r.get('GHI_CHU')) else ""
                                }
                    
                                success, msg = settle_trip_transaction(db.pool, data_dict_excel, 'Hoan_Thanh', cid)
                                
                                if success:
                                    closed_count += 1
                                else:
                                    error_list.append(f"❌ Dòng {index + 2} (Mã chuyến {cid}): Lỗi khi cập nhật - {msg}")
                                    
                            if closed_count > 0:
                                st.success(f"🎉 Đã xử lý khoá sổ thành công {closed_count} chuyến đi!")
                                time.sleep(2)
                                st.rerun()

                            if error_list:
                                with st.expander("⚠️ Chi tiết các đơn không thể quyết toán (Nhấn để xem)", expanded=True):
                                    for err in error_list:
                                        st.warning(err)
                                        
                        except Exception as e:
                            st.error(f"❌ Lỗi hệ thống khi đọc file Excel: {str(e)}")