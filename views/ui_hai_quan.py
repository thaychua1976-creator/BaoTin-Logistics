## HÀM NÀY DÙNG ĐỂ CẤU HÌNH GIÁ LIÊN QUAN THỦ TỤC HẢI QUAN: TỜ KHAI/ C/O
import streamlit as st
import pandas as pd
from datetime import datetime
import time
import uuid  

from declare_hq_manager import (
    save_bang_gia_hai_quan_transaction, 
    update_bang_gia_hai_quan_transaction, 
    delete_bang_gia_hai_quan_transaction 
)
db = st.session_state.get('db')

# Lấy chính xác username từ phiên đăng nhập thực tế của người dùng, nếu không có mặc định là 'Admin'
current_user = st.session_state.get('username') or st.session_state.get('user') or st.session_state.get('logged_in_user', 'Admin')

if not db:
    st.error("⚠️ Lỗi kết nối Cơ sở dữ liệu.")
    st.stop()

# --- HỆ THỐNG CACHE BỘ NHỚ ĐỆM ---
@st.cache_data(ttl=1800, show_spinner=False)
def get_cached_master_data(query, params=None):
    return db.execute_query(query, params)

def clear_master_cache():
    get_cached_master_data.clear()
# ---------------------------------

st.markdown("<h3 style='text-align: center; color: #0b5394;'>🏢 NHẬP SỐ LIỆU BÁO GIÁ THỦ TỤC HẢI QUAN </h3>", unsafe_allow_html=True)
st.divider()

st.title("🚢 Quản Lý Nghiệp Vụ Hải Quan")
    
# Lấy danh sách khách hàng qua CACHE thay vì gọi DB thủ công
df_kh = get_cached_master_data("SELECT id, ten_khach_hang FROM khach_hang")
dict_kh = {row['ten_khach_hang']: row['id'] for _, row in df_kh.iterrows()} if isinstance(df_kh, pd.DataFrame) and not df_kh.empty else {}
list_kh = list(dict_kh.keys())

tab1, tab2, tab3 = st.tabs([
    "➕ 1. Tạo Cấu Hình Giá", 
    "✏️ 2. Sửa Cấu Hình Giá", 
    "🗑️ 3. Xóa Cấu Hình Giá"
])

# ==========================================
# TAB 1: CẤU HÌNH BẢNG GIÁ HẢI QUAN (MASTER)
# ==========================================
with tab1:
    st.subheader("Thiết lập giá theo hợp đồng (Continental, Tân Châu, Zhengxing...)")
    
    if "form_tao_bg_key" not in st.session_state:
        st.session_state["form_tao_bg_key"] = "form_bang_gia_hq_1"
        
    with st.form(st.session_state["form_tao_bg_key"], clear_on_submit=True):
        col1, col2, col3 = st.columns([2, 2, 2])
        
        with col1:
            kh_chon = st.selectbox("Khách hàng", options=list_kh, index=None, placeholder="-- Chọn khách hàng --")
            nhom_dv = st.selectbox("Nhóm dịch vụ",
                     ["Nhập Cont", "Nhập Lẻ", "Xuất Cont","Xin số Cont/Seal","Phí thanh khoản","Tạm nhập tái xuất",
                      "Xuất Lẻ","Làm C/O","Phí tờ khai","Sửa tờ khai","Ghép tờ khai","Phụ phí luồng",
                      "Tờ khai nhánh","Thanh lý tờ khai",
                      "Kiểm hàng hoá NX luồng đỏ"], index=None, placeholder="-- Chọn nhóm dịch vụ --")
            
        with col2:
            dia_diem_ui = st.selectbox("Địa điểm thông quan", ["Cảng Biển (Cát Lái...)", "Sân Bay (Tân Sơn Nhất...)"], index=None, placeholder="-- Chọn địa điểm --")
            don_gia = st.text_input("Đơn giá (VNĐ)", value="0", help="Có thể nhập dấu phẩy. VD: 500,000")
            
        with col3:
            phan_loai = st.text_input("Phân loại (Nguyên liệu, <= 50 dòng...)", placeholder="Nhập điều kiện...")
            ghi_chu = st.text_input("Ghi chú bổ sung")
        
        submit_bg = st.form_submit_button("💾 Lưu Cấu Hình Bảng Giá", type="primary")
        
        if submit_bg:
            if not kh_chon or not nhom_dv or not dia_diem_ui:
                st.error("⚠️ Vui lòng chọn đầy đủ Khách hàng, Nhóm dịch vụ và Địa điểm thông quan!")
            else:
                map_dia_diem = "San_Bay" if "Sân Bay" in dia_diem_ui else "Cang_Bien"
                
                data_dict = {
                    "khach_hang_id": dict_kh[kh_chon],
                    "nhom_dich_vu": nhom_dv,
                    "phan_loai_chi_tiet": phan_loai,
                    "dia_diem_thong_quan": map_dia_diem, 
                    "don_gia_hq": don_gia,
                    "ghi_chu": ghi_chu
                }
                
                success, msg = save_bang_gia_hai_quan_transaction(db, data_dict, current_user)
                if success: 
                    clear_master_cache() # Dọn dẹp cache sau khi thêm mới
                    st.success(msg)
                    st.session_state["form_tao_bg_key"] = f"form_bang_gia_hq_{uuid.uuid4()}"
                    time.sleep(1)
                    st.rerun()
                else: 
                    st.error(msg)

# ==========================================
# TAB 2: SỬA BẢNG GIÁ HẢI QUAN
# ==========================================
with tab2:
    st.subheader("Chỉnh sửa Bảng giá Hải Quan đã cấu hình")
    
    # Sử dụng CACHE để lấy danh sách bảng giá
    sql_bg = """
        SELECT bg.id, bg.khach_hang_id, kh.ten_khach_hang, bg.nhom_dich_vu, 
               bg.phan_loai_chi_tiet, bg.dia_diem_thong_quan, bg.don_gia_hq, bg.ghi_chu 
        FROM bang_gia_hai_quan bg
        JOIN khach_hang kh ON bg.khach_hang_id = kh.id
        ORDER BY bg.id DESC
    """
    df_bang_gia = get_cached_master_data(sql_bg)
    ds_bang_gia = df_bang_gia.to_dict('records') if isinstance(df_bang_gia, pd.DataFrame) and not df_bang_gia.empty else []

    if not ds_bang_gia:
        st.info("📭 Chưa có dữ liệu bảng giá nào để chỉnh sửa.")
    else:
        bg_opts = {
            r['id']: f"[{r['ten_khach_hang']}] - {r['nhom_dich_vu']} - {r['phan_loai_chi_tiet']} - {r['dia_diem_thong_quan']} (Giá: {int(r['don_gia_hq']):,})"
            for r in ds_bang_gia
        }
        
        if "key_edit_bg" not in st.session_state:
            st.session_state["key_edit_bg"] = "sel_edit_bg_1"
            
        bg_edit_id = st.selectbox("🔍 Chọn bảng giá cần sửa:", options=list(bg_opts.keys()), format_func=lambda x: bg_opts[x], index=None, placeholder="-- Vui lòng click chọn 1 bảng giá --", key=st.session_state["key_edit_bg"])
        
        if bg_edit_id:
            bg_selected = next((item for item in ds_bang_gia if item["id"] == bg_edit_id), None)
            
            with st.form(f"form_edit_bg_{bg_edit_id}"):
                c1, c2, c3 = st.columns([2, 2, 2])
                with c1:
                    kh_idx = list_kh.index(bg_selected['ten_khach_hang']) if bg_selected['ten_khach_hang'] in list_kh else 0
                    edit_kh = st.selectbox("Khách hàng", options=list_kh, index=kh_idx)
                    
                    dv_opts = ["Nhập Cont", "Nhập Lẻ", "Xuất Cont","Xin số Cont/Seal","Phí thanh khoản","Tạm nhập tái xuất","Phụ phí luồng",
                               "Xuất Lẻ","Làm C/O","Phí tờ khai","Sửa tờ khai","Ghép tờ khai",
                               "Tờ khai nhánh","Thanh lý tờ khai","Kiểm hàng hoá NX luồng đỏ"]
                    dv_idx = dv_opts.index(bg_selected['nhom_dich_vu']) if bg_selected['nhom_dich_vu'] in dv_opts else 0
                    edit_dv = st.selectbox("Nhóm dịch vụ", dv_opts, index=dv_idx)
                    
                with c2:
                    dd_opts = ["Cảng Biển (Cát Lái...)", "Sân Bay (Tân Sơn Nhất...)"]
                    dd_idx = 1 if bg_selected['dia_diem_thong_quan'] == "San_Bay" else 0
                    edit_dd = st.selectbox("Địa điểm thông quan", dd_opts, index=dd_idx)
                    
                    edit_don_gia = st.text_input("Đơn giá (VNĐ)", value=f"{int(bg_selected['don_gia_hq']):,}")
                    
                with c3:
                    edit_phan_loai = st.text_input("Phân loại", value=bg_selected['phan_loai_chi_tiet'])
                    edit_ghi_chu = st.text_input("Ghi chú bổ sung", value=bg_selected['ghi_chu'] or "")
                    
                submit_edit = st.form_submit_button("🔄 Cập Nhật Cấu Hình", type="primary")
                
                if submit_edit:
                    map_dia_diem = "San_Bay" if "Sân Bay" in edit_dd else "Cang_Bien"
                    data_update = {
                        "khach_hang_id": dict_kh[edit_kh],
                        "nhom_dich_vu": edit_dv,
                        "phan_loai_chi_tiet": edit_phan_loai,
                        "dia_diem_thong_quan": map_dia_diem,
                        "don_gia_hq": edit_don_gia,
                        "ghi_chu": edit_ghi_chu
                    }
                    
                    success, msg = update_bang_gia_hai_quan_transaction(db, bg_edit_id, data_update, current_user)
                    if success:
                        clear_master_cache() # Dọn dẹp cache sau khi cập nhật
                        st.success(msg)
                        st.session_state["key_edit_bg"] = f"sel_edit_bg_{uuid.uuid4()}"
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(msg)

# ==========================================
# TAB 3: XÓA BẢNG GIÁ HẢI QUAN
# ==========================================
with tab3:
    st.subheader("Xóa Bảng giá Hải Quan")
    if not ds_bang_gia:
        st.info("📭 Không có dữ liệu để xóa.")
    else:
        if "key_del_bg" not in st.session_state:
            st.session_state["key_del_bg"] = "sel_del_bg_1"
            
        bg_del_id = st.selectbox("🗑️ Chọn bảng giá cần xóa:", options=list(bg_opts.keys()), index=None, placeholder="-- Vui lòng click chọn 1 bảng giá --", format_func=lambda x: bg_opts[x], key=st.session_state["key_del_bg"])
        
        if bg_del_id:
            st.warning(f"⚠️ Thao tác này sẽ xóa vĩnh viễn cấu hình giá của **{bg_opts[bg_del_id].split('-')[0]}**. Bạn có chắc chắn không?")
            
            if st.button("Xóa Vĩnh Viễn Cấu Hình Này", type="primary"):
                with st.spinner("Đang xóa dữ liệu..."):
                    success, msg = delete_bang_gia_hai_quan_transaction(db, bg_del_id, current_user)
                    if success:
                        clear_master_cache() # Dọn dẹp cache sau khi xóa
                        st.success(msg)
                        st.session_state["key_del_bg"] = f"sel_del_bg_{uuid.uuid4()}"
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(msg)