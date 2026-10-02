import streamlit as st
import pandas as pd
import datetime, time
from utils_core import parse_money_input, tao_tieu_de_kem_nut_refresh
from co_manager import save_co_transaction, delete_co_transaction, get_don_gia_co_theo_khach_hang

# --- HỆ THỐNG CACHE BỘ NHỚ ĐỆM ---
@st.cache_data(ttl=1800, show_spinner=False)
def get_cached_master_data(_db_instance, query, params=None):
    return _db_instance.execute_query(query, params)

def clear_master_cache():
    get_cached_master_data.clear()
# ---------------------------------

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

tab_khai_co, tab_file_co, tab_quan_ly_co = st.tabs(["📋 KHAI BÁO C/O MỚI", "📂 TẠO C/O TỪ FILE", "🔍 DANH SÁCH & QUẢN LÝ (SỬA / XÓA)"])

# ==========================================
# TAB 1: KHAI BÁO C/O MỚI (TÍCH HỢP TỰ ĐỘNG ĐIỀN GIÁ)
# ==========================================
with tab_khai_co:
    st.markdown("#### 📥 Nhập Liệu Chứng Từ C/O Mới")
    @st.fragment
    def vung_thao_tac_declare_co():
        # -------------------------------------------------------------
        # BƯỚC 1: CÁC TRƯỜNG ĐỘNG BÊN NGOÀI FORM ĐỂ STREAMLIT CẬP NHẬT REALTIME
        # -------------------------------------------------------------
        # Chia tỷ lệ: Khách hàng (2 phần) - Tờ khai (1 phần) - Phân loại (1 phần)
        col_a, col_b, col_c = st.columns([5, 3, 2])
        
        # 1. Chọn khách hàng (Sử dụng Cache)
        sql_kh = "SELECT id, ten_khach_hang, ma_khach_hang FROM khach_hang ORDER BY ten_khach_hang ASC"
        df_kh = get_cached_master_data(db, sql_kh)
        dict_kh = {r['id']: f"[{r['ma_khach_hang']}] {r['ten_khach_hang']}" for _, r in df_kh.iterrows()} if not df_kh.empty else {}
        
        khach_hang_id = col_a.selectbox(
            "1. Chọn Khách Hàng*", options=list(dict_kh.keys()),
            format_func=lambda x: dict_kh[x],
            index=0)
        
        # 2. Chọn tờ khai xuất khẩu lọc theo khách hàng (Sử dụng Cache)
        dict_tk = {}
        if khach_hang_id:
            sql_tk_xuat = "SELECT id, so_to_khai, ngay_khai FROM to_khai_hai_quan WHERE loai_to_khai = 'Xuat_Khau' AND khach_hang_id = %s ORDER BY id DESC"
            df_tk_xuat = get_cached_master_data(db, sql_tk_xuat, (khach_hang_id,))
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
            form_co = c1.selectbox("Form C/O", ["", "Form EURO.1", "Form EURO.1UK", "Form AI", "Form EAV","Form AJ","Form AHK","Form RCEP","Form AK", "Form D","Form E","Form VK","Form VJ","Form S","Form VI"])
            so_co = c2.text_input("Số C/O*")
            ngay_co = c3.date_input("Ngày Cấp C/O", value=datetime.date.today())
            
            c4, c5, c6 = st.columns(3)
            # Ẩn số 0 nếu giá tự động bằng 0
            phi_co_val = f"{gia_co_tu_dong:,.0f}" if gia_co_tu_dong > 0 else ""
            
            phi_co = c4.text_input(f"Lệ Phí C/O (VNĐ)*", value=phi_co_val, placeholder="0", help="Hệ thống tự động đề xuất giá theo cấu hình. Có thể sửa tay.")
            phi_dvhq = c5.text_input("Phí DVHQ C/O (VNĐ)", value="", placeholder="0")
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
                        'phi_co': parse_money_input(phi_co or 0),
                        'phi_dvhq': parse_money_input(phi_dvhq or 0),
                        'so_hoa_don_co': so_hoa_don_co,
                        'ghi_chu': ghi_chu_co
                    }
                    ok, msg = save_co_transaction(db.pool, co_data, None, current_user)
                    if ok:
                        clear_master_cache()
                        st.success("✅ Đã lưu chứng từ C/O thành công!")
                        st.session_state["select_co_action"] = None
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(f"Lỗi: {msg}")
    vung_thao_tac_declare_co()
#######################################
# ==========================================
# TAB 1.5: TẠO C/O TỪ FILE EXCEL
# ==========================================
with tab_file_co:
    st.markdown("#### 📥 Nhập Liệu Chứng Từ C/O Hàng Loạt Từ File Excel")
    st.info("Hỗ trợ đọc file danh sách C/O kết xuất từ phần mềm khai báo (VD: CO Fortuna09.xlsx). Hệ thống sẽ tự động đối chiếu Số tờ khai HQ để liên kết dữ liệu.")
    
    uploaded_file = st.file_uploader("📂 Chọn file Excel danh sách C/O", type=["xls", "xlsx"], key="upload_co_excel")
    
    if uploaded_file is not None:
        try:
            df_upload = pd.read_excel(uploaded_file)
            
            # --- 1. LÀM SẠCH DỮ LIỆU TỔNG THỂ ---
            # Xóa các dòng trống hoàn toàn và thay thế NaN/NaT bằng chuỗi rỗng để dễ xử lý
            df_upload.dropna(how='all', inplace=True)
            df_upload.fillna('', inplace=True)
            
            # --- 2. KIỂM TRA ĐỊNH DẠNG FILE ---
            required_cols = ['Số C/O', 'Số tờ khai HQ']
            missing = [c for c in required_cols if c not in df_upload.columns]
            
            if missing:
                st.error(f"❌ File Excel không đúng định dạng. Thiếu các cột: {', '.join(missing)}")
            else:
                # Lấy danh sách tờ khai hiện có trong hệ thống để đối chiếu (Không dùng Cache)
                sql_tk = "SELECT id, so_to_khai FROM to_khai_hai_quan"
                df_tk_sys = db.execute_query(sql_tk)
                
                dict_tk_sys = {}
                if isinstance(df_tk_sys, pd.DataFrame) and not df_tk_sys.empty:
                    for _, row in df_tk_sys.iterrows():
                        tk_str = str(row['so_to_khai']).strip()
                        # Khử đuôi .0 do Pandas tự ép kiểu float cho cột số
                        if tk_str.endswith('.0'): tk_str = tk_str[:-2] 
                        dict_tk_sys[tk_str] = row['id']
                
                valid_records = []
                invalid_records = []
                
                # --- 3. QUÉT VÀ BÓC TÁCH TỪNG DÒNG DỮ LIỆU ---
                for idx, row in df_upload.iterrows():
                    # Xử lý Số C/O an toàn
                    so_co = str(row.get('Số C/O', '')).strip()
                    if not so_co or so_co.lower() == 'nan':
                        continue # Bỏ qua dòng không có Số C/O
                        
                    # Xử lý Số tờ khai HQ an toàn
                    so_tk = str(row.get('Số tờ khai HQ', '')).strip()
                    if so_tk.endswith('.0'): so_tk = so_tk[:-2]
                    
                    tk_id = dict_tk_sys.get(so_tk)
                    
                    if not tk_id:
                        invalid_records.append({
                            "Số C/O": so_co,
                            "Số tờ khai HQ": so_tk,
                            "Lý do lỗi": "Không tìm thấy Số Tờ Khai này trong hệ thống."
                        })
                        continue
                        
                    # Trích xuất phí C/O
                    phi_co = 0.0
                    raw_phi = row.get('PHI', '')
                    if str(raw_phi).strip():
                        try: phi_co = float(raw_phi)
                        except: pass
                        
                    # Trích xuất Ngày cấp phép C/O
                    ngay_co_val = datetime.date.today()
                    raw_ngay = row.get('Ngày cấp phép', '')
                    if str(raw_ngay).strip():
                        try:
                            # Chuyển đổi thành ngày tháng (VD: 02/10/2026 14:14:38 -> 2026-10-02)
                            ngay_co_val = pd.to_datetime(raw_ngay, dayfirst=True).date()
                        except: pass
                            
                    # Tự động nhận diện Form C/O
                    form_co = ""
                    if "VN-CN" in so_co.upper(): form_co = "Form E"
                    elif "VN-KR" in so_co.upper(): form_co = "Form VK"
                    elif "VN-JP" in so_co.upper(): form_co = "Form VJ"
                    elif "VN-CU" in so_co.upper(): form_co = "Form VN-CU"
                    
                    doanh_nghiep = str(row.get('Doanh nghiệp ký', '')).strip()
                    
                    valid_records.append({
                        "to_khai_id": tk_id,
                        "Số tờ khai": so_tk,
                        "Doanh nghiệp": doanh_nghiep,
                        "form_co": form_co,
                        "so_co": so_co,
                        "ngay_co": ngay_co_val,
                        "phi_co": phi_co,
                        "phi_dvhq": 0, # Mặc định là 0
                        "so_hoa_don_co": "",
                        "ghi_chu": "Import hàng loạt từ Excel"
                    })
                
                # --- 4. HIỂN THỊ KẾT QUẢ VÀ NÚT LƯU ---
                if invalid_records:
                    st.warning(f"⚠️ Phát hiện {len(invalid_records)} dòng bị từ chối do chưa có Tờ Khai HQ trong phần mềm:")
                    st.dataframe(pd.DataFrame(invalid_records), use_container_width=True)
                    
                if valid_records:
                    st.success(f"✅ Đã chuẩn bị sẵn sàng {len(valid_records)} chứng từ C/O hợp lệ.")
                    df_valid = pd.DataFrame(valid_records)
                    
                    # Căn chỉnh lại hiển thị số tiền cho dễ nhìn
                    df_view = df_valid[['so_co', 'Số tờ khai', 'Doanh nghiệp', 'form_co', 'ngay_co', 'phi_co']].copy()
                    df_view['phi_co'] = df_view['phi_co'].apply(lambda x: f"{int(x):,}")
                    
                    st.dataframe(df_view, use_container_width=True)
                    
                    if st.button("🚀 XÁC NHẬN LƯU HÀNG LOẠT VÀO HỆ THỐNG", type="primary"):
                        # Tránh click đúp bằng cách đổi key
                        with st.spinner("Đang kết nối Database và tiến hành lưu dữ liệu..."):
                            success_count = 0
                            error_msgs = []
                            
                            # Lưu lần lượt từng dòng để đảm bảo toàn vẹn dữ liệu và bắt lỗi chính xác
                            for rec in valid_records:
                                data_save = {
                                    'to_khai_id': rec['to_khai_id'],
                                    'form_co': rec['form_co'],
                                    'so_co': rec['so_co'],
                                    'ngay_co': rec['ngay_co'].strftime('%Y-%m-%d'),
                                    'phi_co': rec['phi_co'],
                                    'phi_dvhq': rec['phi_dvhq'],
                                    'so_hoa_don_co': rec['so_hoa_don_co'],
                                    'ghi_chu': rec['ghi_chu']
                                }
                                # Hàm save_co_transaction đã có sẵn cơ chế Transaction và Audit Log
                                ok, msg = save_co_transaction(db.pool, data_save, None, current_user)
                                if ok: 
                                    success_count += 1
                                else: 
                                    error_msgs.append(f"- Lỗi ở Số C/O {rec['so_co']}: {msg}")
                            
                            clear_master_cache()
                            
                            if success_count > 0:
                                st.success(f"🎉 Hoàn tất! Đã lưu thành công {success_count}/{len(valid_records)} chứng từ C/O.")
                            if error_msgs:
                                st.error("❌ Các lỗi phát sinh trong quá trình lưu:")
                                for err in error_msgs: 
                                    st.write(err)
                                    
                            # Tự động reload để người dùng thấy dữ liệu mới ở Tab Quản lý
                            if success_count > 0:
                                time.sleep(1.5)
                                st.rerun()
                                    
        except Exception as e:
            st.error(f"❌ Xảy ra lỗi khi phân tích file Excel: {e}")
# ==========================================
# TAB 2: DANH SÁCH & QUẢN LÝ (SỬA / XÓA)
# ==========================================
with tab_quan_ly_co:
    tao_tieu_de_kem_nut_refresh("🔍 Danh sách Chứng từ C/O", "ref_tab_ds_co")
    @st.fragment
    def vung_thao_tac_edit_delete_co():
    
        col_f1, col_f2 = st.columns(2)
        today = datetime.date.today()
        co_tu_ngay = col_f1.date_input("Từ ngày", value=today.replace(day=1), key="co_tu_ngay")
        co_den_ngay = col_f2.date_input("Đến ngày", value=today, key="co_den_ngay")
        
        # Bổ sung trường kh.id (khach_hang_id) để phòng trường hợp sửa Tờ khai (Truy vấn động KHÔNG CẦN CACHE)
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
            # [CẬP NHẬT]: Làm sạch DataFrame, khử triệt để giá trị NaN/None trên giao diện hiển thị
            df_co['phi_co'] = pd.to_numeric(df_co['phi_co'], errors='coerce').fillna(0)
            df_co['phi_dvhq'] = pd.to_numeric(df_co['phi_dvhq'], errors='coerce').fillna(0)
            df_co['so_hoa_don_co'] = df_co['so_hoa_don_co'].fillna('').apply(lambda x: str(x).strip() if str(x).strip().lower() != 'nan' else '')
            df_co['ghi_chu'] = df_co['ghi_chu'].fillna('').apply(lambda x: str(x).strip() if str(x).strip().lower() != 'nan' else '')

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
                
                # [CẬP NHẬT]: Các hàm trích xuất dữ liệu an toàn, chống crash NaN
                def get_safe_val(key, default=""):
                    val = co_info.get(key)
                    if pd.isna(val) or str(val).strip() == "" or str(val).strip().lower() == 'nan':
                        return default
                    return str(val).strip()

                def get_safe_float(key, default=0.0):
                    val = co_info.get(key)
                    if pd.isna(val) or str(val).strip() == "" or str(val).strip().lower() == 'nan':
                        return default
                    try: return float(val)
                    except: return default

                st.markdown(f"Đang thao tác với Số C/O: **{get_safe_val('so_co')}**")
                action_mode_co = st.radio("Hành động:", ["✏️ Sửa C/O", "🗑️ Xóa C/O"], horizontal=True, key="radio_co_action")
                
                if action_mode_co == "🗑️ Xóa C/O":
                    st.warning(f"⚠️ Bạn có chắc chắn muốn xóa vĩnh viễn chứng từ C/O **{get_safe_val('so_co')}**?")
                    if st.button("Xác Nhận Xóa C/O", type="primary"):
                        ok, msg = delete_co_transaction(db.pool, selected_co_id, current_user)
                        if ok:
                            clear_master_cache()
                            st.success("✅ Đã xóa chứng từ C/O thành công!")
                            if "select_co_action" in st.session_state:
                                del st.session_state["select_co_action"]
                            st.rerun()
                        else:
                            st.error(f"Lỗi: {msg}")
                else:
                    with st.form(f"form_edit_co_{selected_co_id}", clear_on_submit=False):
                        sql_tk_edit = "SELECT id, so_to_khai FROM to_khai_hai_quan WHERE khach_hang_id = %s"
                        df_tk_edit = get_cached_master_data(db, sql_tk_edit, (co_info['khach_hang_id'],))
                        dict_tk_edit = {r['id']: f"Số TK: {r['so_to_khai']}" for _, r in df_tk_edit.iterrows()} if not df_tk_edit.empty else {co_info['to_khai_id']: co_info['so_to_khai']}
                        
                        e_to_khai_id = st.selectbox("Tờ Khai Xuất Khẩu Liên Kết", options=list(dict_tk_edit.keys()), index=get_idx(list(dict_tk_edit.keys()), co_info['to_khai_id']), format_func=lambda x: dict_tk_edit[x])
                            
                        ec1, ec2, ec3 = st.columns(3)
                        e_form_co = ec1.text_input("Loại Form C/O", value=get_safe_val('form_co'))
                        e_so_co = ec2.text_input("Số C/O*", value=get_safe_val('so_co'))
                        
                        # Xử lý an toàn ngày cấp C/O chống lỗi NaT/NaN
                        raw_ngay_co = co_info.get('ngay_co')
                        default_ngay_co = pd.to_datetime(raw_ngay_co).date() if pd.notna(raw_ngay_co) and str(raw_ngay_co).strip().lower() != 'nan' else datetime.date.today()
                        e_ngay_co = ec3.date_input("Ngày Cấp C/O", value=default_ngay_co)
                        
                        def fmt(val): 
                            if pd.isna(val) or val == "" or str(val).strip().lower() == 'nan': return ""
                            try:
                                num = float(val)
                                return f"{int(num):,}" if num > 0 else ""
                            except: return ""
                        
                        ec4, ec5, ec6 = st.columns(3)
                        e_phi_co = ec4.text_input("Lệ Phí C/O (VNĐ)*", value=fmt(get_safe_float('phi_co')), placeholder="0")
                        e_phi_dvhq = ec5.text_input("Phí DVHQ C/O (VNĐ)", value=fmt(get_safe_float('phi_dvhq')), placeholder="0")
                        e_so_hoa_don_co = ec6.text_input("Số Hóa Đơn Phí C/O", value=get_safe_val('so_hoa_don_co'))
                        
                        e_ghi_chu = st.text_input("Ghi chú bổ sung", value=get_safe_val('ghi_chu'))
                        
                        if st.form_submit_button("💾 LƯU THAY ĐỔI C/O", type="primary"):
                            if not e_so_co:
                                st.error("Vui lòng nhập số C/O.")
                            else:
                                co_update_data = {
                                    'to_khai_id': e_to_khai_id,
                                    'form_co': e_form_co,
                                    'so_co': e_so_co,
                                    'ngay_co': e_ngay_co.strftime('%Y-%m-%d'),
                                    'phi_co': parse_money_input(e_phi_co or 0),
                                    'phi_dvhq': parse_money_input(e_phi_dvhq or 0),
                                    'so_hoa_don_co': e_so_hoa_don_co,
                                    'ghi_chu': e_ghi_chu
                                }
                                ok, msg = save_co_transaction(db.pool, co_update_data, selected_co_id, current_user)
                                if ok:
                                    clear_master_cache()
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
    vung_thao_tac_edit_delete_co()