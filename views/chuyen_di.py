import streamlit as st
import pandas as pd
import datetime
import io,os,requests
import time
from map_service import MapService
from trip_manager import save_trip_full_process, tao_khach_hang_nhanh,settle_trip_transaction,delete_trip_safe,update_trip_transaction,update_trip_full_process,group_trips_transaction
from utils_core import parse_money_input, tao_tieu_de_kem_nut_refresh
from dotenv import load_dotenv
load_dotenv()

@st.cache_resource
def get_map_service(): return MapService()

map_srv = get_map_service()
db = st.session_state['db']

hide_enter_submit_css = """
<style>
    div[data-testid="InputInstructions"] { display: none !important; visibility: hidden !important; }
</style>
"""
st.markdown(hide_enter_submit_css, unsafe_allow_html=True)

STATUS_MAP = {
    "Tạo Mới": "Tao_Moi",
    "Đang Đi": "Dang_Di",
    "Quyết Toán": "Quyet_Toan",
    "Hoàn Thành": "Hoan_Thanh",
    "Hủy Chuyến": "Huy_Chuyen"
}

st.markdown("<h3 style='text-align: center; color: #0b5394;'>📝 PHÂN HỆ QUẢN LÝ VÀ ĐIỀU PHỐI CHUYẾN ĐI NÂNG CAO</h3>", unsafe_allow_html=True)
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

tab1, tab2, tab3, tab4, tab5,tab6 = st.tabs([
    "📋 Danh sách chuyến", 
    "➕ Tạo/Sửa chuyến thủ công",
    "➕ Tạo chuyến theo file",
    "📊 Chuyến đi trong ngày",
    "📊 Chuyến theo ngày chọn",
    "⚠️ Cảnh báo Xe tồn đọng / Quá hạn"
])

# Lấy dữ liệu danh mục
sql_xe_trong = "SELECT id, bien_so_xe,loai_xe, tai_trong_thiet_ke, tai_xe_co_dinh_id FROM xe WHERE trang_thai = 'Dang_Hoat_Dong'"
df_xe_full = db.execute_query(sql_xe_trong)
xe_map = {int(r['id']): r for _, r in df_xe_full.iterrows()} if isinstance(df_xe_full, pd.DataFrame) and not df_xe_full.empty else {}

df_tx_full = db.execute_query("SELECT id, ho_ten FROM nhan_vien WHERE loai_nhan_vien IN ('Tai_Chinh', 'Tai_Phu') AND trang_thai='Dang_Lam_Viec'")
tx_opts = {int(r['id']): str(r['ho_ten']) for _, r in df_tx_full.iterrows()} if isinstance(df_tx_full, pd.DataFrame) and not df_tx_full.empty else {}

df_kh_full = db.execute_query("SELECT id, ma_khach_hang, ten_khach_hang, ma_so_thue FROM khach_hang")
kh_opts = {"NEW": "➕ [Tạo mới] Đăng ký khách hàng ngay tại đây..."} 
if isinstance(df_kh_full, pd.DataFrame) and not df_kh_full.empty:
    for _, r in df_kh_full.iterrows():
        mst = r['ma_so_thue'] if pd.notna(r['ma_so_thue']) and r['ma_so_thue'] != "" else (r['ma_khach_hang'] if pd.notna(r['ma_khach_hang']) else "KHÔNG CÓ MST")
        kh_opts[int(r['id'])] = f"MST: {mst} — {r['ten_khach_hang']}"

# ==========================================
# TAB 1: DANH SÁCH CHUYẾN ĐI & NGHIỆP VỤ GHÉP CHUYẾN
# ==========================================
with tab1:
    tao_tieu_de_kem_nut_refresh("📋 Danh sách chuyến đi trong ngày", "ref_tab1")
    @st.fragment
    def vung_thao_tac_hien_thi_chuyen_di():
        # ---------------------------------------------------------
        # GIAO DIỆN ĐIỀU VẬN: GHÉP CHUYẾN / CHUYẾN TIẾP NỐI
        # ---------------------------------------------------------
        with st.expander("🔗 NGHIỆP VỤ GHÉP CHUYẾN / CHUYẾN TIẾP NỐI (Dành cho Điều Phối)", expanded=True):
            st.markdown("💡 **Hướng dẫn:** Bôi đen (chọn) các chuyến đi của **cùng một xe** theo đúng thứ tự lấy hàng. Hệ thống sẽ gom nhóm lại thành 1 Manifest và tự động áp dụng giá tiếp nối/tiện chuyến khi kế toán quyết toán.")
            
            # Truy vấn các chuyến chưa hoàn thành, chưa gộp, và là xe nội bộ
            # Đã xóa ký tự "cd." bị dư thừa ở dòng SELECT
            sql_ghep = """
                SELECT cd.id, cd.ngay_chuyen_di, cd.dia_diem_giao_nhan,
                COALESCE(kh.ten_khach_hang, cd.ten_khach_hang) as ten_khach,
                x.bien_so_xe, cd.xe_id
                FROM chuyen_di cd
                JOIN xe x ON cd.xe_id = x.id
                LEFT JOIN khach_hang kh ON cd.khach_hang_id = kh.id
                WHERE cd.trang_thai_chuyen IN ('Tao_Moi', 'Dang_Di') 
                AND cd.is_gop_chuyen = 0 
                AND cd.is_thue_ngoai = 0
                ORDER BY cd.xe_id, cd.id ASC
            """
            df_ghep = db.execute_query(sql_ghep)
            
            if isinstance(df_ghep, pd.DataFrame) and not df_ghep.empty:
                ghep_opts = {}
                for _, r in df_ghep.iterrows():
                    ghep_opts[r['id']] = f"🚛 Xe: {r['bien_so_xe']} | Mã chuyến: {r['id']} | Khách: {r['ten_khach']} | Lộ trình: {r['dia_diem_giao_nhan']}"
                
                chuyen_duoc_chon = st.multiselect(
                    "📌 Click để chọn các chuyến đi cần ghép:",
                    options=list(ghep_opts.keys()),
                    format_func=lambda x: ghep_opts[x],
                    placeholder="Chọn ít nhất 2 chuyến..."
                )
                
                if st.button("🔗 XÁC NHẬN GHÉP CHUYẾN", type="primary"):
                    if len(chuyen_duoc_chon) < 2:
                        st.warning("⚠️ Vui lòng chọn ít nhất 2 chuyến đi để thực hiện nghiệp vụ này.")
                    else:
                        # Ràng buộc Frontend: Kiểm tra các chuyến chọn có cùng xe_id không
                        xe_ids = df_ghep[df_ghep['id'].isin(chuyen_duoc_chon)]['xe_id'].unique()
                        if len(xe_ids) > 1:
                            st.error("❌ Lỗi Điều Phối: Các chuyến đi được chọn KHÔNG thuộc cùng một xe. Vui lòng kiểm tra lại!")
                        else:
                            with st.spinner("Hệ thống đang thiết lập Mã Chuyến Ghép (Manifest)..."):
                                # Gọi hàm Backend (Tuân thủ Transaction & Audit Log)
                                success, msg = group_trips_transaction(db.pool, chuyen_duoc_chon, st.session_state.username)
                                if success:
                                    st.success(msg)
                                    time.sleep(1.5)
                                    st.rerun()
                                else:
                                    st.error(f"Lỗi: {msg}")
            else:
                st.info("📭 Hiện tại không có chuyến đi nội bộ nào (Trạng thái Mới/Đang đi) khả dụng để ghép.")
        
        st.divider()

        # ---------------------------------------------------------
        # HIỂN THỊ LƯỚI DỮ LIỆU CHUYẾN ĐI (BỔ SUNG HIỂN THỊ MÃ GHÉP)
        # ---------------------------------------------------------
        try:
            ngay_hom_nay = datetime.date.today().strftime('%Y-%m-%d')
            # Cập nhật SQL: Thêm hiển thị ma_chuyen_ghep và stt_chuyen_ghep để trực quan hóa
            sql_list = """
                SELECT 
                    cd.ma_chuyen_ghep AS 'Mã Nhóm',
                    cd.stt_chuyen_ghep AS 'STT',
                    cd.id AS 'Mã chuyến đi', 
                    cd.ngay_chuyen_di AS 'Ngày', 
                    COALESCE(kh.ten_khach_hang, cd.ten_khach_hang) AS 'Khách hàng',
                    COALESCE(x.bien_so_xe, cd.bien_so_xe_ngoai) AS 'Biển Số', 
                    cd.khoi_luong_kg AS 'Trọng tải (kg)',
                    cd.dia_diem_giao_nhan AS 'Lộ trình', 
                    cd.trang_thai_chuyen AS 'Trạng thái'
                FROM chuyen_di cd 
                LEFT JOIN khach_hang kh ON cd.khach_hang_id = kh.id
                LEFT JOIN xe x ON cd.xe_id = x.id
                WHERE cd.ngay_chuyen_di = %s
                ORDER BY cd.ma_chuyen_ghep DESC, cd.stt_chuyen_ghep ASC, cd.id DESC
            """
            df_chuyen = db.execute_query(sql_list, (ngay_hom_nay,))
            if isinstance(df_chuyen, pd.DataFrame) and not df_chuyen.empty:
                st.dataframe(df_chuyen, use_container_width=True, hide_index=True)
            else:
                st.info("Chưa có dữ liệu chuyến đi nào trong ngày.")
        except Exception as e:
            st.error(f"Lỗi truy xuất danh sách: {e}")

    vung_thao_tac_hien_thi_chuyen_di()

# ==========================================
# TAB 2: ĐĂNG KÝ, SỬA & XÓA CHUYẾN ĐI THỦ CÔNG
# ==========================================
# ==========================================
# TAB 2: ĐĂNG KÝ, SỬA & XÓA CHUYẾN ĐI THỦ CÔNG
# ==========================================
with tab2:
    tao_tieu_de_kem_nut_refresh("📋 Đăng ký & Quản lý chuyến đi thủ công", "ref_tab2")
    
    @st.fragment
    def vung_thao_tac_chuyen_di():
        # 1. KHỞI TẠO BIẾN STATE (ĐẢM BẢO RESET TRẮNG FORM)
        if "api_km" not in st.session_state: st.session_state["api_km"] = 0.0
        if "form_reset_counter" not in st.session_state: st.session_state["form_reset_counter"] = 0

        # --- CHỌN CHẾ ĐỘ THAO TÁC & LOẠI HÌNH NGHIỆP VỤ ---
        col_mode1, col_mode2 = st.columns(2)
        mode_action = col_mode1.radio(
            "📌 Chọn hành động:", 
            ["➕ Tạo chuyến mới", "✏️ Sửa chuyến hiện tại", "🗑️ Xóa chuyến đi"], 
            horizontal=True, 
            key=f"tab2_mode_action_{st.session_state['form_reset_counter']}"
        )
        
        kieu_nghiep_vu = col_mode2.radio(
            "🚛 Phân loại nghiệp vụ:", 
            ["Nghiệp vụ Xe Tải", "Nghiệp vụ Container"], 
            horizontal=True, 
            key=f"tab2_kieu_nghiep_vu_{st.session_state['form_reset_counter']}"
        )
        
        trip_suffix = f"new_{st.session_state['form_reset_counter']}"

        # ================= CHẾ ĐỘ: XÓA CHUYẾN ĐI =================
        if mode_action == "🗑️ Xóa chuyến đi":
            st.markdown("#### 🗑️ Xóa chuyến đi an toàn")
            sql_delete_list = """
                SELECT id, ngay_chuyen_di, COALESCE(ten_khach_hang, 'Khách Lẻ') as ten_khach_hang, trang_thai_chuyen
                FROM chuyen_di 
                WHERE trang_thai_chuyen IN ('Tao_Moi', 'Dang_Di') 
                ORDER BY id DESC
            """
            df_trips_del = db.execute_query(sql_delete_list)
            if isinstance(df_trips_del, pd.DataFrame) and not df_trips_del.empty:
                trip_del_options = {r['id']: f"Mã chuyến {r['id']} | Ngày: {r['ngay_chuyen_di']} | Khách: {r['ten_khach_hang']} | Trạng thái: {r['trang_thai_chuyen']}" for _, r in df_trips_del.iterrows()}
                
                delete_trip_id = st.selectbox(
                    "🔍 Chọn chuyến đi cần xóa", 
                    options=list(trip_del_options.keys()), 
                    format_func=lambda x: trip_del_options[x], 
                    key=f"selectbox_delete_trip_{st.session_state['form_reset_counter']}"
                )
                
                if delete_trip_id:
                    st.warning(f"⚠️ Bạn có chắc chắn muốn xóa vĩnh viễn chuyến đi mã **{delete_trip_id}**?")
                    if st.button("🗑️ Xác Nhận Xóa Chuyến Đi", type="primary"):
                        with st.spinner("Đang xóa chuyến đi..."):
                            res_del = delete_trip_safe(db.pool, delete_trip_id)
                            if isinstance(res_del, tuple): success, result = res_del
                            else: success, result = (True, res_del) if res_del else (False, "Lỗi xóa cơ sở dữ liệu")
                                
                        if success:
                            st.success(f"✅ Đã xóa thành công chuyến đi mã {delete_trip_id}!")
                            st.session_state["form_reset_counter"] += 1
                            time.sleep(1.2)
                            st.rerun()
                        else: st.error(f"❌ Lỗi khi xóa chuyến đi: {result}")
            else: st.warning("⚠️ Hiện tại không có chuyến đi nào ở trạng thái có thể xóa.")

        # ================= CHẾ ĐỘ: TẠO MỚI HOẶC SỬA CHUYẾN ĐI =================
        else:
            edit_trip_id = None
            trip_data = {}
            
            so_cont_val, so_seal_val, loai_cont_val, chieu_cont_val = "", "", "40HC", "Nhập"
            ghi_chu_thucong_val = ""
            
            if mode_action == "✏️ Sửa chuyến hiện tại":
                sql_edit_list = """
                    SELECT id, ngay_chuyen_di, COALESCE(ten_khach_hang, 'Khách Lẻ') as ten_khach_hang
                    FROM chuyen_di 
                    WHERE trang_thai_chuyen IN ('Tao_Moi', 'Dang_Di') 
                    ORDER BY id DESC
                """
                df_trips = db.execute_query(sql_edit_list)
                if isinstance(df_trips, pd.DataFrame) and not df_trips.empty:
                    trip_options = {r['id']: f"Mã chuyến {r['id']} | Ngày: {r['ngay_chuyen_di']} | Khách: {r['ten_khach_hang']}" for _, r in df_trips.iterrows()}
                    
                    edit_trip_id = st.selectbox(
                        "🔍 Chọn chuyến đi cần sửa", 
                        options=list(trip_options.keys()), 
                        format_func=lambda x: trip_options[x], 
                        key=f"selectbox_edit_trip_{st.session_state['form_reset_counter']}"
                    )
                    
                    if edit_trip_id:
                        trip_suffix = f"edit_{edit_trip_id}_{st.session_state['form_reset_counter']}"
                        df_detail = db.execute_query("SELECT * FROM chuyen_di WHERE id=%s", (edit_trip_id,))
                        if isinstance(df_detail, pd.DataFrame) and not df_detail.empty:
                            trip_data = df_detail.iloc[0].to_dict()
                            
                            df_tx_assigned = db.execute_query("SELECT tai_xe_id FROM chuyen_di_tai_xe WHERE chuyen_di_id=%s AND loai_tai_xe='Tai_Chinh'", (edit_trip_id,))
                            if isinstance(df_tx_assigned, pd.DataFrame) and not df_tx_assigned.empty:
                                trip_data['tai_xe_id_assigned'] = df_tx_assigned.iloc[0]['tai_xe_id']
                                
                            db_ghi_chu = trip_data.get('ghi_chu', '') or ''
                            ghi_chu_thucong_val = db_ghi_chu
                            
                            if kieu_nghiep_vu == "Nghiệp vụ Container":
                                import re
                                match = re.search(r'\[CONT:(.*?)\| SEAL:(.*?)\| LOAI:(.*?)\| CHIEU:(.*?)\]', db_ghi_chu)
                                if match:
                                    so_cont_val = match.group(1).strip()
                                    so_seal_val = match.group(2).strip()
                                    loai_cont_val = match.group(3).strip()
                                    chieu_cont_val = match.group(4).strip()
                                    ghi_chu_thucong_val = db_ghi_chu.replace(match.group(0), "").strip()
                else: st.warning("⚠️ Hiện tại không có chuyến đi nào đang ở trạng thái Tạo Mới / Đang Đi để chỉnh sửa.")

            def get_idx(lst, val, default=0): return lst.index(val) if val in lst else default

            st.divider()

            # ====================================================================
            # PHẦN 1: THÔNG TIN KHÁCH HÀNG
            # ====================================================================
            df_kh_full = db.execute_query("SELECT id, ma_khach_hang, ten_khach_hang, so_dien_thoai, dia_chi, ma_so_thue FROM khach_hang")
            kh_opts = {None: "-- Vui lòng chọn Khách hàng --", "NEW": "➕ [Tạo mới] Đăng ký khách hàng ngay tại đây..."}
            kh_diachi_map = {}
            
            if isinstance(df_kh_full, pd.DataFrame) and not df_kh_full.empty:
                for _, r in df_kh_full.iterrows():
                    k_id = int(r['id'])
                    ma_kh = r['ma_khach_hang'] if pd.notna(r['ma_khach_hang']) and r['ma_khach_hang'] != "" else "CHƯA CÓ MÃ"
                    kh_opts[k_id] = f"Mã: {ma_kh} — {r['ten_khach_hang']}"
                    kh_diachi_map[k_id] = str(r['dia_chi']) if pd.notna(r.get('dia_chi')) else ""

            st.markdown("#### 1. Thông tin Khách hàng dịch vụ")
            kh_opts_keys = list(kh_opts.keys())
            default_kh_idx = get_idx(kh_opts_keys, trip_data.get('khach_hang_id'), 0) if mode_action == "✏️ Sửa chuyến hiện tại" else 0
            diachi_input_key = f"tab2_dia_chi_kh_input_{trip_suffix}"
            
            def on_khach_hang_change():
                selected_kh = st.session_state.get(f"tab2_c_kh_sel_{trip_suffix}")
                if selected_kh and selected_kh != "NEW" and selected_kh != 0:
                    st.session_state[diachi_input_key] = kh_diachi_map.get(selected_kh, "")
                else:
                    st.session_state[diachi_input_key] = ""

            c_kh_sel = st.selectbox(
                "🏢 Chọn Khách hàng (Tìm theo MST hoặc Tên)*", 
                options=kh_opts_keys, 
                index=default_kh_idx, 
                format_func=lambda x: kh_opts[x], 
                key=f"tab2_c_kh_sel_{trip_suffix}",
                on_change=on_khach_hang_change
            )
            
            if mode_action == "✏️ Sửa chuyến hiện tại" and diachi_input_key not in st.session_state:
                st.session_state[diachi_input_key] = trip_data.get('dia_chi_khach_hang', '')

            new_ten_kh, new_sdt_kh, new_zalo_id, new_mst_kh, new_diachi_kh = "", "", "", "", ""
            if c_kh_sel == "NEW":
                st.info("💡 Điền Mã số thuế để tự động tạo Mã khách hàng.")
                nc1, nc2, nc3 = st.columns(3)
                new_mst_kh = nc1.text_input("Mã số thuế (MST)*", key=f"new_mst_kh_{trip_suffix}")
                new_ten_kh = nc2.text_input("Tên Khách Hàng / Công ty*", key=f"new_ten_kh_{trip_suffix}")
                new_sdt_kh = nc3.text_input("Số điện thoại liên hệ", key=f"new_sdt_kh_{trip_suffix}")
                nc4, nc5 = st.columns(2)
                new_diachi_kh = nc4.text_input("Địa chỉ trụ sở khách hàng", key=f"new_diachi_kh_{trip_suffix}")
                new_zalo_id = nc5.text_input("Zalo User ID (Nếu có)", key=f"new_zalo_id_{trip_suffix}")
                
            dia_chi_kh_input = st.text_input("📍 Địa chỉ cụ thể giao dịch / Địa điểm kho*", placeholder="VD: 123 Nguyễn Văn Linh...", key=diachi_input_key)

            # ====================================================================
            # PHẦN 2: THÔNG SỐ HÀNG HÓA & ĐIỀU PHỐI PHƯƠNG TIỆN
            # ====================================================================
            st.markdown(f"#### 2. Thông số Hàng hóa & Phương án điều xe ({kieu_nghiep_vu})")
            
            kg_key = f"input_kg_{trip_suffix}"
            cbm_key = f"input_cbm_{trip_suffix}"
            
            if kieu_nghiep_vu == "Nghiệp vụ Xe Tải":
                col_hl1, col_hl2 = st.columns(2)
                khoi_luong = col_hl1.number_input("📦 Khối lượng (KG)*", min_value=0.0, value=float(trip_data.get('khoi_luong_kg') or 0.0), step=1.0, key=kg_key)
                so_cbm = col_hl2.number_input("🧊 Thể tích (CBM)", min_value=0.0, value=float(trip_data.get('the_tich_cbm') or 0.0), step=0.1, key=cbm_key)
            else:
                c_c1, c_c2 = st.columns(2)
                so_cont_input = c_c1.text_input("🔢 Số Container", value=so_cont_val, key=f"so_cont_{trip_suffix}")
                so_seal_input = c_c2.text_input("🔒 Số Seal", value=so_seal_val, key=f"so_seal_{trip_suffix}")
                
                c_c3, c_c4, c_c5 = st.columns(3)
                loai_cont_opts = ["20DC", "40DC", "40HC", "45HC", "20RF (Lạnh)", "40RF (Lạnh)", "Khác"]
                loai_cont_input = c_c3.selectbox("🧊 Loại Cont", options=loai_cont_opts,  key=f"loai_cont_{trip_suffix}",index= None)
                
                chieu_opts = ["Nhập", "Xuất", "Nội Địa", "Chạy Rỗng"]
                chieu_cont_input = c_c4.selectbox("🔄 Chiều Hàng", options=chieu_opts, key=f"chieu_cont_{trip_suffix}", index= None)
                
                khoi_luong = c_c5.number_input("⚖️ Trọng lượng hàng (KG)*", min_value=0.0, value=float(trip_data.get('khoi_luong_kg') or 0.0), step=1.0, key=kg_key)
                so_cbm = 0.0 
            
            db_xe_id = trip_data.get('xe_id')
            is_ngoai_val = 0 if (pd.notna(db_xe_id) and db_xe_id is not None and int(db_xe_id) > 0) else 1
            if mode_action == "➕ Tạo chuyến mới": is_ngoai_val = 0
                
            loai_hinh_xe = st.radio(
                "Chọn hình thức điều xe:", 
                options=["🚀 Chạy Xe Công Ty", "🤝 Thuê Xe Ngoài"], 
                index=is_ngoai_val, 
                horizontal=True, 
                key=f"tab2_loai_hinh_xe_{trip_suffix}"
            )

            c_xe_sel, tx_id_assign = None, None
            
            if loai_hinh_xe == "🚀 Chạy Xe Công Ty":
                st.markdown("##### 🚛 Thông tin Xe & Tài xế Nội bộ")
                col_xe_1, col_xe_2 = st.columns([1, 1])
                
                with col_xe_1:
                    selectbox_xe_key = f"c_xe_sel_out_{trip_suffix}"
                    
                    if kieu_nghiep_vu == "Nghiệp vụ Xe Tải":
                        if st.button("🔍 Tìm xe tự động (Theo KG & CBM)", type="primary", use_container_width=True):
                            if khoi_luong <= 0:
                                st.warning("⚠️ Vui lòng nhập Khối lượng (KG) lớn hơn 0 để phần mềm tìm xe.")
                            else:
                                sql_xe_ranh = """
                                    SELECT x.id, x.tai_xe_co_dinh_id, x.tai_trong_thiet_ke, x.dung_tich_cbm, x.loai_xe,
                                           COALESCE(SUM(cd.khoi_luong_kg), 0) as da_cho_kg,
                                           COALESCE(SUM(cd.the_tich_cbm), 0) as da_cho_cbm
                                    FROM xe x 
                                    LEFT JOIN chuyen_di cd ON x.id = cd.xe_id AND cd.trang_thai_chuyen IN ('Tao_Moi', 'Dang_Di')
                                    WHERE x.trang_thai = 'Dang_Hoat_Dong' 
                                    AND (LOWER(x.loai_xe) LIKE '%tai%' OR LOWER(x.loai_xe) LIKE '%tải%')
                                    GROUP BY x.id, x.tai_xe_co_dinh_id, x.tai_trong_thiet_ke, x.dung_tich_cbm, x.loai_xe
                                    ORDER BY x.tai_trong_thiet_ke ASC, x.dung_tich_cbm ASC
                                """
                                df_xe_ranh = db.execute_query(sql_xe_ranh)
                                found_xe = None
                                if isinstance(df_xe_ranh, pd.DataFrame) and not df_xe_ranh.empty:
                                    for _, xe in df_xe_ranh.iterrows():
                                        if pd.isna(xe['tai_xe_co_dinh_id']): continue 
                                        
                                        cap_kg = float(xe['tai_trong_thiet_ke'] or 0) * 1000 - float(xe['da_cho_kg'])
                                        cap_cbm = float(xe['dung_tich_cbm'] or 0) - float(xe['da_cho_cbm'])
                                        
                                        if (cap_kg >= khoi_luong) and (so_cbm == 0 or cap_cbm >= so_cbm):
                                            found_xe = int(xe['id'])
                                            break
                                
                                if found_xe:
                                    st.session_state[selectbox_xe_key] = found_xe
                                    st.success("✅ Đã tìm thấy xe phù hợp (đủ tải trọng/thể tích) và tự động chọn!")
                                else:
                                    st.error("❌ Không có xe nào (kể cả ghép) đáp ứng đủ tải trọng / thể tích này!")
                    else:
                        st.info("💡 Hướng dẫn: Vui lòng chọn trực tiếp Đầu Kéo nội bộ từ danh sách bên dưới.")

                    is_ghep_chuyen = st.checkbox("🔗 Hiển thị cả xe đang chạy (Dành cho nghiệp vụ Ghép chuyến)", key=f"check_ghep_{trip_suffix}")
                    
                    sql_busy = "SELECT DISTINCT xe_id FROM chuyen_di WHERE trang_thai_chuyen IN ('Tao_Moi', 'Dang_Di') AND xe_id IS NOT NULL"
                    df_busy = db.execute_query(sql_busy)
                    busy_xe_ids = df_busy['xe_id'].tolist() if isinstance(df_busy, pd.DataFrame) and not df_busy.empty else []

                    xe_dict_opts = {None: "-- Vui lòng chọn Xe Nội Bộ --"}
                    for k, v in xe_map.items():
                        is_busy = int(k) in busy_xe_ids
                        
                        if not is_ghep_chuyen and is_busy and int(k) != trip_data.get('xe_id'):
                            continue
                        
                        loai_xe_db = str(v.get('loai_xe', '')).lower()
                        if kieu_nghiep_vu == "Nghiệp vụ Xe Tải":
                            if 'tải' not in loai_xe_db and 'tai' not in loai_xe_db:
                                continue
                        else:
                            if ('tải' in loai_xe_db or 'tai' in loai_xe_db or 
                                '4 chỗ' in loai_xe_db or '7 chỗ' in loai_xe_db or 
                                '4 cho' in loai_xe_db or '7 cho' in loai_xe_db or 
                                'du lịch' in loai_xe_db or 'du lich' in loai_xe_db):
                                continue        
                                
                        tx_id_raw = v.get('tai_xe_co_dinh_id')
                        ten_tx = "Chưa gán TX"
                        if pd.notna(tx_id_raw) and int(float(tx_id_raw)) in tx_opts:
                            ten_tx = tx_opts[int(float(tx_id_raw))]
                        
                        if is_busy:
                            xe_dict_opts[int(k)] = f"🔄 [ĐANG CHẠY] {v['bien_so_xe']} ({v.get('tai_trong_thiet_ke', 0)}T) | 🧑‍✈️ TX: {ten_tx}"
                        else:
                            xe_dict_opts[int(k)] = f"🚛 [TRỐNG] {v['bien_so_xe']} ({v.get('tai_trong_thiet_ke', 0)}T) | 🧑‍✈️ TX: {ten_tx}"
                        
                    xe_keys = list(xe_dict_opts.keys())
                    
                    default_xe_idx = 0
                    if mode_action == "✏️ Sửa chuyến hiện tại" and trip_data.get('xe_id') in xe_keys:
                        default_xe_idx = xe_keys.index(trip_data.get('xe_id'))
                    
                    title_selectbox = "✅ Chọn Xe Nội Bộ (Điều phối/Ghép chuyến)*" if is_ghep_chuyen else "✅ Chọn Xe Nội Bộ (Đang trống)*"
                    
                    c_xe_sel = st.selectbox(
                        title_selectbox, 
                        options=xe_keys, 
                        index=default_xe_idx, 
                        format_func=lambda x: xe_dict_opts[x],
                        key=selectbox_xe_key
                    )
                    
                    if c_xe_sel is not None:
                        selected_xe_info = xe_map.get(c_xe_sel, {})
                        tx_id_raw = selected_xe_info.get('tai_xe_co_dinh_id') 
                        
                        default_tx_id = None
                        if mode_action == "✏️ Sửa chuyến hiện tại" and edit_trip_id and 'tai_xe_id_assigned' in trip_data and c_xe_sel == trip_data.get('xe_id'):
                            default_tx_id = trip_data.get('tai_xe_id_assigned')
                        elif pd.notna(tx_id_raw) and int(float(tx_id_raw)) in tx_opts:
                            default_tx_id = int(float(tx_id_raw))
                        
                        tx_keys = [None] + list(tx_opts.keys())
                        tx_format = {None: "-- Chưa chọn tài xế --"}
                        tx_format.update(tx_opts)
                        
                        default_idx = tx_keys.index(default_tx_id) if default_tx_id in tx_keys else 0
                        
                        st.markdown("##### 🧑‍✈️ Phân công Tài xế (Cho phép đổi nếu tài xế gốc nghỉ phép)")
                        tx_id_assign = st.selectbox(
                            "Chọn Tài xế phụ trách thực tế*", 
                            options=tx_keys,
                            index=default_idx,
                            format_func=lambda x: tx_format[x],
                            key=f"chon_tai_xe_{trip_suffix}"
                        )
                        
                        if pd.notna(tx_id_raw) and int(float(tx_id_raw)) in tx_opts:
                            tx_goc_id = int(float(tx_id_raw))
                            if tx_id_assign and tx_id_assign != tx_goc_id:
                                st.warning(f"⚠️ Lưu ý: Bạn đang điều Tài xế thay thế. Tài xế gốc của xe này là **{tx_opts[tx_goc_id]}**.")
                        elif not tx_id_assign:
                            st.warning("⚠️ Vui lòng chọn tài xế để phát lệnh!")

                with col_xe_2:
                    st.markdown("**🔸 Các xe đang được điều động (Tham khảo)**")
                    sql_xe_ban = """
                        SELECT x.bien_so_xe as 'Biển Số',cd.khoi_luong_kg AS 'Trọng tải (kg)',ngay_chuyen_di as 'Ngày đi',
                        COALESCE(nv.ho_ten, 'Chưa gán') as 'Tài Xế', cd.dia_diem_giao_nhan as 'Lộ Trình'
                        , trang_thai_chuyen as 'Trạng thái chuyến' FROM chuyen_di cd
                        JOIN xe x ON cd.xe_id = x.id
                        LEFT JOIN chuyen_di_tai_xe ctx ON cd.id = ctx.chuyen_di_id AND ctx.loai_tai_xe = 'Tai_Chinh'
                        LEFT JOIN nhan_vien nv ON ctx.tai_xe_id = nv.id
                        WHERE cd.trang_thai_chuyen IN ('Tao_Moi', 'Dang_Di') AND cd.is_thue_ngoai = 0
                    """
                    df_xe_ban = db.execute_query(sql_xe_ban)
                    if isinstance(df_xe_ban, pd.DataFrame) and not df_xe_ban.empty:
                        st.dataframe(df_xe_ban, use_container_width=True, hide_index=True, height=265)
                    else:
                        st.info("Hiện không có xe nội bộ nào đang chạy.")

            st.divider()

            # ====================================================================
            # PHẦN 3: LỰA CHỌN LỘ TRÌNH VẬN CHUYỂN
            # ====================================================================
            st.markdown("#### 3. Chi tiết lộ trình vận chuyển")
            
            khach_id_filter = None
            if c_kh_sel and c_kh_sel != "NEW": khach_id_filter = int(c_kh_sel)
            elif mode_action == "✏️ Sửa chuyến hiện tại": khach_id_filter = trip_data.get('khach_hang_id')

            # --- CẢI TIẾN: BỔ SUNG LỌC THEO is_hang_tra_ve ---
            is_hang_ve_db = bool(trip_data.get('is_hang_tra_ve', 0)) if mode_action == "✏️ Sửa chuyến hiện tại" else False
            is_hang_ve_ui = st.checkbox("🔄 Lộ trình chở hàng về (Chỉ lọc các tuyến chiều về)", value=is_hang_ve_db, key=f"is_hang_ve_ui_{trip_suffix}")

            lo_trinh_opts = {None: "-- Vui lòng chọn lộ trình (Tạo mới nếu chưa có) --"}
            if khach_id_filter:
                flag_hang_ve = 1 if is_hang_ve_ui else 0
                # Truy vấn SQL kèm theo điều kiện is_hang_tra_ve để chống nhiễu dữ liệu
                sql_rates = "SELECT DISTINCT diem_di, diem_den FROM rate_cards WHERE khach_hang_id = %s AND is_hang_tra_ve = %s ORDER BY diem_di"
                df_rates = db.execute_query(sql_rates, (khach_id_filter, flag_hang_ve))
                if isinstance(df_rates, pd.DataFrame) and not df_rates.empty:
                    for _, r in df_rates.iterrows():
                        lt_key = f"{r['diem_di']} ➡️ {r['diem_den']}"
                        lo_trinh_opts[lt_key] = lt_key

            lo_trinh_db = str(trip_data.get('dia_diem_giao_nhan', ''))
            lo_trinh_keys = list(lo_trinh_opts.keys())
            
            default_lt_idx = 0
            if lo_trinh_db in lo_trinh_keys:
                default_lt_idx = lo_trinh_keys.index(lo_trinh_db)

            st.info("💡 Hệ thống chỉ cho phép chọn lộ trình đã được thiết lập sẵn. Nếu chưa có, vui lòng qua phân hệ Bảng Giá tạo mới.")

            chon_lo_trinh = st.selectbox(
                "🗺️ Chọn lộ trình (Tham chiếu từ Bảng Giá)*",
                options=lo_trinh_keys,
                index=default_lt_idx,
                format_func=lambda x: lo_trinh_opts[x],
                key=f"chon_lo_trinh_out_{trip_suffix}"
            )
            
            c_lt1, c_lt2 = st.columns(2)
            lo_trinh_hien_thi = chon_lo_trinh if chon_lo_trinh is not None else lo_trinh_db
            
            diem_di_val, diem_den_val = "", ""
            if lo_trinh_hien_thi and "➡️" in lo_trinh_hien_thi:
                parts = lo_trinh_hien_thi.split("➡️")
                diem_di_val = parts[0].strip()
                diem_den_val = parts[-1].strip()
                
            diem_dau = c_lt1.text_input("🏠 Địa chỉ bốc hàng*", value=diem_di_val, disabled=True)
            diem_cuoi = c_lt2.text_input("🎯 Địa chỉ giao hàng*", value=diem_den_val, disabled=True)
            
            st.divider()

            # ====================================================================
            # PHẦN 4: FORM XÁC NHẬN VÀ LƯU TRỮ
            # ====================================================================
            with st.form(key=f"trip_form_{st.session_state['form_reset_counter']}", clear_on_submit=True):
                
                ngoai_bien_so, ngoai_ten_doi_tac, ngoai_loai_dt = "", "", "Nha_Xe"
                ngoai_ten_tx, ngoai_cccd_tx, ngoai_sdt_tx = "", "", ""
                
                if loai_hinh_xe == "🤝 Thuê Xe Ngoài": 
                    st.markdown("##### 🤝 Chi tiết phương tiện & Tài xế thuê ngoài")
                    nx1, nx2, nx3 = st.columns(3)
                    ngoai_bien_so = nx1.text_input("Biển số xe thực tế*", value=trip_data.get('bien_so_xe_ngoai') or '')
                    ngoai_ten_doi_tac = nx2.text_input("Tên Nhà xe / Chủ xe*", value=trip_data.get('ten_doi_tac_ngoai') or '')
                    dt_opts = ["Nha_Xe", "Tu_Nhan"]
                    ngoai_loai_dt = nx3.selectbox("Loại đối tác", dt_opts, index=get_idx(dt_opts, trip_data.get('loai_doi_tac_ngoai', 'Nha_Xe')))
                    
                    nx_lh1, nx_ten = st.columns(2)
                    lh_opts = ["Container", "Xe_Tai", "Xe_May"]
                    
                    if kieu_nghiep_vu == "Nghiệp vụ Container":
                        def_lh_idx = lh_opts.index("Container")
                    else:
                        def_lh_idx = lh_opts.index(trip_data.get('loai_hinh_xe', 'Xe_Tai')) if trip_data.get('loai_hinh_xe') in lh_opts else 1
                    
                    ngoai_loai_hinh_xe = nx_lh1.selectbox(
                        "Phân loại phương tiện ngoài*", 
                        options=lh_opts, 
                        index=def_lh_idx,
                        format_func=lambda x: "📦 Xe Container" if x == "Container" else ("🚛 Xe Tải" if x == "Xe_Tai" else "🏍️ Xe Máy")
                    )
                    ngoai_ten_tx = nx_ten.text_input("Họ tên Tài xế ngoài*", value=trip_data.get('tai_xe_ngoai_ten') or '')
                    
                    nx4, nx5 = st.columns(2)
                    ngoai_cccd_tx = nx4.text_input("CCCD Tài xế ngoài*", value=trip_data.get('tai_xe_ngoai_cccd') or '')
                    ngoai_sdt_tx = nx5.text_input("SĐT Tài xế ngoài*", value=trip_data.get('tai_xe_ngoai_sdt') or '')
                    st.divider()

                st.markdown("#### 4. Ngày khởi hành & Chi tiết bổ sung")
                
                c3_col, c_stt_col = st.columns(2)
                db_date = trip_data.get('ngay_chuyen_di', datetime.date.today())
                if isinstance(db_date, pd.Timestamp): db_date = db_date.date()
                ngay_di = c3_col.date_input("🗓️ Ngày khởi hành", value=db_date, format="DD/MM/YYYY")
                
                st_val = {v: k for k, v in STATUS_MAP.items()}.get(trip_data.get('trang_thai_chuyen', 'Tao_Moi'), "Tạo Mới")
                trang_thai_ui_value = c_stt_col.selectbox("Trạng thái chuyến đi", options=list(STATUS_MAP.keys()), index=list(STATUS_MAP.keys()).index(st_val))
                
                ghi_chu_thucong = st.text_input("Ghi chú bổ sung", value=ghi_chu_thucong_val, key="ghi_chu_thucong_key")
                
                ngoai_chi_phi_str, ngoai_thanh_toan = "0", "Cong_No"
                if loai_hinh_xe != "🚀 Chạy Xe Công Ty":
                    nx7, nx8 = st.columns(2)
                    tien_thue = trip_data.get('chi_phi_thue_ngoai', 0)
                    tien_thue_clean = str(int(float(tien_thue))) if pd.notna(tien_thue) and float(tien_thue) > 0 else ""
                    
                    ngoai_chi_phi_str = nx7.text_input("Giá vốn thuê ngoài (VNĐ)*", value=tien_thue_clean)
                    tt_opts = ["Cong_No", "Tien_Mat"]
                    ngoai_thanh_toan = nx8.selectbox("Hình thức thanh toán ngoài", options=tt_opts, index=get_idx(tt_opts, trip_data.get('hinh_thuc_thanh_toan_ngoai', 'Cong_No')), format_func=lambda x: "Công nợ tháng" if x=="Cong_No" else "Tiền mặt")
                
                st.markdown("<br>", unsafe_allow_html=True)
                st.markdown("""
                    <style>
                        div[data-testid="stForm"] button[kind="primary"] {
                            background-color: #d32f2f !important;
                            color: white !important;
                            border: none !important;
                            font-weight: 800 !important;
                            font-size: 16px !important;
                            border-radius: 8px !important;
                            padding: 10px 0px !important;
                            box-shadow: 0 4px 6px rgba(211, 47, 47, 0.3) !important;
                            transition: all 0.3s ease !important;
                        }
                        div[data-testid="stForm"] button[kind="primary"]:hover {
                            background-color: #b71c1c !important;
                            transform: translateY(-2px);
                            box-shadow: 0 6px 8px rgba(183, 28, 28, 0.4) !important;
                        }
                    </style>
                """, unsafe_allow_html=True)
                
                col_btn_left, col_btn_center, col_btn_right = st.columns([1, 2, 1])
                btn_label = "🔄 LƯU THAY ĐỔI " if mode_action == "✏️ Sửa chuyến hiện tại" else "📲 LƯU VÀ GỬI THÔNG TIN TÀI XẾ"
                
                with col_btn_center:
                    submit_send = st.form_submit_button(btn_label, type="primary", use_container_width=True)
            
            # ----------------------------------------------------
            # XỬ LÝ SUBMIT CHÍNH THỨC
            # ----------------------------------------------------
            if submit_send:    
                if chon_lo_trinh is None and mode_action == "➕ Tạo chuyến mới":
                    st.error("❌ HỆ THỐNG CHẶN: Vui lòng chọn lộ trình hợp lệ từ danh sách! Nếu chưa có, hãy tạo mới trong Bảng Giá trước.")
                    st.stop()
                elif chon_lo_trinh is None and mode_action == "✏️ Sửa chuyến hiện tại" and (diem_dau == "" or diem_cuoi == ""):
                    st.error("❌ HỆ THỐNG CHẶN: Không có dữ liệu lộ trình. Vui lòng chọn lại lộ trình từ danh sách!")
                    st.stop()
                    
                if c_kh_sel is None or c_kh_sel == 0:
                    st.error("❌ Vui lòng chọn Khách hàng hợp lệ trước khi lưu!")
                    st.stop()

                tx_id_assign_final = None
                if loai_hinh_xe == "🚀 Chạy Xe Công Ty":
                    if c_xe_sel in (None, 0, "") or tx_id_assign in (None, 0, ""):
                        st.error("❌ Vui lòng chọn Xe nội bộ và Tài xế phụ trách.")
                        st.stop()
                    tx_id_assign_final = int(tx_id_assign)

                try:
                    gia_von_thue_ngoai = parse_money_input(ngoai_chi_phi_str) if loai_hinh_xe != "🚀 Chạy Xe Công Ty" else 0.0
                except Exception:
                    st.error("❌ Dữ liệu tiền tệ nhập vào chứa ký tự không hợp lệ. Vui lòng kiểm tra lại!")
                    st.stop()

                if gia_von_thue_ngoai < 0 or khoi_luong < 0 or so_cbm < 0:
                    st.error("❌ Giá trị Khối lượng, Thể tích, Giá vốn thuê ngoài không được phép là số âm.")
                    st.stop()
                if khoi_luong == 0.0:
                    st.error("❌ Khối lượng hàng hóa phải được khai báo để phục vụ quyết toán! Vui lòng nhập số KG.")
                    st.stop()
                if diem_dau == "" and diem_cuoi == "":
                    st.error("❌ Địa chỉ lấy hàng và giao hàng không được để trống!")
                    st.stop()        
                if mode_action == "✏️ Sửa chuyến hiện tại" and not edit_trip_id:
                    st.error("❌ Vui lòng chọn một chuyến đi cụ thể để chỉnh sửa!")
                    st.stop()
                    
                khach_id_final, ten_kh_val = None, ""
                if c_kh_sel == "NEW":
                    if not new_ten_kh or not new_mst_kh:
                        st.error("❌ Vui lòng nhập đầy đủ Tên khách hàng và Mã số thuế!")
                        st.stop()
                    else:
                        success_kh, k_res = tao_khach_hang_nhanh(db.pool, new_ten_kh, new_sdt_kh, new_zalo_id, new_mst_kh, new_diachi_kh)
                        if success_kh: khach_id_final, ten_kh_val = int(k_res) if k_res else None, new_ten_kh
                        else: 
                            st.error(f"❌ Lỗi tạo khách hàng: {k_res}")
                            st.stop()
                elif c_kh_sel:
                    khach_id_final = int(c_kh_sel)
                    ten_kh_val = kh_opts[c_kh_sel].split("—")[-1].strip()

                if kieu_nghiep_vu == "Nghiệp vụ Container":
                    gc_final = f"[CONT: {so_cont_input} | SEAL: {so_seal_input} | LOAI: {loai_cont_input} | CHIEU: {chieu_cont_input}] {ghi_chu_thucong}".strip()
                else:
                    gc_final = ghi_chu_thucong.strip()

                data_chuyen_di = {
                    'ngay_chuyen_di': ngay_di.strftime('%Y-%m-%d'),                      
                    'khach_hang_id': int(khach_id_final) if khach_id_final else None, 
                    'ten_khach_hang': str(ten_kh_val),
                    'dia_chi_khach_hang': str(dia_chi_kh_input),
                    'dia_diem_giao_nhan': f"{diem_dau} ➡️ {diem_cuoi}", 
                    'khoi_luong_kg': float(khoi_luong),                          
                    'the_tich_cbm': float(so_cbm),                       
                    'trang_thai_chuyen': str(STATUS_MAP[trang_thai_ui_value]),                    
                    'ghi_chu': gc_final,
                    'is_hang_tra_ve': 1 if is_hang_ve_ui else 0               
                }
                
                if loai_hinh_xe == "🚀 Chạy Xe Công Ty":
                    data_chuyen_di.update({'xe_id': int(c_xe_sel), 'is_thue_ngoai': int(0)})
                else:
                    if not ngoai_bien_so or not ngoai_ten_doi_tac or not ngoai_ten_tx or not ngoai_cccd_tx or not ngoai_sdt_tx:
                        st.error("❌ Vui lòng điền đầy đủ thông tin: Biển số, Nhà xe, Tên tài xế, CCCD và SĐT tài xế ngoài!")
                        st.stop()
                    data_chuyen_di.update({
                        'xe_id': None, 
                        'is_thue_ngoai': int(1),
                        'loai_hinh_xe': str(ngoai_loai_hinh_xe), 
                        'loai_doi_tac_ngoai': str(ngoai_loai_dt),
                        'ten_doi_tac_ngoai': str(ngoai_ten_doi_tac).upper(),
                        'bien_so_xe_ngoai': str(ngoai_bien_so).upper(),
                        'tai_xe_ngoai_ten': str(ngoai_ten_tx),
                        'tai_xe_ngoai_cccd': str(ngoai_cccd_tx),
                        'tai_xe_ngoai_sdt': str(ngoai_sdt_tx),
                        'chi_phi_thue_ngoai': gia_von_thue_ngoai,
                        'hinh_thuc_thanh_toan_ngoai': str(ngoai_thanh_toan)
                    })
                
                with st.spinner("Đang lưu lệnh vào hệ thống..."):
                    if mode_action == "➕ Tạo chuyến mới":
                        success, result = save_trip_full_process(db.pool, data_chuyen_di, tx_id_assign_final)
                        msg_success = f"✅ Lên lệnh điều xe thành công! Mã chuyến: {result}"
                    else:
                        edit_trip_id_cast = int(edit_trip_id)
                        success, result = update_trip_full_process(db.pool, edit_trip_id_cast, data_chuyen_di, tx_id_assign_final)
                        msg_success = f"✅ Đã cập nhật thành công chuyến đi mã {edit_trip_id_cast}!"
                
                if success:
                    st.success(msg_success)
                    ma_chuyen_gui = result if mode_action == "➕ Tạo chuyến mới" else edit_trip_id_cast
                    if loai_hinh_xe == "🚀 Chạy Xe Công Ty":
                            bien_so_gui = xe_map.get(int(c_xe_sel), {}).get('bien_so_xe', '') if c_xe_sel else ''
                            df_tx = db.execute_query("SELECT ho_ten, so_dien_thoai, cccd FROM nhan_vien WHERE id=%s", (int(tx_id_assign),))
                            if isinstance(df_tx, pd.DataFrame) and not df_tx.empty:
                                ten_tx_gui = str(df_tx.iloc[0]['ho_ten'] or '')
                                sdt_tx_gui = str(df_tx.iloc[0]['so_dien_thoai'] or '')
                                cccd_tx_gui = str(df_tx.iloc[0]['cccd'] or '')
                            else:
                                ten_tx_gui, sdt_tx_gui, cccd_tx_gui = "Chưa cập nhật", "Chưa cập nhật", "Chưa cập nhật"
                    else:
                            bien_so_gui = ngoai_bien_so
                            ten_tx_gui = ngoai_ten_tx
                            sdt_tx_gui = ngoai_sdt_tx
                            cccd_tx_gui = ngoai_cccd_tx
                            
                    st.session_state["tn_tai_xe"] = f"🚛 LỆNH ĐIỀU XE\n- Mã chuyến: {ma_chuyen_gui}\n- Lộ trình: {diem_dau} ➡️ {diem_cuoi}\n- Khách hàng: {ten_kh_val}"
                    st.session_state["tn_khach"] = f"📦 THÔNG TIN TÀI XẾ VẬN CHUYỂN\n- Tên tài xế: {ten_tx_gui}\n- SĐT: {sdt_tx_gui}\n- CCCD: {cccd_tx_gui}\n- Biển số xe: {bien_so_gui}"

                    st.session_state["tab2_mode_action"] = "➕ Tạo chuyến mới"
                    st.session_state["api_km"] = 0.0
                    if diachi_input_key in st.session_state: del st.session_state[diachi_input_key]
                    st.session_state["form_reset_counter"] += 1
                    
                    time.sleep(1.2)
                    st.rerun()
                else:
                    st.error(f"❌ Lỗi Database: {result}")

        if "tn_tai_xe" in st.session_state and "tn_khach" in st.session_state:
            st.markdown("<br>", unsafe_allow_html=True)
            st.success("✅ Hệ thống đã lên lệnh thành công! Vui lòng copy thông tin dưới đây để gửi đi:")
                
            c_msg1, c_msg2 = st.columns(2)
            c_msg1.text_area("📱 Gửi cho Tài xế:", value=st.session_state["tn_tai_xe"], height=160, key="copy_tx")
            c_msg2.text_area("📱 Gửi cho Khách hàng:", value=st.session_state["tn_khach"], height=160, key="copy_kh")
                
            if st.button("✅ Đã gửi xong / Đóng thông báo", type="primary", use_container_width=True):
                del st.session_state["tn_tai_xe"]
                del st.session_state["tn_khach"]
                st.rerun()
            st.divider()

    vung_thao_tac_chuyen_di()
#######################
# Tạo file auto book theo file
###################################
with tab3:
    @st.fragment
    def vung_thao_tac_tao_file_book_chuyen_auto():
        if "export_dieu_xe" not in st.session_state: 
            st.session_state["export_dieu_xe"] = None
            
        st.markdown("#### ⚙️ Trung tâm điều phối đội xe tự động & Xuất lệnh Zalo thủ công")
        st.divider()
        
        st.markdown("##### 📥 1. Tải File Mẫu (Templates) chuẩn của hệ thống")
        col_t1, col_t2 = st.columns(2)
        with col_t1:
            # 1. Tạo DataFrame cho Sheet Mẫu Book Xe
            df_tpl_order = pd.DataFrame([{
                "NGAY_CHAY": "format cell là text: dd/mm/yyyy", 
                "MA_SO_THUE": "0316666666", 
                "TEN_KHACH_HANG": "Công ty TNHH ABC",
                "DIA_CHI_KHACH_HANG": "123 Đường ABC, Quận 1, TP.HCM",
                "DIA_CHI_KHO_DI": "Bình Dương", 
                "DIA_CHI_KHO_DEN": "Cát Lái",
                "KHOI_LUONG_KG": 1500, 
                "THE_TICH_CBM": 5.5, 
                "GHI_CHU": "Hàng nguyên chuyến"
            }])
            
            # 2. Truy vấn dữ liệu Khách hàng từ Database
            sql_kh_export = "SELECT ma_khach_hang, ten_khach_hang, ma_so_thue, so_dien_thoai, dia_chi FROM khach_hang"
            df_kh_export = db.execute_query(sql_kh_export)
            
            if not isinstance(df_kh_export, pd.DataFrame) or df_kh_export.empty:
                df_kh_export = pd.DataFrame(columns=["Mã Khách Hàng", "Tên Khách Hàng", "Mã Số Thuế", "Số Điện Thoại", "Địa Chỉ"])
            else:
                df_kh_export.rename(columns={
                    'ma_khach_hang': 'Mã Khách Hàng',
                    'ten_khach_hang': 'Tên Khách Hàng',
                    'ma_so_thue': 'Mã Số Thuế',
                    'so_dien_thoai': 'Số Điện Thoại',
                    'dia_chi': 'Địa Chỉ'
                }, inplace=True)

            # 3. Ghi vào file Excel với 2 Sheets
            buffer_order = io.BytesIO()
            with pd.ExcelWriter(buffer_order, engine='xlsxwriter') as writer: 
                df_tpl_order.to_excel(writer, index=False, sheet_name="Mau_Book_Xe")
                df_kh_export.to_excel(writer, index=False, sheet_name="Thong_Tin_Khach_Hang")
                
                # Format độ rộng cột cho sheet Khách hàng để dễ đọc
                worksheet_kh = writer.sheets["Thong_Tin_Khach_Hang"]
                worksheet_kh.set_column('A:A', 20)  # Mã Khách Hàng
                worksheet_kh.set_column('B:B', 45)  # Tên Khách Hàng
                worksheet_kh.set_column('C:C', 20)  # Mã Số Thuế
                worksheet_kh.set_column('D:D', 15)  # Số Điện Thoại
                worksheet_kh.set_column('E:E', 60)  # Địa Chỉ
                
            st.download_button(
                label="⬇️ Tải mẫu Excel Điều phối tự động", 
                data=buffer_order.getvalue(), 
                file_name=f"Mau_Dieu_Xe_Tu_Dong_{datetime.date.today().strftime('%d_%m_%Y')}.xlsx",
                use_container_width=True
            )
            
        st.divider()

        st.markdown("##### 🚀 2. Nạp file Excel đơn hàng & Thuật toán điều phối tự động")
        
        # Đưa file_uploader ra ngoài form để bắt sự kiện thay đổi trạng thái (rerun) ngay lập tức
        file_order = st.file_uploader("Chọn file Excel danh sách đơn hàng (.xlsx)", type=["xlsx", "xls"])
        
        # Kiểm tra file đã được tải lên chưa, nếu chưa thì disable nút
        is_disabled = file_order is None
        
        # Dùng st.button thay cho st.form_submit_button
        submit_order = st.button("🚀 Kiểm tra MST & Chạy thuật toán tự động", type="primary", use_container_width=True, disabled=is_disabled)
        
        if submit_order:
            with st.spinner("⏳ Đang phân tích file Excel và kiểm tra dữ liệu hệ thống..."):
                try:
                    df_orders = pd.read_excel(file_order, dtype={'MA_SO_THUE': str, 'MA_KHACH_HANG': str,'TEN_KHACH_HANG': str})
                    df_orders.columns = [str(c).strip().upper() for c in df_orders.columns] 
                    df_orders['NGAY_CHAY_CHUAN'] = pd.to_datetime(df_orders['NGAY_CHAY'], dayfirst=True, errors='coerce')
                    
                    df_kh = db.execute_query("SELECT id, ma_khach_hang, ten_khach_hang, ma_so_thue FROM khach_hang")
                    
                    kh_dict_mst = {}
                    kh_dict_ma = {}
                    kh_dict_ten = {}
                    
                    if isinstance(df_kh, pd.DataFrame) and not df_kh.empty:
                        for _, r in df_kh.iterrows():
                            kh_id = int(r['id'])
                            mk = str(r['ma_khach_hang']).strip().lower() if pd.notna(r['ma_khach_hang']) else ""
                            mst = str(r['ma_so_thue']).strip().lower() if pd.notna(r['ma_so_thue']) else ""
                            ten = str(r['ten_khach_hang']).strip().lower() if pd.notna(r['ten_khach_hang']) else ""
                            
                            if mk: kh_dict_ma[mk] = kh_id
                            if mst: kh_dict_mst[mst] = kh_id
                            if ten: kh_dict_ten[ten] = kh_id
                    
                    missing_customers = []
                    valid_orders = []
                    
                    for idx, row in df_orders.iterrows():
                        raw_mst = str(row.get('MA_SO_THUE', '')).strip()
                        mst = raw_mst.lower() if raw_mst.lower() != 'nan' else ""
                        
                        raw_ma_kh = str(row.get('MA_KHACH_HANG', '')).strip()
                        ma_kh = raw_ma_kh.lower() if raw_ma_kh.lower() != 'nan' else ""
                        
                        raw_ten_kh = str(row.get('TEN_KHACH_HANG', '')).strip()
                        ten_kh = raw_ten_kh.lower() if raw_ten_kh.lower() != 'nan' else ""
                        
                        kh_id = None
                        
                        if mst and mst in kh_dict_mst:
                            kh_id = kh_dict_mst[mst]
                        elif ma_kh and ma_kh in kh_dict_ma:
                            kh_id = kh_dict_ma[ma_kh]
                        elif ten_kh and ten_kh in kh_dict_ten:
                            kh_id = kh_dict_ten[ten_kh]
                        elif ten_kh and isinstance(df_kh, pd.DataFrame):
                            matched_ids = []
                            for _, r in df_kh.iterrows():
                                db_ten = str(r['ten_khach_hang']).strip().lower()
                                if db_ten and (ten_kh in db_ten or db_ten in ten_kh):
                                    matched_ids.append(int(r['id']))
                                    
                            if len(matched_ids) == 1:
                                kh_id = matched_ids[0]
                        
                        if not kh_id:
                            missing_customers.append({
                                "STT Dòng Excel": idx + 2,
                                "Mã Số Thuế / Mã KH": raw_mst if raw_mst else (raw_ma_kh if raw_ma_kh else "Trống"),
                                "Tên Khách Hàng (Excel)": raw_ten_kh,
                                "Lý do lỗi": "Tên khách không có trong DB hoặc có nhiều tên na ná nhau (Vui lòng gõ cụ thể hơn)" if ten_kh else "Thiếu dữ liệu tra cứu"
                            })
                        else:
                            row['DB_KHACH_HANG_ID'] = kh_id
                            valid_orders.append(row)
                            
                    if missing_customers:
                        st.error(f"🚨 PHÁT HIỆN {len(missing_customers)} ĐƠN HÀNG CÓ KHÁCH HÀNG CHƯA ĐĂNG KÝ HOẶC BỊ TRÙNG LẶP TÊN!")
                        df_missing = pd.DataFrame(missing_customers).drop_duplicates()
                        st.dataframe(df_missing, use_container_width=True, hide_index=True)
                    
                    df_valid_orders = pd.DataFrame(valid_orders)
                    
                    if not df_valid_orders.empty and not missing_customers:
                        sql_xe_ranh = """
                            SELECT x.id, x.bien_so_xe, x.tai_xe_co_dinh_id, x.tai_trong_thiet_ke, x.dung_tich_cbm, 
                                nv.ho_ten as ten_tai_xe, nv.so_dien_thoai as sdt_tai_xe, nv.cccd as cccd_tai_xe
                            FROM xe x 
                            LEFT JOIN nhan_vien nv ON x.tai_xe_co_dinh_id = nv.id
                            WHERE x.trang_thai = 'Dang_Hoat_Dong'
                            AND x.id NOT IN (
                                SELECT xe_id FROM chuyen_di 
                                WHERE trang_thai_chuyen IN ('Tao_Moi', 'Dang_Di') 
                                    AND xe_id IS NOT NULL
                            )
                            ORDER BY x.tai_trong_thiet_ke ASC, x.dung_tich_cbm ASC
                        """
                        df_xe_ranh = db.execute_query(sql_xe_ranh)
                        
                        if isinstance(df_xe_ranh, str) or df_xe_ranh.empty:
                            st.error("❌ Hiện tại không có xe nội bộ nào đang rảnh rỗi để điều phối tự động!")
                        else:
                            success_count = 0
                            xe_list = df_xe_ranh.to_dict('records')
                            danh_sach_xuat_excel = [] 
                            for xe in xe_list: xe['is_used'] = False 
                            
                            def safe_float(val):
                                try: return 0.0 if pd.isna(val) or str(val).strip() == "" else float(val)
                                except: return 0.0
                                
                            df_valid_orders['SORT_KG'] = df_valid_orders['KHOI_LUONG_KG'].apply(safe_float)
                            df_valid_orders['SORT_CBM'] = df_valid_orders['THE_TICH_CBM'].apply(safe_float)
                            df_orders_sorted = df_valid_orders.sort_values(by=['SORT_KG', 'SORT_CBM'], ascending=[False, False])
                            
                            for idx, row in df_orders_sorted.iterrows():
                                if pd.isna(row['NGAY_CHAY_CHUAN']): continue
                                ngay_chay_str = row['NGAY_CHAY_CHUAN'].strftime('%Y-%m-%d')       
                                req_kg = row['SORT_KG']
                                req_cbm = row['SORT_CBM']
                                
                                kh_id = row.get('DB_KHACH_HANG_ID')
                                khach_hang_ten = str(row.get('TEN_KHACH_HANG', 'Khách Lẻ')).strip()
                                dia_chi_kh = str(row.get('DIA_CHI_KHACH_HANG', '')).strip()
                                
                                kho_di = str(row.get('DIA_CHI_KHO_DI', '')).strip()
                                kho_den = str(row.get('DIA_CHI_KHO_DEN', '')).strip()
                                ghi_chu_excel = str(row.get('GHI_CHU', ''))
                                
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
                                    data_chuyen_di = {
                                        'ngay_chuyen_di': ngay_chay_str,
                                        'khach_hang_id': kh_id,
                                        'ten_khach_hang': khach_hang_ten,
                                        'dia_chi_khach_hang': dia_chi_kh,
                                        'xe_id': xe_phu_hop['id'],
                                        'dia_diem_giao_nhan': f"{kho_di} ➡️ {kho_den}",
                                        'khoi_luong_kg': req_kg,
                                        'the_tich_cbm': req_cbm, 
                                        'is_thue_ngoai': 0,
                                        'trang_thai_chuyen': 'Tao_Moi', 
                                        'ghi_chu': str(row.get('GHI_CHU', 'Điều phối tự động qua Excel'))
                                    }
                                
                                    tx_id = int(float(xe_phu_hop['tai_xe_co_dinh_id']))
                                    is_ok, result_msg = save_trip_full_process(db.pool, data_chuyen_di, tx_id)
                                    
                                    if is_ok:
                                        success_count += 1
                                        danh_sach_xuat_excel.append({
                                            "Mã Chuyến Hệ Thống": result_msg, 
                                            "Ngày Chạy": ngay_chay_str,
                                            "Khách Hàng": khach_hang_ten,
                                            "Địa Chỉ Khách Hàng": dia_chi_kh,
                                            "Biển Số Xe": xe_phu_hop['bien_so_xe'],
                                            "Tải Trọng Đã Book (KG)": req_kg,
                                            "Tài Xế Phụ Trách": xe_phu_hop['ten_tai_xe'], 
                                            "Số Điện Thoại Tài Xế": xe_phu_hop['sdt_tai_xe'] if pd.notna(xe_phu_hop['sdt_tai_xe']) else "Chưa cập nhật",
                                            "CCCD Tài Xế": xe_phu_hop['cccd_tai_xe'] if pd.notna(xe_phu_hop['cccd_tai_xe']) else "Chưa cập nhật",
                                            "Lộ Trình": f"{kho_di} ➡️ {kho_den}",
                                            "Ghi Chú": ghi_chu_excel
                                        })
                            
                            st.session_state["export_dieu_xe"] = pd.DataFrame(danh_sach_xuat_excel)
                            if success_count > 0:
                                st.success(f"🎉 Hệ thống đã tự động điều phối thành công {success_count} đơn hàng!")
                                time.sleep(1.5)
                                st.rerun()
                                
                except Exception as e:
                    st.error(f"❌ Lỗi xử lý thuật toán tự động: {str(e)}")

        if st.session_state.get("export_dieu_xe") is not None and not st.session_state["export_dieu_xe"].empty:
            st.markdown("### 🖨️ Danh sách chuyến xe điều phối thành công & Hỗ trợ Zalo Thủ Công")
            st.dataframe(st.session_state["export_dieu_xe"], use_container_width=True, hide_index=True)
            
            danh_sach_zalo = []
            for _, row in st.session_state["export_dieu_xe"].iterrows():
                bien_so = str(row['Biển Số Xe']) if pd.notna(row['Biển Số Xe']) else "CHUA_GAN_XE"
                ten_group = "".join([c for c in bien_so if c.isalnum()]).upper()
                ghi_chu_row = str(row.get('Ghi Chú', ''))
                
                # Format cột 1: Thông tin cho Tài xế
                msg_tai_xe = (
                    f"🚛 LỆNH ĐIỀU XE BẢO TÍN\n"
                    f"- Lộ trình: {row['Lộ Trình']}\n"
                    f"- Mã chuyến: {row['Mã Chuyến Hệ Thống']}\n"
                    f"- Khách hàng: {row['Khách Hàng']}\n"
                    f"- Địa chỉ: {row['Địa Chỉ Khách Hàng']}\n"
                    f"- Ngày chạy: {row['Ngày Chạy']}\n"
                    f"- Ghi chú: {ghi_chu_row}"
                )
                
                # Format cột 2: Thông tin cho Khách hàng
                msg_khach_hang = (
                    f"📦 THÔNG TIN TÀI XẾ VẬN CHUYỂN\n"
                    f"- Tên tài xế: {row['Tài Xế Phụ Trách']}\n"
                    f"- SĐT: {row['Số Điện Thoại Tài Xế']}\n"
                    f"- CCCD: {row['CCCD Tài Xế']}\n"
                    f"- Biển số xe: {row['Biển Số Xe']}\n"
                    f"- Tải trọng: {float(row['Tải Trọng Đã Book (KG)']):,.0f} KG\n"
                    f"- Ghi chú: {ghi_chu_row}"
                )
                
                danh_sach_zalo.append({
                    "TEN_GROUP": ten_group,
                    "GUI_THONG_TIN_TAI_XE": msg_tai_xe,
                    "GUI_THONG_TIN_KHACH_HANG": msg_khach_hang,
                    **row.to_dict()
                })
            
            df_zalo_export = pd.DataFrame(danh_sach_zalo)
            buffer_export = io.BytesIO()
            
            # Cấu hình xlsxwriter để bật tự động xuống hàng (Wrap text)
            with pd.ExcelWriter(buffer_export, engine='xlsxwriter') as writer:
                df_zalo_export.to_excel(writer, index=False, sheet_name="Lenh_Dieu_Xe_ZaloThuCong")
                
                workbook = writer.book
                worksheet = writer.sheets["Lenh_Dieu_Xe_ZaloThuCong"]
                
                # Tạo định dạng tự động Wrap Text và căn lề trên
                wrap_format = workbook.add_format({'text_wrap': True, 'valign': 'top'})
                
                # Áp dụng độ rộng và Wrap Text cho Cột B và C (Chứa nội dung Zalo)
                worksheet.set_column('B:C', 60, wrap_format)
                # Đặt độ rộng vừa phải cho cột Tên Group (Cột A)
                worksheet.set_column('A:A', 20)
                
            st.divider()
            
            col_btn1, col_btn2 = st.columns([1, 4])
            with col_btn1:
                if st.button("🔄 Reset Màn Hình", use_container_width=True):
                    st.session_state["export_dieu_xe"] = None
                    st.rerun()
            with col_btn2:
                st.download_button(
                    label="⬇️ TẢI FILE EXCEL (CÓ CỘT TEN_GROUP, THÔNG TIN GỬI TÀI XẾ/KHÁCH HÀNG & ZALO THỦ CÔNG)", 
                    data=buffer_export.getvalue(), 
                    file_name=f"Lenh_Dieu_Xe_ZaloThuCong_{datetime.date.today().strftime('%d_%m_%Y')}.xlsx", 
                    type="primary",
                    use_container_width=True
                )
                        
        st.divider()
    vung_thao_tac_tao_file_book_chuyen_auto()

# ---------------------------------------------------------
# TAB 4: DANH SÁCH CHUYẾN ĐI TRONG NGÀY
# ---------------------------------------------------------
with tab4:
    tao_tieu_de_kem_nut_refresh("📋 Quản lý danh sách chuyến đi", "ref_ds_chuyen")
    @st.fragment
    def vung_thao_tac_quan_ly_chuyen_di():
        try:
            ngay_hom_nay = datetime.date.today().strftime('%Y-%m-%d')
            
            # 1. TRUY VẤN XE NỘI BỘ
            sql_list_noibo = """
                SELECT cd.id AS 'Mã chuyến đi', cd.ngay_chuyen_di AS 'Ngày', cd.ten_khach_hang AS 'Khách hàng',
                    x.bien_so_xe AS 'Biển Số', nv.ho_ten AS 'Tài Xế', cd.dia_diem_giao_nhan AS 'Lộ trình', 
                    cd.khoi_luong_kg AS 'Trọng tải (kg)',                    
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
                SELECT cd.id AS 'Mã chuyến đi', cd.ngay_chuyen_di AS 'Ngày', cd.ten_khach_hang AS 'Khách hàng',
                    cd.bien_so_xe_ngoai AS 'Biển Số', cd.tai_xe_ngoai_ten AS 'Tài Xế', cd.dia_diem_giao_nhan AS 'Lộ trình', 
                    cd.khoi_luong_kg AS 'Trọng tải (kg)', 
                    cd.ghi_chu AS 'Ghi chú', cd.trang_thai_chuyen AS 'Trạng thái'
                FROM chuyen_di cd 
                WHERE cd.ngay_chuyen_di = %s AND (cd.xe_id IS NULL OR cd.is_thue_ngoai = 1)
                ORDER BY cd.id DESC
            """
            df_ngoai = db.execute_query(sql_list_ngoai, (ngay_hom_nay,))

            has_noibo = isinstance(df_noibo, pd.DataFrame) and not df_noibo.empty
            has_ngoai = isinstance(df_ngoai, pd.DataFrame) and not df_ngoai.empty

            if has_noibo or has_ngoai:
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
# TAB 5: TRA CỨU CHUYẾN ĐI THEO THỜI GIAN VÀ BỘ LỌC PHỤ 
# ---------------------------------------------------------
with tab5:
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
                sql_search_nb = """
                    SELECT cd.id AS 'Mã chuyến đi', cd.ngay_chuyen_di AS 'Ngày', cd.ten_khach_hang AS 'Khách hàng',
                        x.bien_so_xe AS 'Biển Số', nv.ho_ten AS 'Tài Xế', cd.dia_diem_giao_nhan AS 'Lộ trình', 
                        cd.khoi_luong_kg AS 'Trọng tải (kg)',cd.ghi_chu AS 'Ghi chú', cd.trang_thai_chuyen AS 'Trạng thái'
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

                sql_search_ngoai = """
                    SELECT cd.id AS 'Mã chuyến đi', cd.ngay_chuyen_di AS 'Ngày', cd.ten_khach_hang AS 'Khách hàng',
                        cd.bien_so_xe_ngoai AS 'Biển Số', cd.tai_xe_ngoai_ten AS 'Tài Xế', cd.dia_diem_giao_nhan AS 'Lộ trình', 
                        cd.khoi_luong_kg AS 'Trọng tải (kg)', 
                        cd.ghi_chu AS 'Ghi chú', cd.trang_thai_chuyen AS 'Trạng thái'
                    FROM chuyen_di cd 
                    WHERE cd.ngay_chuyen_di >= %s AND cd.ngay_chuyen_di <= %s AND (cd.xe_id IS NULL OR cd.is_thue_ngoai = 1)
                """
                params_ngoai = [tu_ngay.strftime('%Y-%m-%d'), den_ngay.strftime('%Y-%m-%d')]
                
                if loc_trang_thai != "Tất cả":
                    sql_search_ngoai += " AND cd.trang_thai_chuyen = %s"
                    params_ngoai.append(status_mapping[loc_trang_thai])
                
                if loc_tai_xe != 0:
                    sql_search_ngoai += " AND 1 = 0" 
                    
                sql_search_ngoai += " ORDER BY cd.ngay_chuyen_di DESC, cd.id DESC"
                df_search_ngoai = db.execute_query(sql_search_ngoai, tuple(params_ngoai))

                has_nb = isinstance(df_search_nb, pd.DataFrame) and not df_search_nb.empty
                has_ng = isinstance(df_search_ngoai, pd.DataFrame) and not df_search_ngoai.empty

                if has_nb or has_ng:
                    total_len = (len(df_search_nb) if has_nb else 0) + (len(df_search_ngoai) if has_ng else 0)
                    st.success(f"✅ Tìm thấy tổng cộng **{total_len}** chuyến đi thỏa mãn điều kiện.")

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
# TAB 6: CẢNH BÁO XE TỒN ĐỌNG / CHƯA HOÀN THÀNH
# ---------------------------------------------------------
with tab6:
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
                    cd.id AS 'Mã chuyến đi', 
                    cd.ngay_chuyen_di AS 'Ngày Chạy', 
                    COALESCE(x.bien_so_xe, cd.bien_so_xe_ngoai) AS 'Biển Số Xe',
                    cd.khoi_luong_kg AS 'Trọng tải (kg)', 
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
                    
                if 'khoi_luong_kg' in styled_df.columns:
                    styled_df['khoi_luong_kg'] = pd.to_numeric(styled_df['khoi_luong_kg'], errors='coerce').fillna(0).apply(lambda x: f"{x:,.0f}")
                    
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