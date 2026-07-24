import streamlit as st
import pandas as pd
from hr_system_manager import handle_user_transaction_with_audit
import time, math
import bcrypt

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

st.markdown("<h3 style='text-align: center; color: #0b5394;'>🔐 PHÂN HỆ QUẢN LÝ TÀI KHOẢN HỆ THỐNG</h3>", unsafe_allow_html=True)

# --- MỚI: HÀM LẤY DANH SÁCH NHÂN VIÊN (CẬP NHẬT THEO CỘT LOẠI NHÂN VIÊN) ---
def get_danh_sach_nhan_vien(database):
    # Lấy thêm cột loai_nhan_vien từ Database
    sql = "SELECT id, ho_ten, loai_nhan_vien FROM nhan_vien" 
    try:
        df = database.execute_query(sql)
        if isinstance(df, pd.DataFrame) and not df.empty:
            
            # Tạo một từ điển nhỏ để dịch thuật ngữ Enum sang tiếng Việt hiển thị cho đẹp
            dict_dich_thuat = {
                "Tai_Chinh": "Tài xế chính",
                "Tai_Phu": "Tài xế phụ",
                "Dieu_Hanh": "Điều hành"
            }
            
            # Hàm xử lý việc dịch: Nếu giá trị có trong từ điển thì dịch, không thì giữ nguyên
            def dich_loai_nv(ma_loai):
                # Xử lý trường hợp bị NULL (None)
                if pd.isna(ma_loai):
                    return "Chưa phân loại"
                return dict_dich_thuat.get(ma_loai, str(ma_loai))

            # Trả về format: Nguyễn Văn A (Tài xế chính)
            return {
                row['id']: f"{row['ho_ten']} ({dich_loai_nv(row['loai_nhan_vien'])})" 
                for _, row in df.iterrows()
            }
        return {}
    except Exception as e:
        st.error(f"⚠️ Không thể tải danh sách Nhân viên. Lỗi: {e}")
        return {}

nhan_vien_dict = get_danh_sach_nhan_vien(db)

# Khởi tạo các Tab chức năng điều hướng
tab1, tab2, tab3 = st.tabs(["📋 Danh sách Tài khoản", "➕ Tạo Tài khoản Mới", "🔧 Sửa & Xóa Tài khoản"])

# ==========================================
# TAB 1: DANH SÁCH TÀI KHOẢN
# ==========================================
with tab1:
    try:
        sql_users = """
            SELECT 
                u.id AS 'Mã', 
                u.username AS 'Tên đăng nhập', 
                u.ho_ten AS 'Họ và Tên', 
                CASE 
                    WHEN u.role = 'Admin' THEN 'Quản trị viên (Admin)'
                    WHEN u.role = 'Ke_Toan' THEN 'Kế toán tài chính'
                    WHEN u.role = 'Dieu_Do' THEN 'Điều độ điều xe'
                    WHEN u.role = 'Tai_Xe' THEN 'Tài xế vận hành'
                    ELSE u.role 
                END AS 'Quyền hạn',
                COALESCE(nv.ho_ten, '---') AS 'Thuộc Nhân Viên',
                CASE 
                    WHEN u.trang_thai = 'Dang_Hoat_Dong' THEN '🟢 Đang hoạt động'
                    WHEN u.trang_thai = 'Da_Khoa' THEN '🔴 Đã khóa'
                    ELSE u.trang_thai 
                END AS 'Trạng thái'
            FROM users u
            LEFT JOIN nhan_vien nv ON u.nhan_vien_id = nv.id
            ORDER BY u.id DESC
        """
        df_users = db.execute_query(sql_users)
        
        if isinstance(df_users, pd.DataFrame) and not df_users.empty:
            col_opt1, col_opt2 = st.columns([1, 7])
            with col_opt1:
                che_do_xem = st.selectbox("Hiển thị:", ["10 dòng", "Tất cả"])
            
            if che_do_xem == "Tất cả":
                st.caption(f"Đang hiển thị toàn bộ {len(df_users)} tài khoản.")
                st.dataframe(df_users, use_container_width=True, hide_index=True)
            else:
                rows_per_page = 10
                total_rows = len(df_users)
                total_pages = math.ceil(total_rows / rows_per_page)
                
                if total_pages > 0:
                    if 'page_tk' not in st.session_state:
                        st.session_state['page_tk'] = 1
                        
                    if st.session_state['page_tk'] < 1:
                        st.session_state['page_tk'] = 1
                    elif st.session_state['page_tk'] > total_pages:
                        st.session_state['page_tk'] = total_pages
                        
                    col1, col2, col3 = st.columns([1, 2, 1])
                    with col1:
                        if st.button("⬅️ Trước", key="btn_prev_tk", disabled=(st.session_state['page_tk'] <= 1)):
                            st.session_state['page_tk'] -= 1
                            st.rerun()
                    with col3:
                        if st.button("Sau ➡️", key="btn_next_tk", disabled=(st.session_state['page_tk'] >= total_pages)):
                            st.session_state['page_tk'] += 1
                            st.rerun()
                    with col2:
                        st.markdown(f"<div style='text-align: center; margin-top: 5px;'>Trang {st.session_state['page_tk']} / {total_pages}</div>", unsafe_allow_html=True)

                    start_idx = (st.session_state['page_tk'] - 1) * rows_per_page
                    end_idx = start_idx + rows_per_page
                    df_page = df_users.iloc[start_idx:end_idx]
                    
                    st.dataframe(df_page, use_container_width=True, hide_index=True)
        else:
            st.info("Hệ thống chưa ghi nhận tài khoản người dùng nào.")
    except Exception as e:
        st.error(f"⚠️ Không thể tải danh sách tài khoản. Lỗi: {e}")

# ==========================================
# TAB 2: TẠO TÀI KHOẢN MỚI
# ==========================================
with tab2:
    if "reset_add_user" not in st.session_state: st.session_state["reset_add_user"] = 0
    
    with st.form("form_them_tai_khoan", clear_on_submit=False):
        st.markdown("##### ➕ Cấp tài khoản vận hành mới")
        c1, c2 = st.columns(2)
        new_user = c1.text_input("Tên đăng nhập (Viết liền không dấu)*", placeholder="VD: thuan.nguyen", key=f"new_us_{st.session_state['reset_add_user']}")
        new_pass = c2.text_input("Mật khẩu đăng nhập*", type="password", placeholder="Nhập mật khẩu", key=f"new_pw_{st.session_state['reset_add_user']}")
        
        c3, c4 = st.columns(2)
        new_name = c3.text_input("Họ và tên người dùng*", placeholder="VD: Nguyễn Văn Thuận", key=f"new_na_{st.session_state['reset_add_user']}")
        # --- ĐÃ SỬA: Thêm quyền Tai_Xe ---
        new_role = c4.selectbox("Phân quyền hệ thống", options=[("Admin", "Quản trị viên"), ("Ke_Toan", "Kế toán"), ("Dieu_Do", "Điều độ"), ("Tai_Xe", "Tài xế")], format_func=lambda x: x[1], key=f"new_ro_{st.session_state['reset_add_user']}")
        
        # --- MỚI: Liên kết nhân viên ---
        new_nv_id = st.selectbox(
            "🔗 Liên kết tài khoản này với Nhân viên (Bắt buộc với Tài xế):", 
            options=[None] + list(nhan_vien_dict.keys()), 
            format_func=lambda x: "--- Không liên kết ---" if x is None else nhan_vien_dict[x],
            key=f"new_nv_{st.session_state['reset_add_user']}"
        )
        
        if st.form_submit_button("💾 Khởi tạo tài khoản", type="primary"):
            if not new_user or not new_pass or not new_name:
                st.error("⚠️ Vui lòng điền đầy đủ các thông tin bắt buộc có dấu (*)")
            elif new_role[0] == "Tai_Xe" and new_nv_id is None:
                st.error("⚠️ Phân quyền 'Tài xế' bắt buộc phải được liên kết với một Hồ sơ Nhân viên!")
            else:
                try:
                    chk_exist = db.execute_query("SELECT id FROM users WHERE username = %s", (new_user.strip(),))
                    if isinstance(chk_exist, pd.DataFrame) and not chk_exist.empty:
                        st.error("❌ Tên đăng nhập này đã tồn tại trên hệ thống! Vui lòng chọn tên khác.")
                    else:
                        bytes_pass = new_pass.strip().encode('utf-8')
                        hashed_pass = bcrypt.hashpw(bytes_pass, bcrypt.gensalt()).decode('utf-8')

                        # Đóng gói dữ liệu kèm nhan_vien_id
                        user_data = {
                            'username': new_user.strip(),
                            'password': hashed_pass, 
                            'ho_ten': new_name.strip(),
                            'role': new_role[0],
                            'trang_thai': 'Dang_Hoat_Dong',
                            'nhan_vien_id': new_nv_id
                        }
                        
                        current_user = st.session_state.get('username', 'Admin_Chua_Dang_Nhap')
                        success, result = handle_user_transaction_with_audit(db.pool, "TAO_MOI", user_data, current_user)
                        
                        if success:
                            st.success(f"🎉 Đã khởi tạo tài khoản thành công! (ID: {result})")
                            st.session_state["reset_add_user"] += 1
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error(f"⚠️ Lỗi xử lý dữ liệu: {result}")
                except Exception as ex:
                    st.error(f"⚠️ Lỗi kết nối CSDL: {ex}")

# ==========================================
# TAB 3: CHỨC NĂNG SỬA & XÓA TÀI KHOẢN 
# ==========================================
with tab3:
    try:
        if "reset_edit_user" not in st.session_state: st.session_state["reset_edit_user"] = 0
        
        # --- ĐÃ SỬA: Query thêm nhan_vien_id ---
        df_all_us = db.execute_query("SELECT id, username, ho_ten, role, password, trang_thai, nhan_vien_id FROM users")
        
        if isinstance(df_all_us, pd.DataFrame) and not df_all_us.empty:
            user_opts = {row['id']: f"{row['ho_ten']} ({row['username']}) - Quyền: {row['role']}" for _, row in df_all_us.iterrows()}
            
            selected_user_id = st.selectbox(
                "🔍 Chọn Tài khoản cần xử lý (Sửa thông tin hoặc Xóa):", 
                options=list(user_opts.keys()), 
                index=None, 
                format_func=lambda x: user_opts[x],
                key=f"sel_us_{st.session_state['reset_edit_user']}"
            )
            st.divider()
            
            if selected_user_id is not None:
                us_data = df_all_us[df_all_us['id'] == selected_user_id].iloc[0]
                
                with st.form("form_sua_xoa_tai_khoan"):
                    st.markdown(f"##### ⚙️ Hiệu chỉnh thông tin tài khoản: **{us_data['username']}**")
                    
                    c_ed1, c_ed2 = st.columns(2)
                    edit_name = c_ed1.text_input("Họ và Tên người dùng", value=str(us_data['ho_ten']))
                    edit_pass = c_ed2.text_input("Đổi mật khẩu mới (Để trống nếu giữ nguyên)", type="password", placeholder="Nhập mật khẩu mới")
                    
                    c_ed3, c_ed4 = st.columns(2)
                    role_list = [("Admin", "Quản trị viên"), ("Ke_Toan", "Kế toán"), ("Dieu_Do", "Điều độ"), ("Tai_Xe", "Tài xế")]
                    current_role_idx = [x[0] for x in role_list].index(us_data['role']) if us_data['role'] in [x[0] for x in role_list] else 0
                    edit_role = c_ed3.selectbox("Thay đổi phân quyền", options=role_list, index=current_role_idx, format_func=lambda x: x[1])
                    
                    status_list = [("Dang_Hoat_Dong", "🟢 Đang hoạt động"), ("Da_Khoa", "🔴 Khóa tài khoản")]
                    current_status_idx = [x[0] for x in status_list].index(us_data['trang_thai']) if us_data['trang_thai'] in [x[0] for x in status_list] else 0
                    edit_status = c_ed4.selectbox("Trạng thái tài khoản", options=status_list, index=current_status_idx, format_func=lambda x: x[1])
                    
                    # --- MỚI: Xử lý Selectbox Liên kết Nhân viên ---
                    raw_nv_id = us_data.get('nhan_vien_id', None)
                    current_nv_id = int(raw_nv_id) if pd.notna(raw_nv_id) else None
                    options_nv = [None] + list(nhan_vien_dict.keys())
                    try:
                        idx_nv = options_nv.index(current_nv_id)
                    except ValueError:
                        idx_nv = 0
                        
                    edit_nv_id = st.selectbox(
                        "🔗 Liên kết Nhân viên:", 
                        options=options_nv,
                        index=idx_nv,
                        format_func=lambda x: "--- Không liên kết ---" if x is None else nhan_vien_dict[x]
                    )
                    
                    st.divider()
                    b_save, b_del = st.columns(2)
                    
                    if b_save.form_submit_button("🔄 Lưu Cập Nhật", type="primary"):
                        if edit_role[0] == "Tai_Xe" and edit_nv_id is None:
                            st.error("⚠️ Phân quyền 'Tài xế' bắt buộc phải được liên kết với một Hồ sơ Nhân viên!")
                        else:
                            if edit_pass.strip() != "":
                                bytes_pass = edit_pass.strip().encode('utf-8')
                                final_pass = bcrypt.hashpw(bytes_pass, bcrypt.gensalt()).decode('utf-8')
                            else:
                                final_pass = us_data['password']
                            
                            # Đóng gói dữ liệu kèm nhan_vien_id
                            user_data = {
                                'id': int(selected_user_id),
                                'ho_ten': edit_name.strip(),
                                'password': final_pass, 
                                'role': edit_role[0],
                                'trang_thai': edit_status[0],
                                'nhan_vien_id': edit_nv_id
                            }
                            
                            current_user = st.session_state.get('username', 'Admin_Chua_Dang_Nhap')
                            success, result = handle_user_transaction_with_audit(db.pool, "CAP_NHAT", user_data, current_user)
                        
                                                
                            if success:
                                st.success(f"🎉 Đã cập nhật thành công tài khoản {us_data['username']}!")
                                st.session_state["reset_edit_user"] += 1
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error(f"⚠️ Lỗi xử lý dữ liệu: {result}")
                    
                    if b_del.form_submit_button("🗑️ XÓA VĨNH VIỄN TÀI KHOẢN"):
                        user_data = {'id': int(selected_user_id)}
                        current_user = st.session_state.get('username', 'Admin_Chua_Dang_Nhap')
                        success, result = handle_user_transaction_with_audit(db.pool, "XOA", user_data, current_user)
                        
                        if success:
                            st.warning(f"🗑️ Đã xóa bỏ hoàn toàn tài khoản {us_data['username']} khỏi hệ thống!")
                            st.session_state["reset_edit_user"] += 1
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error(f"⚠️ Lỗi xử lý dữ liệu: {result}")
                        
        else:
            st.info("Chưa có tài khoản nào trong hệ thống để thực hiện sửa đổi.")
            
    except Exception as e:
        st.error(f"⚠️ Đã xảy ra lỗi trong quá trình xử lý tài khoản: {e}")