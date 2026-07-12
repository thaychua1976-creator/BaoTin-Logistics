# 🚀 HỒ SƠ DỰ ÁN: HỆ THỐNG QUẢN LÝ BẢO TÍN LOGISTICS

## 1. THÔNG TIN CHUNG & CÔNG NGHỆ
- **Mục tiêu:** Xây dựng phần mềm ERP quản lý vận tải, điều phối xe, nhân sự và quyết toán logistics.
- **Frontend:** Python Streamlit.
- **Backend/Database:** MySQL (lưu trữ trên Aiven) + Connection Pool.
- **Nguyên tắc Coding bắt buộc:**
  1. Mọi thao tác Thêm/Sửa/Xóa (CUD) phải dùng `try...except` và `Transaction` (`conn.autocommit = False`, `conn.commit()`, `conn.rollback()`).
  2. Phải kiểm tra `cursor.rowcount` sau lệnh UPDATE/DELETE.
  3. Dữ liệu tiền tệ từ giao diện bắt buộc đưa qua hàm `parse_money_input()` trước khi xử lý.
  4. Mọi hành động thay đổi dữ liệu phải được ghi vết bằng các hàm Audit Log.

---

## 2. CẤU TRÚC DATABASE (SCHEMA)
*(⚠️ Lời nhắc cho Dev: Hãy copy kết quả của lệnh `SHOW CREATE TABLE` từ DBeaver cho các bảng chính (xe, chuyen_di, lich_su_bao_duong, users, nhan_vien...) và dán vào đây để AI hiểu cấu trúc cột.)*

```sql

CREATE TABLE "audit_logs" (
  "id" int NOT NULL AUTO_INCREMENT,
  "phan_he" varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'Tên phân hệ xảy ra thao tác (Ví dụ: QUAN_LY_TAI_KHOAN, QUAN_LY_CHUYEN_DI)',
  "record_id" int DEFAULT NULL COMMENT 'ID của dòng dữ liệu bị tác động (Ví dụ: user_id hoặc chuyen_di_id)',
  "nguoi_thuc_hien" varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'Username của người thực hiện thao tác',
  "hanh_dong" varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'Loại thao tác (Ví dụ: TAO_MOI, CAP_NHAT, XOA)',
  "chi_tiet" json DEFAULT NULL COMMENT 'Lưu thông tin chi tiết dưới dạng chuỗi JSON',
  "thoi_gian" datetime DEFAULT CURRENT_TIMESTAMP COMMENT 'Thời điểm thực hiện thao tác',
  PRIMARY KEY ("id"),
  KEY "idx_audit_phan_he" ("phan_he"),
  KEY "idx_audit_nguoi_thuc_hien" ("nguoi_thuc_hien"),
  KEY "idx_audit_thoi_gian" ("thoi_gian")
);


-- logistics_app.cau_hinh_thuong definition

CREATE TABLE "cau_hinh_thuong" (
  "ma_tieu_chi" varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  "ten_tieu_chi" varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  "muc_thuong" decimal(15,2) DEFAULT '0.00',
  PRIMARY KEY ("ma_tieu_chi")
);


-- logistics_app.khach_hang definition

CREATE TABLE "khach_hang" (
  "id" int NOT NULL AUTO_INCREMENT,
  "ten_khach_hang" varchar(150) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  "ma_khach_hang" varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  "so_dien_thoai" varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY ("id"),
  UNIQUE KEY "ma_khach_hang" ("ma_khach_hang"),
  KEY "idx_sdt_khach" ("so_dien_thoai")
);


-- logistics_app.lich_su_thao_tac definition

CREATE TABLE "lich_su_thao_tac" (
  "id" int NOT NULL AUTO_INCREMENT,
  "chuyen_di_id" int DEFAULT NULL,
  "nguoi_dung" varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT 'He_Thong',
  "hanh_dong" varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  "chi_tiet" text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  "thoi_gian" datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY ("id"),
  KEY "idx_lich_su_nguoi_dung" ("nguoi_dung"),
  KEY "idx_lich_su_thoi_gian" ("thoi_gian")
);


-- logistics_app.nhan_vien definition

CREATE TABLE "nhan_vien" (
  "id" int NOT NULL AUTO_INCREMENT,
  "ma_nhan_vien" varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  "ho_ten" varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  "so_dien_thoai" varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  "loai_nhan_vien" enum('Tai_Chinh','Tai_Phu','Dieu_Hanh') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT 'Tai_Chinh',
  "trang_thai" enum('Dang_Lam_Viec','Nghi_Phep','Da_Nghi_Viec') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT 'Dang_Lam_Viec',
  "cccd" varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  "giay_phep_lai_xe" varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  "hang_gplx" varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  "han_gplx" date DEFAULT NULL,
  "han_the_tap_huan" date DEFAULT NULL,
  PRIMARY KEY ("id"),
  UNIQUE KEY "ma_nhan_vien" ("ma_nhan_vien"),
  KEY "idx_sdt_nhanvien" ("so_dien_thoai")
);


-- logistics_app.tuyen_duong definition

CREATE TABLE "tuyen_duong" (
  "id" int NOT NULL AUTO_INCREMENT,
  "ten_tuyen" varchar(150) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  "so_km_chuan" decimal(10,2) DEFAULT '0.00',
  PRIMARY KEY ("id")
);


-- logistics_app.users definition

CREATE TABLE "users" (
  "id" int NOT NULL AUTO_INCREMENT,
  "username" varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  "password" varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  "role" varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  "ho_ten" varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  "trang_thai" varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT 'Dang_Hoat_Dong',
  PRIMARY KEY ("id"),
  UNIQUE KEY "username" ("username")
);


-- logistics_app.xe definition

CREATE TABLE "xe" (
  "id" int NOT NULL AUTO_INCREMENT,
  "bien_so_xe" varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  "tai_trong_thiet_ke" double DEFAULT NULL,
  "loai_xe" varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  "dinh_muc_bao_duong" decimal(10,2) DEFAULT '5000.00',
  "km_bao_duong_gan_nhat" decimal(10,2) DEFAULT '0.00',
  "ngay_bao_duong_gan_nhat" date DEFAULT NULL,
  "trang_thai" varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT 'Dang_Hoat_Dong',
  "dinh_muc_nhien_lieu" decimal(10,2) DEFAULT '0.00',
  "ma_dinh_vi" varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  "nha_cung_cap_gps" varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  "phu_hieu_xe" varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  "han_phu_hieu" date DEFAULT NULL,
  "sdt_xac_thuc" varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  "email_xac_thuc" varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  "quy_cach_thung" varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  "cua_xe_bam_seal" varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  "han_dang_kiem" date DEFAULT NULL,
  "han_bao_hiem_ds" date DEFAULT NULL,
  "nhan_hieu_xe" varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  "dung_tich_cbm" double DEFAULT NULL,
  "tai_xe_co_dinh_id" int DEFAULT NULL,
  "tong_km_hien_tai" decimal(15,2) DEFAULT '0.00',
  PRIMARY KEY ("id"),
  UNIQUE KEY "bien_so_xe" ("bien_so_xe"),
  KEY "idx_xe_han_bao_hiem" ("han_bao_hiem_ds"),
  KEY "idx_xe_trang_thai" ("trang_thai"),
  KEY "idx_xe_han_dang_kiem" ("han_dang_kiem"),
  KEY "idx_xe_han_phu_hieu" ("han_phu_hieu")
);


-- logistics_app.chuyen_di definition

CREATE TABLE "chuyen_di" (
  "id" int NOT NULL AUTO_INCREMENT,
  "ngay_chuyen_di" date NOT NULL,
  "xe_id" int DEFAULT NULL,
  "ten_khach_hang" varchar(150) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  "dia_chi_khach_hang" varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  "dia_diem_giao_nhan" varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  "khach_hang_id" int DEFAULT NULL,
  "tuyen_duong_id" int DEFAULT NULL,
  "so_km_thuc_te" decimal(10,2) DEFAULT '0.00',
  "cong_chuyen" decimal(15,2) DEFAULT '0.00',
  "trang_thai_chuyen" enum('Tao_Moi','Dang_Di','Quyet_Toan','Hoan_Thanh','Huy_Chuyen') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'Tao_Moi',
  "ghi_chu" text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  "so_lit_xang" decimal(10,2) DEFAULT '0.00',
  "tien_xang" decimal(15,2) DEFAULT '0.00',
  "phi_hai_quan" decimal(15,2) DEFAULT '0.00',
  "phi_boc_xep" decimal(15,2) DEFAULT '0.00',
  "phi_khac" decimal(15,2) DEFAULT '0.00',
  "is_gop_chuyen" tinyint DEFAULT '0',
  "tien_them" decimal(15,2) DEFAULT '0.00',
  "ghi_chu_quyet_toan" text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  "is_ve_khuya" tinyint DEFAULT '0',
  "khoi_luong_kg" decimal(10,2) DEFAULT '0.00',
  "the_tich_cbm" decimal(10,2) DEFAULT '0.00',
  PRIMARY KEY ("id"),
  KEY "khach_hang_id" ("khach_hang_id"),
  KEY "tuyen_duong_id" ("tuyen_duong_id"),
  KEY "idx_xe_id" ("xe_id"),
  KEY "idx_trangthai_ngay" ("trang_thai_chuyen","ngay_chuyen_di"),
  CONSTRAINT "chuyen_di_ibfk_1" FOREIGN KEY ("xe_id") REFERENCES "xe" ("id") ON DELETE SET NULL,
  CONSTRAINT "chuyen_di_ibfk_2" FOREIGN KEY ("khach_hang_id") REFERENCES "khach_hang" ("id") ON DELETE SET NULL,
  CONSTRAINT "chuyen_di_ibfk_3" FOREIGN KEY ("tuyen_duong_id") REFERENCES "tuyen_duong" ("id") ON DELETE SET NULL,
  CONSTRAINT "chk_khoi_luong" CHECK ((`khoi_luong_kg` >= 0))
);


-- logistics_app.chuyen_di_tai_xe definition

CREATE TABLE "chuyen_di_tai_xe" (
  "id" int NOT NULL AUTO_INCREMENT,
  "chuyen_di_id" int NOT NULL,
  "tai_xe_id" int NOT NULL,
  "loai_tai_xe" enum('Tai_Chinh','Tai_Phu') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT 'Tai_Chinh',
  PRIMARY KEY ("id"),
  KEY "chuyen_di_id" ("chuyen_di_id"),
  KEY "tai_xe_id" ("tai_xe_id"),
  CONSTRAINT "chuyen_di_tai_xe_ibfk_1" FOREIGN KEY ("chuyen_di_id") REFERENCES "chuyen_di" ("id") ON DELETE CASCADE,
  CONSTRAINT "chuyen_di_tai_xe_ibfk_2" FOREIGN KEY ("tai_xe_id") REFERENCES "nhan_vien" ("id") ON DELETE CASCADE
);


-- logistics_app.lich_su_bao_duong definition

CREATE TABLE "lich_su_bao_duong" (
  "id" int NOT NULL AUTO_INCREMENT,
  "xe_id" int DEFAULT NULL,
  "ngay_bao_duong" date DEFAULT NULL,
  "km_thuc_te" decimal(15,2) DEFAULT NULL,
  "hang_muc_sua_chua" text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  "chi_phi" decimal(15,2) DEFAULT NULL,
  "don_vi_thuc_hien" varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  "ghi_chu" text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  "loai_bao_duong" enum('Dinh_Ky','Sua_Chua_Dot_Xuat','Thay_Lop','Khac') COLLATE utf8mb4_unicode_ci DEFAULT 'Dinh_Ky',
  PRIMARY KEY ("id"),
  KEY "xe_id" ("xe_id"),
  CONSTRAINT "lich_su_bao_duong_ibfk_1" FOREIGN KEY ("xe_id") REFERENCES "xe" ("id") ON DELETE CASCADE
);

## CẤU TRÚC BACKEND
*** Hệ thống đã được module hóa thành 5 file Python. Tuyệt đối không viết lại hàm mới nếu hàm đã tồn tại trong danh sách dưới đây, chỉ cần import và gọi lại.
File 1: utils_core.py (Tiện ích dùng chung)
parse_money_input(val_str): Xóa dấu phẩy, chuyển chuỗi tiền tệ thành số int/float.

send_zalo_message(phone, khach_hang, lo_trinh): Gửi tin nhắn ZNS API.

📦 File 2: audit_logger.py (Ghi vết hệ thống - Audit Trail)
ghi_log_thao_tac(cursor, chuyen_di_id, nguoi_dung, hanh_dong, chi_tiet_dict): Log nghiệp vụ chuyến đi.

log_thao_tac(cursor, xe_id, nguoi_dung, hanh_dong, chi_tiet_dict): Log nghiệp vụ phương tiện.

ghi_log_he_thong(cursor, phan_he, record_id, nguoi_thuc_hien, hanh_dong, chi_tiet): Log hệ thống chung (Nhân viên, Users, Cấu hình).

📦 File 3: trip_manager.py (Nghiệp vụ Chuyến Đi)
save_trip_full_process(db_pool, trip_data, tai_xe_id): Tạo chuyến đi mới + Phân công tài xế.

update_trip_full_process(pool, trip_id, trip_data_tuple, tai_xe_id): Cập nhật toàn bộ thông tin chuyến đi lúc chưa chốt.

settle_trip_transaction(db_pool, data_chuyen_di, trang_thai_enum, chuyen_di_id): Quyết toán chuyến, tự động cộng Odometer cho xe.

update_trip_transaction(db_pool, data_chuyen_di, trang_thai_enum, chuyen_di_id): Sửa chuyến đã quyết toán, tự động bù trừ lệch Odometer.

delete_trip_safe(db_pool, chuyen_di_id): Xóa mềm/Xóa an toàn chuyến đi tránh lỗi khóa ngoại.

📦 File 4: fleet_manager.py (Nghiệp vụ Phương tiện & Bảo dưỡng)
save_vehicle_transaction(db_pool, xe_data, xe_id, nguoi_dung): Thêm mới hoặc Cập nhật thông tin xe.

delete_vehicle_transaction(db_pool, xe_id, nguoi_dung): Xóa mềm xe (Ngung_Hoat_Dong).

get_canh_bao_bao_duong(db_pool): Tính toán độ hao mòn Odometer, trả về DataFrame xe sắp đến hạn.

save_lich_su_bao_duong(db_pool, data_dict): Lưu phiếu sửa chữa, tự động reset mốc bảo dưỡng nếu là 'Dinh_Ky'.

get_thong_ke_hoat_dong_xe(db_pool, xe_id, tu_ngay, den_ngay): Lấy Tổng KM, Tổng Nhiên Liệu, Tổng Chuyến.

get_chi_tiet_bao_duong_xe(db_pool, xe_id, tu_ngay, den_ngay): Lấy lịch sử sửa chữa kèm Biển số và Tài xế cố định.

📦 File 5: hr_system_manager.py (Nhân sự & Cấu hình Hệ thống)
handle_user_transaction_with_audit(db_pool, action, user_data, current_user): Thêm/Sửa/Xóa tài khoản đăng nhập (Users).

save_nhan_vien_transaction(db_pool, action, nv_data, nv_id, current_user): Quản lý hồ sơ tài xế / nhân viên.

update_bonus_config_transaction(db_pool, updated_values, nguoi_dung): Cập nhật bảng định mức lương/thưởng.
