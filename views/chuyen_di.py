import streamlit as st
import pandas as pd
import datetime
import io
from map_service import MapService
from st_aggrid import AgGrid, GridOptionsBuilder
import time 
import json
import streamlit.components.v1 as components
from global_func import  parse_money_input, delete_trip_safe, settle_trip_transaction, save_trip_full_process, update_trip_transaction
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



####

st.markdown("<h3 style='text-align: center; color: #0b5394;'>📝 PHÂN HỆ QUẢN LÝ VÀ ĐIỀU PHỐI CHUYẾN ĐI NÂNG CAO</h3>", unsafe_allow_html=True)

# Mở rộng thành 5 Tab nghiệp vụ
tab1, tab2, tab3, tab4,tab5 = st.tabs([
    "📋 Danh sách Chuyến", 
    "➕ Book chuyến thủ công", 
    "🏁 Quyết toán đơn chuyến",
    "🏁 Sửa chuyến đi đã quyết toán", 
    "🤖 Excel Tools & book chuyến tự động" 
    #"📍 Bản đồ GPS"  # Thêm tab này
])

# ==========================================
# 🛠️ CHUẨN HÓA DỮ LIỆU TỪ DATABASE (KHẮC PHỤC LỖI ÉP KIỂU)
# ==========================================
#
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
#df_xe_full = db.execute_query("SELECT id, bien_so_xe, tai_trong_thiet_ke, dung_tich_cbm, tai_xe_co_dinh_id FROM xe WHERE trang_thai='Dang_Hoat_Dong'")
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
    try:
        sql_list = """
            SELECT cd.id AS 'Mã', cd.ngay_chuyen_di AS 'Ngày', cd.ten_khach_hang AS 'Khách hàng',
                   x.bien_so_xe AS 'Biển Số', nv.ho_ten AS 'Tài Xế', cd.dia_diem_giao_nhan AS 'Lộ trình', 
                   CAST(cd.so_km_thuc_te AS FLOAT) AS 'Số KM', CAST(cd.cong_chuyen AS FLOAT) AS 'Lương chuyến',
                   CAST(cd.tien_them AS FLOAT) AS 'Thưởng thêm', cd.trang_thai_chuyen AS 'Trạng thái'
            FROM chuyen_di cd 
            LEFT JOIN xe x ON cd.xe_id = x.id
            LEFT JOIN chuyen_di_tai_xe cdtx ON cd.id = cdtx.chuyen_di_id AND cdtx.loai_tai_xe = 'Tai_Chinh'
            LEFT JOIN nhan_vien nv ON cdtx.tai_xe_id = nv.id 
            WHERE cd.ngay_chuyen_di >= DATE_SUB(NOW(), INTERVAL 7 DAY)
            ORDER BY cd.id DESC
        """
        df_chuyen = db.execute_query(sql_list)
        
        if isinstance(df_chuyen, pd.DataFrame) and not df_chuyen.empty:
            df_chuyen['Ngày'] = pd.to_datetime(df_chuyen['Ngày']).dt.strftime('%d/%m/%Y')
            for col_money in ['Lương chuyến', 'Thưởng thêm']:
                df_chuyen[col_money] = df_chuyen[col_money].apply(lambda x: f"{x:,.0f}" if pd.notnull(x) else "0")
            
            gb = GridOptionsBuilder.from_dataframe(df_chuyen)
            gb.configure_default_column(resizable=True, filter=True, sortable=True, minWidth=140)
            gb.configure_pagination(paginationAutoPageSize=False, paginationPageSize=12)
            
            custom_css = {
                ".ag-header-cell": {"background-color": "#0b5394", "color": "white", "font-weight": "bold"},
                ".ag-row-hover": {"background-color": "#eef2f5 !important"},
            }
            AgGrid(df_chuyen, gridOptions=gb.build(), custom_css=custom_css, allow_unsafe_jscode=True, theme='streamlit')
        else:
            st.info("Chưa có dữ liệu chuyến đi nào trong 7 ngày qua.")
    except Exception as e:
        st.error(f"Lỗi truy xuất danh sách: {e}")

# ==========================================
# TAB 2: ĐĂNG KÝ THỦ CÔNG (ĐÃ FIX LỖI POPUP TÀI XẾ)
# ==========================================
with tab2:
    
    if "reset_tab2" not in st.session_state: st.session_state["reset_tab2"] = 0
    st.subheader("Lên lệnh chạy đơn lẻ")
    
    c_xe_sel = st.selectbox(
        "🚛 Chọn Xe vận chuyển", 
        options=list(xe_map.keys()), 
        format_func=lambda x: f"{xe_map[x]['bien_so_xe']} — ({xe_map[x]['tai_trong_thiet_ke']}T | {xe_map[x]['dung_tich_cbm']} CBM)", 
        index=None, 
        key=f"xe_sel_{st.session_state['reset_tab2']}"
    )
    
    # THUẬT TOÁN BẮT TÀI XẾ
    default_tx_id = None
    if c_xe_sel and pd.notna(xe_map[c_xe_sel]['tai_xe_co_dinh_id']):
        # Ép kiểu an toàn từ float -> int
        tx_id_raw = int(float(xe_map[c_xe_sel]['tai_xe_co_dinh_id']))
        if tx_id_raw in tx_opts:
            default_tx_id = tx_id_raw
            st.toast(f"Đã tự động điền tài xế: {tx_opts[tx_id_raw]}", icon="🤖")

    # Xác định Index của tài xế đó trong danh sách
    danh_sach_tx_id = list(tx_opts.keys())
    tx_index = danh_sach_tx_id.index(default_tx_id) if default_tx_id in danh_sach_tx_id else None

    # 👉 THỦ THUẬT DYNAMIC KEY: Đổi key theo id xe để Streamlit bị ép phải vẽ lại (render) và nhận index mới
    dynamic_tx_key = f"tx_sel_{st.session_state['reset_tab2']}_{c_xe_sel}"

    c_tx_sel = st.selectbox(
        "🧑‍✈️ Xác nhận Tài xế chạy (Có thể chọn thay thế)", 
        options=danh_sach_tx_id, 
        index=tx_index, 
        format_func=lambda x: tx_opts[x], 
        key=dynamic_tx_key
    )
    
    with st.form("form_thu_cong_chuyen", clear_on_submit=False):
        c1, c2 = st.columns(2)
        txt_khach = c1.text_input("🏢 Công ty đối tác / Khách hàng", key=f"kh_{st.session_state['reset_tab2']}")
        ngay_di = c2.date_input("🗓️ Ngày khởi hành", value=datetime.date.today(), format="DD/MM/YYYY", key=f"ngay_{st.session_state['reset_tab2']}")
        
        c3, c4,c5 = st.columns(3)
        diem_dau = c3.text_input("🏠 Kho bốc hàng", key=f"dau_{st.session_state['reset_tab2']}")
        diem_cuoi = c4.text_input("🎯 Kho giao hàng", key=f"cuoi_{st.session_state['reset_tab2']}")
        so_cbm = c5.number_input("Số CBM", min_value=1.0,  key=f"cbm_{st.session_state['reset_tab2']}")
        trang_thai_ui_value = st.selectbox("Trạng thái", options=list(STATUS_MAP.keys()))
        if st.form_submit_button("🔍 Quét bản đồ vệ tinh", type="secondary"):
            if diem_dau and diem_cuoi and hasattr(map_srv, 'tinh_lo_trinh_duong_bo'):
                c_start, c_end = map_srv.lay_toa_do(diem_dau), map_srv.lay_toa_do(diem_cuoi)
                if c_start and c_end:
                    res = map_srv.tinh_lo_trinh_duong_bo(c_start, c_end)
                    if res: st.session_state["api_km"] = res["km"]
        
        val_km = float(st.session_state.get("api_km", 1.0))
        if val_km < 1.0: val_km = 1.0
        
        c6, c7 = st.columns(2)
        km_thuc = c5.number_input("Số KM dự kiến", min_value=1.0, value=val_km, step=0.1, key=f"km_{st.session_state['reset_tab2']}")
        cong_chuyen_str = c6.text_input("Tạm ứng (VNĐ)", placeholder="VD: 200,000", key=f"luong_{st.session_state['reset_tab2']}")
        
        if st.form_submit_button("💾 Phát lệnh chạy thủ công", type="primary"):
            if not c_xe_sel or not c_tx_sel or not txt_khach.strip(): 
                st.error("⚠️ Vui lòng điền đủ thông tin xe, tài xế và khách hàng!")
            else:
                # 1. Chuyển đổi định dạng và parse dữ liệu chữ thành số
                ngay_db = ngay_di.strftime('%Y-%m-%d')
                cong_tien = parse_money_input(cong_chuyen_str) 
            
                # Ánh xạ trạng thái từ giao diện (Tiếng Việt) sang chuẩn Database (Không dấu)
                db_status = STATUS_MAP[trang_thai_ui_value]
                # 2. Khởi tạo Tuple chuyến đi đúng thứ tự 7 cột như trong sql_trip
                trip_data = (
                    ngay_db, 
                    txt_khach.strip(), 
                    c_xe_sel, 
                    f"{diem_dau} ➡️ {diem_cuoi}", 
                    km_thuc,
                    0,             # <--- Khối lượng KG (để 0)
                    so_cbm,
                    cong_tien,
                    db_status
                )
                
            
                
                
                # 3. Gọi hàm Transaction đa bảng
            # Lưu ý gọi db.pool (do biến db = st.session_state['db'] đã chứa class Database)
                success, result = save_trip_full_process(db.pool, trip_data, c_tx_sel)
                
                if success:
                    st.session_state["reset_tab2"] += 1
                    st.session_state["api_km"] = 0.0
                    st.success(f"✅ Đăng ký thành công chuyến đi! Mã nội bộ DB: {result}")
                    st.balloons()
                    time.sleep(1)
                    st.rerun() # Tự động làm mới bảng dữ liệu
                else:
                    st.error(f"Lỗi: {result}")
              ########################      
                
                                 
       
# ==========================================
# TAB 3: QUYẾT TOÁN ĐƠN CHUYẾN
# ==========================================
with tab3:
    # Biến session để ép giao diện tự làm mới khi có thay đổi dữ liệu
    if "reset_chuyen_form" not in st.session_state: 
        st.session_state["reset_chuyen_form"] = 0
        
    st.markdown("#### 🏁 Quyết toán & Cập nhật chi phí chuyến đi")
    
    # 1. TẢI CẤU HÌNH THƯỞNG TỪ DATABASE
    df_cfg = db.execute_query("SELECT ma_tieu_chi, muc_thuong FROM cau_hinh_thuong")
    bonus_rules = {row['ma_tieu_chi']: float(row['muc_thuong']) for _, row in df_cfg.iterrows()} if isinstance(df_cfg, pd.DataFrame) and not df_cfg.empty else {}

    # 2. TẢI DANH SÁCH CHUYẾN ĐI CHƯA HOÀN THÀNH (Lấy thêm thông tin xe và tài xế)
    sql_load = """
        SELECT cd.id, cd.ngay_chuyen_di, cd.ten_khach_hang, x.bien_so_xe, CAST(x.tai_trong_thiet_ke AS FLOAT) AS tai_trong,
               nv.ho_ten AS ten_tai_xe, cd.trang_thai_chuyen,
               cd.so_km_thuc_te, cd.so_lit_xang, cd.cong_chuyen, cd.tien_them,
               cd.phi_hai_quan, cd.phi_boc_xep, cd.phi_khac, cd.ghi_chu_quyet_toan,
               cd.is_gop_chuyen, cd.is_ve_khuya
        FROM chuyen_di cd
        LEFT JOIN xe x ON cd.xe_id = x.id
        LEFT JOIN chuyen_di_tai_xe ctx ON cd.id = ctx.chuyen_di_id AND ctx.loai_tai_xe = 'Tai_Chinh'
        LEFT JOIN nhan_vien nv ON ctx.tai_xe_id = nv.id
        WHERE cd.trang_thai_chuyen NOT IN ('Hoan_Thanh', 'Huy_Chuyen')
        ORDER BY cd.ngay_chuyen_di DESC
    """
    df_cd = db.execute_query(sql_load)

    if isinstance(df_cd, pd.DataFrame) and not df_cd.empty:
        # Tạo danh sách chọn chuyến đi
        trip_options = {
            row['id']: f"Mã: {row['id']} | Ngày: {row['ngay_chuyen_di']} | Khách: {row['ten_khach_hang']} | Xe: {row['bien_so_xe']} | TX: {row['ten_tai_xe']}"
            for _, row in df_cd.iterrows()
        }
        
        # Dropdown chọn chuyến đi
        cd_id = st.selectbox("🔍 Chọn chuyến đi đang chờ quyết toán:", 
                             options=list(trip_options.keys()), 
                             format_func=lambda x: trip_options[x],
                             key=f"sel_trip_{st.session_state['reset_chuyen_form']}")
        
        # Lấy dữ liệu của chuyến đi đang được chọn
        row_sel = df_cd[df_cd['id'] == cd_id].iloc[0]
        tai_trong_xe = row_sel['tai_trong']
        
        with st.form(key=f"form_qt_{st.session_state['reset_chuyen_form']}"):
            
            # --- PHẦN 1: SỐ LIỆU HÀNH TRÌNH THỰC CHẠY ---
            st.markdown("##### 📍 1. Số liệu hành trình thực chạy")
            col1_1, col1_2, col1_3, col1_4 = st.columns(4)
            edit_cong_ty = col1_1.text_input("Tên Khách/Công ty", value=str(row_sel['ten_khach_hang'] or ""))
            final_km     = col1_2.number_input("Số KM thực tế", min_value=0.0, value=float(row_sel['so_km_thuc_te'] or 0.0), step=1.0)
            final_lit    = col1_3.number_input("Số Lít xăng/dầu", min_value=0.0, value=float(row_sel['so_lit_xang'] or 0.0), step=1.0)
            #num_cong     = col1_4.number_input("Công chuyến (VNĐ)", min_value=0, value=int(row_sel['cong_chuyen'] or 0), step=50000)
            num_cong     = col1_4.text_input("Công chuyến (VNĐ)", placeholder="VD: 200,000",value=str(row_sel['cong_chuyen'] or ""))
            #cong_chuyen_str = c6.text_input("Tạm ứng (VNĐ)", placeholder="VD: 200,000", key=f"luong_{st.session_state['reset_tab2']}")
            num_cong = parse_money_input(num_cong)
            st.divider()

            # --- PHẦN 2: CHẾ ĐỘ PHỤ CẤP & TIỀN THƯỞNG ---
            st.markdown("##### 🎁 2. Chế độ phụ cấp & Tiền thưởng")
            st.info(f"💡 Xe hiện tại có tải trọng: **{tai_trong_xe} Tấn**. Mức thưởng sẽ được tính dựa trên tải trọng này và cấu hình.")
            
            col2_1, col2_2, col2_3 = st.columns([1, 1, 2])
            with col2_1:
                chk_gop = st.checkbox("Chuyến đi Gộp", value=bool(row_sel['is_gop_chuyen']))
            with col2_2:
                chk_khuya = st.checkbox("Chạy Về Khuya", value=bool(row_sel['is_ve_khuya']))
            with col2_3:
                num_them = st.number_input("Tổng tiền phụ Cấp (VNĐ)", min_value=0, value=int(row_sel['tien_them'] or 0), step=50000, 
                                           help="Tiền thưởng sẽ tự động tính nếu check ô, nhưng bạn có thể sửa tay.")
            
            st.divider()

            # --- PHẦN 3: QUYẾT TOÁN PHÍ ĐƯỜNG BỘ & GHI CHÚ ---
            st.markdown("##### 🧾 3. Quyết toán phí đường bộ & Ghi chú")
            # --- CHỐT CHẶN BẢO VỆ: CHỐNG NHẤN ENTER NHẦM ---
            st.markdown("##### 🛡️ Xác nhận thao tác")
            xac_nhan_chot = st.checkbox("⚠️ Tôi xác nhận các số liệu trên đã đầy đủ, chính xác và đồng ý CHỐT SỔ chuyến đi này.")

            col3_1, col3_2, col3_3 = st.columns(3)
            #num_hq = col3_1.number_input("Phí Hải Quan (VNĐ)", min_value=0, value=int(row_sel['phi_hai_quan'] or 0), step=10000)
            #num_bx = col3_2.number_input("Phí Bốc Xếp (VNĐ)", min_value=0, value=int(row_sel['phi_boc_xep'] or 0), step=10000)
            #num_k  = col3_3.number_input("Phí Khác (VNĐ)", min_value=0, value=int(row_sel['phi_khac'] or 0), step=10000)
            num_hq = col3_1.text_input("Phí Hải Quan (VNĐ)", placeholder="VD: 100,000", value=str(row_sel['phi_hai_quan'] or ""))
            num_bx = col3_2.text_input("Phí Bốc Xếp (VNĐ)", placeholder="VD: 100,000", value=str(row_sel['phi_boc_xep'] or ""))
            num_k  = col3_3.text_input("Phí Khác (VNĐ)", placeholder="VD: 100,000", value=str(row_sel['phi_khac'] or ""))
            # ep chuyen lai thanh so number
            num_hq= parse_money_input(num_hq)
            num_bx= parse_money_input(num_bx)
            num_k= parse_money_input(num_k)
            # Kiểm tra nếu là NaN hoặc trống thì gán bằng chuỗi rỗng "", ngược lại thì ép kiểu chuỗi
            gia_tri_cu = row_sel['ghi_chu_quyet_toan']
            gc_hien_thi = "" if pd.isna(gia_tri_cu) else str(gia_tri_cu)

            edit_gc = st.text_input("Ghi chú quyết toán", value=gc_hien_thi)

            #edit_gc = st.text_input("Ghi chú quyết toán", value=str(row_sel['ghi_chu_quyet_toan'] or ""))
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            # --- PHẦN 4: NÚT BẤM XỬ LÝ (LƯU / CHỐT / XÓA) ---
            b1, b2, b3 = st.columns(3)
            submit_luu  = b1.form_submit_button("💾 LƯU CẬP NHẬT", type="secondary")
            submit_chot = b2.form_submit_button("🏁 CHỐT SỔ CHUYẾN", type="primary")
            submit_xoa  = b3.form_submit_button("🗑️ XÓA CHUYẾN ĐI")

            # GOM DỮ LIỆU CHUNG (Tuân thủ đúng thứ tự biến %s trong câu SQL)
            update_params = (
                edit_cong_ty, final_km, final_lit, num_cong, 
                1 if chk_gop else 0, 1 if chk_khuya else 0, 
                num_them, num_hq, num_bx, num_k, edit_gc, 
                cd_id 
            )
            data_dict_thu_cong = {
                    'ten_khach_hang': edit_cong_ty,
                    'so_km_thuc_te': final_km,
                    'so_lit_xang': final_lit,
                    'cong_chuyen': num_cong,
                    'is_gop_chuyen': 1 if chk_gop else 0,
                    'is_ve_khuya': 1 if chk_khuya else 0,
                    'tien_them': num_them,
                    'phi_hai_quan': num_hq,
                    'phi_boc_xep': num_bx,
                    'phi_khac': num_k,
                    'ghi_chu_quyet_toan': edit_gc
                }

            # XỬ LÝ SỰ KIỆN LƯU (Cập nhật dữ liệu, giữ nguyên trạng thái cũ)
            if submit_luu:
                is_ok, msg = settle_trip_transaction(db.pool, data_dict_thu_cong, row_sel['trang_thai_chuyen'], cd_id)
                    # Xử lý thông báo (st.success hoặc st.error)
            
                if is_ok:
                    st.session_state["reset_chuyen_form"] += 1
                    st.success("✅ Đã lưu thay đổi chuyến đi này thành công!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(f"❌ Không thể lưu thay đổi chuyến đi này. Chi tiết lỗi: {msg}")

            # XỬ LÝ SỰ KIỆN CHỐT SỔ (Cập nhật dữ liệu + Ép trạng thái thành 'Hoan_Thanh')
            if submit_chot:
                if not xac_nhan_chot:
                    # Báo lỗi chữ đỏ và dừng lại, không gọi hàm Database
                    st.error("✋ HỆ THỐNG ĐÃ CHẶN: Bạn vừa bấm Chốt sổ (hoặc nhấn Enter) nhưng chưa tick vào ô 'Tôi xác nhận...'. Vui lòng kiểm tra lại thông tin và tick xác nhận!")
                else:
                    is_ok, msg = settle_trip_transaction(db.pool, data_dict_thu_cong, 'Hoan_Thanh', cd_id)
                    # Xử lý thông báo
                    if is_ok:
                        st.session_state["reset_chuyen_form"] += 1
                        st.success("✅ Đã chốt chuyến đi thành công!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(f"❌ Không thể chốt chuyến đi. Chi tiết lỗi: {msg}")
                
            # XỬ LÝ SỰ KIỆN XÓA CHUYẾN ĐI (Bằng Transaction dọn dẹp sạch sẽ)
            if submit_xoa:
                success, msg = delete_trip_safe(db.pool, cd_id)
                if success:
                    st.session_state["reset_chuyen_form"] += 1
                    st.success("✅ Đã xóa chuyến đi và dọn dẹp sạch dữ liệu liên quan!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(f"❌ Không thể xóa chuyến đi. Chi tiết lỗi: {msg}")
    else:
        st.info("🎉 Tuyệt vời! Hiện tại không có chuyến đi nào đang chờ quyết toán.")
                    

############################################


# Giả sử bạn đang ở trong khối hiển thị Tab (ví dụ: with tab5:)
with tab4:
    # --- THÊM 2 DÒNG NÀY ĐỂ TẠO BỘ ĐẾM RESET ---
    if "reset_sqt" not in st.session_state:
        st.session_state["reset_sqt"] = 0
    st.markdown("#### 📝 Sửa dữ liệu chuyến đi đã Quyết Toán / Chốt chuyến")
    st.info("Tính năng này dùng để điều chỉnh chi phí, công lương cho các chuyến đã chốt.")
    
    current_user = st.session_state.get('username', 'Admin')
    
    # 1. BỘ LỌC TÌM KIẾM
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

    # 2. HIỂN THỊ DANH SÁCH CHUYẾN ĐI
    if doi_tuong_id:
        ngay_str = ngay_tim_kiem.strftime('%Y-%m-%d')
        
        # Lấy dữ liệu từ Database
        if loai_tim_kiem == "Theo Xe":
            sql_find_trips = """
                SELECT id, dia_diem_giao_nhan, ten_khach_hang, cong_chuyen, so_km_thuc_te, 
                       tien_them, phi_hai_quan, phi_boc_xep, phi_khac, ghi_chu_quyet_toan 
                FROM chuyen_di 
                WHERE ngay_chuyen_di = %s AND xe_id = %s 
                  AND trang_thai_chuyen = 'Hoan_Thanh'
            """
            df_trips = db.execute_query(sql_find_trips, (ngay_str, doi_tuong_id))
        else:
            sql_find_trips = """
                SELECT cd.id, cd.dia_diem_giao_nhan, cd.ten_khach_hang, cd.cong_chuyen, cd.so_km_thuc_te, 
                       cd.tien_them, cd.phi_hai_quan, cd.phi_boc_xep, cd.phi_khac, cd.ghi_chu_quyet_toan 
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
                # --- SỬA DÒNG NÀY (Thêm reset_sqt vào tên key) ---
                key=f"chon_chuyen_sua_{st.session_state['reset_sqt']}",
                index=None, 
                placeholder="-- Vui lòng chọn 1 chuyến đi --"
            )
            
            # 🛑 CHỈ CHẠY CODE BÊN DƯỚI NẾU NGƯỜI DÙNG ĐÃ CHỌN 1 MÃ CHUYẾN
            if chuyen_can_sua is not None:
                
                # Ép kiểu lọc an toàn
                df_filtered = df_trips[df_trips['id'].astype(str) == str(chuyen_can_sua)]
                
                # Kiểm tra chắc chắn bảng không rỗng
                if not df_filtered.empty:
                    # Chỉ dùng iloc[0] khi đã chắc chắn bảng có dữ liệu
                    trip_info = df_filtered.iloc[0]
                    
                    # 3. FORM NHẬP LIỆU
                    # 3. FORM NHẬP LIỆU SỬA ĐỔI
                    with st.form("form_sua_quyet_toan", clear_on_submit=True):
                        st.markdown(f"**Đang sửa dữ liệu chuyến {chuyen_can_sua}**")
                        
                        # --- HÀM 1: ĐỊNH DẠNG SỐ CÓ DẤU PHẨY ĐỂ HIỂN THỊ ---
                        def format_money(val):
                            if pd.isna(val) or val == "":
                                return "0"
                            try:
                                return f"{int(float(val)):,}" # Thêm dấu phẩy ngăn cách ngàn
                            except:
                                return "0"
                                
                        # --- HÀM 2: LỘT BỎ DẤU PHẨY/CHẤM ĐỂ LƯU DATABASE ---
                        def parse_money(val_str):
                            # Xóa mọi dấu phẩy, dấu chấm, khoảng trắng do người dùng gõ
                            clean_str = str(val_str).replace(",", "").replace(".", "").replace(" ", "")
                            try:
                                return float(clean_str)
                            except:
                                return 0.0 # Nếu gõ bậy bạ chữ cái thì trả về 0

                        # Dùng text_input cho Tiền, giữ number_input cho KM
                        c1, c2, c3 = st.columns(3)
                        
                        edit_cong_str = c1.text_input(
                            "Công tài xế (Lương)*", 
                            value=format_money(trip_info['cong_chuyen']), 
                            key=f"cong_{chuyen_can_sua}"
                        )
                        
                        # Số KM giữ nguyên number_input vì thường số nhỏ, không cần dấu phẩy
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
                        
                        c4, c5, c6 = st.columns(3)
                        edit_hai_quan_str = c4.text_input(
                            "Phí hải quan", 
                            value=format_money(trip_info['phi_hai_quan']), 
                            key=f"hq_{chuyen_can_sua}"
                        )
                        
                        edit_boc_xep_str = c5.text_input(
                            "Phí bốc xếp", 
                            value=format_money(trip_info['phi_boc_xep']), 
                            key=f"bx_{chuyen_can_sua}"
                        )
                        
                        edit_khac_str = c6.text_input(
                            "Phí khác (Luật, cầu đường...)", 
                            value=format_money(trip_info['phi_khac']), 
                            key=f"khac_{chuyen_can_sua}"
                        )
                        
                        edit_ghi_chu = st.text_input(
                            "Ghi chú quyết toán (Lý do sửa)", 
                            value="" if pd.isna(trip_info['ghi_chu_quyet_toan']) else str(trip_info['ghi_chu_quyet_toan']),
                            key=f"gc_{chuyen_can_sua}"
                        )
                        
                        if st.form_submit_button("💾 Lưu Sửa Đổi Quyết Toán", type="primary"):
                            # ÉP KIỂU NGƯỢC LẠI THÀNH SỐ KHI LƯU DB
                            data_update = {
                                'cong_chuyen': parse_money(edit_cong_str),
                                'so_km_thuc_te': edit_km, # km đã là dạng số sẵn
                                'tien_them': parse_money(edit_tien_them_str),
                                'phi_hai_quan': parse_money(edit_hai_quan_str),
                                'phi_boc_xep': parse_money(edit_boc_xep_str),
                                'phi_khac': parse_money(edit_khac_str),
                                'ghi_chu_quyet_toan': edit_ghi_chu
                            }
                            
                            is_ok, msg = update_trip_transaction(db.pool, data_chuyen_di=data_update, trang_thai_enum='Hoan_Thanh', chuyen_di_id=chuyen_can_sua)
                            
                            if is_ok:
                                st.success(f"✅ Đã cập nhật thành công quyết toán cho chuyến {chuyen_can_sua}!")
                                
                                st.session_state["reset_sqt"] += 1
                                
                                import time
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

    st.markdown("#### ⚙️ Trung tâm Điều phối Đội xe tự động & Tiện ích Excel")
    st.divider()
    
    # ---------------------------------------------------------
    # TÍNH NĂNG 1: TẢI FILE MẪU EXCEL (Đã thêm dòng dữ liệu mẫu)
    # ---------------------------------------------------------
    st.markdown("##### 📥 1. Tải File Mẫu (Templates) chuẩn của hệ thống")
    col_t1, col_t2 = st.columns(2)
    with col_t1:
        # TẠO FILE MẪU CÓ SẴN 1 DÒNG ĐỂ ÉP NGƯỜI DÙNG NHẬP ĐÚNG FORMAT DD/MM/YYYY
        df_tpl_order = pd.DataFrame([
            {
                "NGAY_CHAY": "dd/mm/yyyy, format ô:text",  # Dòng ví dụ để người dùng bắt chước
                "TEN_KHACH_HANG": "Công ty TNHH ABC (Dòng Mẫu - Hãy Xóa)",
                "KHO_DI": "Bình Dương",
                "KHO_DEN": "Cảng Cát Lái",
                "KHOI_LUONG_KG": 1500,
                "THE_TICH_CBM": 5.5,
                "TIEN_CONG_TAI_XE":0
                
            }
        ])
        buffer_order = io.BytesIO()
        with pd.ExcelWriter(buffer_order, engine='xlsxwriter') as writer:
            df_tpl_order.to_excel(writer, index=False)
        st.download_button("⬇️ Tải mẫu Tạo chuyến Tự động", data=buffer_order.getvalue(), file_name="Mau_Tao_Chuyen_Co_CBM.xlsx")
        
    with col_t2:
        df_tpl_close = pd.DataFrame(columns=["MA_CHUYEN", "KM_THUC_TE", "LIT_DAU", "THUONG_THEM", "PHI_HAI_QUAN", "PHI_BOC_XEP", "PHI_KHAC", "GHI_CHU"])
        buffer_close = io.BytesIO()
        with pd.ExcelWriter(buffer_close, engine='xlsxwriter') as writer:
            df_tpl_close.to_excel(writer, index=False)
        st.download_button("⬇️ Tải mẫu Quyết toán Hàng loạt", data=buffer_close.getvalue(), file_name="Mau_Quyet_Toan.xlsx")
    
    st.divider()

    # ---------------------------------------------------------
    # TÍNH NĂNG 2: ĐIỀU XE TỰ ĐỘNG
    # ---------------------------------------------------------
    st.markdown("##### 🚀 2. Nạp file Excel đơn hàng chạy tự động")
    
    with st.form("form_auto_dispatch"):
        file_order = st.file_uploader("Chọn file Excel Tạo chuyến (Đuôi .xlsx)", type=["xlsx", "xls"])
        submit_order = st.form_submit_button("🚀 Thực thi Thuật toán Tự động", type="primary")
        
        if submit_order:
            if not file_order:
                st.warning("⚠️ Bạn chưa tải file Excel lên!")
            else:
                try:
                    df_orders = pd.read_excel(file_order)
                    df_orders.columns = [str(c).strip().upper() for c in df_orders.columns] 
                    
                    # Lấy thêm thông tin BIỂN SỐ XE và TÊN TÀI XẾ để xuất file báo cáo
                    sql_xe_ranh = """
                        SELECT x.id, x.bien_so_xe, x.tai_xe_co_dinh_id, x.tai_trong_thiet_ke, x.dung_tich_cbm, nv.ho_ten as ten_tai_xe
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
                        danh_sach_xuat_excel = [] # Mảng lưu dữ liệu để xuất file cho Quản lý
                        
                        for xe in xe_list:
                            xe['is_used'] = False 
                        
                        for idx, row in df_orders.iterrows():
                            # FIX LỖI ĐẢO NGÀY THÁNG: Ép Pandas phải hiểu Ngày trước, Tháng sau (dayfirst=True)
                            raw_date = row.get('NGAY_CHAY')
                            try:
                                # 1. Nếu Excel đã tự động format ô đó thành kiểu Date (Timestamp)
                                if isinstance(raw_date, (pd.Timestamp, datetime.datetime, datetime.date)):
                                    ngay_chay_dt = pd.to_datetime(raw_date)
                                else:
                                    # 2. Nếu là dạng chuỗi, cắt bỏ giờ phút (nếu có) để lấy ngày
                                    date_str = str(raw_date).strip().split(' ')[0]
                                    
                                    try:
                                        # ƯU TIÊN 1: Ép cứng Python phải đọc theo chuẩn Việt Nam (Ngày/Tháng/Năm)
                                        ngay_chay_dt = pd.to_datetime(date_str, format='%d/%m/%Y')
                                    except ValueError:
                                        # DỰ PHÒNG: Nếu Excel đã lỡ biến thành YYYY-MM-DD, đọc theo chuẩn tự do
                                        ngay_chay_dt = pd.to_datetime(date_str)
                                
                                # Lưu xuống Database bắt buộc YYYY-MM-DD
                                ngay_chay_str = ngay_chay_dt.strftime('%Y-%m-%d') 
                                # Hiển thị ra báo cáo xuất Excel bắt buộc DD/MM/YYYY
                                ngay_chay_hien_thi = ngay_chay_dt.strftime('%d/%m/%Y') 
                                
                            except Exception:
                                st.error(f"❌ Dòng số {idx + 2}: Sai ngày tháng (Dữ liệu gốc: '{raw_date}'). Vui lòng sửa lại cột NGAY_CHAY thành dạng DD/MM/YYYY.")
                                continue # Bỏ qua dòng lỗi, chạy tiếp các dòng khác

                            req_kg = float(row.get('KHOI_LUONG_KG', 0) or 0)
                            req_cbm = float(row.get('THE_TICH_CBM', 0) or 0)
                            khach_hang = str(row.get('TEN_KHACH_HANG', 'Khách Lẻ')).strip()
                            kho_di = str(row.get('KHO_DI', '')).strip()
                            kho_den = str(row.get('KHO_DEN', '')).strip()
                            cong_tai_xe = float(row.get('TIEN_CONG_TAI_XE', 0) or 0)
                            #ghi_chu = int(row.get('GHI_CHU', '')).strip()


                            xe_phu_hop = None
                            
                            for xe in xe_list:
                                if xe['is_used'] or pd.isna(xe['tai_xe_co_dinh_id']): continue 
                                
                                cap_kg = float(xe['tai_trong_thiet_ke'] or 0) * 1000 
                                cap_cbm = float(xe['dung_tich_cbm'] or 0)
                                
                                if cap_kg >= req_kg and cap_cbm >= req_cbm:
                                    xe_phu_hop = xe
                                    xe['is_used'] = True 
                                    break
                            
                            if xe_phu_hop:
                                # Lưu vào Database
                                trip_data = (
                                    ngay_chay_str, khach_hang, xe_phu_hop['id'], 
                                    f"{kho_di} ➡️ {kho_den}", 0, req_kg, req_cbm, cong_tai_xe, 'Tao_Moi'
                                )
                               
                                
                                is_ok, result_msg = save_trip_full_process(db.pool, trip_data, int(xe_phu_hop['tai_xe_co_dinh_id']))
                                if is_ok:
                                    success_count += 1
                                    # LƯU VÀO MẢNG ĐỂ TÍNH NỮA XUẤT EXCEL
                                    danh_sach_xuat_excel.append({
                                        "Mã Hệ Thống": result_msg,
                                        "Ngày Chạy": ngay_chay_hien_thi,
                                        "Khách Hàng": khach_hang,
                                        "Lộ Trình": f"{kho_di} ➡️ {kho_den}",
                                        "Biển Số Xe": xe_phu_hop['bien_so_xe'],
                                        "Tên Tài Xế": xe_phu_hop['ten_tai_xe'],
                                        "Công tài xế": cong_tai_xe,
                                        "Khối Lượng (KG)": req_kg,
                                        "Thể Tích (CBM)": req_cbm
                                        #"Ghi Chú": ""
                                    })
                                else:
                                    st.error(f"❌ Lỗi lưu đơn '{khach_hang}': {result_msg}")
                            else:
                                st.warning(f"⚠️ Đơn '{khach_hang}' ({req_kg}kg, {req_cbm} CBM) không có xe nào phù hợp hoặc hết xe!")
                                
                        if success_count > 0:
                            st.success(f"🎉 Đã điều phối thành công {success_count} chuyến đi!")
                            st.balloons()
                            time.sleep(1)
                            # Lưu mảng thành DataFrame vào bộ nhớ tạm để hiển thị nút Tải xuống ở bên dưới
                            st.session_state["export_dieu_xe"] = pd.DataFrame(danh_sach_xuat_excel)
                            st.rerun()
                            
                except Exception as e:
                    st.error(f"❌ Lỗi xử lý file Excel: {str(e)}")

    # ---------------------------------------------------------
    # KẾT QUẢ ĐIỀU XE: XUẤT FILE IN & GỌI TÀI XẾ
    # ---------------------------------------------------------
    if st.session_state.get("export_dieu_xe") is not None and not st.session_state["export_dieu_xe"].empty:
        st.markdown("### 🖨️ Danh sách chuyến đi vừa điều phối thành công")
        st.dataframe(st.session_state["export_dieu_xe"], use_container_width=True)
        
        # Nút xuất file Excel
        buffer_export = io.BytesIO()
        with pd.ExcelWriter(buffer_export, engine='xlsxwriter') as writer:
            st.session_state["export_dieu_xe"].to_excel(writer, index=False, sheet_name="Lịch Chạy")
        
        st.download_button(
            label="⬇️ TẢI FILE EXCEL ĐỂ IN & GIAO VIỆC TÀI XẾ", 
            data=buffer_export.getvalue(), 
            file_name=f"Lenh_Dieu_Xe_{datetime.date.today().strftime('%d_%m_%Y')}.xlsx", 
            type="primary"
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
                try:
                    df_close = pd.read_excel(file_close)
                    df_close.columns = [str(c).strip().upper() for c in df_close.columns]
                    
                    closed_count = 0
                    update_count = 0
                    error_list = []
                    
                    # --- HÀM LÀM SẠCH VÀ ÉP KIỂU SỐ TỪ EXCEL (CÓ BẪY LỖI) ---
                    def parse_excel_money(val):
                        if pd.isna(val) or val == "" or val is None:
                            return 0.0
                        try:
                            # Nếu Excel đã hiểu là dạng Số (int, float) thì ép kiểu luôn
                            if isinstance(val, (int, float)):
                                return float(val)
                            
                            # Nếu Excel hiểu là Chữ (Text) có chứa dấu phẩy (VD: "1,500,000")
                            clean_str = str(val).replace(",", "").replace(" ", "").strip()
                            return float(clean_str)
                        except ValueError:
                            # Bẫy lỗi: Nếu nhập bậy bạ chữ cái "abc" thì trả về 0.0
                            return 0.0

                    # LẶP QUA TỪNG DÒNG TRONG EXCEL
                    for index, r in df_close.iterrows():
                        if pd.isna(r.get('MA_CHUYEN')): 
                            continue 
                        
                        cid = int(r['MA_CHUYEN'])
                        
                        # Sử dụng hàm làm sạch dữ liệu vào Dictionary
                        data_dict_excel = {
                            'so_km_thuc_te': parse_excel_money(r.get('KM_THUC_TE')),
                            'so_lit_xang': parse_excel_money(r.get('LIT_DAU')),
                            'tien_them': parse_excel_money(r.get('THUONG_THEM')),
                            'phi_hai_quan': parse_excel_money(r.get('PHI_HAI_QUAN')),
                            'phi_boc_xep': parse_excel_money(r.get('PHI_BOC_XEP')),
                            'phi_khac': parse_excel_money(r.get('PHI_KHAC')),
                            'ghi_chu_quyet_toan': str(r.get('GHI_CHU', '')).strip() if pd.notna(r.get('GHI_CHU')) else ""
                        }
            
                        # Gọi hàm Giao dịch Database (Hàm dùng chung)
                        success, msg = settle_trip_transaction(db.pool, data_dict_excel, 'Hoan_Thanh', cid)
                        
                        if success:
                            closed_count += 1
                        else:
                            error_list.append(f"Chuyến {cid}: {msg}")
                            
                    # TỔNG KẾT BÁO CÁO SAU KHI CHẠY XONG
                    if closed_count > 0:
                        st.success(f"🎉 Đã xử lý khoá sổ thành công {closed_count} chuyến đi!")
                        
                    if error_list:
                        with st.expander("⚠️ Chi tiết các đơn bị lỗi (Nhấn để xem)"):
                            for err in error_list:
                                st.warning(err)
                                
                    if closed_count > 0:
                        import time
                        time.sleep(2)
                        st.rerun()

                except Exception as e:
                    st.error(f"❌ Lỗi hệ thống khi đọc file Excel: {str(e)}")
        
      


# ==========================================
# TAB 5: BẢN ĐỒ GIÁM SÁT HÀNH TRÌNH
# ==========================================
#with tab5:
#    st.markdown("### 📍 Trung tâm Giám sát Hành trình GPS Trực tiếp")
#    st.info("💡 Lần đầu tiên truy cập, bạn cần đăng nhập bằng tài khoản GPS của công ty. Hệ thống sẽ tự động lưu phiên đăng nhập cho các lần sau.")
    
    # Lệnh nhúng trang web với chiều cao 800px để hiển thị bản đồ rộng rãi
#    components.iframe("https://gps.hanhtrinhxe.vn", height=800, scrolling=True)