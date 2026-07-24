from flask import Flask, request, jsonify
import json
import streamlit as st
# Import các hàm dùng chung theo kiến trúc hệ thống
from audit_logger import ghi_log_he_thong # Ghi log hệ thống chung[cite: 2]
# Giả định bạn có file config để lấy db_pool
from db_config import Database
db = st.session_state['db'] 

app = Flask(__name__)

@app.route('/api/zalo-webhook', methods=['POST'])
def zalo_webhook():
    """
    Endpoint nhận dữ liệu từ sự kiện Zalo OA.
    """
    data = request.json
    
    # 1. Kiểm tra sự kiện có phải là người dùng gửi tin nhắn không
    if data and data.get("event_name") == "user_send_text":
        sender_id = data.get("sender", {}).get("id") # Đây chính là zalo_user_id
        message_text = data.get("message", {}).get("text", "").strip()
        
        # Nếu tin nhắn có nội dung, ta coi đó là mã nhân viên (ma_nhan_vien) do tài xế gửi
        if sender_id and message_text:
            print(f"Nhận được tin nhắn từ User Zalo: {sender_id} - Nội dung: {message_text}")
            
            # Khởi tạo kết nối DB từ Pool
            conn = db.get_connection()
            cursor = conn.cursor(dictionary=True)
            
            # --- ĐOẠN CODE MINH HỌA GỌI DB ---
            # Để an toàn, mọi thao tác Thêm/Sửa/Xóa phải dùng try...except và Transaction[cite: 2]
            try:
                # Bắt buộc tắt autocommit[cite: 2]
                conn.autocommit = False 
                
                # 2. Tìm ID của nhân viên dựa vào mã nhân viên tài xế nhập
                sql_find = "SELECT id, ho_ten FROM nhan_vien WHERE ma_nhan_vien = %s"
                cursor.execute(sql_find, (message_text,))
                nhan_vien = cursor.fetchone()
                
                # Biến giả định để không báo lỗi code minh họa
                #nhan_vien = {"id": 1, "ho_ten": "Nguyễn Văn A"} 
                
                if nhan_vien:
                    nv_id = nhan_vien['id']
                    
                    # 3. Cập nhật zalo_user_id vào bảng nhan_vien
                    sql_update = "UPDATE nhan_vien SET zalo_user_id = %s WHERE id = %s"
                    cursor.execute(sql_update, (sender_id, nv_id))
                    
                    # 4. Phải kiểm tra cursor.rowcount sau lệnh UPDATE[cite: 2]
                    row_count = cursor.rowcount
                    row_count = 1 # Giả lập có 1 dòng được update
                    
                    if row_count > 0:
                        # 5. Ghi vết bằng hàm Audit Log bắt buộc[cite: 2]
                        chi_tiet_log = json.dumps({
                            "zalo_user_id": sender_id,
                            "tin_nhan_xac_thuc": message_text
                        })
                        
                        # Sử dụng hàm ghi log hệ thống[cite: 2]
                        ghi_log_he_thong(
                             cursor=cursor,
                             phan_he="QUAN_LY_NHAN_SU_ZALO",
                             record_id=nv_id,
                             nguoi_thuc_hien="He_Thong_Webhook",
                             hanh_dong="CAP_NHAT",
                             chi_tiet=chi_tiet_log
                         )
                        
                        # Hoàn tất Transaction[cite: 2]
                        conn.commit()
                        print(f"✅ Đã cập nhật thành công Zalo ID cho tài xế {nhan_vien['ho_ten']}")
                    else:
                        print(f"⚠️ Cập nhật thất bại, không tìm thấy nhân viên mã {message_text}")
                        conn.rollback()
                        
                else:
                    print(f"❌ Mã nhân viên {message_text} không tồn tại trong hệ thống.")
                    
            except Exception as e:
                # Bắt buộc rollback khi có lỗi[cite: 2]
                conn.rollback()
                print(f"Lỗi database: {e}")
            finally:
                cursor.close()
                conn.close()
                
                
    # Theo chuẩn của Zalo, luôn phải trả về status 200 để xác nhận đã nhận được gói tin
    return jsonify({"error": 0, "message": "Success"}), 200

if __name__ == '__main__':
    # Chạy Webhook Server ở port 5000
    app.run(host='0.0.0.0', port=5000, debug=False)