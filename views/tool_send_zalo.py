import streamlit as st
import pandas as pd
import time
# Import các hàm tiện ích và log hệ thống theo chuẩn dự án[cite: 2]
from utils_core import send_zalo_gmf_message, send_zalo_personal_message
from audit_logger import ghi_log_he_thong

st.markdown("### 📲 PHÁT LỆNH ĐIỀU XE TỰ ĐỘNG (ZALO OA)")
st.info("💡 **Hướng dẫn:** Tải lên file Excel đã duyệt. Tùy thuộc vào phương thức bạn chọn, file Excel bắt buộc phải có cột **GROUP_ID** (nếu gửi nhóm) hoặc **ZALO_USER_ID** (nếu gửi cá nhân).")

with st.form("form_phat_lenh_zalo_oa"):
    file_duyet = st.file_uploader("📂 Chọn file Excel Lệnh chạy (.xlsx)", type=["xlsx", "xls"])
    
    st.markdown("---")
    st.write("⚙️ **Chọn phương thức gửi tin nhắn:**")
    
    # Tạo 2 cột để đặt 2 nút submit phân biệt hình thức gửi
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        submit_group = st.form_submit_button("🚀 Gửi vào Nhóm (GMF API)", type="primary", use_container_width=True)
    with col_btn2:
        submit_personal = st.form_submit_button("👤 Gửi Cá Nhân (CS API)", type="secondary", use_container_width=True)
    
    # Xử lý sự kiện khi người dùng bấm một trong hai nút
    if submit_group or submit_personal:
        if not file_duyet:
            st.warning("⚠️ Vui lòng tải file Excel lên!")
        else:
            db = st.session_state.get('db')
            current_user = st.session_state.get('username', 'He_Thong')
            
            # Xác định hình thức gửi dựa vào nút được bấm
            hinh_thuc = "GROUP_GMF" if submit_group else "PERSONAL_CS"
            
            try:
                df = pd.read_excel(file_duyet)
                df.columns = [str(c).strip().upper() for c in df.columns]
                
                # Kiểm tra cột bắt buộc tùy theo hình thức gửi
                if hinh_thuc == "GROUP_GMF" and 'GROUP_ID' not in df.columns:
                    st.error("❌ File Excel thiếu cột bắt buộc: 'GROUP_ID'.")
                    st.stop()
                elif hinh_thuc == "PERSONAL_CS" and 'ZALO_USER_ID' not in df.columns:
                    st.error("❌ File Excel thiếu cột bắt buộc: 'ZALO_USER_ID'.")
                    st.stop()

                tong_so_lenh = len(df)
                thanh_cong = 0
                that_bai = 0
                ket_qua_log = []
                
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                # Khởi tạo kết nối CSDL và Transaction an toàn[cite: 2]
                conn = db.get_connection()
                cursor = conn.cursor(dictionary=True)
                conn.autocommit = False
                
                for idx, row in df.iterrows():
                    ma_chuyen = str(row.get('MA_HE_THONG', '')).strip()
                    tai_xe = str(row.get('TEN_TAI_XE', '')).strip()
                    cccd = str(row.get('CCCD', '')).strip()
                    bien_so = str(row.get('BIEN_SO_XE', '')).strip()
                    lo_trinh = str(row.get('LO_TRINH', '')).strip()
                    
                    if hinh_thuc == "GROUP_GMF":
                        target_id = str(row.get('GROUP_ID', '')).strip()
                        if not target_id or target_id == 'nan':
                            ket_qua_log.append({"Dòng": idx+2, "Mã Chuyến": ma_chuyen, "Trạng Thái": "❌ Thiếu Group ID"})
                            that_bai += 1
                            continue
                            
                        # Soạn nội dung nhóm có gắn thẻ tag nhóm
                        noi_dung = (
                            f"🚗 LỆNH ĐIỀU XE BẢO TÍN 🚗\n"
                            f"🔹 Mã chuyến: {ma_chuyen}\n"
                            f"🔹 Xe: {bien_so} | Tài xế: {tai_xe}\n"
                            f"🔹 CCCD: {cccd}\n"
                            f"🔹 Lộ trình: {lo_trinh}\n"
                            f"Vui lòng chuẩn bị hàng hóa! [@{target_id}]"
                        )
                        is_success, msg = send_zalo_gmf_message(target_id, noi_dung)
                        label_log = f"Nhóm ID: {target_id}"
                        
                    else:  # PERSONAL_CS
                        target_id = str(row.get('ZALO_USER_ID', '')).strip()
                        if not target_id or target_id == 'nan':
                            ket_qua_log.append({"Dòng": idx+2, "Mã Chuyến": ma_chuyen, "Trạng Thái": "❌ Thiếu Zalo User ID"})
                            that_bai += 1
                            continue
                            
                        # Soạn nội dung cá nhân hóa
                        noi_dung = (
                            f"🚗 LỆNH ĐIỀU XE BẢO TÍN 🚗\n"
                            f"🔹 Mã chuyến: {ma_chuyen}\n"
                            f"🔹 Xe: {bien_so} | Tài xế: {tai_xe}\n"
                            f"🔹 CCCD: {cccd}\n"
                            f"🔹 Lộ trình: {lo_trinh}\n"
                            f"Vui lòng xác nhận khi nhận được lệnh!"
                        )
                        is_success, msg = send_zalo_personal_message(target_id, noi_dung)
                        label_log = f"User ID: {target_id}"
                    
                    if is_success:
                        thanh_cong += 1
                        trang_thai = "✅ Đã gửi"
                    else:
                        that_bai += 1
                        trang_thai = f"❌ Lỗi: {msg}"
                        
                    ket_qua_log.append({"Dòng": idx+2, "Mã Chuyến": ma_chuyen, "Đối Tượng Nhận": label_log, "Trạng Thái": trang_thai})
                    
                    percent = int(((idx + 1) / tong_so_lenh) * 100)
                    progress_bar.progress(percent)
                    status_text.markdown(f"⏳ Đang xử lý ({hinh_thuc}): **{idx + 1}/{tong_so_lenh}**")
                    
                    # Tránh vi phạm Rate Limit của Zalo OA API
                    time.sleep(0.5)
                
                # Ghi Log Hệ Thống (Bắt buộc theo chuẩn Audit Trail của dự án)[cite: 2]
                try:
                    hanh_dong_log = "GUI_LENH_GMF" if hinh_thuc == "GROUP_GMF" else "GUI_LENH_OA_CS"
                    ghi_log_he_thong(
                        cursor=cursor, 
                        phan_he="DIEU_HANH_ZALO_OA", 
                        record_id=0, 
                        nguoi_thuc_hien=current_user, 
                        hanh_dong=hanh_dong_log, 
                        chi_tiet={"hinh_thuc": hinh_thuc, "thanh_cong": thanh_cong, "that_bai": that_bai}
                    )
                    conn.commit()
                except Exception as log_e:
                    conn.rollback()
                    st.error(f"Lỗi ghi log hệ thống: {log_e}")
                finally:
                    cursor.close()
                    conn.close()

                # Hiển thị kết quả hoàn tất
                progress_bar.empty()
                status_text.empty()
                st.success(f"🎉 Hoàn tất gửi Zalo OA ({hinh_thuc})! Thành công: {thanh_cong}, Lỗi: {that_bai}")
                st.dataframe(pd.DataFrame(ket_qua_log), use_container_width=True)
                
            except Exception as e:
                st.error(f"❌ Lỗi hệ thống: {str(e)}")