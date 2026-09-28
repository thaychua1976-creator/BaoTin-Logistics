import streamlit as st
import bcrypt
import json
import time

def show_page():
    st.markdown("### 🔑 ĐỔI MẬT KHẨU CÁ NHÂN")
    st.info("Vui lòng nhập mật khẩu hiện tại và mật khẩu mới để thực hiện thay đổi.")

    db = st.session_state.get('db')
    current_username = st.session_state.get('username')
    
    if not db or not current_username:
        st.error("Lỗi: Không tìm thấy phiên đăng nhập. Vui lòng đăng nhập lại.")
        return

    with st.form("form_doi_mat_khau", clear_on_submit=True):
        mat_khau_cu = st.text_input("Mật khẩu hiện tại", type="password")
        mat_khau_moi = st.text_input("Mật khẩu mới", type="password")
        nhap_lai_mat_khau_moi = st.text_input("Nhập lại mật khẩu mới", type="password")
        
        submit = st.form_submit_button("Lưu Thay Đổi", type="primary", use_container_width=True)
        
        if submit:
            if not mat_khau_cu or not mat_khau_moi or not nhap_lai_mat_khau_moi:
                st.warning("⚠️ Vui lòng điền đầy đủ các trường.")
            elif mat_khau_moi != nhap_lai_mat_khau_moi:
                st.error("❌ Mật khẩu mới và Nhập lại mật khẩu mới không khớp!")
            elif len(mat_khau_moi) < 6:
                st.warning("⚠️ Mật khẩu mới phải có ít nhất 6 ký tự.")
            else:
                conn = db.pool.get_connection()
                try:
                    conn.autocommit = False
                    cursor = conn.cursor(dictionary=True)
                    
                    # Kiểm tra mật khẩu cũ
                    cursor.execute("SELECT id, password FROM users WHERE username = %s", (current_username,))
                    user = cursor.fetchone()
                    
                    if not user:
                        st.error("❌ Lỗi: Không tìm thấy thông tin tài khoản.")
                    else:
                        is_correct = False
                        try:
                            is_correct = bcrypt.checkpw(mat_khau_cu.encode('utf-8'), user['password'].encode('utf-8'))
                        except ValueError:
                            pass
                            
                        if not is_correct:
                            st.error("❌ Mật khẩu hiện tại không đúng!")
                        else:
                            # Cập nhật mật khẩu mới
                            new_hashed_password = bcrypt.hashpw(mat_khau_moi.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                            
                            cursor.execute(
                                "UPDATE users SET password = %s WHERE id = %s",
                                (new_hashed_password, user['id'])
                            )
                            
                            if cursor.rowcount > 0:
                                # Ghi log thay đổi mật khẩu (Theo quy định dự án)
                                chi_tiet = json.dumps({"ghi_chu": "User tự đổi mật khẩu"}, ensure_ascii=False)
                                cursor.execute("""
                                    INSERT INTO audit_logs (phan_he, record_id, nguoi_thuc_hien, hanh_dong, chi_tiet) 
                                    VALUES (%s, %s, %s, %s, %s)
                                """, ('QUAN_LY_TAI_KHOAN', user['id'], current_username, 'DOI_MAT_KHAU', chi_tiet))
                                
                                conn.commit()
                                st.success("✅ Đổi mật khẩu thành công! Hãy ghi nhớ mật khẩu mới của bạn.")
                                time.sleep(1)
                                st.rerun()
                            else:
                                conn.rollback()
                                st.warning("⚠️ Có lỗi xảy ra, không thể cập nhật mật khẩu.")
                                
                except Exception as e:
                    if conn:
                        conn.rollback()
                    st.error(f"❌ Lỗi hệ thống: {e}")
                finally:
                    if cursor: cursor.close()
                    if conn: conn.close()

if __name__ == "__main__":
    show_page()