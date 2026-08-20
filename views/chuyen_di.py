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

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📋 Danh sách chuyến", 
    "➕ Tạo/Sửa chuyến thủ công", 
    "🏁 Quyết toán đơn chuyến",
    "🏁 Sửa chuyến đi đã quyết toán", 
    "🤖 Tạo chuyến tự động/ Excel tool" 
])

# Lấy dữ liệu danh mục
sql_xe_trong = "SELECT id, bien_so_xe, tai_trong_thiet_ke, tai_xe_co_dinh_id FROM xe WHERE trang_thai = 'Dang_Hoat_Dong'"
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
            sql_ghep = """
                SELECT cd.id, cd.ngay_chuyen_di, cd.dia_diem_giao_nhan, COALESCE(kh.ten_khach_hang, cd.ten_khach_hang) as ten_khach, x.bien_so_xe, cd.xe_id
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
                    cd.id AS 'Mã Chuyến', 
                    cd.ngay_chuyen_di AS 'Ngày', 
                    COALESCE(kh.ten_khach_hang, cd.ten_khach_hang) AS 'Khách hàng',
                    COALESCE(x.bien_so_xe, cd.bien_so_xe_ngoai) AS 'Biển Số', 
                    cd.dia_diem_giao_nhan AS 'Lộ trình', 
                    CAST(cd.cong_chuyen AS FLOAT) AS 'Lương chuyến',
                    CAST(cd.doanh_thu AS FLOAT) AS 'Doanh thu', 
                    cd.trang_thai_chuyen AS 'Trạng thái'
                FROM chuyen_di cd 
                LEFT JOIN khach_hang kh ON cd.khach_hang_id = kh.id
                LEFT JOIN xe x ON cd.xe_id = x.id
                WHERE cd.ngay_chuyen_di = %s
                ORDER BY cd.ma_chuyen_ghep DESC, cd.stt_chuyen_ghep ASC, cd.id DESC
            """
            df_chuyen = db.execute_query(sql_list, (ngay_hom_nay,))
            if isinstance(df_chuyen, pd.DataFrame) and not df_chuyen.empty:
                # Highlight các dòng được ghép (Tô màu hoặc icon tùy chọn của dataframe)
                st.dataframe(df_chuyen, use_container_width=True, hide_index=True)
            else:
                st.info("Chưa có dữ liệu chuyến đi nào trong ngày.")
        except Exception as e:
            st.error(f"Lỗi truy xuất danh sách: {e}")

    vung_thao_tac_hien_thi_chuyen_di()

# ==========================================
# TAB 2: ĐĂNG KÝ, SỬA & XÓA CHUYẾN ĐI THỦ CÔNG (HỖ TRỢ CONTAINER & XE TẢI)
# ==========================================
with tab2:
    tao_tieu_de_kem_nut_refresh("📋 Đăng ký & Quản lý chuyến đi thủ công", "ref_tab2")
    
    # ĐÓNG GÓI TOÀN BỘ TAB 2 VÀO FRAGMENT ĐỂ NGĂN CHẶN RERUN TOÀN TRANG
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
                            st.rerun() # Lệnh này sẽ tự động tải lại cả trang để làm mới Tab 1
                        else: st.error(f"❌ Lỗi khi xóa chuyến đi: {result}")
            else: st.warning("⚠️ Hiện tại không có chuyến đi nào ở trạng thái có thể xóa.")

        # ================= CHẾ ĐỘ: TẠO MỚI HOẶC SỬA CHUYẾN ĐI =================
        else:
            edit_trip_id = None
            trip_data = {}
            
            # Biến hứng dữ liệu Container (Phục vụ chức năng Sửa)
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
                                
                            # 🧠 BÓC TÁCH DỮ LIỆU CONTAINER TỪ GHI CHÚ
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
            # PHẦN 1: THÔNG TIN KHÁCH HÀNG (Giữ nguyên)
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
            # PHẦN 2: THÔNG SỐ HÀNG HÓA & ĐIỀU PHỐI PHƯƠNG TIỆN (TÁCH LUỒNG)
            # ====================================================================
            st.markdown(f"#### 2. Thông số Hàng hóa & Phương án điều xe ({kieu_nghiep_vu})")
            
            kg_key = f"input_kg_{trip_suffix}"
            cbm_key = f"input_cbm_{trip_suffix}"
            
            # 📦 LUỒNG DỮ LIỆU ĐẦU VÀO TÙY THEO NGHIỆP VỤ
            if kieu_nghiep_vu == "Nghiệp vụ Xe Tải":
                col_hl1, col_hl2 = st.columns(2)
                khoi_luong = col_hl1.number_input("📦 Khối lượng (KG)*", min_value=0.0, value=float(trip_data.get('khoi_luong_kg') or 0.0), step=1.0, key=kg_key)
                so_cbm = col_hl2.number_input("🧊 Thể tích (CBM)", min_value=0.0, value=float(trip_data.get('the_tich_cbm') or 1.0), step=0.1, key=cbm_key)
            else:
                c_c1, c_c2 = st.columns(2)
                so_cont_input = c_c1.text_input("🔢 Số Container", value=so_cont_val, key=f"so_cont_{trip_suffix}")
                so_seal_input = c_c2.text_input("🔒 Số Seal", value=so_seal_val, key=f"so_seal_{trip_suffix}")
                
                c_c3, c_c4, c_c5 = st.columns(3)
                loai_cont_opts = ["20DC", "40DC", "40HC", "45HC", "20RF (Lạnh)", "40RF (Lạnh)", "Khác"]
                loai_cont_input = c_c3.selectbox("🧊 Loại Cont", options=loai_cont_opts, index=get_idx(loai_cont_opts, loai_cont_val), key=f"loai_cont_{trip_suffix}")
                
                chieu_opts = ["Nhập", "Xuất", "Nội Địa", "Chạy Rỗng"]
                chieu_cont_input = c_c4.selectbox("🔄 Chiều Hàng", options=chieu_opts, index=get_idx(chieu_opts, chieu_cont_val), key=f"chieu_cont_{trip_suffix}")
                
                khoi_luong = c_c5.number_input("⚖️ Trọng lượng hàng (KG)*", min_value=0.0, value=float(trip_data.get('khoi_luong_kg') or 0.0), step=1.0, key=kg_key)
                so_cbm = 0.0 # Container không chú trọng CBM khi điều xe
            
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
                    
                    # Nút tìm xe tự động CHỈ DÀNH CHO XE TẢI (Đã tích hợp tính tải trọng còn lại)
                    if kieu_nghiep_vu == "Nghiệp vụ Xe Tải":
                        if st.button("🔍 Tìm xe tự động (Theo KG & CBM)", type="primary", use_container_width=True):
                            if khoi_luong <= 0:
                                st.warning("⚠️ Vui lòng nhập Khối lượng (KG) lớn hơn 0 để phần mềm tìm xe.")
                            else:
                                sql_xe_ranh = """
                                    SELECT x.id, x.tai_xe_co_dinh_id, x.tai_trong_thiet_ke, x.dung_tich_cbm,
                                           COALESCE(SUM(cd.khoi_luong_kg), 0) as da_cho_kg,
                                           COALESCE(SUM(cd.the_tich_cbm), 0) as da_cho_cbm
                                    FROM xe x 
                                    LEFT JOIN chuyen_di cd ON x.id = cd.xe_id AND cd.trang_thai_chuyen IN ('Tao_Moi', 'Dang_Di')
                                    WHERE x.trang_thai = 'Dang_Hoat_Dong'
                                    GROUP BY x.id, x.tai_xe_co_dinh_id, x.tai_trong_thiet_ke, x.dung_tich_cbm
                                    ORDER BY x.tai_trong_thiet_ke ASC, x.dung_tich_cbm ASC
                                """
                                df_xe_ranh = db.execute_query(sql_xe_ranh)
                                found_xe = None
                                if isinstance(df_xe_ranh, pd.DataFrame) and not df_xe_ranh.empty:
                                    for _, xe in df_xe_ranh.iterrows():
                                        if pd.isna(xe['tai_xe_co_dinh_id']): continue 
                                        
                                        # Tính tải trọng và thể tích CÒN LẠI của xe (Cho phép ghép chuyến)
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

                    # ---- [NEW] CHECKBOX ĐIỀU KHIỂN LUỒNG HIỂN THỊ UI ----
                    is_ghep_chuyen = st.checkbox("🔗 Hiển thị cả xe đang chạy (Dành cho nghiệp vụ Ghép chuyến)", key=f"check_ghep_{trip_suffix}")
                    
                    # Truy vấn danh sách xe đang bận (đang có chuyến)
                    sql_busy = "SELECT DISTINCT xe_id FROM chuyen_di WHERE trang_thai_chuyen IN ('Tao_Moi', 'Dang_Di') AND xe_id IS NOT NULL"
                    df_busy = db.execute_query(sql_busy)
                    busy_xe_ids = df_busy['xe_id'].tolist() if isinstance(df_busy, pd.DataFrame) and not df_busy.empty else []

                    xe_dict_opts = {None: "-- Vui lòng chọn Xe Nội Bộ --"}
                    for k, v in xe_map.items():
                        is_busy = int(k) in busy_xe_ids
                        
                        # LOGIC LỌC: Nếu không tick "Ghép chuyến" -> Ẩn xe đang bận (Trừ khi xe đó là xe đang được sửa)
                        if not is_ghep_chuyen and is_busy and int(k) != trip_data.get('xe_id'):
                            continue

                        tx_id_raw = v.get('tai_xe_co_dinh_id')
                        ten_tx = "Chưa gán TX"
                        if pd.notna(tx_id_raw) and int(float(tx_id_raw)) in tx_opts:
                            ten_tx = tx_opts[int(float(tx_id_raw))]
                        
                        # [NEW] Đổi nhãn trực quan giúp người điều phối phân biệt xe
                        if is_busy:
                            xe_dict_opts[int(k)] = f"🔄 [ĐANG CHẠY] {v['bien_so_xe']} ({v.get('tai_trong_thiet_ke', 0)}T) | 🧑‍✈️ TX: {ten_tx}"
                        else:
                            xe_dict_opts[int(k)] = f"🚛 [TRỐNG] {v['bien_so_xe']} ({v.get('tai_trong_thiet_ke', 0)}T) | 🧑‍✈️ TX: {ten_tx}"
                        
                    xe_keys = list(xe_dict_opts.keys())
                    
                    default_xe_idx = 0
                    if selectbox_xe_key not in st.session_state and mode_action == "✏️ Sửa chuyến hiện tại" and trip_data.get('xe_id') in xe_keys:
                        default_xe_idx = xe_keys.index(trip_data.get('xe_id'))
                    
                    title_selectbox = "✅ Chọn Xe Nội Bộ (Điều phối/Ghép chuyến)*" if is_ghep_chuyen else "✅ Chọn Xe Nội Bộ (Đang trống)*"
                    
                    c_xe_sel = st.selectbox(
                        title_selectbox, 
                        options=xe_keys, 
                        index=default_xe_idx if selectbox_xe_key not in st.session_state else None, 
                        format_func=lambda x: xe_dict_opts[x],
                        key=selectbox_xe_key
                    )
                    
                    if c_xe_sel is not None:
                        selected_xe_info = xe_map.get(c_xe_sel, {})
                        tx_id_raw = selected_xe_info.get('tai_xe_co_dinh_id') 
                        
                        # Xác định tài xế mặc định (Tài xế gốc của xe, hoặc tài xế đã gán nếu đang sửa chuyến)
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
                        
                        # AI Cảnh báo nếu điều phối viên chọn tài xế khác với tài xế cố định của xe
                        if pd.notna(tx_id_raw) and int(float(tx_id_raw)) in tx_opts:
                            tx_goc_id = int(float(tx_id_raw))
                            if tx_id_assign and tx_id_assign != tx_goc_id:
                                st.warning(f"⚠️ Lưu ý: Bạn đang điều Tài xế thay thế. Tài xế gốc của xe này là **{tx_opts[tx_goc_id]}**.")
                        elif not tx_id_assign:
                            st.warning("⚠️ Vui lòng chọn tài xế để phát lệnh!")

                with col_xe_2:
                    st.markdown("**🔸 Các xe đang được điều động (Tham khảo)**")
                    sql_xe_ban = """
                        SELECT x.bien_so_xe as 'Biển Số',ngay_chuyen_di as 'Ngày đi', COALESCE(nv.ho_ten, 'Chưa gán') as 'Tài Xế', cd.dia_diem_giao_nhan as 'Lộ Trình'
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

            lo_trinh_opts = {None: "-- Vui lòng chọn lộ trình (Tạo mới nếu chưa có) --"}
            if khach_id_filter:
                sql_rates = "SELECT DISTINCT diem_di, diem_den FROM rate_cards WHERE khach_hang_id = %s ORDER BY diem_di"
                df_rates = db.execute_query(sql_rates, (khach_id_filter,))
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
            if chon_lo_trinh is None:
                diem_di_val, diem_den_val = "", ""
            else:
                parts = chon_lo_trinh.split(" ➡️ ")
                diem_di_val = parts[0]
                diem_den_val = parts[-1] if len(parts) > 1 else ""
                
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
                    
                    # ÉP KIỂU XE MẶC ĐỊNH THEO LUỒNG NGHIỆP VỤ
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
                
                btn_submit = st.columns(1)
                btn_label = "🔄 LƯU THAY ĐỔI CHUYẾN ĐI" if mode_action == "✏️ Sửa chuyến hiện tại" else "💾 XÁC NHẬN & PHÁT LỆNH ĐIỀU XE"
                submit_save = btn_submit[0].form_submit_button(btn_label, type="primary", use_container_width=True)
            
            # ----------------------------------------------------
            # XỬ LÝ SUBMIT CHÍNH THỨC
            # ----------------------------------------------------
            if submit_save:
                if chon_lo_trinh is None:
                    st.error("❌ HỆ THỐNG CHẶN: Vui lòng chọn lộ trình hợp lệ từ danh sách! Nếu chưa có, hãy tạo mới trong Bảng Giá trước.")
                    st.stop()
                if c_kh_sel is None or c_kh_sel == 0:
                    st.error("❌ Vui lòng chọn Khách hàng hợp lệ trước khi lưu!")
                    st.stop()
                if loai_hinh_xe == "🚀 Chạy Xe Công Ty" and (c_xe_sel is None or c_xe_sel == 0):
                    st.error("❌ Vui lòng chọn Xe nội bộ hợp lệ!")
                    st.stop()

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

                # 📦 NHÚNG DỮ LIỆU CONTAINER VÀO GHI CHÚ
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
                    'ghi_chu': gc_final               
                }
                
                tx_id_assign_final = None
                if loai_hinh_xe == "🚀 Chạy Xe Công Ty":
                    if not c_xe_sel or not tx_id_assign:
                        st.error("❌ Vui lòng chọn Xe nội bộ và Tài xế phụ trách.")
                        st.stop()
                    data_chuyen_di.update({'xe_id': int(c_xe_sel), 'is_thue_ngoai': int(0)})
                    tx_id_assign_final = int(tx_id_assign)
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
                    tx_id_assign_final = None
                
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
                    st.session_state["tab2_mode_action"] = "➕ Tạo chuyến mới"
                    st.session_state["api_km"] = 0.0
                    if diachi_input_key in st.session_state: del st.session_state[diachi_input_key]
                    st.session_state["form_reset_counter"] += 1
                    
                    time.sleep(1.2)
                    st.rerun() # Lệnh này sẽ tự động làm mới toàn bộ Script để refresh thông tin ở Tab 1
                else:
                    st.error(f"❌ Lỗi Database: {result}")

    # KÍCH HOẠT VÙNG THAO TÁC ĐỘC LẬP
    vung_thao_tac_chuyen_di()



# =========================================================================
# HÀM LÕI: ĐỘNG CƠ LUẬT TÍNH PHỤ PHÍ (RULE ENGINE) - DÙNG CHUNG CHO TAB 3 & TAB 5
# =========================================================================

import json
import pandas as pd
import re

def clean_money_val(val):
    """Hàm làm sạch tiền tệ, giữ nguyên độ chuẩn xác"""
    if val is None or pd.isna(val) or str(val).strip() == "": return 0.0
    if isinstance(val, (int, float)): return float(val)
    s = str(val).replace(',', '').replace(' ', '').strip()
    try:
        return float(s)
    except:
        return 0.0
def rule_engine_calc(kh_id, tai_trong_xe_tan, doanh_thu, facts, db_instance):
    tong_tien_tu_dong = 0.0
    ghi_chu_tu_dong = []
    if not kh_id: return 0.0, []
    
    if tai_trong_xe_tan >= 50:
        tai_trong_xe_tan = tai_trong_xe_tan / 1000.0
        
    def tinh_tien_goc(gia_niem_yet, loai_chuoi, doanh_thu_chuyen):
        loai_str = str(loai_chuoi).strip().lower()
        is_phan_tram = ('%' in loai_str) or ('phan_tram' in loai_str) or ('phantram' in loai_str)
        if not is_phan_tram and loai_str not in ['co_dinh', 'codinh', 'vnd', '']:
            try:
                val = float(loai_str)
                if 0 < val <= 1.0: is_phan_tram = True
            except: pass
            
        if is_phan_tram:
            if doanh_thu_chuyen <= 0: return 0.0 
            import re
            nums = re.findall(r'\d+\.?\d*', loai_str)
            if nums:
                ty_le = float(nums[0])
                return (ty_le * doanh_thu_chuyen) if ty_le <= 1.0 else ((ty_le / 100.0) * doanh_thu_chuyen)
            else:
                if gia_niem_yet > 0 and gia_niem_yet <= 1.0: return gia_niem_yet * doanh_thu_chuyen
                elif gia_niem_yet > 1.0: return (gia_niem_yet / 100.0) * doanh_thu_chuyen
        return float(gia_niem_yet)
        
    try:
        sql_pp = "SELECT ten_phu_phi, don_gia_phu_phi, loai_ap_dung, dieu_kien_kich_hoat FROM phu_phi_khach_hang WHERE khach_hang_id = %s"
        df_pp = db_instance.execute_query(sql_pp, (kh_id,))
        
        matched_candidates = []
        
        import json
        if isinstance(df_pp, pd.DataFrame) and not df_pp.empty:
            for _, pp in df_pp.iterrows():
                dk_str = str(pp.get('dieu_kien_kich_hoat', '')).strip()
                ten_pp = str(pp['ten_phu_phi'])
                loai = str(pp.get('loai_ap_dung', 'Co_Dinh'))
                gia = float(pp.get('don_gia_phu_phi') or 0.0)
                
                tien_item = 0.0
                ly_do = ""
                ldk_key = ""
                range_size = 99999.0
                
                if dk_str.startswith("{") and dk_str.endswith("}"):
                    try:
                        dk_raw = json.loads(dk_str)
                        dk = {str(k).strip().lower(): v for k, v in dk_raw.items()}
                        
                        ldk = str(dk.get('loai', '')).strip().lower()
                        ldk_key = ldk
                        
                        raw_min = float(dk.get('tai_trong_min', 0.0))
                        raw_max = float(dk.get('tai_trong_max', 999.0))
                        tt_min = (raw_min / 1000.0) if raw_min >= 50 else raw_min
                        tt_max = (raw_max / 1000.0) if raw_max >= 50 else raw_max
                        
                        range_size = tt_max - tt_min
                        has_weight_limit = (raw_min > 0 or raw_max < 999.0)
                        is_tt_ok = (tt_min <= tai_trong_xe_tan <= tt_max) if has_weight_limit else True
                        
                        if ldk == "giao_diem_them" and facts.get('so_diem_giao_them', 0) > 0:
                            km_min = float(dk.get('km_min', 0.0))
                            km_max = float(dk.get('km_max', 9999.0))
                            km = facts.get('so_km_phat_sinh', 0.0)
                            if (km_min <= km <= km_max) and is_tt_ok:
                                kieu_tinh = str(dk.get('kieu_tinh', '')).strip().lower()
                                if kieu_tinh == "phan_tram_diem_xa_nhat": tien_item = tinh_tien_goc(gia, loai, doanh_thu)
                                else: tien_item = gia * facts['so_diem_giao_them']
                                ly_do = f"Giao {facts['so_diem_giao_them']} điểm, {km}km"
                        
                        elif ldk == "boc_xep" and facts.get('is_boc_xep') and is_tt_ok:
                            tien_item = tinh_tien_goc(gia, loai, doanh_thu)
                            ly_do = f"Bốc xếp {tai_trong_xe_tan}T"
                                
                        elif ldk == "ve_khuya" and facts.get('is_ve_khuya') and is_tt_ok:
                            tien_item = tinh_tien_goc(gia, loai, doanh_thu)
                            ly_do = f"Về khuya {tai_trong_xe_tan}T"
                                
                        elif ldk in ["nang_ha_cont", "phi_qua_cang"] and facts.get('cang_nang_ha'):
                            cang_dk = str(dk.get('cang', '')).strip().lower()
                            cang_fact = str(facts.get('cang_nang_ha', '')).strip().lower()
                            if cang_dk == cang_fact:
                                tien_item = tinh_tien_goc(gia, loai, doanh_thu)
                                ly_do = f"Qua cảng/Nâng hạ {dk.get('cang')}"
                                
                        elif ldk == "phu_thu_chu_nhat" and facts.get('is_chu_nhat'):
                            tien_item = tinh_tien_goc(gia, loai, doanh_thu)
                            ly_do = "Phụ thu Chủ Nhật"
                            
                        elif ldk == "lay_seal_som" and facts.get('is_lay_seal_som') and is_tt_ok:
                            tien_item = tinh_tien_goc(gia, loai, doanh_thu)
                            ly_do = "Lấy seal/cont sớm 1 ngày"

                        elif ldk == "lam_hang_cang" and facts.get('is_lam_hang_cang') and is_tt_ok:
                            tien_item = tinh_tien_goc(gia, loai, doanh_thu)
                            ly_do = "Làm hàng cảng"    

                        elif ldk == "chuyen_cont_rong" and facts.get('is_cont_rong') and is_tt_ok:
                            nghiep_vu = str(dk.get('nghiep_vu', '')).strip().lower()
                            if nghiep_vu == "trai_tuyen" and not facts.get('is_cont_rong_trai_tuyen'): pass 
                            else:
                                tien_item = tinh_tien_goc(gia, loai, doanh_thu)
                                ly_do = f"{facts.get('loai_cont_rong_text', 'Xử lý Cont rỗng')}"
                        # 👇 THÊM MỚI NHÁNH NÀY: Xử lý đích danh cấu hình JSON "ha_xa_trai_tuyen"
                        elif ldk == "ha_xa_trai_tuyen" and facts.get('is_cont_rong_trai_tuyen') and is_tt_ok:
                            tien_item = tinh_tien_goc(gia, loai, doanh_thu)
                            ly_do = f"{facts.get('loai_cont_rong_text', 'Hạ xả cont rỗng trái tuyến')}"
                                
                        elif ldk == "neo_xe_tai":
                            so_ngay = facts.get('so_ngay_neo_xe', 0)
                            if so_ngay > 0:
                                tien_item = tinh_tien_goc(gia, loai, doanh_thu) * so_ngay
                                ly_do = f"Neo Xe tải {so_ngay} ngày"

                        elif ldk == "neo_xe_tai_nha_may":
                            so_ngay = facts.get('so_ngay_neo_xe_nha_may', 0)
                            if so_ngay > 0:
                                tien_item = tinh_tien_goc(gia, loai, doanh_thu) * so_ngay
                                ly_do = f"Neo Xe tải Nhà máy {so_ngay} ngày"

                        #elif ldk == "neo_cont":
                        #    so_ngay = facts.get('so_ngay_neo_cont', 0)
                        #    if so_ngay > 0:
                        #        tien_item = tinh_tien_goc(gia, loai, doanh_thu) * so_ngay
                        #        ly_do = f"Neo Container {so_ngay} ngày"
                        # 1. TRƯỜNG HỢP CẤU HÌNH BẰNG CHUỖI JSON
                        elif ldk == "neo_cont":
                            so_ngay = facts.get('so_ngay_neo_cont', 0)
                            if so_ngay > 0:
                                # Trích xuất chiều cont từ cấu hình JSON và từ UI truyền vào
                                chieu_dk = str(dk.get('chieu', '')).strip().lower()
                                chieu_fact = str(facts.get('chieu_cont', '')).strip().lower()
                                
                                # Chỉ áp dụng giá nếu không cấu hình chiều, hoặc chiều cấu hình khớp hoàn toàn với thực tế
                                if not chieu_dk or chieu_dk == chieu_fact:
                                    tien_item = tinh_tien_goc(gia, loai, doanh_thu) * so_ngay
                                    ly_do = f"Neo Container {so_ngay} ngày"
                                    # Ghi chú rõ chiều cont để hiển thị log quyết toán
                                    if chieu_dk: 
                                        ly_do += f" (Chiều {chieu_fact.title()})"
                                        ldk_key = f"{ldk}_{chieu_fact}" #
                            
                        elif ldk == "huy_chuyen" and facts.get('is_huy_chuyen'):
                            tien_item = tinh_tien_goc(gia, loai, doanh_thu)
                            ly_do = "Hủy chuyến"
                            
                        elif ldk == "qua_tai_cont" and facts.get('is_overload_cont'):
                            tien_item = tinh_tien_goc(gia, loai, doanh_thu)
                            ly_do = "Quá tải cont"
                        #elif ldk == "hai_quan_kiem_dich" and facts.get('is_luong_do'):
                        #    tien_item = tinh_tien_goc(gia, loai, doanh_thu)
                        #    ly_do = "HQ/Kiểm hóa"
                            
                        elif ldk == "phu_phi_khac" or "khác khu" in ten_pp.lower() or "khac khu" in ten_pp.lower():
                            if facts.get('is_giao_khac_khu'):
                                tien_item = tinh_tien_goc(gia, loai, doanh_thu)
                                ly_do = "Giao khác khu nội bộ"
                            
                    except Exception as e: pass
                else:
                    tl = ten_pp.lower()
                    ldk_key = "text_match_" + tl
                    if "neo xe tải nhà máy" in tl or "neo xe tai nha may" in tl:
                        so_ngay = facts.get('so_ngay_neo_xe_nha_may', 0)
                        if so_ngay > 0:
                            tien_item = tinh_tien_goc(gia, loai, doanh_thu) * so_ngay
                            ly_do = f"Neo Xe tải Nhà máy {so_ngay} ngày"
                    elif "neo xe tải" in tl or "neo xe tai" in tl:
                        so_ngay = facts.get('so_ngay_neo_xe', 0)
                        if so_ngay > 0:
                            tien_item = tinh_tien_goc(gia, loai, doanh_thu) * so_ngay
                            ly_do = f"Neo Xe tải {so_ngay} ngày"
                    # 2. TRƯỜNG HỢP CẤU HÌNH BẰNG TEXT GÕ TAY (Text Match)
                    elif "neo cont" in tl:
                        so_ngay = facts.get('so_ngay_neo_cont', 0)
                        if so_ngay > 0:
                            chieu_fact = str(facts.get('chieu_cont', '')).strip().lower()
                            
                            # Kiểm tra xem tên phụ phí có cấu hình đích danh chữ "nhập" hoặc "xuất" hay không
                            is_match = True
                            if ("nhập" in tl or "nhap" in tl) and chieu_fact != "nhap": is_match = False
                            if ("xuất" in tl or "xuat" in tl) and chieu_fact != "xuat": is_match = False
                            
                            if is_match:
                                tien_item = tinh_tien_goc(gia, loai, doanh_thu) * so_ngay
                                ly_do = f"Neo Container {so_ngay} ngày"
                                if chieu_fact:
                                    ly_do += f" (Chiều {chieu_fact.title()})"
                                    ldk_key = f"text_match_neocont_{chieu_fact}"
                    elif facts.get('is_huy_chuyen') and ("huỷ" in tl or "hủy" in tl):
                        tien_item = tinh_tien_goc(gia, loai, doanh_thu)
                        ly_do = "Hủy chuyến"
                    elif facts.get('is_chu_nhat') and ("chủ nhật" in tl or "chu nhat" in tl):
                        tien_item = tinh_tien_goc(gia, loai, doanh_thu)
                        ly_do = "Phụ thu Chủ Nhật"
                    elif facts.get('is_lay_seal_som') and ("seal sớm" in tl or "seal som" in tl or "trước 1 ngày" in tl):
                        tien_item = tinh_tien_goc(gia, loai, doanh_thu)
                        ly_do = "Lấy seal/cont sớm 1 ngày"
                    # 👇 THÊM MỚI NHÁNH NÀY (Bên dưới lấy seal sớm, bên trên cont rỗng): Bắt chữ "trái tuyến"
                    elif facts.get('is_cont_rong_trai_tuyen') and ("trái tuyến" in tl or "trai tuyen" in tl):
                        tien_item = tinh_tien_goc(gia, loai, doanh_thu)
                        ly_do = f"{facts.get('loai_cont_rong_text', 'Hạ xả cont rỗng trái tuyến')}"

                    elif facts.get('is_cont_rong') and ("cont rỗng" in tl or "cont rong" in tl):
                        tien_item = tinh_tien_goc(gia, loai, doanh_thu)
                        ly_do = f"{facts.get('loai_cont_rong_text', 'Xử lý Cont rỗng')}"
                    elif facts.get('is_giao_khac_khu') and ("khác khu" in tl or "khac khu" in tl):
                        tien_item = tinh_tien_goc(gia, loai, doanh_thu)
                        ly_do = "Giao khác khu nội bộ"
                        
                if tien_item > 0:
                    matched_candidates.append({
                        'ldk': ldk_key,
                        'ten_pp': ten_pp,
                        'tien': tien_item,
                        'ly_do': ly_do,
                        'range_size': range_size
                    })

        final_fees = []
        best_per_ldk = {}
        for cand in matched_candidates:
            c_ldk = cand['ldk']
            if c_ldk == "phu_phi_khac" or c_ldk.startswith("text_match_"):
                final_fees.append(cand)
            else:
                if c_ldk not in best_per_ldk: best_per_ldk[c_ldk] = cand
                else:
                    if cand['range_size'] < best_per_ldk[c_ldk]['range_size']: best_per_ldk[c_ldk] = cand
                        
        for k, v in best_per_ldk.items(): final_fees.append(v)
            
        for f in final_fees:
            tong_tien_tu_dong += f['tien']
            ghi_chu_tu_dong.append(f"{f['ten_pp']}: {f['tien']:,.0f}đ ({f['ly_do']})")
            
    except Exception as e: print(f"Lỗi DB Phụ phí: {e}")
    
    return tong_tien_tu_dong, ghi_chu_tu_dong

# =========================================================================
# BỔ SUNG: HÀM LÕI TÍNH TOÁN PHỤ CẤP TÀI XẾ TỪ MA TRẬN
# =========================================================================
def tinh_phu_cap_tai_xe(db_instance, xe_id, danh_sach_tieu_chi_id):
    if not danh_sach_tieu_chi_id or pd.isna(xe_id) or not xe_id: 
        return 0.0, ""
    try:
        df_xe = db_instance.execute_query("SELECT tai_trong_thiet_ke FROM xe WHERE id = %s", (int(xe_id),))
        if not isinstance(df_xe, pd.DataFrame) or df_xe.empty: return 0.0, ""
        tai_trong = float(df_xe.iloc[0]['tai_trong_thiet_ke'] or 0)
        
        sql_khung = "SELECT id FROM dm_tai_trong_phu_cap WHERE tai_trong_min <= %s AND tai_trong_max >= %s ORDER BY tai_trong_min DESC LIMIT 1"
        df_khung = db_instance.execute_query(sql_khung, (tai_trong, tai_trong))
        if not isinstance(df_khung, pd.DataFrame) or df_khung.empty: return 0.0, ""
        tt_id = int(df_khung.iloc[0]['id'])
        
        format_strs = ','.join(['%s'] * len(danh_sach_tieu_chi_id))
        sql_tien = f"SELECT mt.so_tien, tc.ten_tieu_chi FROM ma_tran_phu_cap mt JOIN dm_tieu_chi_phu_cap tc ON mt.tieu_chi_id = tc.id WHERE mt.tai_trong_id = %s AND mt.tieu_chi_id IN ({format_strs})"
        params = [tt_id] + danh_sach_tieu_chi_id
        df_tien = db_instance.execute_query(sql_tien, tuple(params))
        
        tong_tien = 0.0
        dien_giai = []
        if isinstance(df_tien, pd.DataFrame) and not df_tien.empty:
            for _, r in df_tien.iterrows():
                tong_tien += float(r['so_tien'])
                dien_giai.append(f"{r['ten_tieu_chi']} (+{float(r['so_tien']):,.0f}đ)")
        
        return tong_tien, " | ".join(dien_giai)
    except Exception as e:
        print(f"Lỗi tính phụ cấp: {e}")
        return 0.0, ""
# ==========================================
# TAB 3: QUYẾT TOÁN ĐƠN CHUYẾN (ĐÃ TỐI ƯU HÓA)
# ==========================================
with tab3:
    tao_tieu_de_kem_nut_refresh("📋 Quyết toán và cập nhật chi phí chuyến đi", "ref_tab3")

    @st.fragment
    def vung_thao_tac_quyet_toan_chuyen_di():
        if "reset_chuyen_form" not in st.session_state: 
            st.session_state["reset_chuyen_form"] = 0

            # có bổ sung cd.stt_chuyen_ghep
        sql_load = """
            SELECT cd.id, cd.ngay_chuyen_di, cd.ten_khach_hang, cd.khach_hang_id, cd.xe_id,
                COALESCE(x.bien_so_xe, cd.bien_so_xe_ngoai) AS bien_so_xe, 
                CAST(x.tai_trong_thiet_ke AS FLOAT) AS tai_trong,
                x.quy_cach_thung, cd.ghi_chu,
                COALESCE(nv.ho_ten, cd.tai_xe_ngoai_ten) AS ten_tai_xe, 
                cd.trang_thai_chuyen, cd.doanh_thu, cd.dia_diem_giao_nhan,
                cd.cong_chuyen, cd.tien_them,
                cd.phi_hai_quan, cd.phi_boc_xep, cd.phi_khac, cd.ghi_chu_quyet_toan,
                cd.is_gop_chuyen, cd.stt_chuyen_ghep, cd.is_ve_khuya, cd.khoi_luong_kg, cd.the_tich_cbm,
                cd.is_thue_ngoai, cd.chi_phi_thue_ngoai, cd.hinh_thuc_thanh_toan_ngoai
            FROM chuyen_di cd
            LEFT JOIN xe x ON cd.xe_id = x.id
            LEFT JOIN chuyen_di_tai_xe ctx ON cd.id = ctx.chuyen_di_id AND ctx.loai_tai_xe = 'Tai_Chinh'
            LEFT JOIN nhan_vien nv ON ctx.tai_xe_id = nv.id
            WHERE cd.trang_thai_chuyen IN ('Quyet_Toan','Tao_Moi','Dang_Di')
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
            is_thue_ngoai = bool(row_sel['is_thue_ngoai'])
            
            kh_id_raw = row_sel.get('khach_hang_id')
            ten_kh_qt = row_sel.get('ten_khach_hang')
            kh_id_qt = int(float(kh_id_raw)) if pd.notna(kh_id_raw) and str(kh_id_raw).strip() != "" else None
            
            if not kh_id_qt and pd.notna(ten_kh_qt):
                try:
                    df_find_kh = db.execute_query("SELECT id FROM khach_hang WHERE ten_khach_hang LIKE %s LIMIT 1", (f"%{str(ten_kh_qt).strip()}%",))
                    if isinstance(df_find_kh, pd.DataFrame) and not df_find_kh.empty: 
                        kh_id_qt = int(df_find_kh.iloc[0]['id'])
                except: pass

            # ========================================================
            # 📦 THÊM GIAO DIỆN CHỌN THUỘC TÍNH HÀNG HÓA & CONTAINER
            # ========================================================
            st.markdown("##### 📦 Khai báo Tính chất Hàng hóa & Container")
            col_hh1, col_hh2, col_hh3 = st.columns(3)
            loai_hang_ui = col_hh1.selectbox("Tính chất hàng", options=["Thường", "Nguy hiểm"], key=f"lh_{cd_id}")
            loai_cont_ui = col_hh2.selectbox("Loại Container", options=["Thường", "Lạnh (RF)"], key=f"lc_{cd_id}")
            chieu_cont_ui = col_hh3.selectbox("Chiều Cont", options=["Không phân biệt", "Nhập", "Xuất"], key=f"chieu_{cd_id}")

            dt_state_key = f"cached_dt_{cd_id}_{loai_hang_ui}_{loai_cont_ui}"
            
            if dt_state_key not in st.session_state:
                doanh_thu_db = float(row_sel.get('doanh_thu', 0) or 0.0)
                lo_trinh_hien_tai = str(row_sel.get('dia_diem_giao_nhan', ''))
                # --- KHỞI TẠO CỜ HIỆU ĐỂ BÁO CÁO RA UI ---
                st.session_state[f"has_route_{cd_id}"] = False
                st.session_state[f"tt_tan_{cd_id}"] = 0.0
                if doanh_thu_db == 0 and "➡️" in lo_trinh_hien_tai and kh_id_qt:
                    try:
                        import re
                        parts = lo_trinh_hien_tai.split("➡️")
                        ddi = parts[0].strip()
                        dden = parts[1].strip()
                        
                        sql_rc = """
                            SELECT id, don_gia_cuoc,gia_chuyen_tiep_noi, phan_loai_phuong_tien, loai_xe_quy_cach 
                            FROM rate_cards 
                            WHERE khach_hang_id = %s AND diem_di LIKE %s AND diem_den LIKE %s 
                            ORDER BY id DESC
                        """
                        df_rc = db.execute_query(sql_rc, (kh_id_qt, f"%{ddi}%", f"%{dden}%"))
                        
                        if isinstance(df_rc, pd.DataFrame) and not df_rc.empty:
                            matched_price = 0.0
                            # 2. FIX LỖI SO SÁNH TRỌNG TẢI: Ưu tiên lấy Khối lượng (KG) khách book của riêng mã chuyến này
                            booked_kg = float(row_sel.get('khoi_luong_kg', 0.0) or 0.0)
                            tt_xe_tan = (booked_kg / 1000.0) if booked_kg > 0 else 0.0
                            
                            # Fallback: Chỉ khi Kế toán lúc lên lệnh quên nhập KG thì mới lấy tạm tải trọng xe
                            if tt_xe_tan <= 0:
                                tt_xe_float = float(row_sel.get('tai_trong', 99.0) or 99.0)
                                tt_xe_tan = (tt_xe_float / 1000.0) if tt_xe_float >= 50 else tt_xe_float
                            
                            quy_cach_xe = str(row_sel.get('quy_cach_thung', '')).lower()
                            ghi_chu_chuyen = str(row_sel.get('ghi_chu', '')).lower()
                            text_context = f"{quy_cach_xe} {ghi_chu_chuyen}".replace("_", " ")

                            has_nguy_hiem = (loai_hang_ui == "Nguy hiểm") or ('nguy hiem' in text_context) or ('nguyhiem' in text_context)
                            has_lanh = (loai_cont_ui == "Lạnh (RF)") or ('lạnh' in text_context) or ('lanh' in text_context) or ('rf' in text_context)
                            # 2. BỐC DỮ LIỆU TỪ DATABASE (Đã fix theo đúng schema của bạn)
                            is_ghep = int(row_sel.get('is_gop_chuyen', 0) if pd.notna(row_sel.get('is_gop_chuyen')) else 0)
                            stt_ghep = int(row_sel.get('stt_chuyen_ghep', 1) if pd.notna(row_sel.get('stt_chuyen_ghep')) else 1)

                            for _, rc in df_rc.iterrows():
                                pl_pt_gia = str(rc.get('phan_loai_phuong_tien', '')).strip() 
                                qc_gia = str(rc.get('loai_xe_quy_cach', '')).strip().lower().replace("_", " ")

                                req_nguy_hiem = any(x in qc_gia for x in ['nguy hiem', 'nguyhiem'])
                                req_lanh = any(x in qc_gia for x in ['lạnh', 'lanh', 'rf'])
                                req_thuong = any(x in qc_gia for x in ['thường', 'thuong'])

                                is_prop_match = True
                                if req_nguy_hiem and not has_nguy_hiem: is_prop_match = False
                                if req_lanh and not has_lanh: is_prop_match = False
                                if req_thuong and (has_nguy_hiem or has_lanh): is_prop_match = False

                                if pl_pt_gia == 'Xe_May':
                                    if tt_xe_tan < 1.0 or 'xe may' in text_context or 'xe máy' in text_context:
                                        if is_prop_match:
                                            matched_price = float(rc['don_gia_cuoc'])
                                            break
                                    continue

                                if pl_pt_gia == 'Container':
                                    cont_kws = ['20', '40', '45', 'hc', 'dc','rf'] 
                                    req_kws = [kw for kw in cont_kws if kw in qc_gia]
                                    
                                    if req_kws:
                                        if all(kw in text_context for kw in req_kws) and is_prop_match:
                                            matched_price = float(rc['don_gia_cuoc'])
                                            break
                                    else:
                                        if ('cont' in text_context or tt_xe_tan >= 15) and is_prop_match:
                                            matched_price = float(rc['don_gia_cuoc'])
                                            break
                                    continue

                                if pl_pt_gia in ['Xe_Tai', 'Hang_Le']:
                                    nums_in_str = re.findall(r'\d+\.?\d*', qc_gia)
                                    float_nums = [float(n) for n in nums_in_str]
                                    is_weight_match = False

                                    if len(float_nums) == 2:
                                        if min(float_nums) <= tt_xe_tan <= max(float_nums): is_weight_match = True
                                    elif len(float_nums) == 1:
                                        val = float_nums[0]
                                        if any(op in qc_gia for op in ['<=', 'dưới', 'duoi']):
                                            if tt_xe_tan <= val: is_weight_match = True
                                        elif '<' in qc_gia:
                                            if tt_xe_tan < val: is_weight_match = True
                                        elif any(op in qc_gia for op in ['>=', 'trên', 'tren']):
                                            if tt_xe_tan >= val: is_weight_match = True
                                        elif '>' in qc_gia:
                                            if tt_xe_tan > val: is_weight_match = True
                                        else:
                                            # 🎯 CHỈ SO SÁNH CHÍNH XÁC (KHÔNG TỰ Ý LÀM TRÒN)
                                            if tt_xe_tan == val: is_weight_match = True
                                    elif len(float_nums) == 0:
                                        is_weight_match = True 

                                    if not (is_weight_match and is_prop_match):
                                        continue

                                
                                    # 3. CHỐT GIÁ: Dùng đúng dữ liệu stt_chuyen_ghep từ Database của bạn
                                    gia_goc = float(rc.get('don_gia_cuoc', 0) or 0.0)
                                    gia_tiep_noi = float(rc.get('gia_chuyen_tiep_noi', 0) or 0.0)
                                    
                                    if is_ghep == 1 and stt_ghep > 1:
                                        # Nếu là chuyến thứ 2 trở đi -> Lấy giá tiếp nối. 
                                        # Nếu giá tiếp nối = 0 (chưa thiết lập) -> Fallback lấy giá gốc.
                                        matched_price = gia_tiep_noi if gia_tiep_noi > 0 else gia_goc
                                    else:
                                        # Chuyến đầu tiên (STT = 1) -> Lấy giá gốc
                                        matched_price = gia_goc
                                        
                                    break # Match thành công -> Thoát vòng lặp
                            
                            if matched_price > 0:
                                doanh_thu_db = matched_price
                                
                    except Exception as e: pass 
                
                st.session_state[dt_state_key] = doanh_thu_db

            doanh_thu_hien_tai = st.session_state[dt_state_key]
            has_route_in_db = st.session_state.get(f"has_route_{cd_id}", False)
            tt_xe_tan = st.session_state.get(f"tt_tan_{cd_id}", 0.0)

            with st.form(key=f"form_qt_{st.session_state['reset_chuyen_form']}"):
                st.markdown(f"##### 📍 1. Chi phí vận hành {'[THUÊ NGOÀI]' if is_thue_ngoai else '[NỘI BỘ]'}")
                edit_cong_ty = st.text_input("Tên Khách hàng / Công ty", value=str(row_sel['ten_khach_hang'] or ""))
                
                show_save_rate = False

                if doanh_thu_hien_tai > 0:
                    st.success(f"💡 HỆ THỐNG ĐÃ XÁC NHẬN CƯỚC BẢNG GIÁ: **{doanh_thu_hien_tai:,.0f} VNĐ**")
                elif has_route_in_db:
                    st.warning(f"⚠️ Tuyến đường đã có trong Bảng giá nhưng **lệch tải trọng/quy cách** ({tt_xe_tan} Tấn). Vui lòng tự nhập cước và lưu lại để dùng cho lần sau!")
                    show_save_rate = True
                else:
                    st.warning("⚠️ Tuyến đường này chưa có trong Bảng giá. Vui lòng tự nhập cước vào ô bên dưới:")

                doanh_thu_input = st.text_input(
                    "Doanh thu cước khách (VNĐ)", 
                    value=f"{doanh_thu_hien_tai:,.0f}" if doanh_thu_hien_tai > 0 else "0"
                )

                is_save_to_rc = False
                if show_save_rate:
                    is_save_to_rc = st.checkbox(f"💾 Lưu mức giá này cho tải trọng {tt_xe_tan}T vào Bảng giá (rate_cards)", value=True)

                if not is_thue_ngoai:
                    chi_phi_ngoai_input = "0"
                    hinh_thuc_thanh_toan_ngoai = "Cong_No"
                else:
                    col_n1, col_n2 = st.columns(2)
                    chi_phi_ngoai_input = col_n1.text_input("Chi phí thuê xe ngoài (VNĐ)*", value=f"{float(row_sel['chi_phi_thue_ngoai'] or 0):,.0f}")
                    tt_opts = ["Cong_No", "Tien_Mat"]
                    def_idx = tt_opts.index(row_sel['hinh_thuc_thanh_toan_ngoai']) if pd.notna(row_sel['hinh_thuc_thanh_toan_ngoai']) and row_sel['hinh_thuc_thanh_toan_ngoai'] in tt_opts else 0
                    hinh_thuc_thanh_toan_ngoai = col_n2.selectbox("Hình thức thanh toán", options=tt_opts, index=def_idx, format_func=lambda x: "Công nợ" if x=="Cong_No" else "Tiền mặt")

                st.divider()
                
                st.markdown("##### 🤖 2. Khai báo phát sinh (AI sẽ tự động tính ra Phụ phí)")
                c_f1, c_f2, c_f3 = st.columns(3)
                f_km = c_f1.number_input("🛣️ Số KM đi lố (Phát sinh)", min_value=0.0, step=1.0)
                f_diem = c_f2.number_input("📍 Số điểm giao thêm", min_value=0, step=1)
                f_neo_xe = c_f3.number_input("⏳ Số ngày neo xe tải", min_value=0, step=1)

                c_f4, c_f5, c_f6, c_f7 = st.columns(4)
                f_neo_cont = c_f4.number_input("🧊 Số ngày neo Cont", min_value=0, step=1)
                f_huy = c_f5.checkbox("❌ Khách Hủy chuyến")
                f_boc = c_f6.checkbox("📦 Có bốc xếp")
                f_overload_cont = c_f7.checkbox("🛂 Quá tải container")

                # GIAO DIỆN MỚI CHO CÁC NGHIỆP VỤ CAO CẤP
                c_f8, c_f9, c_f10, c_f11,c_f12 = st.columns(5)
                f_seal = c_f8.checkbox("🔒 Lấy Seal/Cont sớm 1 ngày")
                f_khac_khu = c_f9.checkbox("🏢 Giao khác khu nội bộ")
                cang_opts = ["", "Dong_Nai", "Hiep_Phuoc", "VICT", "Cai_Mep"]
                f_cang = c_f10.selectbox("⚓ Nâng hạ/Qua cảng", options=cang_opts)
                cont_rong_opts = ["Không", "Lấy Cont rỗng", "Hạ Cont rỗng", "Trái tuyến (Lấy/Hạ)"]
                f_cont_rong = c_f11.selectbox("🔄 Xử lý Cont rỗng", options=cont_rong_opts)
                f_lam_hang_cang = c_f12.checkbox("📦 Có làm hàng cảng")
                st.divider()

                # --- BỔ SUNG: KHAI BÁO PHỤ CẤP TÀI XẾ ---
                selected_tc_ids = []
                if not is_thue_ngoai:
                    st.markdown("##### 🎁 3. Khai báo Phụ cấp Tài xế (Theo ma trận tải trọng)")
                    df_tc = db.execute_query("SELECT id, ten_tieu_chi FROM dm_tieu_chi_phu_cap")
                    if isinstance(df_tc, pd.DataFrame) and not df_tc.empty:
                        tc_cols = st.columns(2)
                        for i, r_tc in df_tc.iterrows():
                            if tc_cols[i % 2].checkbox(r_tc['ten_tieu_chi'], key=f"tc_{cd_id}_{r_tc['id']}"):
                                selected_tc_ids.append(int(r_tc['id']))
                    st.divider()

                st.markdown("##### 🧾 4. Quyết toán Phí thủ công & Ghi chú")

                
                col3_1, col3_2, col3_3 = st.columns(3)
                num_hq = col3_1.text_input("Phí Hải Quan/Bến bãi (Nhập tay)", value=f"{float(row_sel['phi_hai_quan'] or 0):,.0f}")
                num_bx = col3_2.text_input("Phí Bốc Xếp (Nhập tay)", value=f"{float(row_sel['phi_boc_xep'] or 0):,.0f}")
                num_k  = col3_3.text_input("Phí Khác (Nhập tay)", value=f"{float(row_sel['phi_khac'] or 0):,.0f}")
                
                gc_hien_thi = "" if pd.isna(row_sel['ghi_chu_quyet_toan']) else str(row_sel['ghi_chu_quyet_toan'])
                edit_gc = st.text_input("Ghi chú quyết toán", value=gc_hien_thi, placeholder="Nhập thêm ghi chú nếu cần...")
                
                st.markdown("##### 🛡️ Xác nhận thao tác")
                xac_nhan_chot = st.checkbox("⚠️ TÔI XÁC NHẬN SỐ LIỆU LÀ HỢP LÝ VÀ ĐỒNG Ý CHỐT SỔ CHUYẾN ĐI.")
                
                b1, b2, b3 = st.columns(3)
                submit_luu  = b1.form_submit_button("💾 LƯU CẬP NHẬT TẠM", type="secondary")
                submit_chot = b2.form_submit_button("🏁 CHỐT SỔ CHUYẾN ĐI", type="primary")
                submit_xoa  = b3.form_submit_button("🗑️ XÓA CHUYẾN ĐI")

                if submit_luu or submit_chot:
                    try:
                        doanh_thu_val = clean_money_val(doanh_thu_input)
                        phi_khac_nhap_tay = clean_money_val(num_k)
                        phi_bx_nhap_tay = clean_money_val(num_bx)
                        phi_hq_nhap_tay = clean_money_val(num_hq)
                        
                        # 🚀 SỬA LỖI: Ưu tiên lấy Khối lượng (KG) Khách book làm mốc so sánh
                        booked_kg = float(row_sel.get('khoi_luong_kg', 0.0) or 0.0)
                        tai_trong_so_sanh_tan = (booked_kg / 1000.0) if booked_kg > 0 else 0.0
                        
                        # Fallback (chỉ kích hoạt nếu Kế toán lúc Book quên nhập Khối lượng)
                        if tai_trong_so_sanh_tan <= 0:
                            raw_tt = float(row_sel.get('tai_trong', 0.0) or 0.0)
                            tai_trong_so_sanh_tan = (raw_tt / 1000.0) if raw_tt >= 50 else raw_tt
                        
                        # [Đoạn ngay_chd, facts_dict... giữ nguyên]
                        
                        # 🚀 LẤY NGÀY CHUYẾN ĐI ĐỂ KIỂM TRA CHỦ NHẬT
                        ngay_chd = row_sel['ngay_chuyen_di']
                        is_chu_nhat = False
                        if pd.notna(ngay_chd):
                            try:
                                if hasattr(ngay_chd, 'weekday'): is_chu_nhat = (ngay_chd.weekday() == 6)
                                else: is_chu_nhat = (pd.to_datetime(ngay_chd).weekday() == 6)
                            except: pass
                        
                        facts_dict = {
                            'so_km_phat_sinh': f_km,
                            'so_diem_giao_them': f_diem,
                            'so_ngay_neo_xe': f_neo_xe,
                            'so_ngay_neo_cont': f_neo_cont,
                            'is_huy_chuyen': f_huy,
                            'is_boc_xep': f_boc,
                            'is_ve_khuya': bool(row_sel['is_ve_khuya']),
                            'is_overload_cont': f_overload_cont,
                            'cang_nang_ha': f_cang,
                            'chieu_cont': 'nhap' if chieu_cont_ui == "Nhập" else ('xuat' if chieu_cont_ui == "Xuất" else ''),
                            'is_lay_seal_som': f_seal,
                            'is_giao_khac_khu': f_khac_khu,
                            'is_cont_rong': (f_cont_rong != "Không"),
                            'is_cont_rong_trai_tuyen': (f_cont_rong == "Trái tuyến (Lấy/Hạ)"),
                            'loai_cont_rong_text': f_cont_rong,
                            'is_lam_hang_cang': f_lam_hang_cang,
                            'is_chu_nhat': is_chu_nhat
                        }
                        
                        tong_phi_ai, chuoi_ghi_chu_ai = rule_engine_calc(kh_id_qt, tai_trong_so_sanh_tan, doanh_thu_val, facts_dict, db)
                        # --- BỔ SUNG: TÍNH TỔNG PHỤ CẤP TÀI XẾ ---
                        tien_phu_cap_tx, chuoi_phu_cap_tx = tinh_phu_cap_tai_xe(db, row_sel.get('xe_id'), selected_tc_ids)
                        tien_them_final = float(row_sel.get('tien_them', 0.0) or 0.0) + tien_phu_cap_tx

                        phi_khac_final = phi_khac_nhap_tay + tong_phi_ai
                        gc_final = str(edit_gc).strip()
                        if chuoi_ghi_chu_ai:
                            gc_final += f" [AI Tự động: {', '.join(chuoi_ghi_chu_ai)}]"
                        if chuoi_phu_cap_tx:
                            # Nối cả tổng tiền và chi tiết phụ cấp vào ghi chú
                            gc_final += f" [Phụ cấp TX: +{tien_phu_cap_tx:,.0f}đ ({chuoi_phu_cap_tx})]"

                        data_dict_thu_cong = {
                            'ten_khach_hang': edit_cong_ty,
                            'doanh_thu': doanh_thu_val, 
                            'chi_phi_thue_ngoai': clean_money_val(chi_phi_ngoai_input),
                            'hinh_thuc_thanh_toan_ngoai': hinh_thuc_thanh_toan_ngoai,
                            'phi_hai_quan': phi_hq_nhap_tay,
                            'phi_boc_xep': phi_bx_nhap_tay,
                            'phi_khac': phi_khac_final,
                            'tien_them': tien_them_final, # Đã tự động cộng tiền phụ cấp
                            'ghi_chu_quyet_toan': gc_final
                        }

                        if submit_chot and not xac_nhan_chot:
                            st.error("✋ HỆ THỐNG ĐÃ CHẶN: Vui lòng tick vào ô 'Tôi xác nhận...' trước khi chốt sổ!")
                        else:
                            # --- AI TỰ ĐỘNG LƯU BẢNG GIÁ NẾU ĐƯỢC CHỌN ---
                            if is_save_to_rc and doanh_thu_val > 0:
                                ddi_save = st.session_state.get(f"ddi_{cd_id}", "")
                                dden_save = st.session_state.get(f"dden_{cd_id}", "")
                                qc_moi = f"{tt_xe_tan}T"
                                
                                sql_insert_rc = """
                                    INSERT INTO rate_cards (khach_hang_id, diem_di, diem_den, phan_loai_phuong_tien, loai_xe_quy_cach, don_gia_cuoc, gia_chuyen_tiep_noi) 
                                    VALUES (%s, %s, %s, %s, %s, %s, 0)
                                """
                                try:
                                    db.execute_non_query(sql_insert_rc, (kh_id_qt, ddi_save, dden_save, 'Hang_Le', qc_moi, doanh_thu_val))
                                    st.toast(f"✅ Đã tự động thêm lộ trình mới cho mức tải {qc_moi} vào Bảng giá!")
                                except Exception as e:
                                    st.error(f"Lỗi khi lưu Bảng giá: {e}")    
                            trang_thai_luu = 'Hoan_Thanh' if submit_chot else row_sel['trang_thai_chuyen']
                            is_ok, msg = settle_trip_transaction(db.pool, data_dict_thu_cong, trang_thai_luu, cd_id)
                            if is_ok:
                                if dt_state_key in st.session_state: del st.session_state[dt_state_key]
                                st.session_state["reset_chuyen_form"] += 1
                                st.success(f"🎉 THÀNH CÔNG! AI đã tính thêm **{tong_phi_ai:,.0f} VNĐ** phụ phí vào Phí Khác!")
                                time.sleep(2)
                                st.rerun()
                            else: st.error(f"❌ Lỗi Database: {msg}")
                    except Exception as ex: st.error(f"❌ Lỗi xử lý dữ liệu: {ex}")

                if submit_xoa:
                    success, msg = delete_trip_safe(db.pool, cd_id)
                    if success:
                        if dt_state_key in st.session_state: del st.session_state[dt_state_key]
                        st.session_state["reset_chuyen_form"] += 1
                        st.success("✅ Đã xóa chuyến đi thành công!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(f"❌ Lỗi xóa chuyến: {msg}")
        else:
            st.info("🎉 Tuyệt vời! Hiện tại không có chuyến đi nào đang chờ quyết toán.")
    vung_thao_tac_quyet_toan_chuyen_di()        

# ==========================================
# TAB 4: SỬA DỮ LIỆU ĐÃ QUYẾT TOÁN (HỖ TRỢ XE NGOÀI)
# ==========================================
with tab4:
    tao_tieu_de_kem_nut_refresh("📋 Sửa dữ liệu chuyến đi đã quyết toán", "ref_tab4")

    @st.fragment
    def vung_thao_tac_sua_quyet_toan():
        if "reset_sqt" not in st.session_state:
            st.session_state["reset_sqt"] = 0
        if "sqt_searched" not in st.session_state:
            st.session_state["sqt_searched"] = False
            
        st.info("Tính năng này dùng để điều chỉnh chi phí, công lương cho các chuyến đã chốt. Dữ liệu chỉ được tải khi bạn bấm 'Tìm Kiếm'.")
        
        col_filter1, col_filter2, col_filter3 = st.columns(3)
        
        with col_filter1:
            ngay_tim_kiem = st.date_input("Chọn ngày chạy", value=datetime.date.today(), key="sqt_date")
            
        with col_filter2:
            loai_tim_kiem = st.radio("Tìm kiếm theo:", ["Theo Xe Nội Bộ", "Theo Tài xế", "Tất cả các chuyến trong ngày"], horizontal=True, key="sqt_type")
            
        with col_filter3:
            if loai_tim_kiem == "Theo Xe Nội Bộ":
                df_xe = db.execute_query("SELECT id, bien_so_xe FROM xe WHERE trang_thai = 'Dang_Hoat_Dong'")
                if isinstance(df_xe, pd.DataFrame) and not df_xe.empty:
                    dict_xe = dict(zip(df_xe['id'], df_xe['bien_so_xe']))
                    doi_tuong_id = st.selectbox("Chọn Xe", options=list(dict_xe.keys()), format_func=lambda x: dict_xe[x], key="sqt_obj_xe")
                else:
                    st.warning("Không có dữ liệu xe"); doi_tuong_id = None
            elif loai_tim_kiem == "Theo Tài xế":
                df_tx = db.execute_query("SELECT id, ho_ten FROM nhan_vien WHERE trang_thai = 'Dang_Lam_Viec'")
                if isinstance(df_tx, pd.DataFrame) and not df_tx.empty:
                    dict_tx = dict(zip(df_tx['id'], df_tx['ho_ten']))
                    doi_tuong_id = st.selectbox("Chọn Tài xế", options=list(dict_tx.keys()), format_func=lambda x: dict_tx[x], key="sqt_obj_tx")
                else:
                    st.warning("Không có dữ liệu tài xế"); doi_tuong_id = None
            else:
                doi_tuong_id = "ALL"

        if st.button("🔍 Tìm Kiếm Dữ Liệu", type="primary", use_container_width=True):
            st.session_state["sqt_searched"] = True
            st.session_state["sqt_date_val"] = ngay_tim_kiem
            st.session_state["sqt_type_val"] = loai_tim_kiem
            st.session_state["sqt_obj_val"] = doi_tuong_id
            
            select_key = f"chon_chuyen_sua_{st.session_state['reset_sqt']}"
            if select_key in st.session_state:
                del st.session_state[select_key]

        st.divider()

        if st.session_state.get("sqt_searched") and st.session_state.get("sqt_obj_val") is not None:
            
            ngay_str = st.session_state["sqt_date_val"].strftime('%Y-%m-%d')
            saved_type = st.session_state["sqt_type_val"]
            saved_obj = st.session_state["sqt_obj_val"]
            
            base_query = """
                SELECT cd.id, cd.dia_diem_giao_nhan, cd.ten_khach_hang, cd.doanh_thu, cd.khoi_luong_kg,
                    cd.cong_chuyen, cd.is_thue_ngoai, cd.chi_phi_thue_ngoai, cd.hinh_thuc_thanh_toan_ngoai,
                    cd.tien_them, cd.phi_hai_quan, cd.phi_boc_xep, cd.phi_khac, cd.ghi_chu_quyet_toan
                FROM chuyen_di cd
            """
            
            if saved_type == "Theo Xe Nội Bộ":
                sql_find_trips = base_query + " WHERE cd.ngay_chuyen_di = %s AND cd.xe_id = %s AND cd.trang_thai_chuyen = 'Hoan_Thanh'"
                df_trips = db.execute_query(sql_find_trips, (ngay_str, saved_obj))
            elif saved_type == "Theo Tài xế":
                sql_find_trips = base_query + """ JOIN chuyen_di_tai_xe ctx ON cd.id = ctx.chuyen_di_id
                                                WHERE cd.ngay_chuyen_di = %s AND ctx.tai_xe_id = %s AND cd.trang_thai_chuyen = 'Hoan_Thanh' """
                df_trips = db.execute_query(sql_find_trips, (ngay_str, saved_obj))
            else:
                sql_find_trips = base_query + " WHERE cd.ngay_chuyen_di = %s AND cd.trang_thai_chuyen = 'Hoan_Thanh'"
                df_trips = db.execute_query(sql_find_trips, (ngay_str,))

            if isinstance(df_trips, pd.DataFrame) and not df_trips.empty:
                dict_trips = {}
                for _, row in df_trips.iterrows():
                    tag = "[NGOÀI]" if row['is_thue_ngoai'] == 1 else "[NỘI BỘ]"
                    label = f"Mã: {row['id']} {tag} | Khách: {row['ten_khach_hang']} | Lộ trình: {row['dia_diem_giao_nhan']}"
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
                        is_thue_ngoai = bool(trip_info['is_thue_ngoai'])
                        
                        with st.form("form_sua_quyet_toan", clear_on_submit=True):
                            st.markdown(f"**Đang sửa dữ liệu chuyến {chuyen_can_sua} {'(THUÊ XE NGOÀI)' if is_thue_ngoai else '(XE NỘI BỘ)'}**")
                            
                            def format_money(val):
                                if pd.isna(val) or val == "": return "0"
                                try: return f"{int(float(val)):,}" 
                                except: return "0"
                                    
                            def parse_money(val_str):
                                clean_str = str(val_str).replace(",", "").replace(".", "").replace(" ", "")
                                try: return float(clean_str)
                                except: return 0.0 

                            c1, c2, c3, c4 = st.columns(4)
                            
                            edit_khoi_kuong = c1.number_input(
                                "Trọng tải Kg", 
                                value=0.0 if pd.isna(trip_info['khoi_luong_kg']) else float(trip_info['khoi_luong_kg']), 
                                step=1.0, key=f"kholuong_{chuyen_can_sua}"
                            )
                            edit_doanh_thu_str = c2.text_input(
                                "Doanh thu chuyến (VNĐ)", 
                                value=format_money(trip_info['doanh_thu']), key=f"doanhthu_{chuyen_can_sua}"
                            )
                            edit_tien_them_str = c3.text_input(
                                "Tiền phụ cấp/thưởng thêm", 
                                value=format_money(trip_info['tien_them']), key=f"them_{chuyen_can_sua}"
                            )
                            
                            if not is_thue_ngoai:
                                edit_cong_str = c4.text_input("Công tài xế (Lương)*", value=format_money(trip_info['cong_chuyen']))
                                
                                #c5, c6 = st.columns(2)
                                #edit_so_lit_xang_str = c5.text_input("Số lít xăng", value=format_money(trip_info['so_lit_xang']))
                                #edit_tien_xang_str = c6.text_input("Tiền xăng", value=format_money(trip_info['tien_xang']))
                                
                                edit_chi_phi_ngoai = "0"
                                edit_thanh_toan_ngoai = "Cong_No"
                            else:
                                edit_chi_phi_ngoai = c4.text_input("Chi phí thuê ngoài (VNĐ)*", value=format_money(trip_info['chi_phi_thue_ngoai']))
                                
                                tt_opts = ["Cong_No", "Tien_Mat"]
                                def_tt_idx = tt_opts.index(trip_info['hinh_thuc_thanh_toan_ngoai']) if pd.notna(trip_info['hinh_thuc_thanh_toan_ngoai']) and trip_info['hinh_thuc_thanh_toan_ngoai'] in tt_opts else 0
                                edit_thanh_toan_ngoai = st.selectbox("Thanh toán thuê xe", tt_opts, index=def_tt_idx, format_func=lambda x: "Công nợ" if x=="Cong_No" else "Tiền mặt")
                                
                                edit_cong_str = "0"

                            c7, c8, c9 = st.columns(3)
                            edit_hai_quan_str = c7.text_input("Phí hải quan", value=format_money(trip_info['phi_hai_quan']))
                            edit_boc_xep_str = c8.text_input("Phí bốc xếp", value=format_money(trip_info['phi_boc_xep']))
                            edit_khac_str = c9.text_input("Phí khác (Luật, cầu đường...)", value=format_money(trip_info['phi_khac']))
                            
                            edit_ghi_chu = st.text_input(
                                "Ghi chú quyết toán (Lý do sửa)", 
                                value="" if pd.isna(trip_info['ghi_chu_quyet_toan']) else str(trip_info['ghi_chu_quyet_toan'])
                            )
                            
                            if st.form_submit_button("💾 Lưu sửa đổi quyết toán", type="primary"):
                                data_update = {
                                    'khoi_luong_kg': edit_khoi_kuong,
                                    'doanh_thu': parse_money(edit_doanh_thu_str),
                                    'tien_them': parse_money(edit_tien_them_str),
                                    'cong_chuyen': parse_money(edit_cong_str),
                                    #'so_lit_xang': parse_money(edit_so_lit_xang_str),
                                    #'tien_xang': parse_money(edit_tien_xang_str),
                                    'chi_phi_thue_ngoai': parse_money(edit_chi_phi_ngoai),
                                    'hinh_thuc_thanh_toan_ngoai': edit_thanh_toan_ngoai,
                                    'phi_hai_quan': parse_money(edit_hai_quan_str),
                                    'phi_boc_xep': parse_money(edit_boc_xep_str),
                                    'phi_khac': parse_money(edit_khac_str),
                                    'ghi_chu_quyet_toan': edit_ghi_chu
                                }
                                
                                is_ok, msg = update_trip_transaction(db.pool, data_chuyen_di=data_update, trang_thai_enum='Hoan_Thanh', chuyen_di_id=chuyen_can_sua)
                                
                                if is_ok:
                                    st.success(f"✅ Đã cập nhật thành công quyết toán cho chuyến {chuyen_can_sua}!")
                                    st.session_state["reset_sqt"] += 1
                                    time.sleep(1.2) 
                                    st.rerun()
                                else:
                                    st.error(f"❌ Lỗi khi lưu: {msg}")
            else:
                st.info("📭 Không tìm thấy chuyến đi nào đã quyết toán khớp với điều kiện tìm kiếm của bạn.")
    vung_thao_tac_sua_quyet_toan()

# ==========================================
# TAB 5: 🤖 TỰ ĐỘNG ĐIỀU XE & EXCEL TOOLS
# ==========================================
with tab5:
    @st.fragment
    def vung_thao_tac_quyet_toan_auto():
        if "export_dieu_xe" not in st.session_state: 
            st.session_state["export_dieu_xe"] = None
            
        st.markdown("#### ⚙️ Trung tâm điều phối đội xe tự động & Xuất lệnh Zalo thủ công")
        st.divider()
        
        st.markdown("##### 📥 1. Tải File Mẫu (Templates) chuẩn của hệ thống")
        col_t1, col_t2 = st.columns(2)
        with col_t1:
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
            buffer_order = io.BytesIO()
            with pd.ExcelWriter(buffer_order, engine='xlsxwriter') as writer: 
                df_tpl_order.to_excel(writer, index=False)
                
            st.download_button(
                label="⬇️ Tải mẫu Excel Điều phối tự động", 
                data=buffer_order.getvalue(), 
                file_name=f"Mau_Dieu_Xe_Tu_Dong_{datetime.date.today().strftime('%d_%m_%Y')}.xlsx",
                use_container_width=True
            )
            
        st.divider()

        st.markdown("##### 🚀 2. Nạp file Excel đơn hàng & Thuật toán điều phối tự động")
        with st.form("form_auto_dispatch_tab5"):
            file_order = st.file_uploader("Chọn file Excel danh sách đơn hàng (.xlsx)", type=["xlsx", "xls"])
            submit_order = st.form_submit_button("🚀 Kiểm tra MST & Chạy thuật toán tự động", type="primary", use_container_width=True)
            
            if submit_order:
                if not file_order: 
                    st.warning("⚠️ Vui lòng tải file Excel đơn hàng lên!")
                else:
                    with st.spinner("⏳ Đang phân tích file Excel và kiểm tra dữ liệu hệ thống..."):
                        try:
                            df_orders = pd.read_excel(file_order, dtype={'MA_SO_THUE': str, 'MA_KHACH_HANG': str,'TEN_KHACH_HANG': str})
                            df_orders.columns = [str(c).strip().upper() for c in df_orders.columns] 
                            df_orders['NGAY_CHAY_CHUAN'] = pd.to_datetime(df_orders['NGAY_CHAY'], dayfirst=True, errors='coerce')
                            
                            df_kh = db.execute_query("SELECT id, ma_khach_hang, ten_khach_hang, ma_so_thue FROM khach_hang")
                            
                            # ========================================================
                            # 🧠 XÂY DỰNG TỪ ĐIỂN TRA CỨU KHÁCH HÀNG 4 TẦNG
                            # ========================================================
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
                                # Làm sạch dữ liệu từ file Excel
                                raw_mst = str(row.get('MA_SO_THUE', '')).strip()
                                mst = raw_mst.lower() if raw_mst.lower() != 'nan' else ""
                                
                                raw_ma_kh = str(row.get('MA_KHACH_HANG', '')).strip()
                                ma_kh = raw_ma_kh.lower() if raw_ma_kh.lower() != 'nan' else ""
                                
                                raw_ten_kh = str(row.get('TEN_KHACH_HANG', '')).strip()
                                ten_kh = raw_ten_kh.lower() if raw_ten_kh.lower() != 'nan' else ""
                                
                                kh_id = None
                                
                                # TẦNG 1 & 2: Tra cứu tuyệt đối bằng Mã (Mã KH / MST)
                                if mst and mst in kh_dict_mst:
                                    kh_id = kh_dict_mst[mst]
                                elif ma_kh and ma_kh in kh_dict_ma:
                                    kh_id = kh_dict_ma[ma_kh]
                                    
                                # TẦNG 3: Tra cứu chính xác bằng Tên (Bỏ qua viết hoa/thường)
                                elif ten_kh and ten_kh in kh_dict_ten:
                                    kh_id = kh_dict_ten[ten_kh]
                                    
                                # TẦNG 4: Tra cứu tương đối bằng Tên (Chứa từ khóa)
                                elif ten_kh and isinstance(df_kh, pd.DataFrame):
                                    matched_ids = []
                                    for _, r in df_kh.iterrows():
                                        db_ten = str(r['ten_khach_hang']).strip().lower()
                                        if db_ten and (ten_kh in db_ten or db_ten in ten_kh):
                                            matched_ids.append(int(r['id']))
                                            
                                    # 🛡️ BẢO VỆ CHỐNG SAI LỆCH DỮ LIỆU
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
                                    # Nhúng ID thực tế vào dòng dữ liệu
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
                                        
                                        # 🚀 TỐI ƯU HÓA: Bốc ID trực tiếp từ biến đã ghim ở nửa trên
                                        kh_id = row.get('DB_KHACH_HANG_ID')
                                        khach_hang_ten = str(row.get('TEN_KHACH_HANG', 'Khách Lẻ')).strip()
                                        dia_chi_kh = str(row.get('DIA_CHI_KHACH_HANG', '')).strip()
                                        
                                        kho_di = str(row.get('DIA_CHI_KHO_DI', '')).strip()
                                        kho_den = str(row.get('DIA_CHI_KHO_DEN', '')).strip()
                                        
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
                                                    "Tài Xế Phụ Trách": xe_phu_hop['ten_tai_xe'], 
                                                    "Số Điện Thoại Tài Xế": xe_phu_hop['sdt_tai_xe'] if pd.notna(xe_phu_hop['sdt_tai_xe']) else "Chưa cập nhật",
                                                    "CCCD Tài Xế": xe_phu_hop['cccd_tai_xe'] if pd.notna(xe_phu_hop['cccd_tai_xe']) else "Chưa cập nhật",
                                                    "Lộ Trình": f"{kho_di} ➡️ {kho_den}"
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
                
                noi_dung_chat = (
                    f"🚛 LỆNH ĐIỀU XE BẢO TÍN\n"
                    f"- Mã chuyến: {row['Mã Chuyến Hệ Thống']}\n"
                    f"- Ngày chạy: {row['Ngày Chạy']}\n"
                    f"- Khách hàng: {row['Khách Hàng']}\n"
                    f"- Địa chỉ KH: {row['Địa Chỉ Khách Hàng']}\n"
                    f"- Biển số xe: {row['Biển Số Xe']}\n"
                    f"- Tài xế: {row['Tài Xế Phụ Trách']} (SĐT: {row['Số Điện Thoại Tài Xế']})\n"
                    f"- CCCD Tài xế: {row['CCCD Tài Xế']}\n"
                    f"- Lộ trình: {row['Lộ Trình']}\n"
                )
                
                danh_sach_zalo.append({
                    "TEN_GROUP": ten_group,
                    "NOI_DUNG_ZALO": noi_dung_chat,
                    **row.to_dict()
                })
            
            df_zalo_export = pd.DataFrame(danh_sach_zalo)
            buffer_export = io.BytesIO()
            with pd.ExcelWriter(buffer_export, engine='xlsxwriter') as writer:
                df_zalo_export.to_excel(writer, index=False, sheet_name="Lenh_Dieu_Xe_ZaloThuCong")
                
            st.divider()
            
            col_btn1, col_btn2 = st.columns([1, 4])
            with col_btn1:
                if st.button("🔄 Reset Màn Hình", use_container_width=True):
                    st.session_state["export_dieu_xe"] = None
                    st.rerun()
            with col_btn2:
                st.download_button(
                    label="⬇️ TẢI FILE EXCEL (CÓ CỘT TEN_GROUP, SĐT, CCCD, ĐỊA CHỈ & ZALO THỦ CÔNG)", 
                    data=buffer_export.getvalue(), 
                    file_name=f"Lenh_Dieu_Xe_ZaloThuCong_{datetime.date.today().strftime('%d_%m_%Y')}.xlsx", 
                    type="primary",
                    use_container_width=True
                )
                        
        st.divider()
        
        st.markdown("##### 📥 1. Tải File Mẫu (Templates) chuẩn của hệ thống")
        col_t1, col_t2 = st.columns(2)
        with col_t1:
            df_tpl_close = pd.DataFrame([{
                "MA_CHUYEN": 1001, 
                "DOANH_THU_CHUYEN": 2000000, 
                "TIEN_CONG_TAI_XE": 300000, 
                "CHI_PHI_THUE_NGOAI": 0,
                "HINH_THUC_THANH_TOAN_NGOAI": "Cong_No",
                "PHI_HAI_QUAN": 0,
                "PHI_BOC_XEP": 100000,
                "PHI_KHAC": 0,
                "SO_KM_PHAT_SINH": 15,
                "SO_DIEM_GIAO_THEM": 1,
                "SO_NGAY_NEO_XE": 0,
                "SO_NGAY_NEO_XE_NHA_MAY": 0,
                "SO_NGAY_NEO_CONT": 0,
                "IS_HUY_CHUYEN": 0,
                "IS_BOC_XEP": 0,
                "IS_VE_KHUYA": 0,
                "IS_OVERLOAD_CONT": 0,
                "CANG_NANG_HA": "Dong_Nai",
                "LOAI_HANG_HOA": "Thường",
                "LOAI_CONT": "Thường",
                "CHIEU_CONT": "Không",
                "LAY_SEAL_SOM": 0,
                "GIAO_KHAC_KHU": 0,
                "CONT_RONG": "Không",
                "DS_PHU_CAP_TAI_XE": "1, 3 (Hoặc gõ chữ: Bốc xếp, Về khuya)", # Cột tên mới
                "GHI_CHU": "Chốt cuối tháng"
            }])
            
            # --- XUẤT 2 SHEET ĐỂ HỖ TRỢ KẾ TOÁN ---
            df_dm_pc = db.execute_query("SELECT id, ten_tieu_chi FROM dm_tieu_chi_phu_cap")
            
            buffer_close = io.BytesIO()
            with pd.ExcelWriter(buffer_close, engine='xlsxwriter') as writer: 
                df_tpl_close.to_excel(writer, index=False, sheet_name="MAU_QUYET_TOAN")
                if isinstance(df_dm_pc, pd.DataFrame) and not df_dm_pc.empty:
                    df_dm_pc.columns = ["ID_PHU_CAP", "TEN_TIEU_CHI_COPPY_SANG_SHEET_1"]
                    df_dm_pc.to_excel(writer, index=False, sheet_name="TỪ ĐIỂN PHỤ CẤP")
                
            st.download_button(
                label="⬇️ Tải mẫu Excel Quyết toán hàng loạt", 
                data=buffer_close.getvalue(), 
                file_name=f"Mau_Quyet_Toan_Tudong_{datetime.date.today().strftime('%d_%m_%Y')}.xlsx",
                use_container_width=True
            )
        
        with st.form("form_mass_close"):
            file_close = st.file_uploader("Chọn file Excel Quyết toán (Đuôi .xlsx, .csv)", type=["xlsx", "xls", "csv"])
            submit_close = st.form_submit_button("🏁 Khóa sổ & Chốt chuyến hàng loạt", type="primary")
            
            if submit_close:
                if not file_close:
                    st.warning("⚠️ Bạn chưa tải file Excel lên!")
                else:
                    with st.spinner("⏳ Đang quét Bảng giá & Phụ phí theo Khối Lượng Book ban đầu..."):
                        try:
                            if file_close.name.endswith('.csv'):
                                df_close = pd.read_csv(file_close)
                            else:
                                df_close = pd.read_excel(file_close)
                                
                            df_close.columns = [str(c).strip().upper() for c in df_close.columns]
                            
                            closed_count = 0
                            error_list = []
                            
                            import re
                            def parse_excel_money(val):
                                if pd.isna(val) or val == "" or val is None: return 0.0
                                try:
                                    if isinstance(val, (int, float)): return float(val)
                                    clean_str = str(val).replace(",", "").replace(" ", "").strip()
                                    match = re.search(r'[-+]?\d*\.\d+|\d+', clean_str)
                                    if match: return float(match.group())
                                    return 0.0
                                except Exception: return 0.0

                            def parse_excel_bool(val):
                                if pd.isna(val) or val == "" or val is None: return False
                                v_str = str(val).replace(".0", "").strip().lower()
                                return v_str in ['1', 'true', 'yes', 'có', 'x', 'v', 'y']

                            for index, r in df_close.iterrows():
                                raw_cid = r.get('MA_CHUYEN')
                                if pd.isna(raw_cid) or str(raw_cid).strip() == "": 
                                    continue 
                                try:
                                    cid = int(float(raw_cid))
                                except ValueError:
                                    continue
                                    
                                try:
                                    sql_check = """
                                        SELECT trang_thai_chuyen, khach_hang_id, ten_khach_hang, 
                                            doanh_thu, dia_diem_giao_nhan, chi_phi_thue_ngoai, 
                                            hinh_thuc_thanh_toan_ngoai, ghi_chu,
                                            ngay_chuyen_di, khoi_luong_kg, xe_id
                                        FROM chuyen_di 
                                        WHERE id = %s
                                    """
                                    df_check = db.execute_query(sql_check, (cid,))
                                    
                                    if not isinstance(df_check, pd.DataFrame) or df_check.empty:
                                        error_list.append(f"❌ Dòng {index + 2} (Mã {cid}): Không tồn tại chuyến đi.")
                                        continue
                                    
                                    row_db = df_check.iloc[0]
                                    trang_thai = row_db['trang_thai_chuyen']
                                    kh_id = int(row_db.get('khach_hang_id')) if pd.notna(row_db.get('khach_hang_id')) else None
                                    ten_khach_hang_db = str(row_db.get('ten_khach_hang', ''))
                                    
                                    if trang_thai == 'Hoan_Thanh':
                                        error_list.append(f"⚠️ Dòng {index + 2} (Mã {cid}): Đã khóa sổ trước đó.")
                                        continue
                                    
                                    booked_kg = float(row_db.get('khoi_luong_kg', 0.0) or 0.0)
                                    tai_trong_so_sanh_tan = booked_kg / 1000.0 if booked_kg > 0 else 0.0

                                    doanh_thu_db = float(row_db.get('doanh_thu', 0.0) or 0.0)
                                    lo_trinh_hien_tai = str(row_db.get('dia_diem_giao_nhan', '')).strip()
                                    
                                    doanh_thu_chuyen = parse_excel_money(r.get('DOANH_THU_CHUYEN'))
                                    if doanh_thu_chuyen == 0: doanh_thu_chuyen = doanh_thu_db
                                        
                                    # ĐỐI CHIẾU RATE CARDS
                                    if doanh_thu_chuyen == 0 and "➡️" in lo_trinh_hien_tai and kh_id:
                                        try:
                                            parts = lo_trinh_hien_tai.split("➡️")
                                            ddi = parts[0].strip()
                                            dden = parts[1].strip()
                                            
                                            sql_rc = """
                                                SELECT id, don_gia_cuoc, phan_loai_phuong_tien, loai_xe_quy_cach 
                                                FROM rate_cards 
                                                WHERE khach_hang_id = %s AND diem_di LIKE %s AND diem_den LIKE %s 
                                                ORDER BY id DESC
                                            """
                                            df_rc = db.execute_query(sql_rc, (kh_id, f"%{ddi}%", f"%{dden}%"))
                                            
                                            if isinstance(df_rc, pd.DataFrame) and not df_rc.empty:
                                                matched_price = 0.0
                                                
                                                loai_hang_excel = str(r.get('LOAI_HANG_HOA', 'Thường')).strip().lower()
                                                loai_cont_excel = str(r.get('LOAI_CONT', 'Thường')).strip().lower()
                                                has_nguy_hiem = 'nguy hiểm' in loai_hang_excel or 'nguy hiem' in loai_hang_excel
                                                has_lanh = 'lạnh' in loai_cont_excel or 'lanh' in loai_cont_excel

                                                for _, rc in df_rc.iterrows():
                                                    pl_pt_gia = str(rc.get('phan_loai_phuong_tien', '')).strip()
                                                    qc_gia = str(rc.get('loai_xe_quy_cach', '')).strip().lower().replace("_", " ")

                                                    req_nguy_hiem = any(x in qc_gia for x in ['nguy hiem', 'nguyhiem'])
                                                    req_lanh = any(x in qc_gia for x in ['lạnh', 'lanh', 'rf'])
                                                    req_thuong = any(x in qc_gia for x in ['thường', 'thuong'])

                                                    is_prop_match = True
                                                    if req_nguy_hiem and not has_nguy_hiem: is_prop_match = False
                                                    if req_lanh and not has_lanh: is_prop_match = False
                                                    if req_thuong and (has_nguy_hiem or has_lanh): is_prop_match = False

                                                    if pl_pt_gia in ['Xe_Tai', 'Hang_Le']:
                                                        nums_in_str = re.findall(r'\d+\.?\d*', qc_gia)
                                                        float_nums = [float(n) for n in nums_in_str]
                                                        is_weight_match = False

                                                        if len(float_nums) == 2:
                                                            if min(float_nums) <= tai_trong_so_sanh_tan <= max(float_nums): is_weight_match = True
                                                        elif len(float_nums) == 1:
                                                            val = float_nums[0]
                                                            if any(op in qc_gia for op in ['<=', 'dưới', 'duoi']) and tai_trong_so_sanh_tan <= val: is_weight_match = True
                                                            elif '<' in qc_gia and tai_trong_so_sanh_tan < val: is_weight_match = True
                                                            elif any(op in qc_gia for op in ['>=', 'trên', 'tren']) and tai_trong_so_sanh_tan >= val: is_weight_match = True
                                                            elif '>' in qc_gia and tai_trong_so_sanh_tan > val: is_weight_match = True
                                                            else:
                                                                if tai_trong_so_sanh_tan == val: is_weight_match = True
                                                        elif len(float_nums) == 0:
                                                            is_weight_match = True

                                                        if is_weight_match and is_prop_match:
                                                            matched_price = float(rc['don_gia_cuoc'])
                                                            break
                                                
                                                if matched_price > 0:
                                                    doanh_thu_chuyen = matched_price
                                        except Exception as ex: pass
                                    
                                    # 🚨 CẢNH BÁO NẾU DOANH THU = 0 (Nguyên nhân làm lọt sổ phụ phí mã 8 và 9)
                                    if doanh_thu_chuyen == 0:
                                        error_list.append(f"⚠️ Dòng {index + 2} (Mã {cid}): Không dò ra Doanh Thu (Khối lượng book {tai_trong_so_sanh_tan}T không khớp Rate Cards). Phụ phí % bị nhân với 0đ = 0đ!")

                                    is_chu_nhat = False
                                    ngay_chd = row_db.get('ngay_chuyen_di')
                                    if pd.notna(ngay_chd):
                                        try:
                                            is_chu_nhat = (pd.to_datetime(ngay_chd).weekday() == 6)
                                        except: pass

                                    chieu_cont_excel = str(r.get('CHIEU_CONT', '')).strip().lower()
                                    chieu_val = 'nhap' if 'nhập' in chieu_cont_excel or 'nhap' in chieu_cont_excel else ('xuat' if 'xuất' in chieu_cont_excel or 'xuat' in chieu_cont_excel else '')
                                    cont_rong_excel = str(r.get('CONT_RONG', 'Không')).strip()
                                    
                                    # 💡 BỔ SUNG CỘT "SO_NGAY_NEO_XE_NHA_MAY" VÀO FACTS
                                    facts = {
                                        'so_km_phat_sinh': parse_excel_money(r.get('SO_KM_PHAT_SINH')),
                                        'so_diem_giao_them': parse_excel_money(r.get('SO_DIEM_GIAO_THEM')),
                                        'so_ngay_neo_xe': parse_excel_money(r.get('SO_NGAY_NEO_XE')),
                                        'so_ngay_neo_xe_nha_may': parse_excel_money(r.get('SO_NGAY_NEO_XE_NHA_MAY')), # <--- THÊM MỚI Ở ĐÂY
                                        'so_ngay_neo_cont': parse_excel_money(r.get('SO_NGAY_NEO_CONT')),
                                        'is_huy_chuyen': parse_excel_bool(r.get('IS_HUY_CHUYEN')),
                                        'is_boc_xep': parse_excel_bool(r.get('IS_BOC_XEP')),
                                        'is_ve_khuya': parse_excel_bool(r.get('IS_VE_KHUYA')),
                                        'is_overload_cont': parse_excel_bool(r.get('IS_OVERLOAD_CONT')),
                                        'cang_nang_ha': str(r.get('CANG_NANG_HA', '')).strip() if pd.notna(r.get('CANG_NANG_HA')) else "",
                                        'chieu_cont': chieu_val,
                                        'is_lay_seal_som': parse_excel_bool(r.get('LAY_SEAL_SOM')),
                                        'is_giao_khac_khu': parse_excel_bool(r.get('GIAO_KHAC_KHU')),
                                        'is_cont_rong': (cont_rong_excel.lower() not in ['không', 'khong', '0', 'nan', '']),
                                        'is_cont_rong_trai_tuyen': ('trái tuyến' in cont_rong_excel.lower() or 'trai tuyen' in cont_rong_excel.lower()),
                                        'loai_cont_rong_text': cont_rong_excel,
                                        'is_chu_nhat': is_chu_nhat
                                    }
                                    
                                    tong_phi_ai, chuoi_ghi_chu_ai = rule_engine_calc(kh_id, tai_trong_so_sanh_tan, doanh_thu_chuyen, facts, db)
                                    
                                    # --- BỔ SUNG LẦN 1: LOAD TỪ ĐIỂN TÊN PHỤ CẤP ĐỂ TÌM KIẾM THÔNG MINH ---
                                    df_tc_db = db.execute_query("SELECT id, ten_tieu_chi FROM dm_tieu_chi_phu_cap")
                                    tc_dict = {}
                                    if isinstance(df_tc_db, pd.DataFrame) and not df_tc_db.empty:
                                        for _, r_tc in df_tc_db.iterrows():
                                            tc_dict[str(r_tc['id'])] = int(r_tc['id'])
                                            tc_dict[str(r_tc['ten_tieu_chi']).strip().lower()] = int(r_tc['id'])

                                    # --- BỔ SUNG LẦN 2: THUẬT TOÁN ĐỌC TÊN / ID TỰ ĐỘNG ---
                                    ds_phu_cap_str = str(r.get('DS_PHU_CAP_TAI_XE', '')).strip()
                                    selected_tc_ids_excel = []
                                    if ds_phu_cap_str and ds_phu_cap_str.lower() not in ['nan', '']:
                                        items = [x.strip() for x in ds_phu_cap_str.split(',')]
                                        for item in items:
                                            # Ưu tiên 1: Tìm xem có khớp ID hoặc tên chính xác tuyệt đối không
                                            if item in tc_dict:
                                                selected_tc_ids_excel.append(tc_dict[item])
                                            else:
                                                # Ưu tiên 2: Khớp chữ tương đối (VD: gõ "Khuya" sẽ tự nhận "Về Khuya 24h")
                                                item_lower = item.lower()
                                                for k_name, v_id in tc_dict.items():
                                                    if not k_name.isdigit() and item_lower in k_name:
                                                        selected_tc_ids_excel.append(v_id)
                                                        break
                                        selected_tc_ids_excel = list(set(selected_tc_ids_excel)) # Lọc trùng lặp

                                    tien_phu_cap_tx, chuoi_phu_cap_tx = tinh_phu_cap_tai_xe(db, row_db.get('xe_id'), selected_tc_ids_excel)
                                    tien_them_final = float(row_db.get('tien_them', 0.0) or 0.0) + tien_phu_cap_tx
                                    
                                    phi_khac_excel = parse_excel_money(r.get('PHI_KHAC'))
                                    tong_phi_khac_final = phi_khac_excel + tong_phi_ai
                                    
                                    ghi_chu_goc = str(r.get('GHI_CHU', '')).strip() if pd.notna(r.get('GHI_CHU')) else ""
                                    if ghi_chu_goc.lower() == 'nan': ghi_chu_goc = ""
                                    if chuoi_ghi_chu_ai: ghi_chu_goc = f"{ghi_chu_goc} [Phụ phí Khách: {', '.join(chuoi_ghi_chu_ai)}]".strip()
                                    if chuoi_phu_cap_tx: ghi_chu_goc = f"{ghi_chu_goc} [Phụ cấp TX: {chuoi_phu_cap_tx}]".strip()

                                    chi_phi_thue_ngoai_val = parse_excel_money(r.get('CHI_PHI_THUE_NGOAI'))
                                    if chi_phi_thue_ngoai_val == 0:
                                        raw_cp = row_db.get('chi_phi_thue_ngoai')
                                        chi_phi_thue_ngoai_val = float(raw_cp) if pd.notna(raw_cp) else 0.0
                                        
                                    hinh_thuc_tt = str(r.get('HINH_THUC_THANH_TOAN_NGOAI', '')).strip()
                                    if not hinh_thuc_tt or hinh_thuc_tt.lower() == 'nan': hinh_thuc_tt = 'Cong_No'

                                    data_dict_excel = {
                                        'ten_khach_hang': ten_khach_hang_db,
                                        'cong_chuyen': parse_excel_money(r.get('TIEN_CONG_TAI_XE')),
                                        'doanh_thu': doanh_thu_chuyen,
                                        'chi_phi_thue_ngoai': chi_phi_thue_ngoai_val,
                                        'hinh_thuc_thanh_toan_ngoai': hinh_thuc_tt,
                                        'phi_hai_quan': parse_excel_money(r.get('PHI_HAI_QUAN')),
                                        'phi_boc_xep': parse_excel_money(r.get('PHI_BOC_XEP')),
                                        'phi_khac': tong_phi_khac_final,
                                        'tien_them': tien_them_final, # Lưu tiền thưởng/phụ cấp tự động  
                                        'ghi_chu_quyet_toan': ghi_chu_goc 
                                    }
                        
                                    success, msg = settle_trip_transaction(db.pool, data_dict_excel, 'Hoan_Thanh', cid)
                                    if success: closed_count += 1
                                    else: error_list.append(f"❌ Dòng {index + 2} (Mã {cid}): Lỗi DB - {msg}")
                                        
                                except Exception as ex:
                                    error_list.append(f"❌ Dòng {index + 2} (Mã {cid}): Lỗi tính toán - {str(ex)}")
                                    
                            if error_list:
                                st.warning(f"⚠️ Đã chốt thành công {closed_count} chuyến. Có {len(error_list)} lỗi/cảnh báo:")
                                for err in error_list: st.error(err)
                            else:
                                if closed_count > 0:
                                    st.success(f"🎉 TUYỆT VỜI! Đã chốt {closed_count} chuyến. Tách biệt thành công Neo xe tải & Neo xe nhà máy!")
                                    time.sleep(2.5)
                                    st.rerun()
                                        
                        except Exception as e:
                            st.error(f"❌ Lỗi đọc file Excel: {str(e)}")
    vung_thao_tac_quyet_toan_auto()                        