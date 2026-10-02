import streamlit as st
import pandas as pd
import datetime
import io, time, re,os
from map_service import MapService
from trip_manager import save_trip_full_process, tao_khach_hang_nhanh, group_trips_transaction, update_trip_full_process, delete_trip_safe
from utils_core import parse_money_input, tao_tieu_de_kem_nut_refresh
from dotenv import load_dotenv
from openpyxl.styles import PatternFill, Border, Side, Font, Alignment

#[api_keys]
#gemini = "value"  : cấu trúc trên cloud toml


# Vẫn load file .env cho môi trường Local
load_dotenv(override=False) 

# =====================================================================
# THUẬT TOÁN QUÉT TÌM GEMINI_API_KEY CHỐNG LỖI (LOCAL & CLOUD)
# =====================================================================
api_key = None

# Bước 1: Thử lấy từ biến môi trường của hệ điều hành (Nếu chạy Local có file .env)
api_key = os.getenv("GEMINI_API_KEY")

# Bước 2: Nếu chưa có, tiến hành quét trong kho Secrets của Streamlit Cloud
if not api_key:
    try:
        # Trường hợp 2A: Quét theo cấu trúc phân nhóm TOML [api_keys] -> gemini
        if "api_keys" in st.secrets and "gemini" in st.secrets["api_keys"]:
            api_key = st.secrets["api_keys"]["gemini"]
            
        # Trường hợp 2B: Quét theo cấu trúc phẳng (đề phòng trường hợp dán thẳng file .env vào Cloud)
        elif "GEMINI_API_KEY" in st.secrets:
            api_key = st.secrets["GEMINI_API_KEY"]
    except Exception:
        pass

# Kiểm tra chốt chặn cuối cùng
if not api_key:
    st.error("Lỗi: Không tìm thấy GEMINI_API_KEY trong hệ thống! Vui lòng kiểm tra lại cấu trúc Secrets trên Cloud.")
else:
    # Khởi tạo Gemini API của bạn tại đây với biến api_key
    pass
# =====================================================================

@st.cache_resource
def get_map_service(): return MapService()

map_srv = get_map_service()
db = st.session_state['db']

# --- HỆ THỐNG CACHE BỘ NHỚ ĐỆM ---
@st.cache_data(ttl=1800, show_spinner=False)
def get_cached_master_data(query, params=None):
    return db.execute_query(query, params)

def clear_master_cache():
    get_cached_master_data.clear()
# ---------------------------------

hide_enter_submit_css = """
<style>
    /* Ẩn hướng dẫn Enter của Streamlit */
    div[data-testid='InputInstructions'] { display: none !important; visibility: hidden !important; }
    
    /* 1. Ẩn hoàn toàn thanh Header mặc định chứa khoảng trắng đỉnh của Streamlit */
    header[data-testid="stHeader"] { 
        display: none !important; 
    }

    /* 2. Kéo tịnh tiến đều tất cả các Tiêu đề (h4, h5) trên toàn bộ App */
    h4, h5 { 
        padding-top: 0.5rem !important; 
        padding-bottom: 0.2rem !important; 
        margin-top: 0px !important; 
        margin-bottom: 5px !important; 
        line-height: 1.2 !important;
    }
    
    /* 3. Ép khoảng cách các khối div chứa markdown sát lại nhau */
    [data-testid="stMarkdownContainer"] {
        margin-bottom: -5px !important;
    }
    
    /* 4. Tối ưu khoảng cách các đường kẻ ngang (Divider) */
    hr { 
        margin-top: 5px !important; 
        margin-bottom: 12px !important; 
    }
    
    /* 5. Ép các dòng bên trong khối Form xích lại gần nhau hơn */
    div[data-testid="stForm"] > div { 
        gap: 0.5rem !important; 
    }
    
    /* 6. Triệt tiêu khoảng đệm và đẩy ngược toàn bộ khối giao diện lên trên */
    .block-container {
        gap: 0.5rem !important;
        padding-top: 0rem !important; 
        margin-top: -2.5rem !important; /* Lực đẩy âm kéo sát lề trên */
    }
    
    /* 7. Xóa bỏ khoảng padding thừa mặc định của thành phần hiển thị ứng dụng */
    [data-testid="stAppViewBlockContainer"] {
        padding-top: 0rem !important;
    }
</style>
"""
st.markdown(hide_enter_submit_css, unsafe_allow_html=True)

STATUS_MAP = {"Tạo Mới": "Tao_Moi", "Đang Đi": "Dang_Di", "Quyết Toán": "Quyet_Toan", "Hoàn Thành": "Hoan_Thanh", "Hủy Chuyến": "Huy_Chuyen"}

st.markdown("<h3 style='text-align: center; color: #0b5394;'>📝 PHÂN HỆ QUẢN LÝ VÀ ĐIỀU PHỐI CHUYẾN ĐI NÂNG CAO</h3>", unsafe_allow_html=True)

st.divider()
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["➕ Tạo/Sửa chuyến ","📋 Ghép chuyến", "➕ Tạo chuyến theo file", "📊 Chuyến đi trong ngày", "📊 Chuyến theo ngày chọn", "⚠️ Chuyển trạng thái xe - Cảnh báo Xe tồn đọng"])

# Ứng dụng Cache lấy toàn bộ Danh mục dùng chung
df_xe_full = get_cached_master_data("SELECT id, bien_so_xe,loai_xe, tai_trong_thiet_ke,dung_tich_cbm, tai_xe_co_dinh_id FROM xe WHERE trang_thai = 'Dang_Hoat_Dong'")
xe_map = {int(r['id']): r for _, r in df_xe_full.iterrows()} if isinstance(df_xe_full, pd.DataFrame) and not df_xe_full.empty else {}

df_tx_full = get_cached_master_data("SELECT id, ho_ten FROM nhan_vien WHERE loai_nhan_vien IN ('Tai_Chinh', 'Tai_Phu') AND trang_thai='Dang_Lam_Viec'")
tx_opts = {int(r['id']): str(r['ho_ten']) for _, r in df_tx_full.iterrows()} if isinstance(df_tx_full, pd.DataFrame) and not df_tx_full.empty else {}

df_kh_full = get_cached_master_data("SELECT id, ma_khach_hang, ten_khach_hang, ma_so_thue, dia_chi FROM khach_hang")
kh_opts = {"NEW": "➕ [Tạo mới] Đăng ký khách hàng ngay tại đây..."} 
kh_diachi_map = {}
if isinstance(df_kh_full, pd.DataFrame) and not df_kh_full.empty:
    for _, r in df_kh_full.iterrows():
        mst = r['ma_so_thue'] if pd.notna(r['ma_so_thue']) and r['ma_so_thue'] != "" else (r['ma_khach_hang'] if pd.notna(r['ma_khach_hang']) else "KHÔNG CÓ MST")
        kh_opts[int(r['id'])] = f"MST: {mst} — {r['ten_khach_hang']}"
        kh_diachi_map[int(r['id'])] = str(r['dia_chi']) if pd.notna(r.get('dia_chi')) else ""

####################################
# ==========================================
# TAB 1: ĐĂNG KÝ, SỬA & XÓA CHUYẾN ĐI THỦ CÔNG
# ==========================================
with tab1:
    try:
        tao_tieu_de_kem_nut_refresh("📋 Đăng ký & Quản lý chuyến đi thủ công", "ref_tab1")
        
        @st.fragment
        def vung_thao_tac_chuyen_di():
            # =================================================================
            # [UX CẢI TIẾN] ĐƯA KHỐI THÔNG BÁO COPY ZALO LÊN NGAY ĐẦU TRANG
            # =================================================================
            if "tn_tai_xe" in st.session_state and "tn_khach" in st.session_state:
                st.markdown("<div style='background-color: #e8f5e9; padding: 15px; border-radius: 8px; border-left: 5px solid #4caf50; margin-bottom: 15px;'>", unsafe_allow_html=True)
                st.success("🎉 HỆ THỐNG ĐÃ LÊN LỆNH THÀNH CÔNG! Copy thông tin dưới đây để gửi Zalo:")
                
                c_msg1, c_msg2 = st.columns(2)
                c_msg1.text_area("📱 Gửi cho Tài xế:", value=st.session_state["tn_tai_xe"], height=160, key="copy_tx")
                c_msg2.text_area("📱 Gửi cho Khách hàng:", value=st.session_state["tn_khach"], height=160, key="copy_kh")
                
                if st.button("✅ Đã copy xong / Đóng thông báo", type="primary", use_container_width=True, key="btn_dong_msg"):
                    del st.session_state["tn_tai_xe"]
                    del st.session_state["tn_khach"]
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
                st.divider()

            # Hàm trích xuất float an toàn
            def safe_float_val(key, data_dict, default=0.0):
                val = data_dict.get(key)
                if pd.isna(val) or str(val).strip() == "" or str(val).strip().lower() == 'nan':
                    return default
                try: return float(val)
                except: return default
                                            
            # Hàm trích xuất số nguyên (ID) an toàn chống crash NaN
            def safe_int_val(key, data_dict, default=None):
                val = data_dict.get(key)
                if pd.isna(val) or str(val).strip() == "" or str(val).strip().lower() == 'nan':
                     return default
                try: return int(float(val))
                except: return default    

            if "api_km" not in st.session_state: st.session_state["api_km"] = 0.0
            if "form_reset_counter" not in st.session_state: st.session_state["form_reset_counter"] = 0

            # ================= CHUẨN BỊ DỮ LIỆU =================
            edit_trip_id = None
            trip_data = {}
            so_cont_val, so_seal_val, loai_cont_val, chieu_cont_val = "", "", "40HC", "Nhập"
            ghi_chu_thucong_val = ""
            default_nghiep_vu_idx = 0 
            
            # Khởi tạo biến quản lý Chuyến Chính - Phụ
            is_chuyen_phu = False
            chuyen_goc_id_val = None
            thong_tin_chuyen_goc = {}
            
            col_mode1, col_mode2 = st.columns([3,1])
            
            with col_mode1:
                mode_action = st.radio(
                    "📌 Chọn hành động:", 
                    ["➕ Tạo chuyến mới", "✏️ Sửa chuyến hiện tại", "🗑️ Xóa chuyến đi"], 
                    horizontal=True, 
                    key=f"tab1_mode_action_{st.session_state['form_reset_counter']}"
                )

                if mode_action == "✏️ Sửa chuyến hiện tại":
                    # Cập nhật query lấy thêm chuyen_goc_id
                    sql_edit_list = "SELECT id, ngay_chuyen_di, COALESCE(ten_khach_hang, 'Khách Lẻ') as ten_khach_hang, chuyen_goc_id FROM chuyen_di WHERE trang_thai_chuyen IN ('Tao_Moi', 'Dang_Di') ORDER BY id DESC"
                    df_trips = db.execute_query(sql_edit_list)
                    
                    if isinstance(df_trips, pd.DataFrame) and not df_trips.empty:
                        trip_options = {}
                        for _, r in df_trips.iterrows():
                            cg = safe_int_val('chuyen_goc_id', r)
                            tag = f"[CHUYẾN PHỤ của #{cg}] " if cg else "[CHUYẾN ĐỘC LẬP/CHÍNH] "
                            trip_options[r['id']] = f"{tag}Mã {r['id']} | Ngày: {r['ngay_chuyen_di']} | Khách: {r['ten_khach_hang']}"
                            
                        edit_trip_id = st.selectbox("🔍 Chọn chuyến đi cần sửa", options=list(trip_options.keys()), format_func=lambda x: trip_options[x], key=f"selectbox_edit_trip_{st.session_state['form_reset_counter']}")
                        
                        if edit_trip_id:
                            df_detail = db.execute_query("SELECT * FROM chuyen_di WHERE id=%s", (edit_trip_id,))
                            if isinstance(df_detail, pd.DataFrame) and not df_detail.empty:
                                trip_data = df_detail.iloc[0].to_dict()
                                
                                # Đọc dữ liệu tài xế
                                df_tx_assigned = db.execute_query("SELECT tai_xe_id FROM chuyen_di_tai_xe WHERE chuyen_di_id=%s AND loai_tai_xe='Tai_Chinh'", (edit_trip_id,))
                                if isinstance(df_tx_assigned, pd.DataFrame) and not df_tx_assigned.empty:
                                    tx_val = df_tx_assigned.iloc[0]['tai_xe_id']
                                    if pd.notna(tx_val):
                                        trip_data['tai_xe_id_assigned'] = int(float(tx_val))
                                        
                                db_ghi_chu = trip_data.get('ghi_chu', '') or ''
                                ghi_chu_thucong_val = db_ghi_chu
                                match = re.search(r'\[CONT:\s*(.*?)\s*\|\s*SEAL:\s*(.*?)\s*\|\s*LOAI:\s*(.*?)\s*\|\s*CHIEU:\s*(.*?)\s*\]', db_ghi_chu)
                                if match:
                                    so_cont_val, so_seal_val, loai_cont_val, chieu_cont_val = match.group(1).strip(), match.group(2).strip(), match.group(3).strip(), match.group(4).strip()
                                    ghi_chu_thucong_val = db_ghi_chu.replace(match.group(0), "").strip()
                                    default_nghiep_vu_idx = 1 
                                
                                # Khôi phục trạng thái chuyến phụ
                                current_cg_id = safe_int_val('chuyen_goc_id', trip_data)
                                if current_cg_id:
                                    is_chuyen_phu = True
                                    chuyen_goc_id_val = current_cg_id

            trip_suffix = f"edit_{edit_trip_id}_{st.session_state['form_reset_counter']}" if edit_trip_id else f"new_{st.session_state['form_reset_counter']}"

            with col_mode2:
                kieu_nghiep_vu = st.radio(
                    "🚛 Phân loại nghiệp vụ:", 
                    ["Nghiệp vụ Xe Tải", "Nghiệp vụ Container"], 
                    horizontal=True, 
                    index=default_nghiep_vu_idx,
                    key=f"tab1_kieu_nghiep_vu_{trip_suffix}"
                )

            # ================= CHẾ ĐỘ: XÓA CHUYẾN ĐI =================
            if mode_action == "🗑️ Xóa chuyến đi":
                st.markdown("#### 🗑️ Xóa chuyến đi an toàn")
                sql_delete_list = """
                    SELECT id, ngay_chuyen_di, COALESCE(ten_khach_hang, 'Khách Lẻ') as ten_khach_hang, trang_thai_chuyen, chuyen_goc_id
                    FROM chuyen_di 
                    WHERE trang_thai_chuyen IN ('Tao_Moi', 'Dang_Di') 
                    ORDER BY id DESC
                """
                df_trips_del = db.execute_query(sql_delete_list)
                if isinstance(df_trips_del, pd.DataFrame) and not df_trips_del.empty:
                    trip_del_opts = {}
                    for _, r in df_trips_del.iterrows():
                        cg = safe_int_val('chuyen_goc_id', r)
                        tag = f"[PHỤ của #{cg}] " if cg else "[CHÍNH] "
                        trip_del_opts[r['id']] = f"{tag}Mã {r['id']} | Ngày: {r['ngay_chuyen_di']} | Khách: {r['ten_khach_hang']}"
                    
                    delete_trip_id = st.selectbox(
                        "🔍 Chọn chuyến đi cần xóa", 
                        options=list(trip_del_opts.keys()), 
                        format_func=lambda x: trip_del_opts[x], 
                        key=f"selectbox_delete_trip_{st.session_state['form_reset_counter']}"
                    )
                    
                    if delete_trip_id:
                        del_row = df_trips_del[df_trips_del['id'] == delete_trip_id].iloc[0]
                        if not safe_int_val('chuyen_goc_id', del_row):
                            st.warning(f"⚠️ CẢNH BÁO: Bạn đang xóa một CHUYẾN CHÍNH. Các chuyến phụ liên quan (nếu có) sẽ bị mất liên kết doanh thu!")
                            
                        if st.button("🗑️ Xác Nhận Xóa Chuyến Đi", type="primary"):
                            with st.spinner("Đang xóa chuyến đi..."):
                                res_del = delete_trip_safe(db.pool, delete_trip_id)
                                if isinstance(res_del, tuple): success, result = res_del
                                else: success, result = (True, res_del) if res_del else (False, "Lỗi xóa cơ sở dữ liệu")
                                    
                            if success:
                                st.toast(f"✅ Đã xóa thành công chuyến đi mã {delete_trip_id}!")
                                for key in ["df_search_nb", "df_search_ngoai", "df_canh_bao"]: st.session_state.pop(key, None)
                                st.session_state["form_reset_counter"] += 1
                                time.sleep(1.2)
                                st.rerun()
                            else: st.error(f"❌ Lỗi khi xóa chuyến đi: {result}")
                else: st.warning("⚠️ Hiện tại không có chuyến đi nào ở trạng thái có thể xóa.")

            # ================= CHẾ ĐỘ: TẠO MỚI HOẶC SỬA CHUYẾN ĐI =================
            else:
                def get_idx(lst, val, default=0): return lst.index(val) if val in lst else default
                st.divider()

                # --- BỔ SUNG LOGIC CHUYẾN CHÍNH - PHỤ ---
                st.markdown("#### 🔗 Liên kết đơn hàng (Phân bổ doanh thu nhiều xe)")
                
                check_phu_ui = st.checkbox("Đánh dấu đây là **[Chuyến Phụ]** (Dùng khi 1 đơn hàng lớn phải điều nhiều xe. Doanh thu sẽ tính bằng 0đ để tránh nhân đôi).", value=is_chuyen_phu, key=f"check_phu_{trip_suffix}")
                
                if check_phu_ui:
                    is_chuyen_phu = True
                    sql_chuyen_chinh = """
                        SELECT id, ten_khach_hang, dia_diem_giao_nhan, khach_hang_id, dia_chi_khach_hang 
                        FROM chuyen_di 
                        WHERE trang_thai_chuyen IN ('Tao_Moi', 'Dang_Di') AND chuyen_goc_id IS NULL
                        ORDER BY id DESC
                    """
                    df_chuyen_chinh = db.execute_query(sql_chuyen_chinh)
                    
                    if isinstance(df_chuyen_chinh, pd.DataFrame) and not df_chuyen_chinh.empty:
                        master_opts = {r['id']: f"Mã Gốc #{r['id']} | Khách: {r['ten_khach_hang']} | Tuyến: {r['dia_diem_giao_nhan']}" for _, r in df_chuyen_chinh.iterrows()}
                        
                        # Khôi phục index nếu đang sửa
                        def_master_idx = list(master_opts.keys()).index(chuyen_goc_id_val) if chuyen_goc_id_val in master_opts else 0
                        
                        chuyen_goc_id_val = st.selectbox("📌 Chọn Chuyến Chính để lấy thông tin:", options=list(master_opts.keys()), index=def_master_idx, format_func=lambda x: master_opts[x], key=f"sel_master_{trip_suffix}")
                        
                        if chuyen_goc_id_val:
                            # Trích xuất thông tin chuyến gốc để khóa UI bên dưới
                            row_goc = df_chuyen_chinh[df_chuyen_chinh['id'] == chuyen_goc_id_val].iloc[0]
                            thong_tin_chuyen_goc = row_goc.to_dict()
                            st.success(f"✅ Đã liên kết. Hệ thống sẽ khóa thông tin Khách Hàng và Lộ Trình theo chuyến gốc #{chuyen_goc_id_val}.")
                    else:
                        st.warning("Không tìm thấy Chuyến Chính nào đang chạy. Vui lòng tạo chuyến chính trước.")
                        is_chuyen_phu = False
                else:
                    is_chuyen_phu = False
                    chuyen_goc_id_val = None

                st.divider()

                # ====================================================================
                # PHẦN 1: THÔNG TIN KHÁCH HÀNG (CÓ KHÓA UI NẾU LÀ CHUYẾN PHỤ)
                # ====================================================================
                df_kh_full = get_cached_master_data("SELECT id, ma_khach_hang, ten_khach_hang, so_dien_thoai, dia_chi, ma_so_thue FROM khach_hang")
                kh_opts = {None: "-- Vui lòng chọn Khách hàng --", "NEW": "➕ [Tạo mới] Đăng ký khách hàng ngay tại đây..."}
                kh_diachi_map = {}
                
                if isinstance(df_kh_full, pd.DataFrame) and not df_kh_full.empty:
                    for _, r in df_kh_full.iterrows():
                        k_id = int(r['id'])
                        ma_kh = r['ma_khach_hang'] if pd.notna(r['ma_khach_hang']) and r['ma_khach_hang'] != "" else "CHƯA CÓ MÃ"
                        kh_opts[k_id] = f"Mã: {ma_kh} — {r['ten_khach_hang']}"
                        kh_diachi_map[k_id] = str(r['dia_chi']) if pd.notna(r.get('dia_chi')) else ""

                st.markdown("#### 1. Thông tin Khách hàng dịch vụ")
                diachi_input_key = f"tab1_dia_chi_kh_input_{trip_suffix}"

                if is_chuyen_phu and thong_tin_chuyen_goc:
                    st.info(f"🔒 Khách hàng kế thừa từ chuyến gốc: **{thong_tin_chuyen_goc.get('ten_khach_hang')}**")
                    c_kh_sel = thong_tin_chuyen_goc.get('khach_hang_id')
                    dia_chi_kh_input = thong_tin_chuyen_goc.get('dia_chi_khach_hang', '')
                    new_ten_kh, new_mst_kh = "", ""
                else:
                    kh_opts_keys = list(kh_opts.keys())
                    default_kh_idx = get_idx(kh_opts_keys, trip_data.get('khach_hang_id'), 0) if mode_action == "✏️ Sửa chuyến hiện tại" else 0
                    
                    
                    def on_khach_hang_change():
                        selected_kh = st.session_state.get(f"tab1_c_kh_sel_{trip_suffix}")
                        if selected_kh and selected_kh != "NEW" and selected_kh != 0:
                            st.session_state[diachi_input_key] = kh_diachi_map.get(selected_kh, "")
                        else:
                            st.session_state[diachi_input_key] = ""

                    c_kh_sel = st.selectbox(
                        "🏢 Chọn Khách hàng (Tìm theo MST hoặc Tên)*", 
                        options=kh_opts_keys, 
                        index=default_kh_idx, 
                        format_func=lambda x: kh_opts[x], 
                        key=f"tab1_c_kh_sel_{trip_suffix}",
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
                # PHẦN 2: THÔNG SỐ HÀNG HÓA & ĐIỀU PHỐI (CHUYẾN PHỤ MẶC ĐỊNH LÀ 0)
                # ====================================================================
                st.markdown(f"#### 2. Thông số Hàng hóa & Phương án điều xe ({kieu_nghiep_vu})")
                
                kg_key = f"input_kg_{trip_suffix}"
                cbm_key = f"input_cbm_{trip_suffix}"
                
                val_kl = safe_float_val('khoi_luong_kg', trip_data, 0.0)
                val_cbm = safe_float_val('the_tich_cbm', trip_data, 0.0)
                
                # Nếu đang là Chuyến Phụ, ưu tiên đổ số 0.0 để tránh tính cước 
                if is_chuyen_phu and mode_action == "➕ Tạo chuyến mới":
                    val_kl, val_cbm = 0.0, 0.0
                
                if kieu_nghiep_vu == "Nghiệp vụ Xe Tải":
                    col_hl1, col_hl2 = st.columns(2)
                    khoi_luong = col_hl1.number_input("📦 Khối lượng (KG)* (Nhập 0 nếu là xe phụ)", min_value=0.0, value=val_kl if val_kl > 0 else None, format="%g", step=1.0, key=kg_key)
                    so_cbm = col_hl2.number_input("🧊 Thể tích (CBM)", min_value=0.0, value=val_cbm if val_cbm > 0 else None, format="%g", step=0.1, key=cbm_key)
                else:
                    c_c1, c_c2 = st.columns(2)
                    so_cont_input = c_c1.text_input("🔢 Số Container", value=so_cont_val, key=f"so_cont_{trip_suffix}")
                    so_seal_input = c_c2.text_input("🔒 Số Seal", value=so_seal_val, key=f"so_seal_{trip_suffix}")
                    
                    c_c3, c_c4, c_c5 = st.columns(3)
                    loai_cont_opts = ["20DC","20HC", "40DC", "40HC", "45HC", "20RF", "40RF", "Khác"]
                    def_loai_idx = loai_cont_opts.index(loai_cont_val) if loai_cont_val in loai_cont_opts else 0
                    loai_cont_input = c_c3.selectbox("🧊 Loại Cont", options=loai_cont_opts, key=f"loai_cont_{trip_suffix}", index=def_loai_idx)
                    
                    chieu_opts = ["Nhập", "Xuất", "Nội Địa", "Chạy Rỗng"]
                    def_chieu_idx = chieu_opts.index(chieu_cont_val) if chieu_cont_val in chieu_opts else 0
                    chieu_cont_input = c_c4.selectbox("🔄 Chiều Hàng", options=chieu_opts, key=f"chieu_cont_{trip_suffix}", index=def_chieu_idx)
                    
                    khoi_luong = c_c5.number_input("⚖️ Trọng lượng hàng (KG)*", min_value=0.0, value=val_kl if val_kl > 0 else None, format="%g", step=1.0, key=kg_key)
                    so_cbm = 0.0 
                
                # Logic xác định xe nội bộ / thuê ngoài (Giữ nguyên)
                if mode_action == "➕ Tạo chuyến mới":
                    is_ngoai_val = 0
                else:
                    is_thue_ngoai_db = trip_data.get('is_thue_ngoai', 0)
                    db_xe_id = trip_data.get('xe_id')
                    if pd.notna(is_thue_ngoai_db) and int(is_thue_ngoai_db) == 1: is_ngoai_val = 1
                    elif pd.notna(db_xe_id) and db_xe_id is not None and int(db_xe_id) > 0: is_ngoai_val = 0
                    else: is_ngoai_val = 1 

                loai_hinh_xe = st.radio(
                    "Chọn hình thức điều xe:", 
                    options=["🚀 Chạy Xe Công Ty", "🤝 Thuê Xe Ngoài"], 
                    index=is_ngoai_val, 
                    horizontal=True, 
                    key=f"tab1_loai_hinh_xe_{trip_suffix}"
                )

                c_xe_sel, tx_id_assign = None, None
                chon_xe_ngoai_dang_chay = "NEW"
                df_ngoai_ban = None
                
                if loai_hinh_xe == "🚀 Chạy Xe Công Ty":
                    st.markdown("##### 🚛 Thông tin Xe & Tài xế Nội bộ")
                    col_xe_1, col_xe_2 = st.columns([1, 1])
                    
                    with col_xe_1:
                        selectbox_xe_key = f"c_xe_sel_out_{trip_suffix}"
                        if kieu_nghiep_vu == "Nghiệp vụ Xe Tải":
                            if st.button("🔍 Tìm xe tự động (Theo KG & CBM)", type="primary", use_container_width=True):
                                safe_khoi_luong = float(khoi_luong or 0.0)
                                safe_so_cbm = float(so_cbm or 0.0)
                                if safe_khoi_luong <= 0 and not is_chuyen_phu:
                                    st.warning("⚠️ Nhập Khối lượng > 0 hoặc đánh dấu là Chuyến Phụ để tìm xe.")
                                else:
                                    sql_xe_ranh = """
                                        SELECT x.id, x.tai_xe_co_dinh_id, x.tai_trong_thiet_ke, x.dung_tich_cbm, x.loai_xe,
                                            COALESCE(SUM(cd.khoi_luong_kg), 0) as da_cho_kg, COALESCE(SUM(cd.the_tich_cbm), 0) as da_cho_cbm
                                        FROM xe x 
                                        LEFT JOIN chuyen_di cd ON x.id = cd.xe_id AND cd.trang_thai_chuyen IN ('Tao_Moi', 'Dang_Di')
                                        WHERE x.trang_thai = 'Dang_Hoat_Dong' AND (LOWER(x.loai_xe) LIKE '%tai%' OR LOWER(x.loai_xe) LIKE '%tải%')
                                        GROUP BY x.id, x.tai_xe_co_dinh_id, x.tai_trong_thiet_ke, x.dung_tich_cbm, x.loai_xe
                                        ORDER BY x.tai_trong_thiet_ke ASC, x.dung_tich_cbm ASC
                                    """
                                    df_xe_ranh = db.execute_query(sql_xe_ranh)
                                    found_xe = None
                                    if isinstance(df_xe_ranh, pd.DataFrame) and not df_xe_ranh.empty:
                                        for _, xe in df_xe_ranh.iterrows():
                                            if pd.isna(xe['tai_xe_co_dinh_id']): continue 
                                            da_cho_kg = float(xe['da_cho_kg'] or 0.0)
                                            cap_kg = float(xe['tai_trong_thiet_ke'] or 0.0) * 1000 - da_cho_kg
                                            # Tìm xe rảnh không cần xét tải trọng nếu là xe phụ (vì = 0)
                                            if (cap_kg >= safe_khoi_luong):
                                                found_xe = int(xe['id'])
                                                break
                                    if found_xe:
                                        st.session_state[selectbox_xe_key] = found_xe
                                        st.toast("✅ Đã tìm thấy xe rảnh và tự động chọn!")
                                    else:
                                        st.error("❌ Không có xe nào đáp ứng đủ tải trọng / thể tích này!")
                        
                        is_ghep_chuyen = st.checkbox("🔗 Hiển thị cả xe đang chạy (Dành cho nghiệp vụ Ghép chuyến)", key=f"check_ghep_{trip_suffix}")
                        
                        sql_busy = "SELECT DISTINCT xe_id FROM chuyen_di WHERE trang_thai_chuyen IN ('Tao_Moi', 'Dang_Di') AND xe_id IS NOT NULL"
                        df_busy = db.execute_query(sql_busy)
                        busy_xe_ids = df_busy['xe_id'].tolist() if isinstance(df_busy, pd.DataFrame) and not df_busy.empty else []

                        xe_dict_opts = {None: "-- Vui lòng chọn Xe Nội Bộ --"}
                        saved_xe_id = safe_int_val('xe_id', trip_data) if mode_action == "✏️ Sửa chuyến hiện tại" else None

                        for k, v in xe_map.items():
                            k_int = int(k)
                            is_busy = k_int in busy_xe_ids
                            is_assigned_to_this = (saved_xe_id == k_int)

                            if not is_ghep_chuyen and is_busy and not is_assigned_to_this: continue
                            
                            if not is_assigned_to_this:
                                loai_xe_db = str(v.get('loai_xe', '')).lower()
                                if kieu_nghiep_vu == "Nghiệp vụ Xe Tải":
                                    if 'tải' not in loai_xe_db and 'tai' not in loai_xe_db: continue
                                else:
                                    if ('tải' in loai_xe_db or 'tai' in loai_xe_db or 'du lịch' in loai_xe_db) and 'đầu kéo' not in loai_xe_db: continue        
                                    
                            tx_id_raw = v.get('tai_xe_co_dinh_id')
                            ten_tx = tx_opts[int(float(tx_id_raw))] if pd.notna(tx_id_raw) and int(float(tx_id_raw)) in tx_opts else "Chưa gán TX"
                            
                            # Đọc an toàn thông số khối và tấn để render ra giao diện
                            ton_val = v.get('tai_trong_thiet_ke') or 0
                            cbm_val = v.get('dung_tich_cbm') or 0

                            if is_busy and not is_assigned_to_this:
                                xe_dict_opts[k_int] = f"🔄 [ĐANG CHẠY] {v['bien_so_xe']} ({ton_val}T - {cbm_val} Khối) | 🧑‍✈️ TX: {ten_tx}"
                            else:
                                xe_dict_opts[k_int] = f"🚛 [SẴN SÀNG] {v['bien_so_xe']} ({ton_val}T - {cbm_val} Khối) | 🧑‍✈️ TX: {ten_tx}"
                            
                        xe_keys = list(xe_dict_opts.keys())
                        default_xe_idx = xe_keys.index(saved_xe_id) if mode_action == "✏️ Sửa chuyến hiện tại" and saved_xe_id in xe_keys else 0
                        
                        c_xe_sel = st.selectbox(
                            "✅ Chọn Xe Nội Bộ*", 
                            options=xe_keys, index=default_xe_idx, format_func=lambda x: xe_dict_opts.get(x, ""), key=selectbox_xe_key
                        )
                        
                        if c_xe_sel is not None:
                            selected_xe_info = xe_map.get(c_xe_sel, {})
                            tx_id_raw = selected_xe_info.get('tai_xe_co_dinh_id') 
                            
                            default_tx_id = None
                            if mode_action == "✏️ Sửa chuyến hiện tại" and edit_trip_id and 'tai_xe_id_assigned' in trip_data and c_xe_sel == saved_xe_id:
                                assigned_tx = trip_data.get('tai_xe_id_assigned')
                                if pd.notna(assigned_tx): default_tx_id = int(float(assigned_tx))
                            elif pd.notna(tx_id_raw) and int(float(tx_id_raw)) in tx_opts:
                                default_tx_id = int(float(tx_id_raw))
                            
                            tx_keys = [None] + list(tx_opts.keys())
                            tx_format = {None: "-- Chưa chọn tài xế --"}
                            tx_format.update(tx_opts)
                            
                            default_idx = tx_keys.index(default_tx_id) if default_tx_id in tx_keys else 0
                            
                            st.markdown("##### 🧑‍✈️️ Phân công Tài xế")
                            tx_id_assign = st.selectbox(
                                "Chọn Tài xế phụ trách thực tế*", 
                                options=tx_keys, index=default_idx, format_func=lambda x: tx_format[x], key=f"chon_tai_xe_{trip_suffix}_{c_xe_sel}"
                            )

                    with col_xe_2:
                        st.markdown("**🔸 Các xe đang được điều động (Tham khảo)**")
                        sql_xe_ban = """
                            SELECT x.bien_so_xe as 'Biển Số',cd.khoi_luong_kg AS 'Trọng tải (kg)',ngay_chuyen_di as 'Ngày đi',
                            COALESCE(nv.ho_ten, 'Chưa gán') as 'Tài Xế', cd.dia_diem_giao_nhan as 'Lộ Trình', cd.trang_thai_chuyen as 'Trạng thái' 
                            FROM chuyen_di cd
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
                else:
                    st.markdown("##### 🤝 Chọn Xe Ngoài Đang Chạy (Nghiệp vụ Ghép Chuyến)")
                    sql_ngoai_ban = """
                        SELECT DISTINCT bien_so_xe_ngoai, ten_doi_tac_ngoai, loai_doi_tac_ngoai, loai_hinh_xe, tai_xe_ngoai_ten, tai_xe_ngoai_cccd, tai_xe_ngoai_sdt
                        FROM chuyen_di
                        WHERE is_thue_ngoai = 1 AND trang_thai_chuyen IN ('Tao_Moi', 'Dang_Di') AND bien_so_xe_ngoai IS NOT NULL AND bien_so_xe_ngoai != ''
                    """
                    df_ngoai_ban = db.execute_query(sql_ngoai_ban)
                    
                    ngoai_opts = {"NEW": "✨ -- Không ghép chuyến / Tạo xe ngoài mới (Nhập ở Bước 4) --"}
                    if isinstance(df_ngoai_ban, pd.DataFrame) and not df_ngoai_ban.empty:
                        for _, r in df_ngoai_ban.iterrows():
                            ngoai_opts[r['bien_so_xe_ngoai']] = f"🔄 [ĐANG CHẠY] BSX: {r['bien_so_xe_ngoai']} | Nhà xe: {r['ten_doi_tac_ngoai']} | TX: {r['tai_xe_ngoai_ten']}"
                    
                    chon_xe_ngoai_dang_chay = st.selectbox(
                        "🔗 Chọn Xe Ngoài có sẵn để tự động điền thông tin:", 
                        options=list(ngoai_opts.keys()), format_func=lambda x: ngoai_opts[x], key=f"chon_xe_ngoai_{trip_suffix}"
                    )

                st.divider()

                # ====================================================================
                # PHẦN 3: LỰA CHỌN LỘ TRÌNH VẬN CHUYỂN
                # ====================================================================
                st.markdown("#### 3. Chi tiết lộ trình vận chuyển")
                
                chon_lo_trinh = None
                diem_dau_val, diem_cuoi_val = "", ""
                
                if is_chuyen_phu and thong_tin_chuyen_goc:
                    st.info("🔒 Lộ trình vận chuyển đã được khóa đồng bộ với chuyến gốc.")
                    lo_trinh_goc = str(thong_tin_chuyen_goc.get('dia_diem_giao_nhan', ''))
                    if "➡️" in lo_trinh_goc:
                        diem_dau_val = lo_trinh_goc.split("➡️")[0].strip()
                        diem_cuoi_val = lo_trinh_goc.split("➡️")[-1].strip()
                        
                    c_lt1, c_lt2 = st.columns(2)
                    diem_dau = c_lt1.text_input("🏠 Địa chỉ bốc hàng*", value=diem_dau_val, disabled=True)
                    diem_cuoi = c_lt2.text_input("🎯 Địa chỉ giao hàng*", value=diem_cuoi_val, disabled=True)
                    chon_lo_trinh = lo_trinh_goc
                else:
                    khach_id_filter = None
                    if c_kh_sel and c_kh_sel != "NEW": khach_id_filter = int(c_kh_sel)
                    elif mode_action == "✏️ Sửa chuyến hiện tại": khach_id_filter = trip_data.get('khach_hang_id')

                    is_hang_ve_db = bool(trip_data.get('is_hang_tra_ve', 0)) if mode_action == "✏️ Sửa chuyến hiện tại" else False
                    is_xe_may_db = (trip_data.get('loai_hinh_xe') == 'Xe_May') if mode_action == "✏️ Sửa chuyến hiện tại" else False
                    
                    col_cb_lt1, col_cb_lt2 = st.columns(2)
                    chieu_hang_ui = col_cb_lt1.radio("🔄 Chọn chiều tuyến đường:", ["Lộ trình Hướng Đi", "Lộ trình Hướng Về"], index=1 if is_hang_ve_db else 0, horizontal=True, key=f"chieu_hang_ui_{trip_suffix}")
                    is_hang_ve_ui = (chieu_hang_ui == "Lộ trình Hướng Về")
                    is_xe_may_ui = col_cb_lt2.checkbox("🏍️ Lộ trình dành cho Xe Máy", value=is_xe_may_db, key=f"is_xe_may_ui_{trip_suffix}")
                    
                    lo_trinh_opts = {None: "-- Vui lòng chọn lộ trình (Tạo mới nếu chưa có) --"}
                    if khach_id_filter:
                        flag_hang_ve = 1 if is_hang_ve_ui else 0
                        sql_rates = """
                            SELECT DISTINCT diem_di, diem_den FROM rate_cards 
                            WHERE khach_hang_id = %s AND is_hang_tra_ve = %s 
                        """
                        if is_xe_may_ui: sql_rates += " AND phan_loai_phuong_tien = 'Xe_May'"
                        else: sql_rates += " AND (phan_loai_phuong_tien != 'Xe_May' OR phan_loai_phuong_tien IS NULL)"
                        sql_rates += " ORDER BY diem_di"
                            
                        df_rates = get_cached_master_data(sql_rates, (khach_id_filter, flag_hang_ve))
                        if isinstance(df_rates, pd.DataFrame) and not df_rates.empty:
                            for _, r in df_rates.iterrows():
                                lt_key = f"{r['diem_di']} ➡️ {r['diem_den']}"
                                lo_trinh_opts[lt_key] = lt_key

                    lo_trinh_db = str(trip_data.get('dia_diem_giao_nhan', ''))
                    lo_trinh_keys = list(lo_trinh_opts.keys())
                    default_lt_idx = lo_trinh_keys.index(lo_trinh_db) if lo_trinh_db in lo_trinh_keys else 0

                    st.info("💡💡 Nếu xe máy thì hãy click checkbox lộ trình cho xe máy ở trên.")
                    chon_lo_trinh = st.selectbox("🗺️ Chọn lộ trình (Tham chiếu từ Bảng Giá)*", options=lo_trinh_keys, index=default_lt_idx, format_func=lambda x: lo_trinh_opts[x], key=f"chon_lo_trinh_out_{trip_suffix}")
                    
                    c_lt1, c_lt2 = st.columns(2)
                    lo_trinh_hien_thi = chon_lo_trinh if chon_lo_trinh is not None else lo_trinh_db
                    
                    if lo_trinh_hien_thi and "➡️" in lo_trinh_hien_thi:
                        parts = lo_trinh_hien_thi.split("➡️")
                        diem_dau_val = parts[0].strip()
                        diem_cuoi_val = parts[-1].strip()
                        
                    diem_dau = c_lt1.text_input("🏠 Địa chỉ bốc hàng*", value=diem_dau_val, disabled=True)
                    diem_cuoi = c_lt2.text_input("🎯 Địa chỉ giao hàng*", value=diem_cuoi_val, disabled=True)
                
                st.divider()

                # ====================================================================
                # PHẦN 4: FORM XÁC NHẬN VÀ LƯU TRỮ
                # ====================================================================
                with st.form(key=f"trip_form_{st.session_state['form_reset_counter']}", clear_on_submit=True):
                    
                    ngoai_bien_so, ngoai_ten_doi_tac, ngoai_loai_dt = "", "", "Nha_Xe"
                    ngoai_ten_tx, ngoai_cccd_tx, ngoai_sdt_tx = "", "", ""
                    
                    if loai_hinh_xe == "🤝 Thuê Xe Ngoài": 
                        st.markdown("##### 🤝 Chi tiết phương tiện & Tài xế thuê ngoài")
                        def_bs, def_dt, def_loai_dt, def_lh, def_tx, def_cccd, def_sdt = "", "", "Nha_Xe", "Xe_Tai", "", "", ""
                        
                        if mode_action == "✏️ Sửa chuyến hiện tại" and trip_data.get('is_thue_ngoai') == 1:
                            def_bs = str(trip_data.get('bien_so_xe_ngoai') or "")
                            def_dt = str(trip_data.get('ten_doi_tac_ngoai') or "")
                            def_loai_dt = str(trip_data.get('loai_doi_tac_ngoai') or "Nha_Xe")
                            def_lh = str(trip_data.get('loai_hinh_xe') or "Xe_Tai")
                            def_tx = str(trip_data.get('tai_xe_ngoai_ten') or "")
                            def_cccd = str(trip_data.get('tai_xe_ngoai_cccd') or "")
                            def_sdt = str(trip_data.get('tai_xe_ngoai_sdt') or "")
                        elif chon_xe_ngoai_dang_chay != "NEW" and df_ngoai_ban is not None:
                            row_sel = df_ngoai_ban[df_ngoai_ban['bien_so_xe_ngoai'] == chon_xe_ngoai_dang_chay].iloc[0]
                            def_bs = str(row_sel['bien_so_xe_ngoai'] or "")
                            def_dt = str(row_sel['ten_doi_tac_ngoai'] or "")
                            def_loai_dt = str(row_sel['loai_doi_tac_ngoai'] or "Nha_Xe")
                            def_lh = str(row_sel['loai_hinh_xe'] or "Xe_Tai")
                            def_tx = str(row_sel['tai_xe_ngoai_ten'] or "")
                            def_cccd = str(row_sel['tai_xe_ngoai_cccd'] or "")
                            def_sdt = str(row_sel['tai_xe_ngoai_sdt'] or "")

                        nx1, nx2, nx3 = st.columns(3)
                        ngoai_bien_so = nx1.text_input("Biển số xe thực tế*", value=def_bs)
                        ngoai_ten_doi_tac = nx2.text_input("Tên Nhà xe / Chủ xe*", value=def_dt)
                        dt_opts = ["Nha_Xe", "Tu_Nhan"]
                        ngoai_loai_dt = nx3.selectbox("Loại đối tác", dt_opts, index=get_idx(dt_opts, def_loai_dt))
                        
                        nx_lh1, nx_ten = st.columns(2)
                        lh_opts = ["Container", "Xe_Tai", "Xe_May"]
                        def_lh_idx = lh_opts.index("Container") if kieu_nghiep_vu == "Nghiệp vụ Container" else (lh_opts.index(def_lh) if def_lh in lh_opts else 1)
                        
                        ngoai_loai_hinh_xe = nx_lh1.selectbox("Phân loại phương tiện ngoài*", options=lh_opts, index=def_lh_idx, format_func=lambda x: "📦 Xe Container" if x == "Container" else ("🚛 Xe Tải" if x == "Xe_Tai" else "🏍️ Xe Máy"))
                        ngoai_ten_tx = nx_ten.text_input("Họ tên Tài xế ngoài*", value=def_tx)
                        
                        nx4, nx5 = st.columns(2)
                        ngoai_cccd_tx = nx4.text_input("CCCD Tài xế ngoài*", value=def_cccd)
                        ngoai_sdt_tx = nx5.text_input("SĐT Tài xế ngoài*", value=def_sdt)
                        st.divider()

                    st.markdown("#### 4. Ngày khởi hành & Chi tiết bổ sung")
                    c3_col, c_stt_col = st.columns(2)
                    db_date = trip_data.get('ngay_chuyen_di', datetime.date.today())
                    if isinstance(db_date, pd.Timestamp): db_date = db_date.date()
                    ngay_di = c3_col.date_input("🗓️ Ngày khởi hành", value=db_date, format="DD/MM/YYYY")
                    
                    st_val = {v: k for k, v in STATUS_MAP.items()}.get(trip_data.get('trang_thai_chuyen', 'Tao_Moi'), "Tạo Mới")
                    trang_thai_ui_value = c_stt_col.selectbox("Trạng thái chuyến đi", options=list(STATUS_MAP.keys()), index=list(STATUS_MAP.keys()).index(st_val))
                    
                    ghi_chu_thucong = st.text_input("Ghi chú bổ sung", value=ghi_chu_thucong_val, key=f"ghi_chu_thucong_key_{trip_suffix}")
                    
                    ngoai_chi_phi_str, ngoai_thanh_toan = "0", "Cong_No"
                    if loai_hinh_xe != "🚀 Chạy Xe Công Ty":
                        nx7, nx8 = st.columns(2)
                        tien_thue = trip_data.get('chi_phi_thue_ngoai', 0)
                        tien_thue_clean = str(int(float(tien_thue))) if pd.notna(tien_thue) and float(tien_thue) > 0 else ""
                        ngoai_chi_phi_str = nx7.text_input("Giá vốn thuê ngoài (VNĐ)*", value=tien_thue_clean, placeholder="0")
                        tt_opts = ["Cong_No", "Tien_Mat"]
                        ngoai_thanh_toan = nx8.selectbox("Hình thức thanh toán ngoài", options=tt_opts, index=get_idx(tt_opts, trip_data.get('hinh_thuc_thanh_toan_ngoai', 'Cong_No')), format_func=lambda x: "Công nợ tháng" if x=="Cong_No" else "Tiền mặt")
                    
                    st.markdown("""
                        <style>
                            div[data-testid="stForm"] button[kind="primary"] {
                                background-color: #d32f2f !important; color: white !important;
                                border: none !important; font-weight: 800 !important; font-size: 16px !important;
                                border-radius: 8px !important; padding: 6px 0px !important; margin-top: -10px !important;
                                box-shadow: 0 4px 6px rgba(211, 47, 47, 0.3) !important; transition: all 0.3s ease !important;
                            }
                            div[data-testid="stForm"] button[kind="primary"]:hover { background-color: #b71c1c !important; transform: translateY(-2px); box-shadow: 0 6px 8px rgba(183, 28, 28, 0.4) !important;}
                        </style>
                    """, unsafe_allow_html=True)
                    
                    col_btn_center = st.columns([1, 2, 1])[1]
                    btn_label = "🔄 LƯU THAY ĐỔI " if mode_action == "✏️ Sửa chuyến hiện tại" else "📲 LƯU VÀ GỬI THÔNG TIN TÀI XẾ"
                    with col_btn_center:
                        submit_send = st.form_submit_button(btn_label, type="primary", use_container_width=True)
                
                # ----------------------------------------------------
                # XỬ LÝ SUBMIT CHÍNH THỨC
                # ----------------------------------------------------
                if submit_send:    
                    if not is_chuyen_phu and chon_lo_trinh is None and mode_action == "➕ Tạo chuyến mới":
                        st.error("❌ HỆ THỐNG CHẶN: Vui lòng chọn lộ trình hợp lệ từ danh sách!")
                        st.stop()
                    elif chon_lo_trinh is None and mode_action == "✏️ Sửa chuyến hiện tại" and (diem_dau == "" or diem_cuoi == ""):
                        st.error("❌ HỆ THỐNG CHẶN: Không có dữ liệu lộ trình. Vui lòng chọn lại lộ trình!")
                        st.stop()
                        
                    if (c_kh_sel is None or c_kh_sel == 0) and not is_chuyen_phu:
                        st.error("❌ Vui lòng chọn Khách hàng hợp lệ trước khi lưu!")
                        st.stop()

                    tx_id_assign_final = None
                    if loai_hinh_xe == "🚀 Chạy Xe Công Ty":
                        if c_xe_sel in (None, 0, "") or tx_id_assign in (None, 0, ""):
                            st.error("❌ Vui lòng chọn Xe nội bộ và Tài xế phụ trách.")
                            st.stop()
                        tx_id_assign_final = int(tx_id_assign)

                    try: gia_von_thue_ngoai = parse_money_input(ngoai_chi_phi_str) if loai_hinh_xe != "🚀 Chạy Xe Công Ty" else 0.0
                    except: st.error("❌ Dữ liệu tiền tệ không hợp lệ."); st.stop()

                    if gia_von_thue_ngoai < 0 or (so_cbm or 0.0) < 0:
                        st.error("❌ Thể tích, Giá vốn thuê ngoài không được âm."); st.stop()
                        
                    if kieu_nghiep_vu == "Nghiệp vụ Container":
                        if not so_cont_input or str(so_cont_input).strip() == "": st.error("❌ Vui lòng nhập Số Container!"); st.stop()
                        if not loai_cont_input: st.error("❌ Vui lòng chọn Loại Container!"); st.stop()
                        if not chieu_cont_input: st.error("❌ Vui lòng chọn Chiều Hàng!"); st.stop()
                        if (khoi_luong or 0.0) <= 0 and not is_chuyen_phu: st.error("❌ Trọng lượng phải > 0!"); st.stop()
                    
                    if (khoi_luong or 0.0) == 0.0 and not is_chuyen_phu:
                        st.error("❌ Khối lượng phải > 0 để quyết toán!"); st.stop()
                    if diem_dau == "" and diem_cuoi == "": st.error("❌ Địa chỉ lấy/giao hàng trống!"); st.stop()        
                    if mode_action == "✏️ Sửa chuyến hiện tại" and not edit_trip_id: st.error("❌ Vui lòng chọn chuyến đi!"); st.stop()
                        
                    khach_id_final, ten_kh_val = None, ""
                    if is_chuyen_phu and thong_tin_chuyen_goc:
                        khach_id_final = safe_int_val('khach_hang_id', thong_tin_chuyen_goc)
                        ten_kh_val = thong_tin_chuyen_goc.get('ten_khach_hang', '')
                    elif c_kh_sel == "NEW":
                        if not new_ten_kh or not new_mst_kh: st.error("❌ Nhập đủ Tên KH và MST!"); st.stop()
                        else:
                            success_kh, k_res = tao_khach_hang_nhanh(db.pool, new_ten_kh, new_sdt_kh, new_zalo_id, new_mst_kh, new_diachi_kh)
                            if success_kh: khach_id_final, ten_kh_val = int(k_res) if k_res else None, new_ten_kh
                            else: st.error(f"❌ Lỗi tạo khách hàng: {k_res}"); st.stop()
                    elif c_kh_sel:
                        khach_id_final = int(c_kh_sel)
                        ten_kh_val = kh_opts[c_kh_sel].split("—")[-1].strip()

                    gc_final = f"[CONT: {so_cont_input} | SEAL: {so_seal_input} | LOAI: {loai_cont_input} | CHIEU: {chieu_cont_input}] {ghi_chu_thucong}".strip() if kieu_nghiep_vu == "Nghiệp vụ Container" else ghi_chu_thucong.strip()

                    data_chuyen_di = {
                        'ngay_chuyen_di': ngay_di.strftime('%Y-%m-%d'),                      
                        'khach_hang_id': khach_id_final, 
                        'ten_khach_hang': ten_kh_val,
                        'dia_chi_khach_hang': str(dia_chi_kh_input),
                        'dia_diem_giao_nhan': f"{diem_dau} ➡️ {diem_cuoi}", 
                        'khoi_luong_kg': float(khoi_luong or 0.0),                          
                        'the_tich_cbm': float(so_cbm or 0.0),                       
                        'trang_thai_chuyen': str(STATUS_MAP[trang_thai_ui_value]),                    
                        'ghi_chu': gc_final,
                        'is_hang_tra_ve': 1 if (not is_chuyen_phu and is_hang_ve_ui) else 0, # Chuyến phụ không kích hoạt cờ chiều về tính cước
                        'loai_hinh_xe': "Container" if kieu_nghiep_vu == "Nghiệp vụ Container" else "Xe_Tai",
                        'chuyen_goc_id': int(chuyen_goc_id_val) if is_chuyen_phu and chuyen_goc_id_val else None
                    }
                    
                    if loai_hinh_xe == "🚀 Chạy Xe Công Ty":
                        data_chuyen_di.update({'xe_id': int(c_xe_sel), 'is_thue_ngoai': 0})
                    else:
                        data_chuyen_di.update({
                            'xe_id': None, 'is_thue_ngoai': 1, 'loai_hinh_xe': str(ngoai_loai_hinh_xe), 
                            'loai_doi_tac_ngoai': str(ngoai_loai_dt), 'ten_doi_tac_ngoai': str(ngoai_ten_doi_tac).upper(),
                            'bien_so_xe_ngoai': str(ngoai_bien_so).upper(), 'tai_xe_ngoai_ten': str(ngoai_ten_tx),
                            'tai_xe_ngoai_cccd': str(ngoai_cccd_tx), 'tai_xe_ngoai_sdt': str(ngoai_sdt_tx),
                            'chi_phi_thue_ngoai': gia_von_thue_ngoai, 'hinh_thuc_thanh_toan_ngoai': str(ngoai_thanh_toan)
                        })
                    
                    with st.spinner("Đang lưu dữ liệu..."):
                        if mode_action == "➕ Tạo chuyến mới":
                            success, result = save_trip_full_process(db.pool, data_chuyen_di, tx_id_assign_final)
                            msg_success = f"✅ Lên lệnh điều xe thành công! Mã chuyến: {result}"
                        else:
                            edit_trip_id_cast = int(edit_trip_id)
                            success, result = update_trip_full_process(db.pool, edit_trip_id_cast, data_chuyen_di, tx_id_assign_final)
                            msg_success = f"✅ Đã cập nhật thành công chuyến đi mã {edit_trip_id_cast}!"
                    
                    if success:
                        st.toast(msg_success, icon="🎉")
                        for key in ["df_search_nb", "df_search_ngoai", "df_canh_bao"]: st.session_state.pop(key, None)
                        
                        if STATUS_MAP[trang_thai_ui_value] == "Tao_Moi":
                            ma_chuyen_gui = result if mode_action == "➕ Tạo chuyến mới" else edit_trip_id_cast
                            if loai_hinh_xe == "🚀 Chạy Xe Công Ty":
                                bien_so_gui = xe_map.get(int(c_xe_sel), {}).get('bien_so_xe', '') if c_xe_sel else ''
                                df_tx = get_cached_master_data("SELECT ho_ten, so_dien_thoai, cccd FROM nhan_vien WHERE id=%s", (int(tx_id_assign),))
                                if isinstance(df_tx, pd.DataFrame) and not df_tx.empty:
                                    ten_tx_gui = str(df_tx.iloc[0]['ho_ten'] or '')
                                    sdt_tx_gui = str(df_tx.iloc[0]['so_dien_thoai'] or '')
                                    cccd_tx_gui = str(df_tx.iloc[0]['cccd'] or '')
                                else:
                                    ten_tx_gui, sdt_tx_gui, cccd_tx_gui = "Chưa cập nhật", "Chưa cập nhật", "Chưa cập nhật"
                            else:
                                bien_so_gui, ten_tx_gui, sdt_tx_gui, cccd_tx_gui = ngoai_bien_so, ngoai_ten_tx, ngoai_sdt_tx, ngoai_cccd_tx
                            
                            ten_kh_rut_gon = re.sub(r'(?i)công ty tnhh\s*|cty tnhh\s*', '', str(ten_kh_val)).strip()
                            diem_dau_rut_gon = re.sub(r'(?i)công ty tnhh\s*|cty tnhh\s*|công ty\s*', '', str(diem_dau)).strip()
                            diem_cuoi_rut_gon = re.sub(r'(?i)công ty tnhh\s*|cty tnhh\s*|cong ty\s*', '', str(diem_cuoi)).strip()
                            
                            msg_ghichu = ""
                            if is_chuyen_phu: msg_ghichu = f"\n- Ghi chú: Chuyến ghép cùng đơn hàng lớn #{chuyen_goc_id_val}"
                            
                            st.session_state["tn_tai_xe"] = f"🚛 Anh, em, chú, cậu vào:\n - Khách hàng: {ten_kh_rut_gon} giao, lấy hàng \n- Lộ trình: {diem_dau_rut_gon} ➡️ {diem_cuoi_rut_gon} \n- Mã chuyến: {ma_chuyen_gui}{msg_ghichu}"
                            st.session_state["tn_khach"] = f"📦 THÔNG TIN TÀI XẾ\n- Tên tài xế: {ten_tx_gui}\n- SĐT: {sdt_tx_gui}\n- CCCD: {cccd_tx_gui}\n- Biển số xe: {bien_so_gui}"

                        st.session_state["tab1_mode_action"] = "➕ Tạo chuyến mới"
                        st.session_state["api_km"] = 0.0

                        # [SỬA TẠI ĐÂY] Lấy khóa an toàn, nếu biến chưa từng được khai báo sẽ trả về None
                        safe_key = locals().get('diachi_input_key')
                        if safe_key and safe_key in st.session_state: 
                            del st.session_state[safe_key]
                            
                        st.session_state["form_reset_counter"] += 1
                        time.sleep(1.2)
                        st.rerun()
                    else: st.error(f"❌ Lỗi Database: {result}")

        vung_thao_tac_chuyen_di()
    except Exception as e:
        st.error(f"❌ Lỗi tải Tab 1: {e}")
##################################################### end of tab1

with tab2:
    try:
        tao_tieu_de_kem_nut_refresh("📋 Danh sách chuyến đi trong ngày và ghép chuyến", "ref_tab2")
        
        @st.fragment
        def vung_thao_tac_hien_thi_chuyen_di():
            with st.expander("🔗 NGHIỆP VỤ GHÉP CHUYẾN / CHUYẾN TIẾP NỐI (Dành cho Điều Phối)", expanded=True):
                st.markdown("💡 **Hướng dẫn:** Bôi đen (chọn) các chuyến đi của **cùng một xe** theo đúng thứ tự lấy hàng.")
                
                
                # CẬP NHẬT: Xử lý an toàn các chuyến chưa gán xe (CHUA_GAN)
                sql_ghep = """
                    SELECT cd.id, cd.ngay_chuyen_di, cd.dia_diem_giao_nhan, 
                           COALESCE(kh.ten_khach_hang, cd.ten_khach_hang) as ten_khach, 
                           COALESCE(x.bien_so_xe, cd.bien_so_xe_ngoai, 'Chưa gán xe') as bien_so_xe, 
                           COALESCE(CAST(cd.xe_id AS CHAR), cd.bien_so_xe_ngoai, 'CHUA_GAN') as identifier_xe
                    FROM chuyen_di cd 
                    LEFT JOIN xe x ON cd.xe_id = x.id 
                    LEFT JOIN khach_hang kh ON cd.khach_hang_id = kh.id
                    WHERE cd.trang_thai_chuyen IN ('Tao_Moi', 'Dang_Di') AND cd.is_gop_chuyen = 0 
                    ORDER BY identifier_xe, cd.id ASC
                """
                df_ghep = db.execute_query(sql_ghep)
                
                if isinstance(df_ghep, pd.DataFrame) and not df_ghep.empty:
                    # BƯỚC 1: Lấy danh sách các xe có chuyến đi (Loại bỏ các chuyến chưa gán xe)
                    xe_dict = {}
                    for _, row in df_ghep.iterrows():
                        if row['identifier_xe'] != 'CHUA_GAN':
                            xe_dict[row['identifier_xe']] = row['bien_so_xe']
                    
                    if not xe_dict:
                        st.info("📭 Các chuyến đi hiện tại chưa được phân công xe cụ thể, không thể thực hiện ghép chuyến.")
                    else:
                        # BƯỚC 2: Cho người dùng chọn Xe trước
                        xe_duoc_chon = st.selectbox(
                            "🚛 1. Chọn phương tiện cần thao tác ghép chuyến:", 
                            options=list(xe_dict.keys()), 
                            format_func=lambda x: f"Biển số xe: {xe_dict[x]}",
                            key="selectbox_xe_ghep"
                        )
                        
                        # BƯỚC 3: Lọc danh sách chuyến đi chỉ thuộc về chiếc xe vừa chọn
                        df_ghep_filtered = df_ghep[df_ghep['identifier_xe'] == xe_duoc_chon]
                        ghep_opts = {r['id']: f"Mã chuyến: {r['id']} | Khách: {r['ten_khach']} | Lộ trình: {r['dia_diem_giao_nhan']}" for _, r in df_ghep_filtered.iterrows()}
                        
                        chuyen_duoc_chon = st.multiselect(
                            f"📌 2. Click để chọn các chuyến đi cần ghép của xe {xe_dict[xe_duoc_chon]}:", 
                            options=list(ghep_opts.keys()), 
                            format_func=lambda x: ghep_opts[x], 
                            key="multiselect_ghep_chuyen_tab2"
                        )
                        
                        # BƯỚC 4: Xử lý Submit
                        if st.button("🔗 XÁC NHẬN GHÉP CHUYẾN", type="primary", key="btn_xac_nhan_ghep_tab2"):
                            if len(chuyen_duoc_chon) < 2: 
                                st.warning("⚠️ Vui lòng chọn ít nhất 2 chuyến đi để tiến hành ghép.")
                            else:
                                # Đoạn check xe trùng nhau đã bị loại bỏ vì UI đã khóa chặt logic lọc theo 1 xe duy nhất
                                success, msg = group_trips_transaction(db.pool, chuyen_duoc_chon, st.session_state.get('username', 'Admin'))
                                if success:
                                    st.toast(msg, icon="🎉")
                                    # Dọn rác cache để các Tab khác cập nhật ngay lập tức
                                    for key in ["df_search_nb", "df_search_ngoai", "df_canh_bao"]:
                                        st.session_state.pop(key, None)
                                    time.sleep(1.2)
                                    st.rerun()
                                else: 
                                    st.error(f"Lỗi hệ thống: {msg}")
                else: 
                    st.info("📭 Không có chuyến đi nào ở trạng thái khả dụng để ghép.")
                    
            st.divider()
            
            try:
                sql_list = """
                    SELECT cd.ma_chuyen_ghep AS 'Mã Nhóm', cd.stt_chuyen_ghep AS 'STT', cd.id AS 'Mã chuyến đi', cd.ngay_chuyen_di AS 'Ngày', 
                    COALESCE(kh.ten_khach_hang, cd.ten_khach_hang) AS 'Khách hàng', COALESCE(x.bien_so_xe, cd.bien_so_xe_ngoai) AS 'Biển Số', 
                    cd.khoi_luong_kg AS 'Trọng tải (kg)', cd.dia_diem_giao_nhan AS 'Lộ trình', cd.trang_thai_chuyen AS 'Trạng thái'
                    FROM chuyen_di cd LEFT JOIN khach_hang kh ON cd.khach_hang_id = kh.id LEFT JOIN xe x ON cd.xe_id = x.id
                    WHERE cd.ngay_chuyen_di = %s ORDER BY cd.ma_chuyen_ghep DESC, cd.stt_chuyen_ghep ASC, cd.id DESC
                """
                df_chuyen = db.execute_query(sql_list, (datetime.date.today().strftime('%Y-%m-%d'),))
                
                if isinstance(df_chuyen, pd.DataFrame) and not df_chuyen.empty:
                    st.dataframe(df_chuyen, use_container_width=True, hide_index=True)
                else: 
                    st.info("Chưa có dữ liệu chuyến đi trong ngày hôm nay.")
                    
            except Exception as e: 
                st.error(f"Lỗi tải danh sách chuyến: {e}")
                
        vung_thao_tac_hien_thi_chuyen_di()
    except Exception as e:
        st.error(f"❌ Lỗi tải Tab2: {e}")



# Tạo file auto book theo file
###################################
with tab3:
    try:
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
                    "DIA_CHI_KHO_DI": "Bình Dương", 
                    "DIA_CHI_KHO_DEN": "Cát Lái",
                    "KHOI_LUONG_KG": 1500, 
                    "THE_TICH_CBM": 5.5, 
                    "GHI_CHU": "Hàng nguyên chuyến"
                }])
                
                # 2. Truy vấn dữ liệu Khách hàng từ Database (Sử dụng Cache)
                sql_kh_export = "SELECT ma_khach_hang, ten_khach_hang, ma_so_thue, so_dien_thoai, dia_chi FROM khach_hang"
                df_kh_export = get_cached_master_data(sql_kh_export)
                
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
                    
                    workbook = writer.book
                    # Tạo format wrap text cho toàn bộ file
                    wrap_format = workbook.add_format({'text_wrap': True, 'valign': 'top'})
                    
                    # --- Format cho sheet Mẫu Book Xe ---
                    worksheet_mau = writer.sheets["Mau_Book_Xe"]
                    # Áp dụng độ rộng phù hợp và wrap text cho cột Ghi Chú (Cột H)
                    worksheet_mau.set_column('A:E', 20) 
                    worksheet_mau.set_column('F:G', 15) 
                    worksheet_mau.set_column('H:H', 50, wrap_format) # Wrap text cho Ghi chú
                    worksheet_mau.set_default_row(30) # Tăng nhẹ chiều cao dòng mặc định

                    # --- Format cho sheet Thông Tin Khách Hàng ---
                    worksheet_kh = writer.sheets["Thong_Tin_Khach_Hang"]
                    worksheet_kh.set_column('A:A', 20)  # Mã Khách Hàng
                    worksheet_kh.set_column('B:B', 45)  # Tên Khách Hàng
                    worksheet_kh.set_column('C:C', 20)  # Mã Số Thuế
                    worksheet_kh.set_column('D:D', 15)  # Số Điện Thoại
                    worksheet_kh.set_column('E:E', 60, wrap_format)  # Địa Chỉ (Wrap text)
                    worksheet_kh.set_default_row(25)
                    
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
            
            is_disabled = file_order is None
            
            submit_order = st.button("🚀 Kiểm tra MST & Chạy thuật toán tự động", type="primary", use_container_width=True, disabled=is_disabled)
            
            if submit_order:
                with st.spinner("⏳ Đang phân tích file Excel và kiểm tra dữ liệu hệ thống..."):
                    try:
                        df_orders = pd.read_excel(file_order, dtype={'MA_SO_THUE': str, 'MA_KHACH_HANG': str,'TEN_KHACH_HANG': str})
                        df_orders.columns = [str(c).strip().upper() for c in df_orders.columns] 
                        
                        # [CẬP NHẬT]: Khử đuôi .0 do Pandas ép kiểu ngầm trên toàn bộ DataFrame file order
                        for col in df_orders.columns:
                            df_orders[col] = df_orders[col].apply(
                                lambda x: re.sub(r'\.0$', '', str(x).strip()) if pd.notna(x) and str(x).strip().lower() != 'nan' else x
                            )
                            
                        df_orders['NGAY_CHAY_CHUAN'] = pd.to_datetime(df_orders['NGAY_CHAY'], dayfirst=True, errors='coerce')
                        
                        # Sử dụng Cache cho danh sách đối chiếu Khách hàng
                        df_kh = get_cached_master_data("SELECT id, ma_khach_hang, ten_khach_hang, ma_so_thue FROM khach_hang")
                        
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
                            # KHÔNG DÙNG CACHE: Trạng thái xe bận rảnh thay đổi liên tục theo từng giây
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
                                # [CẬP NHẬT 1]: Khởi tạo mảng lưu danh sách các đơn không tìm được xe
                                unassigned_orders = [] 
                                
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
                                                "Biển Số Xe": xe_phu_hop['bien_so_xe'],
                                                "Tải Trọng Đã Book (KG)": req_kg,
                                                # [CẬP NHẬT 2]: Ghi nhận CBM nếu lớn hơn 0
                                                "Thể Tích Đã Book (CBM)": req_cbm if req_cbm > 0 else 0,
                                                "Tài Xế Phụ Trách": xe_phu_hop['ten_tai_xe'], 
                                                "Số Điện Thoại Tài Xế": xe_phu_hop['sdt_tai_xe'] if pd.notna(xe_phu_hop['sdt_tai_xe']) else "Chưa cập nhật",
                                                "CCCD Tài Xế": xe_phu_hop['cccd_tai_xe'] if pd.notna(xe_phu_hop['cccd_tai_xe']) else "Chưa cập nhật",
                                                "Lộ Trình": f"{kho_di} ➡️ {kho_den}",
                                                "Ghi Chú": ghi_chu_excel
                                            })
                                    else:
                                        # [CẬP NHẬT 3]: Bắt sự kiện không tìm thấy xe và lưu vào mảng cảnh báo để tiếp tục chạy vòng lặp
                                        cbm_msg = f" và {req_cbm} CBM" if req_cbm > 0 else ""
                                        unassigned_orders.append(f"- **{khach_hang_ten}** ({kho_di} ➡️ {kho_den}): Yêu cầu tải **{req_kg:,.0f} KG**{cbm_msg}")
                                
                                st.session_state["export_dieu_xe"] = pd.DataFrame(danh_sach_xuat_excel)
                                st.session_state["unassigned_orders"] = unassigned_orders
                                
                                # [CẬP NHẬT 4]: Đã xóa st.rerun() để UI render ngay lập tức bảng cảnh báo ở phía dưới
                                    
                    except Exception as e:
                        st.error(f"❌ Lỗi xử lý thuật toán tự động: {str(e)}")

            # [CẬP NHẬT 5]: Hiển thị cảnh báo các đơn không tìm được xe (nếu có)
            if st.session_state.get("unassigned_orders"):
                st.warning(f"⚠️ **CẢNH BÁO:** Không tìm thấy phương tiện nội bộ rảnh rỗi nào đáp ứng đủ điều kiện cho {len(st.session_state['unassigned_orders'])} đơn hàng dưới đây. Vui lòng tạo chuyến thủ công để Thuê xe ngoài hoặc Ghép chuyến:")
                for msg in st.session_state["unassigned_orders"]:
                    st.markdown(msg)

            if st.session_state.get("export_dieu_xe") is not None and not st.session_state["export_dieu_xe"].empty:
                st.toast(f"🎉 Hệ thống đã tự động điều phối thành công {len(st.session_state['export_dieu_xe'])} đơn hàng!")
                st.markdown("### 🖨️ Danh sách chuyến xe điều phối thành công & Hỗ trợ Zalo Thủ Công")
                
                # Format cột CBM cho đẹp (Chỉ hiển thị CBM nếu có giá trị)
                df_display = st.session_state["export_dieu_xe"].copy()
                if 'Thể Tích Đã Book (CBM)' in df_display.columns:
                    df_display['Thể Tích Đã Book (CBM)'] = df_display['Thể Tích Đã Book (CBM)'].apply(lambda x: str(x) if float(x) > 0 else "")
                
                st.dataframe(df_display, use_container_width=True, hide_index=True)
                
                danh_sach_zalo = []
                for _, row in st.session_state["export_dieu_xe"].iterrows():
                    bien_so = str(row['Biển Số Xe']) if pd.notna(row['Biển Số Xe']) else "CHUA_GAN_XE"
                    ten_group = "".join([c for c in bien_so if c.isalnum()]).upper()
                    ghi_chu_row = str(row.get('Ghi Chú', ''))
                    
                    msg_tai_xe = (
                        f"🚛 Mai anh,em,chú,cậu vào:\n"
                        f"- Khách hàng: {row['Khách Hàng']}\n"
                        f"- Lộ trình: {row['Lộ Trình']}\n"
                        f"- Mã chuyến: {row['Mã Chuyến Hệ Thống']}\n"
                        f"- Ngày chạy: {row['Ngày Chạy']}\n"
                        f"- Ghi chú: {ghi_chu_row}"
                    )
                    
                    # [CẬP NHẬT 6]: Tự động thêm thông tin CBM vào tin nhắn Zalo gửi KH nếu có
                    cbm_val = float(row.get('Thể Tích Đã Book (CBM)', 0))
                    cbm_text_kh = f"\n- Thể tích: {cbm_val} CBM" if cbm_val > 0 else ""
                    
                    msg_khach_hang = (
                        f"📦 THÔNG TIN TÀI XẾ VẬN CHUYỂN\n"
                        f"- Tên tài xế: {row['Tài Xế Phụ Trách']}\n"
                        f"- SĐT: {row['Số Điện Thoại Tài Xế']}\n"
                        f"- CCCD: {row['CCCD Tài Xế']}\n"
                        f"- Biển số xe: {row['Biển Số Xe']}\n"
                        f"- Tải trọng: {float(row['Tải Trọng Đã Book (KG)']):,.0f} KG{cbm_text_kh}\n"
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
                
                with pd.ExcelWriter(buffer_export, engine='openpyxl') as writer:
                    df_zalo_export.to_excel(writer, index=False, sheet_name="Lenh_Dieu_Xe_ZaloThuCong")
                    worksheet = writer.sheets["Lenh_Dieu_Xe_ZaloThuCong"]
                    
                    # 1. Định nghĩa các định dạng style (Đỏ, Trắng, Viền mỏng)
                    header_fill = PatternFill(start_color="FF0000", end_color="FF0000", fill_type="solid")
                    header_font = Font(color="FFFFFF", bold=True)
                    thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
                    wrap_alignment = Alignment(wrap_text=True, vertical='top', horizontal='left')
                    center_alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
                    
                    # 2. Định dạng dòng Tiêu đề (Header)
                    for col_num, value in enumerate(df_zalo_export.columns.values):
                        cell = worksheet.cell(row=1, column=col_num + 1)
                        cell.fill = header_fill
                        cell.font = header_font
                        cell.border = thin_border
                        cell.alignment = center_alignment
                        
                    # 3. Định dạng ô dữ liệu (Kẻ viền và wrap text)
                    for row_num in range(2, len(df_zalo_export) + 2):
                        # Tăng chiều cao của tất cả các dòng dữ liệu để chứa nội dung nhắn tin Zalo dài
                        worksheet.row_dimensions[row_num].height = 100 
                        
                        for col_num in range(1, len(df_zalo_export.columns) + 1):
                            cell = worksheet.cell(row=row_num, column=col_num)
                            cell.border = thin_border
                            
                            # Cột thứ 2 (GUI_THONG_TIN_TAI_XE) và Cột 3 (GUI_THONG_TIN_KHACH_HANG) áp dụng xuống dòng
                            if col_num in [2, 3]:
                                cell.alignment = wrap_alignment
                            else:
                                cell.alignment = Alignment(vertical='top') # Căn trên cho tất cả các cột khác
                                
                    # 4. Điều chỉnh độ rộng cột
                    worksheet.column_dimensions['A'].width = 15  # TEN_GROUP
                    worksheet.column_dimensions['B'].width = 50  # GUI_THONG_TIN_TAI_XE
                    worksheet.column_dimensions['C'].width = 50  # GUI_THONG_TIN_KHACH_HANG
                    
                st.divider()
                
                col_btn1, col_btn2 = st.columns([1, 4])
                with col_btn1:
                    if st.button("🔄 Reset Màn Hình", use_container_width=True):
                        st.session_state["export_dieu_xe"] = None
                        st.session_state.pop("unassigned_orders", None)
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
    except Exception as e:
        st.error(f"❌ Lỗi tải Tab3 : {e}")
# # ---------------------------------------------------------
# TAB 4: BẢNG ĐIỀU PHỐI CHUYẾN ĐI TRONG NGÀY (DẠNG KANBAN HTML CARDS)
# ---------------------------------------------------------
with tab4:
    try:
        tao_tieu_de_kem_nut_refresh("🗂️ Bảng điều phối chuyến đi & Quản lý đội xe", "ref_ds_chuyen")
        
        @st.fragment
        def vung_thao_tac_quan_ly_chuyen_di():
            try:
                ngay_hom_nay = datetime.date.today().strftime('%Y-%m-%d')
                
                # 1. Truy vấn các chuyến đi: Bao gồm chuyến trong ngày VÀ các chuyến tồn đọng chưa hoàn thành từ trước
                sql_kanban = """
                    SELECT 
                        cd.id AS ma_chuyen, 
                        cd.ngay_chuyen_di, 
                        COALESCE(kh.ten_khach_hang, cd.ten_khach_hang) AS khach_hang,
                        COALESCE(x.bien_so_xe, cd.bien_so_xe_ngoai, 'Chưa gán xe') AS bien_so, 
                        COALESCE(nv.ho_ten, cd.tai_xe_ngoai_ten, 'Chưa gán TX') AS tai_xe, 
                        cd.dia_diem_giao_nhan AS lo_trinh, 
                        cd.khoi_luong_kg AS trong_tai, 
                        cd.trang_thai_chuyen AS trang_thai,
                        cd.is_gop_chuyen,
                        cd.is_thue_ngoai,
                        cd.xe_id
                    FROM chuyen_di cd 
                    LEFT JOIN xe x ON cd.xe_id = x.id
                    LEFT JOIN khach_hang kh ON cd.khach_hang_id = kh.id
                    LEFT JOIN chuyen_di_tai_xe cdtx ON cd.id = cdtx.chuyen_di_id AND cdtx.loai_tai_xe = 'Tai_Chinh'
                    LEFT JOIN nhan_vien nv ON cdtx.tai_xe_id = nv.id 
                    WHERE cd.ngay_chuyen_di = %s 
                       OR (cd.trang_thai_chuyen NOT IN ('Hoan_Thanh', 'Huy_Chuyen') AND cd.ngay_chuyen_di < %s)
                    ORDER BY cd.ngay_chuyen_di DESC, cd.id DESC
                """
                df_kanban = db.execute_query(sql_kanban, (ngay_hom_nay, ngay_hom_nay))

                # 2. Truy vấn danh sách toàn bộ xe đang hoạt động trong hệ thống
                sql_all_xe = "SELECT id, bien_so_xe, tai_trong_thiet_ke FROM xe WHERE trang_thai = 'Dang_Hoat_Dong'"
                df_all_xe = db.execute_query(sql_all_xe)

                if (isinstance(df_kanban, pd.DataFrame) and not df_kanban.empty) or (isinstance(df_all_xe, pd.DataFrame) and not df_all_xe.empty):
                    st.markdown("##### 🚛 TIẾN ĐỘ VẬN HÀNH & TRẠNG THÁI ĐẦU XE")
                    
                    # Chia 3 cột: Tạo Mới, Hoàn Thành, Xe Trống
                    c_tao_moi, c_hoan_thanh, c_xe_trong = st.columns(3)
                    
                    # Hàm rút gọn chuỗi tên Khách hàng và Lộ trình giống thông báo tài xế
                    # [CẬP NHẬT]: Hàm rút gọn thông tin an toàn chống chuỗi 'nan'
                    def rut_gon_thong_tin(text):
                        if pd.isna(text) or str(text).strip() == "" or str(text).strip().lower() == 'nan': 
                            return "Chưa cập nhật"
                        # Loại bỏ các từ khóa công ty rườm rà không phân biệt chữ hoa/thường
                        clean_text = re.sub(r'(?i)công ty tnhh\s*|cty tnhh\s*|công ty\s*|cty\s*', '', str(text))
                        return clean_text.strip()

                    # Hàm render Card HTML cho chuyến đi
                    def render_kanban_card(row, border_color, bg_color):
                        is_ghep = row.get('is_gop_chuyen', 0) == 1
                        is_ngoai = row.get('is_thue_ngoai', 0) == 1
                        ngay_chuyen = str(row.get('ngay_chuyen_di', ''))
                        
                        # Rút gọn tên khách hàng và lộ trình
                        khach_hang_gon = rut_gon_thong_tin(row.get('khach_hang'))
                        lo_trinh_gon = rut_gon_thong_tin(row.get('lo_trinh'))
                        
                        badge_ghep = f"<span style='font-size: 10px; background-color: #ffecb3; padding: 2px 5px; border-radius: 4px; color: #f57f17; font-weight: bold; margin-left: 4px;'>🔗 Ghép</span>" if is_ghep else ""
                        badge_xe = f"<span style='font-size: 10px; background-color: #fce4ec; padding: 2px 5px; border-radius: 4px; color: #c2185b; font-weight: bold; margin-left: 4px;'>🤝 Ngoài</span>" if is_ngoai else f"<span style='font-size: 10px; background-color: #e3f2fd; padding: 2px 5px; border-radius: 4px; color: #1565c0; font-weight: bold; margin-left: 4px;'>🏢 Cty</span>"
                        badge_ton = f"<span style='font-size: 10px; background-color: #ffccbc; padding: 2px 5px; border-radius: 4px; color: #d84315; font-weight: bold; margin-left: 4px;'>⚠️ Tồn ({ngay_chuyen})</span>" if ngay_chuyen != ngay_hom_nay else ""
                        
                        # [CẬP NHẬT]: Ép kiểu số an toàn cho định dạng hiển thị
                        try:
                            trong_tai = float(row.get('trong_tai', 0)) if pd.notna(row.get('trong_tai')) else 0.0
                        except:
                            trong_tai = 0.0
                        
                        return (
                            f"<div style='background-color: {bg_color}; border-left: 6px solid {border_color}; padding: 10px; border-radius: 8px; margin-bottom: 10px; box-shadow: 2px 2px 5px rgba(0,0,0,0.05); font-family: sans-serif;'>"
                            f"<div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; border-bottom: 1px solid #ddd; padding-bottom: 4px;'>"
                            f"<span style='font-size: 13px; font-weight: 900; color: #333;'>#{row['ma_chuyen']} - {row['bien_so']}</span>"
                            f"<div>{badge_xe}{badge_ghep}{badge_ton}</div>"
                            f"</div>"
                            f"<div style='font-size: 11px; color: #444; line-height: 1.5;'>"
                            f"🧑‍✈️ TX: <b>{row['tai_xe']}</b><br>"
                            f"🏢 KH: <b>{khach_hang_gon}</b><br>"
                            f"📍 Tuyến: <b>{lo_trinh_gon}</b><br>"
                            f"📦 Tải hàng: <span style='color: #d32f2f; font-weight: bold;'>{trong_tai:,.0f} KG</span>"
                            f"</div></div>"
                        )

                    # Hàm render Card HTML cho xe trống
                    def render_empty_vehicle_card(xe_row, border_color, bg_color):
                        tai_trong_xe = float(xe_row['tai_trong_thiet_ke']) if pd.notna(xe_row['tai_trong_thiet_ke']) else 0
                        return (
                            f"<div style='background-color: {bg_color}; border-left: 6px solid {border_color}; padding: 10px; border-radius: 8px; margin-bottom: 10px; box-shadow: 2px 2px 5px rgba(0,0,0,0.05); font-family: sans-serif;'>"
                            f"<div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; border-bottom: 1px solid #ddd; padding-bottom: 4px;'>"
                            f"<span style='font-size: 13px; font-weight: 900; color: #2e7d32;'>🚛 {xe_row['bien_so_xe']}</span>"
                            f"<span style='font-size: 10px; background-color: #c8e6c9; padding: 2px 5px; border-radius: 4px; color: #2e7d32; font-weight: bold;'>Trống</span>"
                            f"</div>"
                            f"<div style='font-size: 11px; color: #444; line-height: 1.5;'>"
                            f"⚖️ Tải trọng TK: <b>{tai_trong_xe:g} Tấn</b><br>"
                            f"🟢 Trạng thái: <b>Sẵn sàng nhận chuyến</b>"
                            f"</div></div>"
                        )

                    df_kanban = df_kanban if isinstance(df_kanban, pd.DataFrame) else pd.DataFrame()
                    
                    # 3. Xác định chính xác các xe đang bận (Vẫn giữ trạng thái Quyet_Toan để tránh xe đang quyết toán hiển thị thành Xe Trống)
                    xe_dang_ban = []
                    if not df_kanban.empty:
                        mask_ban = df_kanban['trang_thai'].isin(['Tao_Moi', 'Dang_Di', 'Quyet_Toan'])
                        xe_dang_ban = df_kanban[mask_ban]['xe_id'].dropna().unique().tolist()

                    # Đổ dữ liệu vào các cột Kanban
                    with c_tao_moi:
                        df_tm = df_kanban[df_kanban['trang_thai'].isin(['Tao_Moi', 'Dang_Di'])] if not df_kanban.empty else pd.DataFrame()
                        st.markdown(f"<h6 style='text-align: center; color: #f57f17; background-color: #fff9c4; padding: 6px; border-radius: 5px;'>🟡 TẠO MỚI / ĐANG CHẠY ({len(df_tm)})</h6>", unsafe_allow_html=True)
                        for _, row in df_tm.iterrows():
                            st.markdown(render_kanban_card(row, "#fbc02d", "#fffde7"), unsafe_allow_html=True)

                    with c_hoan_thanh:
                        df_ht = df_kanban[(df_kanban['trang_thai'] == 'Hoan_Thanh') & (df_kanban['ngay_chuyen_di'].astype(str) == ngay_hom_nay)] if not df_kanban.empty else pd.DataFrame()
                        st.markdown(f"<h6 style='text-align: center; color: #2e7d32; background-color: #c8e6c9; padding: 6px; border-radius: 5px;'>🟢 HOÀN THÀNH HÔM NAY ({len(df_ht)})</h6>", unsafe_allow_html=True)
                        for _, row in df_ht.iterrows():
                            st.markdown(render_kanban_card(row, "#388e3c", "#e8f5e9"), unsafe_allow_html=True)

                    with c_xe_trong:
                        df_trong = pd.DataFrame()
                        if isinstance(df_all_xe, pd.DataFrame) and not df_all_xe.empty:
                            df_trong = df_all_xe[~df_all_xe['id'].isin(xe_dang_ban)]
                        st.markdown(f"<h6 style='text-align: center; color: #2e7d32; background-color: #f1f8e9; padding: 6px; border-radius: 5px;'>🟢 XE TRỐNG ({len(df_trong)})</h6>", unsafe_allow_html=True)
                        for _, xe_row in df_trong.iterrows():
                            st.markdown(render_empty_vehicle_card(xe_row, "#4caf50", "#f9fbe7"), unsafe_allow_html=True)
                else:
                    st.info(f"📭 Chưa có dữ liệu chuyến đi hoặc phương tiện nào được khởi tạo trong hệ thống.")
                    
            except Exception as e:
                st.error(f"Lỗi truy xuất danh sách Kanban: {e}")
                
        vung_thao_tac_quan_ly_chuyen_di()
    except Exception as e:
        st.error(f"❌ Lỗi tải Tab 4: {e}")
# ---------------------------------------------------------
# TAB 5: TRA CỨU CHUYẾN ĐI THEO THỜI GIAN VÀ BỘ LỌC PHỤ 
# ---------------------------------------------------------
with tab5:
    try:
        tao_tieu_de_kem_nut_refresh("📋 Quản lý danh sách chuyến đi", "ref_ds_chuyen1")
        @st.fragment
        def vung_thao_tac_tra_cuu_chuyen_di():
            st.markdown("##### 🔍 Chọn điều kiện tra cứu")
            
            sql_tx_list = "SELECT id, ho_ten FROM nhan_vien WHERE loai_nhan_vien IN ('Tai_Chinh', 'Tai_Phu') ORDER BY ho_ten"
            df_tx_filter = get_cached_master_data(sql_tx_list)
            
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
                    # Gắn cờ loading
                    with st.spinner("Đang truy xuất dữ liệu..."):
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
                        
                        # Lưu kết quả vào Session State
                        st.session_state["df_search_nb"] = db.execute_query(sql_search_nb, tuple(params_nb))

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
                        
                        # Lưu kết quả vào Session State
                        st.session_state["df_search_ngoai"] = db.execute_query(sql_search_ngoai, tuple(params_ngoai))
                except Exception as e:
                    st.error(f"Lỗi hệ thống khi tra cứu dữ liệu: {e}")

            # ĐƯA PHẦN HIỂN THỊ RA NGOÀI NÚT BẤM
            # Nếu có dữ liệu trong Session State, luôn luôn hiển thị nó (bất chấp việc vừa đổi Tab)
            if "df_search_nb" in st.session_state and "df_search_ngoai" in st.session_state:
                df_search_nb = st.session_state["df_search_nb"]
                df_search_ngoai = st.session_state["df_search_ngoai"]
                
                has_nb = isinstance(df_search_nb, pd.DataFrame) and not df_search_nb.empty
                has_ng = isinstance(df_search_ngoai, pd.DataFrame) and not df_search_ngoai.empty

                if has_nb or has_ng:
                    total_len = (len(df_search_nb) if has_nb else 0) + (len(df_search_ngoai) if has_ng else 0)
                    st.toast(f"✅ Tìm thấy tổng cộng **{total_len}** chuyến đi thỏa mãn điều kiện.")

                    st.markdown("#### 🚛 Danh sách chuyến xe Nội bộ")
                    if has_nb:
                        # Copy để tránh warning SettingWithCopy của Pandas
                        df_hien_thi_nb = df_search_nb.copy()
                        if 'Ngày' in df_hien_thi_nb.columns:
                            df_hien_thi_nb['Ngày'] = pd.to_datetime(df_hien_thi_nb['Ngày'], errors='coerce').dt.strftime('%d/%m/%Y').fillna('')
                            
                        # [CẬP NHẬT]: Format tiền tệ an toàn chống lỗi NaN
                        for col_money in ['Lương chuyến', 'Thưởng thêm', 'Doanh thu']:
                            if col_money in df_hien_thi_nb.columns:
                                df_hien_thi_nb[col_money] = df_hien_thi_nb[col_money].apply(
                                    lambda x: f"{int(float(x)):,}" if pd.notnull(x) and str(x).strip() != "" and str(x).lower() != 'nan' else "0"
                                )
                        st.dataframe(df_hien_thi_nb, use_container_width=True, hide_index=True)
                    else:
                        st.info("Không tìm thấy chuyến xe nội bộ nào phù hợp bộ lọc.")

                    st.markdown("<br>", unsafe_allow_html=True)

                    st.markdown("#### 🤝 Danh sách chuyến xe Thuê ngoài")
                    if has_ng:
                        df_hien_thi_ng = df_search_ngoai.copy()
                        df_hien_thi_ng['Ngày'] = pd.to_datetime(df_hien_thi_ng['Ngày']).dt.strftime('%d/%m/%Y')
                        for col_money in ['Lương chuyến', 'Thưởng thêm', 'Doanh thu', 'Phí Thuê Ngoài']:
                            if col_money in df_hien_thi_ng.columns:
                                #df_hien_thi_ng[col_money] = df_hien_thi_ng[col_money].apply(lambda x: f"{x:,.0f}" if pd.notnull(x) else "0")
                                df_hien_thi_ng[col_money] = df_hien_thi_ng[col_money].apply(
                                    lambda x: f"{int(float(x)):,}" if pd.notnull(x) and str(x).strip() != "" and str(x).lower() != 'nan' else "0"
                                    )
                        st.dataframe(df_hien_thi_ng, use_container_width=True, hide_index=True)
                    else:
                        st.info("Không tìm thấy chuyến xe thuê ngoài nào phù hợp bộ lọc.")
                else:
                    st.warning("📭 Không có dữ liệu chuyến đi nào khớp với bộ lọc bạn vừa chọn.")
        vung_thao_tac_tra_cuu_chuyen_di()
    except Exception as e:
        st.error(f"❌ Lỗi tải Tab 5: {e}")
    
# ---------------------------------------------------------
# TAB 6: CẢNH BÁO XE TỒN ĐỌNG / CHƯA HOÀN THÀNH
# ---------------------------------------------------------
with tab6:
    try:
        @st.fragment
        def vung_thao_tac_canh_bao_chuyen_di():
            st.markdown("##### 🚨 Danh sách Chuyến đi chưa chốt sổ (Đã qua ngày)")
            st.info("Bảng này thống kê các chuyến đi có lịch chạy trước ngày hôm nay nhưng hệ thống vẫn ghi nhận là chưa hoàn thành.")
            
            c_date1, c_date2, c_driver = st.columns([1, 1, 2])
            today = datetime.date.today()
            
            tu_ngay_cb = c_date1.date_input("Từ ngày", value=today.replace(day=1), format="DD/MM/YYYY", key="tu_ngay_cb")
            den_ngay_cb = c_date2.date_input("Đến ngày", value=today, format="DD/MM/YYYY", key="den_ngay_cb")
            
            sql_tx_list = "SELECT id, ho_ten FROM nhan_vien WHERE loai_nhan_vien IN ('Tai_Chinh', 'Tai_Phu') ORDER BY ho_ten"
            df_tx_filter = get_cached_master_data(sql_tx_list)
            tx_options_cb = {0: "✨ Tất cả tài xế (Mặc định)"}
            if isinstance(df_tx_filter, pd.DataFrame) and not df_tx_filter.empty:
                for _, r in df_tx_filter.iterrows(): tx_options_cb[r['id']] = r['ho_ten']
                
            tai_xe_cb = c_driver.selectbox("Lọc theo Tài xế", options=list(tx_options_cb.keys()), format_func=lambda x: tx_options_cb[x], key="tx_cb")
            st.divider()

            try:
                if "df_canh_bao" not in st.session_state or st.session_state.get("last_cb_driver") != tai_xe_cb or st.session_state.get("last_tu_ngay") != tu_ngay_cb or st.session_state.get("last_den_ngay") != den_ngay_cb:
                    tx_clause_2 = ""
                    params_bc2 = [f"{tu_ngay_cb.strftime('%Y-%m-%d')} 00:00:00", f"{den_ngay_cb.strftime('%Y-%m-%d')} 23:59:59"]
                    
                    if tai_xe_cb != 0:
                        tx_clause_2 = "AND cdtx.tai_xe_id = %s"
                        params_bc2.append(tai_xe_cb)

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
                    
                    st.session_state["df_canh_bao"] = db.execute_query(sql_canh_bao, tuple(params_bc2))
                    st.session_state["last_cb_driver"] = tai_xe_cb
                    st.session_state["last_tu_ngay"] = tu_ngay_cb
                    st.session_state["last_den_ngay"] = den_ngay_cb

                df_canh_bao = st.session_state["df_canh_bao"]
                
                if isinstance(df_canh_bao, pd.DataFrame) and not df_canh_bao.empty:
                    df_canh_bao['Ngày Chạy'] = pd.to_datetime(df_canh_bao['Ngày Chạy']).dt.strftime('%d/%m/%Y')
                    st.error(f"⚠️ PHÁT HIỆN **{len(df_canh_bao)}** CHUYẾN ĐI QUÁ HẠN CHƯA QUYẾT TOÁN!")
                    
                    def highlight_tre(val):
                        return 'background-color: #ffcccc' if isinstance(val, (int, float)) and val > 0 else ''
                    
                    try:
                        styled_df = df_canh_bao.style.map(highlight_tre, subset=['Số Ngày Trễ'])
                    except AttributeError:
                        styled_df = df_canh_bao.style.applymap(highlight_tre, subset=['Số Ngày Trễ'])
                        
                    if 'khoi_luong_kg' in styled_df.columns:
                        styled_df['khoi_luong_kg'] = pd.to_numeric(styled_df['khoi_luong_kg'], errors='coerce').fillna(0).apply(lambda x: f"{x:,.0f}")
                        
                    st.dataframe(styled_df, use_container_width=True, hide_index=True)
                    
                    excel_buffer_cb = io.BytesIO()
                    with pd.ExcelWriter(excel_buffer_cb, engine='xlsxwriter') as writer_cb:
                        df_canh_bao.to_excel(writer_cb, sheet_name='Canh_Bao_Xe_Ton', index=False)
                    
                    st.download_button(
                        label="🚨 TẢI FILE EXCEL CẢNH BÁO TỒN ĐỌNG",
                        data=excel_buffer_cb.getvalue(),
                        file_name=f"Canh_Bao_Chuyen_Ton_Dong_{datetime.date.today().strftime('%d%m%Y')}.xlsx",
                        type="primary"
                    )
                else:
                    st.toast("🎉 Tuyệt vời! Không có chuyến đi nào bị tồn đọng hay treo hệ thống trong khoảng thời gian này.")
                    
            except Exception as e:
                st.error(f"⚠️ Chi tiết lỗi truy vấn Cảnh báo: {e}")

            st.divider()
            
            # --- TÍNH NĂNG: CẬP NHẬT NHANH TRẠNG THÁI HOÀN THÀNH ---
            st.markdown("##### ⚡ Cập nhật nhanh giải phóng xe trống")
            st.info("Ép chuyển các chuyến đi sang trạng thái **Hoàn Thành** để giải phóng đầu xe tiếp tục nhận chuyến mới. Khâu quyết toán sẽ được xử lý độc lập sau.")
            
            c_up1, c_up2 = st.columns(2)
            with c_up1:
                st.markdown("**1. Khai báo mã đơn lẻ**")
                ma_chuyen_str = st.text_input("Nhập Mã chuyến đi cần chốt:", value="", placeholder="VD: 1025", key="nhap_ma_chuyen_str")
                btn_up_single = st.button("✅ Xác nhận Hoàn Thành chuyến này", type="primary", use_container_width=True)
            
            with c_up2:
                st.markdown("**2. Cập nhật hàng loạt bằng Excel**")
                file_up = st.file_uploader("Tải lên file (Bắt buộc chứa cột 'Mã chuyến đi')", type=["xlsx", "xls"], key="file_uploader_up_trang_thai")
                btn_up_bulk = st.button("🚀 Thực thi chuyển đổi hàng loạt", type="primary", use_container_width=True, disabled=(file_up is None))

            # Xử lý Logic Database Transaction & Audit Log
            if btn_up_single or btn_up_bulk:
                ds_ma_chuyen = []
                
                if btn_up_single:
                    cleaned_ma = ma_chuyen_str.strip()
                    if not cleaned_ma:
                        st.error("❌ Vui lòng nhập Mã chuyến đi trước khi bấm xác nhận!")
                    elif not cleaned_ma.isdigit() or int(cleaned_ma) <= 0:
                        st.error("❌ Mã chuyến đi phải là một dãy số nguyên dương hợp lệ!")
                    else:
                        ds_ma_chuyen.append(int(cleaned_ma))
                
                if btn_up_bulk and file_up is not None:
                    try:
                        df_up = pd.read_excel(file_up)
                        col_name = next((col for col in df_up.columns if str(col).strip().lower() in ['mã chuyến đi', 'ma_chuyen_di', 'id', 'mã chuyến']), None)
                        
                        if col_name:
                            # [CẬP NHẬT]: Ép kiểu an toàn sang số, các giá trị chữ/trống sẽ bị ép thành NaN, sau đó dropna() sẽ dọn dẹp sạch sẽ
                            df_up['id_chuyen_clean'] = pd.to_numeric(df_up[col_name], errors='coerce')
                            ds_ma_chuyen = df_up['id_chuyen_clean'].dropna().astype(int).unique().tolist()
                        else:
                            st.error("❌ File Excel không hợp lệ. Phải có cột mang tên 'Mã chuyến đi'.")
                    except Exception as e:
                        st.error(f"❌ Xảy ra lỗi khi phân tích file Excel: {e}")
                        
                if ds_ma_chuyen:
                    conn = db.pool.get_connection()
                    if conn:
                        try:
                            conn.autocommit = False
                            cursor = conn.cursor()
                            nguoi_dung = st.session_state.get('username', 'He_Thong')
                            
                            thanh_tien_trinh = st.progress(0)
                            tong_so = len(ds_ma_chuyen)
                            thanh_cong = 0
                            
                            for i, ma_cd in enumerate(ds_ma_chuyen):
                                # [FIX] Lấy thêm chuyen_goc_id và ghi_chu để xử lý logic chuyến phụ
                                cursor.execute("SELECT trang_thai_chuyen, chuyen_goc_id, ghi_chu FROM chuyen_di WHERE id = %s", (ma_cd,))
                                row = cursor.fetchone()
                                
                                if row:
                                    tt_hien_tai = row[0]
                                    chuyen_goc_id_val = row[1]
                                    ghi_chu_ht = str(row[2] or "").strip()
                                    
                                    if tt_hien_tai in ['Hoan_Thanh', 'Huy_Chuyen', 'Quyet_Toan']:
                                        st.warning(f"⚠️ Bỏ qua chuyến #{ma_cd}: Đang ở trạng thái '{tt_hien_tai}'.")
                                    else:
                                        if chuyen_goc_id_val is not None:
                                            # Đây là chuyến phụ: Ép thêm chữ WAIT_QUYET_TOAN vào ghi chú để kế toán biết đường vớt lại
                                            ghi_chu_moi = f"{ghi_chu_ht} WAIT_QUYET_TOAN".strip() if "WAIT_QUYET_TOAN" not in ghi_chu_ht else ghi_chu_ht
                                            cursor.execute("UPDATE chuyen_di SET trang_thai_chuyen = 'Hoan_Thanh', ghi_chu = %s WHERE id = %s", (ghi_chu_moi, ma_cd))
                                        else:
                                            # Chuyến chính: Cập nhật bình thường, hệ thống tự vớt bằng điều kiện doanh_thu = 0 ở phần quyết toán
                                            cursor.execute("UPDATE chuyen_di SET trang_thai_chuyen = 'Hoan_Thanh' WHERE id = %s", (ma_cd,))
                                            
                                        if cursor.rowcount > 0:
                                            chi_tiet = f'{{"trang_thai_cu": "{tt_hien_tai}", "trang_thai_moi": "Hoan_Thanh", "ghi_chu": "Cập nhật nhanh giải phóng đầu xe"}}'
                                            cursor.execute("INSERT INTO lich_su_thao_tac (chuyen_di_id, nguoi_dung, hanh_dong, chi_tiet) VALUES (%s, %s, 'CAP_NHAT_Nhanh_Hoan_Thanh', %s)", (ma_cd, nguoi_dung, chi_tiet))
                                            thanh_cong += 1
                                else:
                                    st.error(f"❌ Từ chối: Không tồn tại chuyến đi mã #{ma_cd} trong hệ thống.")
                                    
                                thanh_tien_trinh.progress(min((i + 1) / tong_so, 1.0))
                                
                            conn.commit()
                            
                            if thanh_cong > 0:
                                st.toast(f"🎉 Hoàn tất! Đã chuyển đổi {thanh_cong}/{tong_so} chuyến sang trạng thái Hoàn Thành.")
                                
                                # XÓA TRẮNG TEXT INPUT VÀ FILE UPLOADER SAU KHI CẬP NHẬT THÀNH CÔNG
                                st.session_state["nhap_ma_chuyen_str"] = ""
                                st.session_state.pop("file_uploader_up_trang_thai", None)
                                
                                for key in ["df_canh_bao", "df_search_nb", "df_search_ngoai", "last_cb_driver"]:
                                    st.session_state.pop(key, None)
                                time.sleep(2)
                                st.rerun()
                            elif tong_so > 0:
                                st.info("Không có chuyến đi nào được thay đổi do không thỏa mãn điều kiện cập nhật.")
                                
                        except Exception as e:
                            conn.rollback()
                            st.error(f"❌ Lỗi giao dịch Database (Transaction Rollback): {e}")
                        finally:
                            cursor.close()
                            conn.close()

        vung_thao_tac_canh_bao_chuyen_di()
    except Exception as e:
        st.error(f"❌ Lỗi tải Tab 6: {e}")