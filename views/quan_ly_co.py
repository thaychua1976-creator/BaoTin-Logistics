import streamlit as st
import pandas as pd
import datetime, time
from utils_core import parse_money_input, tao_tieu_de_kem_nut_refresh
from co_manager import save_co_transaction, delete_co_transaction, get_don_gia_co_theo_khach_hang

# 1. KIỂM TRA ĐĂNG NHẬP (Bắt buộc)
if 'username' not in st.session_state or not st.session_state['username']:
    st.error("⚠️ Phiên đăng nhập đã hết hạn hoặc bạn chưa đăng nhập. Vui lòng đăng nhập lại!")
    st.stop() # Dừng toàn bộ code phía dưới nếu chưa đăng nhập

# 2. LẤY CHÍNH XÁC USERNAME ĐÃ LOGIN
current_user = st.session_state['username']

# 3. KIỂM TRA KẾT NỐI DATABASE
db = st.session_state.get('db')
if not db:
    st.error("⚠️ Lỗi kết nối Cơ sở dữ liệu.")
    st.stop()

def get_idx(lst, val, default=0):
    try: return lst.index(val)
    except: return default

st.markdown("<h3 style='text-align: center; color: #0b5394;'>📄 PHÂN HỆ QUẢN LÝ CHỨNG TỪ C/O (XUẤT KHẨU)</h3>", unsafe_allow_html=True)
st.divider()

tab_khai_co, tab_quan_ly_co = st.tabs(["📋 KHAI BÁO C/O MỚI", "🔍 DANH SÁCH & QUẢN LÝ (SỬA / XÓA)"])

# ==========================================
# TAB 1: KHAI BÁO C/O MỚI (TÍCH HỢP TỰ ĐỘNG ĐIỀN GIÁ)
# ==========================================
with tab_khai_co:
    st.markdown("#### 📥 Nhập Liệu Chứng Từ C/O Mới")
    
    # -------------------------------------------------------------
    # BƯỚC 1: CÁC TRƯỜNG ĐỘNG BÊN NGOÀI FORM ĐỂ STREAMLIT CẬP NHẬT REALTIME
    # -------------------------------------------------------------
    col_a, col_b, col_c = st.columns(3)
    
    # 1. Chọn khách hàng
    sql_kh = "SELECT id, ten_khach_hang, ma_khach_hang FROM khach_hang ORDER BY ten_khach_hang ASC"
    df_kh = db.execute_query(sql_kh)
    dict_kh = {r['id']: f"[{r['ma_khach_hang']}] {r['ten_khach_hang']}" for _, r in df_kh.iterrows()} if not df_kh.empty else {}
    
    khach_hang_id = col_a.selectbox(
        "1. Chọn Khách Hàng*", options=list(dict_kh.keys()),
        format_func=lambda x: dict_kh[x],
        index=0)
    
    # 2. Chọn tờ khai xuất khẩu lọc theo khách hàng
    dict_tk = {}
    if khach_hang_id:
        sql_tk_xuat = "SELECT id, so_to_khai, ngay_khai FROM to_khai_hai_quan WHERE loai_to_khai = 'Xuat_Khau' AND khach_hang_id = %s ORDER BY id DESC"
        df_tk_xuat = db.execute_query(sql_tk_xuat, (khach_hang_id,))
        if isinstance(df_tk_xuat, pd.DataFrame) and not df_tk_xuat.empty:
            dict_tk = {r['id']: f"Số TK: {r['so_to_khai']} ({r['ngay_khai']})" for _, r in df_tk_xuat.iterrows()}
            
    to_khai_id = col_b.selectbox("2. Chọn Tờ Khai Của Khách*", options=list(dict_tk.keys()), format_func=lambda x: dict_tk[x]) if dict_tk else None
    
    if not to_khai_id and khach_hang_id:
        st.warning("⚠️ Khách hàng này chưa có tờ khai xuất khẩu nào trong hệ thống.")

    # 3. Phân loại C/O để tự động nội suy giá
    phan_loai_co = col_c.selectbox("3. Phân Loại Làm C/O", ["Thường", "Gấp", "Ghép"])
    
    # GỌI HÀM LẤY GIÁ TỪ DATABASE
    gia_co_tu_dong = 0.0
    if khach_hang_id:
        gia_co_tu_dong = get_don_gia_co_theo_khach_hang(db.pool, khach_hang_id, phan_loai_co)
        
    st.divider()

    # -------------------------------------------------------------
    # BƯỚC 2: FORM NHẬP LIỆU CHÍNH
    # -------------------------------------------------------------
    with st.form("form_khai_co", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        form_co = c1.selectbox("Form C/O", ["", "Form E", "Form D", "Form AJ", "Form VJ", "Form AK"])
        so_co = c2.text_input("Số C/O*")
        ngay_co = c3.date_input("Ngày Cấp C/O", value=datetime.date.today())
        
        c4, c5, c6 = st.columns(3)
        # Giá tiền được tự động điền dựa trên phan_loai_co ở trên, người dùng vẫn có quyền sửa tay
        phi_co = c4.text_input(f"Lệ Phí C/O (VNĐ)*", value=f"{gia_co_tu_dong:,.0f}", help="Hệ thống tự động đề xuất giá theo cấu hình. Có thể sửa tay.")
        phi_dvhq = c5.text_input("Phí DVHQ C/O (VNĐ)", value="0")
        so_hoa_don_co = c6.text_input("Số Hóa Đơn Phí C/O")
        
        # Ghi chú mặc định thêm Loại làm C/O để đối soát sau này
        ghi_chu_co = st.text_input("Ghi chú bổ sung", value=f"Phân loại C/O: {phan_loai_co}")
        
        if st.form_submit_button("💾 LƯU CHỨNG TỪ C/O", type="primary"):
            if not to_khai_id:
                st.error("Vui lòng chọn tờ khai xuất khẩu hợp lệ.")
            elif not so_co:
                st.error("Vui lòng nhập Số C/O.")
            else:
                co_data = {
                    'to_khai_id': to_khai_id,
                    'form_co': form_co,
                    'so_co': so_co,
                    'ngay_co': ngay_co.strftime('%Y-%m-%d'),
                    'phi_co': parse_money_input(phi_co),
                    'phi_dvhq': parse_money_input(phi_dvhq),
                    'so_hoa_don_co': so_hoa_don_co,
                    'ghi_chu': ghi_chu_co
                }
                ok, msg = save_co_transaction(db.pool, co_data, None, current_user)
                if ok:
                    st.success("✅ Đã lưu chứng từ C/O thành công!")
                    st.session_state["select_co_action"] = None
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(f"Lỗi: {msg}")

# ==========================================
# TAB 2: DANH SÁCH & QUẢN LÝ (SỬA / XÓA)
# ==========================================
with tab_quan_ly_co:
    tao_tieu_de_kem_nut_refresh("🔍 Danh sách Chứng từ C/O", "ref_tab_ds_co")
    
    col_f1, col_f2 = st.columns(2)
    today = datetime.date.today()
    co_tu_ngay = col_f1.date_input("Từ ngày", value=today.replace(day=1), key="co_tu_ngay")
    co_den_ngay = col_f2.date_input("Đến ngày", value=today, key="co_den_ngay")
    
    # Bổ sung trường kh.id (khach_hang_id) để phòng trường hợp sửa Tờ khai
    sql_ds_co = """
        SELECT co.id, co.to_khai_id, co.form_co, co.so_co, co.ngay_co, 
               co.phi_co, co.phi_dvhq, co.so_hoa_don_co, co.ghi_chu, 
               tk.so_to_khai, kh.ten_khach_hang, kh.id AS khach_hang_id
        FROM to_khai_co co
        JOIN to_khai_hai_quan tk ON co.to_khai_id = tk.id
        JOIN khach_hang kh ON tk.khach_hang_id = kh.id
        WHERE co.ngay_co BETWEEN %s AND %s
        ORDER BY co.ngay_co DESC, co.id DESC
    """
    df_co = db.execute_query(sql_ds_co, (co_tu_ngay.strftime('%Y-%m-%d'), co_den_ngay.strftime('%Y-%m-%d')))
    
    if isinstance(df_co, pd.DataFrame) and not df_co.empty:
        df_co_view = df_co[['id', 'form_co', 'so_co', 'ngay_co', 'so_to_khai', 'ten_khach_hang', 'phi_co', 'phi_dvhq', 'so_hoa_don_co', 'ghi_chu']].copy()
        df_co_view['phi_co'] = df_co_view['phi_co'].apply(lambda x: f"{int(x):,}" if pd.notnull(x) else "0")
        df_co_view['phi_dvhq'] = df_co_view['phi_dvhq'].apply(lambda x: f"{int(x):,}" if pd.notnull(x) else "0")
        st.dataframe(df_co_view, use_container_width=True, hide_index=True)
        
        st.divider()
        st.markdown("#### 🛠️ Thao Tác Quản Lý C/O (Sửa / Xóa)")
        
        dict_co_edit = {row['id']: f"Form: {row['form_co']} | Số C/O: {row['so_co']} (TK: {row['so_to_khai']} - {row['ten_khach_hang']})" for _, row in df_co.iterrows()}
        
        selected_co_id = st.selectbox(
            "📌 Chọn chứng từ C/O để sửa hoặc xóa:",
            options=list(dict_co_edit.keys()),
            format_func=lambda x: dict_co_edit[x],
            index=None,
            placeholder="-- Vui lòng click chọn 1 chứng từ C/O --",
            key="select_co_action"
        )
        
        if selected_co_id is not None:
            co_info = df_co[df_co['id'] == selected_co_id].iloc[0]
            
            st.markdown(f"Đang thao tác với Số C/O: **{co_info['so_co']}**")
            action_mode_co = st.radio("Hành động:", ["✏️ Sửa C/O", "🗑️ Xóa C/O"], horizontal=True, key="radio_co_action")
            
            if action_mode_co == "🗑️ Xóa C/O":
                st.warning(f"⚠️ Bạn có chắc chắn muốn xóa vĩnh viễn chứng từ C/O **{co_info['so_co']}**?")
                if st.button("Xác Nhận Xóa C/O", type="primary"):
                    ok, msg = delete_co_transaction(db.pool, selected_co_id, current_user)
                    if ok:
                        st.success("✅ Đã xóa chứng từ C/O thành công!")
                        if "select_co_action" in st.session_state:
                            del st.session_state["select_co_action"]
                        st.rerun()
                    else:
                        st.error(f"Lỗi: {msg}")
            else:
                with st.form(f"form_edit_co_{selected_co_id}", clear_on_submit=False):
                    # Lấy lại danh sách Tờ khai của chính khách hàng này để có thể sửa đổi nếu cần
                    sql_tk_edit = "SELECT id, so_to_khai FROM to_khai_hai_quan WHERE khach_hang_id = %s"
                    df_tk_edit = db.execute_query(sql_tk_edit, (co_info['khach_hang_id'],))
                    dict_tk_edit = {r['id']: f"Số TK: {r['so_to_khai']}" for _, r in df_tk_edit.iterrows()} if not df_tk_edit.empty else {co_info['to_khai_id']: co_info['so_to_khai']}
                    
                    e_to_khai_id = st.selectbox("Tờ Khai Xuất Khẩu Liên Kết", options=list(dict_tk_edit.keys()), index=get_idx(list(dict_tk_edit.keys()), co_info['to_khai_id']), format_func=lambda x: dict_tk_edit[x])
                        
                    ec1, ec2, ec3 = st.columns(3)
                    e_form_co = ec1.text_input("Loại Form C/O", value=co_info['form_co'] or "")
                    e_so_co = ec2.text_input("Số C/O*", value=co_info['so_co'] or "")
                    e_ngay_co = ec3.date_input("Ngày Cấp C/O", value=pd.to_datetime(co_info['ngay_co']).date())
                    
                    def fmt(val): return f"{int(float(val)):,}" if pd.notna(val) else "0"
                    
                    ec4, ec5, ec6 = st.columns(3)
                    # Giao diện sửa hiển thị giá cũ, người dùng có thể tự gõ đè giá trị nếu cần đổi Thường -> Gấp
                    e_phi_co = ec4.text_input("Lệ Phí C/O (VNĐ)*", value=fmt(co_info['phi_co']))
                    e_phi_dvhq = ec5.text_input("Phí DVHQ C/O (VNĐ)", value=fmt(co_info['phi_dvhq']))
                    e_so_hoa_don_co = ec6.text_input("Số Hóa Đơn Phí C/O", value=co_info['so_hoa_don_co'] or "")
                    
                    e_ghi_chu = st.text_input("Ghi chú bổ sung", value=co_info['ghi_chu'] or "")
                    
                    if st.form_submit_button("💾 LƯU THAY ĐỔI C/O", type="primary"):
                        if not e_so_co:
                            st.error("Vui lòng nhập số C/O.")
                        else:
                            co_update_data = {
                                'to_khai_id': e_to_khai_id,
                                'form_co': e_form_co,
                                'so_co': e_so_co,
                                'ngay_co': e_ngay_co.strftime('%Y-%m-%d'),
                                'phi_co': parse_money_input(e_phi_co),
                                'phi_dvhq': parse_money_input(e_phi_dvhq),
                                'so_hoa_don_co': e_so_hoa_don_co,
                                'ghi_chu': e_ghi_chu
                            }
                            ok, msg = save_co_transaction(db.pool, co_update_data, selected_co_id, current_user)
                            if ok:
                                st.success("✅ Cập nhật chứng từ C/O thành công!")
                                if "select_co_action" in st.session_state:
                                    del st.session_state["select_co_action"]
                                st.rerun()
                            else:
                                st.error(f"Lỗi: {msg}")
        else:
            st.info("👆 Vui lòng chọn một chứng từ C/O từ danh sách bên trên để tiến hành sửa hoặc xóa.")
    else:
        st.info("📭 Không có chứng từ C/O nào trong khoảng thời gian này.")