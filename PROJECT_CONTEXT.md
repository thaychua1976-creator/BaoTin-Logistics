# 🚀 HỒ SƠ DỰ ÁN: HỆ THỐNG QUẢN LÝ BẢO TÍN LOGISTICS

## 1. THÔNG TIN CHUNG & CÔNG NGHỆ
- **Mục tiêu:** Xây dựng phần mềm ERP quản lý vận tải, điều phối xe, nhân sự và quyết toán logistics.
- **Frontend:** Python Streamlit.
- **Backend/Database:** MySQL (lưu trữ trên Aiven) + Connection Pool.
- **Nguyên tắc Coding bắt buộc:**
  1. Mọi thao tác Thêm/Sửa/Xóa (CUD) phải dùng `try...except` và `Transaction` (`conn.autocommit = False`, `conn.commit()`, `conn.rollback()`).
  2. Phải kiểm tra `cursor.rowcount` sau lệnh UPDATE/DELETE.
  3. Dữ liệu tiền tệ từ giao diện bắt buộc đưa qua hàm `parse_money_input()` trước khi xử lý, hiển thị ra giao diện phải có dấu phẩy phân cách nhóm ngàn cho dễ nhìn.
  4. Dữ liệu ngày tháng khi hiển thị phải format dạng dd/mm/yyyy và khi lưu vào database phải định dạng lại cho đúng theo mysql
  5. Kiểm tra NAN, NULL, lỗi convert, không tự ý thêm số 0 phía sau dấu chấm nếu là tiền tệ.
  6. Hãy tự phân mảnh fragment để khi thực hiện các tác vụ các tab được mềm mại tránh bị dựt để tăng trải nghiệm người dùng khi làm việc với streamlit
  7. Khi rerun form khi thực hiện các tác vụ liên quan đến database như thêm, sửa, xoá thì form phải reset trắng tránh để form còn dữ liệu.
  8. Khi sửa code thì chỉ sữa theo yêu cầu không tự ý xoá hay thay đổi các phần khác mà chưa có sự đồng ý; hãy hỏi trước khi thay đổi code
  9. Mọi hành động thay đổi dữ liệu phải được ghi vết bằng các hàm Audit Log.

---

## 2. CẤU TRÚC DATABASE (SCHEMA)
*(⚠️ Lời nhắc cho Dev: Hãy copy kết quả của lệnh `SHOW CREATE TABLE` từ DBeaver cho các bảng chính (xe, chuyen_di, lich_su_bao_duong, users, nhan_vien...) và dán vào đây để AI hiểu cấu trúc cột.)*

```sql

-- logistics_app.audit_logs definition

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


-- logistics_app.danh_muc_phu_phi definition

CREATE TABLE "danh_muc_phu_phi" (
  "ma_phu_phi" varchar(50) NOT NULL,
  "ten_phu_phi" varchar(150) NOT NULL,
  "loai_ap_dung" enum('Co_Dinh','Theo_Gio','Theo_Ty_Le') DEFAULT 'Co_Dinh',
  "don_gia_mac_dinh" decimal(15,2) DEFAULT '0.00',
  PRIMARY KEY ("ma_phu_phi")
);


-- logistics_app.dm_tai_trong_phu_cap definition

CREATE TABLE "dm_tai_trong_phu_cap" (
  "id" int NOT NULL AUTO_INCREMENT,
  "ten_hien_thi" varchar(50) NOT NULL COMMENT 'VD: 1<=2T, 3.5T, 14T',
  "tai_trong_min" decimal(10,2) NOT NULL DEFAULT '0.00',
  "tai_trong_max" decimal(10,2) NOT NULL DEFAULT '99.00',
  PRIMARY KEY ("id")
);


-- logistics_app.dm_tieu_chi_phu_cap definition

CREATE TABLE "dm_tieu_chi_phu_cap" (
  "id" int NOT NULL AUTO_INCREMENT,
  "ten_tieu_chi" text NOT NULL COMMENT 'VD: Vận chuyển hàng 1 cty giao >=3 điểm',
  "km_min" decimal(10,2) DEFAULT '0.00' COMMENT 'Khoảng cách tối thiểu',
  "km_max" decimal(10,2) DEFAULT '0.00' COMMENT 'Khoảng cách tối đa để kích hoạt phụ cấp',
  PRIMARY KEY ("id")
);


-- logistics_app.khach_hang definition

CREATE TABLE "khach_hang" (
  "id" int NOT NULL AUTO_INCREMENT,
  "ten_khach_hang" varchar(150) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  "ma_khach_hang" varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  "so_dien_thoai" varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  "zalo_user_id" varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Mã định danh User ID Zalo OA',
  "ma_so_thue" varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Mã số thuế để xuất hóa đơn',
  "dia_chi" varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Địa chỉ trụ sở khách hàng',
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
  "zalo_user_id" varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Mã định danh User ID Zalo OA',
  PRIMARY KEY ("id"),
  UNIQUE KEY "ma_nhan_vien" ("ma_nhan_vien"),
  KEY "idx_sdt_nhanvien" ("so_dien_thoai")
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
  "ghi_chu" text COLLATE utf8mb4_unicode_ci,
  PRIMARY KEY ("id"),
  UNIQUE KEY "bien_so_xe" ("bien_so_xe"),
  KEY "idx_xe_han_bao_hiem" ("han_bao_hiem_ds"),
  KEY "idx_xe_trang_thai" ("trang_thai"),
  KEY "idx_xe_han_dang_kiem" ("han_dang_kiem"),
  KEY "idx_xe_han_phu_hieu" ("han_phu_hieu")
);


-- logistics_app.bang_gia_hai_quan definition

CREATE TABLE "bang_gia_hai_quan" (
  "id" int NOT NULL AUTO_INCREMENT,
  "khach_hang_id" int NOT NULL,
  "nhom_dich_vu" varchar(150) NOT NULL COMMENT 'VD: Thủ tục Hải Quan Nhập Cont, Thủ tục HQ Nhập Lẻ',
  "phan_loai_chi_tiet" varchar(255) NOT NULL COMMENT 'VD: Nguyên Liệu, Thiết bị <= 50 dòng, > 50 dòng',
  "don_gia_hq" decimal(15,2) NOT NULL DEFAULT '0.00',
  "dia_diem_thong_quan" varchar(50) DEFAULT 'Cang_Bien' COMMENT 'Phân loại: Cang_Bien (Cát Lái, Cảng đích...), San_Bay (Tân Sơn Nhất, Nội Bài...)',
  "ghi_chu" text,
  PRIMARY KEY ("id"),
  KEY "idx_bghq_kh" ("khach_hang_id"),
  CONSTRAINT "fk_bghq_kh" FOREIGN KEY ("khach_hang_id") REFERENCES "khach_hang" ("id") ON DELETE CASCADE
);


-- logistics_app.chuyen_di definition

CREATE TABLE "chuyen_di" (
  "id" int NOT NULL AUTO_INCREMENT,
  "chuyen_goc_id" int DEFAULT NULL,
  "ngay_chuyen_di" date NOT NULL,
  "xe_id" int DEFAULT NULL,
  "ten_khach_hang" varchar(150) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  "dia_chi_khach_hang" varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  "dia_diem_giao_nhan" varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  "doanh_thu" decimal(15,2) DEFAULT '0.00',
  "khach_hang_id" int DEFAULT NULL,
  "tuyen_duong_id" int DEFAULT NULL,
  "cong_chuyen" decimal(15,2) DEFAULT '0.00',
  "trang_thai_chuyen" enum('Tao_Moi','Dang_Di','Quyet_Toan','Hoan_Thanh','Huy_Chuyen') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'Tao_Moi',
  "ghi_chu" text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  "phi_hai_quan" decimal(15,2) DEFAULT '0.00',
  "phi_boc_xep" decimal(15,2) DEFAULT '0.00',
  "phi_khac" decimal(15,2) DEFAULT '0.00',
  "is_gop_chuyen" tinyint DEFAULT '0',
  "tien_them" decimal(15,2) DEFAULT '0.00',
  "ghi_chu_quyet_toan" text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  "is_ve_khuya" tinyint DEFAULT '0',
  "khoi_luong_kg" decimal(10,2) DEFAULT '0.00',
  "the_tich_cbm" decimal(10,2) DEFAULT '0.00',
  "is_thue_ngoai" tinyint(1) DEFAULT '0' COMMENT '1: Chuyến có thuê ngoài, 0: Nội bộ',
  "loai_doi_tac_ngoai" enum('Nha_Xe','Tu_Nhan') COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Phân loại đối tác',
  "ten_doi_tac_ngoai" varchar(150) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Tên nhà xe hoặc tên chủ xe tư nhân',
  "bien_so_xe_ngoai" varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Biển số thực tế chở hàng',
  "tai_xe_ngoai_ten" varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Tên tài xế thực tế',
  "tai_xe_ngoai_sdt" varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'SĐT tài xế',
  "tai_xe_ngoai_cccd" varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'CCCD tài xế để đối chiếu',
  "chi_phi_thue_ngoai" decimal(15,2) DEFAULT '0.00' COMMENT 'Giá vốn thuê ngoài',
  "hinh_thuc_thanh_toan_ngoai" enum('Tien_Mat','Cong_No') COLLATE utf8mb4_unicode_ci DEFAULT 'Cong_No' COMMENT 'Tiền tươi hay công nợ tháng',
  "loai_hinh_xe" enum('Container','Xe_Tai','Xe_May') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT 'Xe_Tai' COMMENT 'Phân loại chuyến đi: Container, Xe_Tai hoặc Xe_May',
  "is_tinh_cuoc_tu_dong" tinyint(1) DEFAULT '0' COMMENT '1: Đã được module auto-billing xử lý, 0: Chưa tính',
  "is_hang_tra_ve" tinyint(1) DEFAULT '0' COMMENT '1: Đánh dấu chuyến này là chạy hàng trả về',
  "quy_cach_thuc_te" varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Lưu mã quy cách thực tế chạy (VD: 20RF, 40HC, 1T_NGUY_HIEM) để khớp với rate_cards',
  "ma_chuyen_ghep" varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Mã nhóm để gom các chuyến ghép/tiếp nối của cùng 1 xe (VD: GC-260807-001)',
  "stt_chuyen_ghep" int DEFAULT '1' COMMENT 'Thứ tự lấy/giao hàng (1, 2, 3...) để xét giảm giá hoặc chia lương',
  PRIMARY KEY ("id"),
  KEY "khach_hang_id" ("khach_hang_id"),
  KEY "tuyen_duong_id" ("tuyen_duong_id"),
  KEY "idx_xe_id" ("xe_id"),
  KEY "idx_trangthai_ngay" ("trang_thai_chuyen","ngay_chuyen_di"),
  KEY "idx_trip_search" ("trang_thai_chuyen","ngay_chuyen_di","xe_id"),
  KEY "fk_chuyen_di_chuyen_goc" ("chuyen_goc_id"),
  CONSTRAINT "chuyen_di_ibfk_1" FOREIGN KEY ("xe_id") REFERENCES "xe" ("id") ON DELETE SET NULL,
  CONSTRAINT "chuyen_di_ibfk_2" FOREIGN KEY ("khach_hang_id") REFERENCES "khach_hang" ("id") ON DELETE SET NULL,
  CONSTRAINT "fk_chuyen_di_chuyen_goc" FOREIGN KEY ("chuyen_goc_id") REFERENCES "chuyen_di" ("id") ON DELETE SET NULL,
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


-- logistics_app.lich_su_do_xang definition

CREATE TABLE "lich_su_do_xang" (
  "id" int NOT NULL AUTO_INCREMENT,
  "xe_id" int NOT NULL,
  "ngay_do" datetime DEFAULT CURRENT_TIMESTAMP,
  "odo_hien_tai" decimal(15,2) NOT NULL COMMENT 'Số KM trên đồng hồ lúc đổ xăng',
  "so_lit" decimal(10,2) NOT NULL,
  "tong_tien" decimal(15,2) NOT NULL,
  "don_gia" decimal(10,2) DEFAULT NULL,
  "hieu_suat_tieu_hao" decimal(10,2) DEFAULT NULL COMMENT 'Tính toán Lít/100km từ lần đổ trước',
  "trang_thai_canh_bao" enum('Binh_Thuong','Hao_Hut_Bat_Thuong') DEFAULT 'Binh_Thuong',
  "hinh_anh_bill" varchar(255) DEFAULT NULL,
  "ghi_chu" text,
  "nguoi_nhap" varchar(50) NOT NULL,
  PRIMARY KEY ("id"),
  KEY "idx_xe_do_xang" ("xe_id"),
  CONSTRAINT "fk_do_xang_xe" FOREIGN KEY ("xe_id") REFERENCES "xe" ("id") ON DELETE CASCADE
);


-- logistics_app.ma_tran_phu_cap definition

CREATE TABLE "ma_tran_phu_cap" (
  "tai_trong_id" int NOT NULL,
  "tieu_chi_id" int NOT NULL,
  "so_tien" decimal(15,2) DEFAULT '0.00',
  PRIMARY KEY ("tai_trong_id","tieu_chi_id"),
  KEY "fk_mt_tc" ("tieu_chi_id"),
  CONSTRAINT "fk_mt_tc" FOREIGN KEY ("tieu_chi_id") REFERENCES "dm_tieu_chi_phu_cap" ("id") ON DELETE CASCADE,
  CONSTRAINT "fk_mt_tt" FOREIGN KEY ("tai_trong_id") REFERENCES "dm_tai_trong_phu_cap" ("id") ON DELETE CASCADE
);


-- logistics_app.phu_phi_khach_hang definition

CREATE TABLE "phu_phi_khach_hang" (
  "id" int NOT NULL AUTO_INCREMENT,
  "khach_hang_id" int NOT NULL,
  "ten_phu_phi" varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'VD: Phụ phí Đồng Nai, Phí Hiệp Phước, Kiểm hóa luồng đỏ',
  "don_gia_phu_phi" decimal(15,2) NOT NULL DEFAULT '0.00',
  "dieu_kien_kich_hoat" varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Từ khóa tự động kích hoạt trên lộ trình/tờ khai (VD: ĐỒNG NAI, HIỆP PHƯỚC, ĐỎ)',
  "loai_ap_dung" varchar(100) DEFAULT NULL,
  "ghi_chu" text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci COMMENT 'Ghi chú chi tiết phụ phí',
  PRIMARY KEY ("id"),
  KEY "idx_phu_phi_khach" ("khach_hang_id"),
  CONSTRAINT "fk_phu_phi_khach" FOREIGN KEY ("khach_hang_id") REFERENCES "khach_hang" ("id") ON DELETE CASCADE
);


-- logistics_app.rate_cards definition

CREATE TABLE "rate_cards" (
  "id" int NOT NULL AUTO_INCREMENT,
  "khach_hang_id" int NOT NULL,
  "ten_bang_gia" varchar(150) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Mã báo giá (VD: 02 ZX-BT/2026)',
  "diem_di" varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Từ khóa Kho lấy hàng (VD: Phước Đông, Tân Hương)',
  "diem_den" varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Từ khóa Kho giao/Cảng (VD: Cát Lái, Bình Dương)',
  "phan_loai_phuong_tien" enum('Container','Xe_Tai','Hang_Le','Hang_Air','Xe_May') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'Xe_Tai',
  "loai_xe_quy_cach" varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Từ khóa khớp xe: 1T, 5T, 20DC, 40HC',
  "gioi_han_kg" decimal(10,2) DEFAULT '0.00' COMMENT 'Dành cho báo giá Hàng Lẻ (Max KG)',
  "gioi_han_cbm" decimal(10,2) DEFAULT '0.00' COMMENT 'Dành cho báo giá Hàng Lẻ (Max CBM)',
  "is_hang_tra_ve" tinyint(1) DEFAULT '0' COMMENT '1: Giá áp dụng cho hàng trả về (Case Sincetech)',
  "don_gia_cuoc" decimal(15,2) NOT NULL DEFAULT '0.00' COMMENT 'Giá cước vận chuyển',
  "hieu_luc_tu" date DEFAULT NULL,
  "hieu_luc_den" date DEFAULT NULL,
  "gia_chuyen_tiep_noi" decimal(15,2) DEFAULT '0.00' COMMENT 'Mức giá (hoặc số tiền giảm) áp dụng từ chuyến thứ 2 trở đi',
  "khoang_cach" decimal(15,2) DEFAULT NULL,
  "ghi_chu" text,
  PRIMARY KEY ("id"),
  KEY "idx_rate_khach_hang" ("khach_hang_id"),
  CONSTRAINT "fk_rate_khach" FOREIGN KEY ("khach_hang_id") REFERENCES "khach_hang" ("id") ON DELETE CASCADE
);


-- logistics_app.to_khai_hai_quan definition

CREATE TABLE "to_khai_hai_quan" (
  "id" int NOT NULL AUTO_INCREMENT,
  "so_to_khai" varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  "so_van_don" varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  "loai_to_khai" enum('Noi_Dia','Nhap_Khau','Xuat_Khau','DHL') COLLATE utf8mb4_unicode_ci NOT NULL,
  "ngay_khai" date NOT NULL,
  "khach_hang_id" int NOT NULL,
  "so_hoa_don_tm" varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  "kho_cang_lay_hang" text COLLATE utf8mb4_unicode_ci,
  "ten_doi_tac" text COLLATE utf8mb4_unicode_ci,
  "ma_loai_hinh" varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  "so_kien" varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  "tong_trong_luong_hang" decimal(10,2) DEFAULT '0.00',
  "loai_cont_xe" varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  "so_cont" varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  "phan_luong" enum('Xanh','Vang','Do') COLLATE utf8mb4_unicode_ci DEFAULT 'Xanh',
  "phi_khac" decimal(15,2) DEFAULT '0.00' COMMENT 'Phí phát sinh',
  "phi_dich_vu_hq" decimal(15,2) DEFAULT NULL,
  "trang_thai" enum('Moi_Tao','Hoan_Thanh','Da_Huy') COLLATE utf8mb4_unicode_ci DEFAULT 'Hoan_Thanh',
  "ghi_chu" text COLLATE utf8mb4_unicode_ci,
  PRIMARY KEY ("id"),
  UNIQUE KEY "so_to_khai" ("so_to_khai"),
  KEY "fk_tk_kh" ("khach_hang_id"),
  CONSTRAINT "fk_tk_kh" FOREIGN KEY ("khach_hang_id") REFERENCES "khach_hang" ("id")
);


-- logistics_app.users definition

CREATE TABLE "users" (
  "id" int NOT NULL AUTO_INCREMENT,
  "username" varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  "password" varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  "role" varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  "ho_ten" varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  "trang_thai" varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT 'Dang_Hoat_Dong',
  "nhan_vien_id" int DEFAULT NULL,
  PRIMARY KEY ("id"),
  UNIQUE KEY "username" ("username"),
  KEY "fk_user_nhanvien" ("nhan_vien_id"),
  CONSTRAINT "fk_user_nhanvien" FOREIGN KEY ("nhan_vien_id") REFERENCES "nhan_vien" ("id") ON DELETE SET NULL
);


-- logistics_app.chi_tiet_phi_hai_quan definition

CREATE TABLE "chi_tiet_phi_hai_quan" (
  "id" int NOT NULL AUTO_INCREMENT,
  "to_khai_id" int NOT NULL COMMENT 'Liên kết tới bảng to_khai_hai_quan',
  "ten_loai_phi" varchar(150) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'VD: Phí sửa tờ khai, Phí kiểm hóa luồng đỏ...',
  "so_tien" decimal(15,2) NOT NULL DEFAULT '0.00',
  "ghi_chu" text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  PRIMARY KEY ("id"),
  KEY "fk_ct_phi_hq" ("to_khai_id"),
  CONSTRAINT "fk_ct_phi_hq" FOREIGN KEY ("to_khai_id") REFERENCES "to_khai_hai_quan" ("id") ON DELETE CASCADE
);


-- logistics_app.container_quan_ly definition

CREATE TABLE "container_quan_ly" (
  "id" int NOT NULL AUTO_INCREMENT,
  "so_cont" varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'Số container (đã chuẩn hóa viết hoa)',
  "loai_cont" varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Loại cont (VD: 20DC, 40HC, 45RF)',
  "chuyen_di_id" int DEFAULT NULL COMMENT 'Liên kết tới chuyến đi điều xe',
  "to_khai_id" int DEFAULT NULL COMMENT 'Liên kết tới tờ khai hải quan',
  "phi_nang_ha_on" decimal(15,2) DEFAULT '0.00' COMMENT 'Phí nâng ON của container này',
  "so_hoa_don_lift_on" varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Số hóa đơn nâng ON',
  "phi_nang_ha_off" decimal(15,2) DEFAULT '0.00' COMMENT 'Phí hạ OFF của container này',
  "so_hoa_don_lift_off" varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Số hóa đơn hạ OFF',
  "phi_to_khai" decimal(15,2) DEFAULT '0.00' COMMENT 'Phí tờ khai theo số container',
  "phi_bot" decimal(15,2) DEFAULT '0.00' COMMENT 'Phí BOT',
  "phi_lay_mau" decimal(15,2) DEFAULT '0.00' COMMENT 'Phí lấy mẫu',
  "phi_kiem_dich" decimal(15,2) DEFAULT '0.00' COMMENT 'Phí kiểm dịch',
  "so_hoa_don_kiem_dich" varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Số hóa đơn kiểm dịch',
  "phi_luu_bai" decimal(15,2) DEFAULT '0.00' COMMENT 'Phí lưu bãi',
  "so_hoa_don_luu_bai" varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Số hóa đơn lưu bãi',
  "phi_do" decimal(15,2) DEFAULT '0.00' COMMENT 'Phí chứng từ DO',
  "so_hoa_don_do" varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Số hóa đơn DO',
  "phi_handling" decimal(15,2) DEFAULT '0.00' COMMENT 'Phí Handling',
  "so_hoa_don_handling" varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Số hóa đơn Handling',
  "phi_khu_trung" decimal(15,2) DEFAULT '0.00' COMMENT 'Phí khử trùng',
  "so_hoa_don_khu_trung" varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Số hóa đơn khử trùng',
  "phi_van_chuyen" decimal(15,2) DEFAULT '0.00' COMMENT 'Cước vận chuyển riêng cho container này',
  "phi_thong_quan" decimal(15,2) DEFAULT NULL,
  "phi_csht" decimal(10,2) DEFAULT NULL,
  "so_hoa_don_csht" varchar(10) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  "ghi_chu" text COLLATE utf8mb4_unicode_ci,
  PRIMARY KEY ("id"),
  KEY "idx_cont_chuyen_di" ("chuyen_di_id"),
  KEY "idx_cont_to_khai" ("to_khai_id"),
  CONSTRAINT "fk_cont_chuyen_di" FOREIGN KEY ("chuyen_di_id") REFERENCES "chuyen_di" ("id") ON DELETE CASCADE,
  CONSTRAINT "fk_cont_to_khai" FOREIGN KEY ("to_khai_id") REFERENCES "to_khai_hai_quan" ("id") ON DELETE CASCADE
);


-- logistics_app.to_khai_co definition

CREATE TABLE "to_khai_co" (
  "id" int NOT NULL AUTO_INCREMENT,
  "to_khai_id" int NOT NULL COMMENT 'Liên kết tới bảng to_khai_hai_quan',
  "form_co" varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Loại Form C/O (VD: FORM AJ, Form D, Form E...)',
  "so_co" varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'Số C/O',
  "ngay_co" date DEFAULT NULL COMMENT 'Ngày cấp C/O',
  "phi_co" decimal(15,2) DEFAULT '0.00' COMMENT 'Lệ phí xin C/O',
  "phi_dvhq" decimal(15,2) DEFAULT NULL,
  "so_hoa_don_co" varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Số hóa đơn phí C/O',
  "ghi_chu" text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci COMMENT 'Ghi chú thêm',
  PRIMARY KEY ("id"),
  UNIQUE KEY "so_co" ("so_co"),
  KEY "fk_co_to_khai" ("to_khai_id"),
  CONSTRAINT "fk_co_to_khai" FOREIGN KEY ("to_khai_id") REFERENCES "to_khai_hai_quan" ("id") ON DELETE CASCADE
);

## CẤU TRÚC BACKEND
*** Hệ thống đã được module hóa thành 5 file Python. Tuyệt đối không viết lại hàm mới nếu hàm đã tồn tại trong danh sách dưới đây, chỉ cần import và gọi lại.
File 1: utils_core.py (Tiện ích dùng chung)
parse_money_input(val_str): Xóa dấu phẩy, chuyển chuỗi tiền tệ thành số int/float.
clean_limit_number(val): Hàm làm sạch các chuỗi giới hạn như '<=6', '< 10 KGS', '<=25CBM' để trích xuất ra số thực float an toàn.
normalize_text(text):Chuẩn hóa chuỗi tiếng Việt (NFC) để so sánh chính xác, xóa khoảng trắng thừa
import_and_update_bang_gia_transaction(db_pool, df_rates, df_surcharges, current_user):Import/Update Bảng giá từ Excel. 
import_and_update_phu_phi_transaction(db_pool, df_surcharges, current_user):Import/Update Phụ phí khách hàng từ Excel. Sửa lỗi tương tự bảng giá.
update_single_rate_card_transaction(db_pool, rate_id, data_dict, current_user):Cập nhật một dòng bảng giá cụ thể theo ID
delete_single_rate_card_transaction(db_pool, rate_id, current_user):Xóa một dòng bảng giá cụ thể theo ID
update_single_phu_phi_transaction(db_pool, pp_id, data_dict, current_user):Cập nhật một dòng phụ phí cụ thể theo ID
delete_single_phu_phi_transaction(db_pool, pp_id, current_user): Xóa một dòng phụ phí cụ thể theo ID
create_single_rate_card_transaction(db_pool, data_dict, current_user):Thêm mới một dòng bảng giá từ giao diện UI
create_single_phu_phi_transaction(db_pool, data_add_pp, current_user):Hàm thêm mới 1 dòng Phụ phí vào cơ sở dữ liệu.
tinh_tong_phu_cap_tu_dong(db_pool, xe_id, danh_sach_tieu_chi_id):Hệ thống tự động dò ma trận để tính phụ cấp dựa trên Tải trọng xe và Tiêu chí phát sinh
parse_tai_trong_excel(text):Hàm AI bóc tách Tải Trọng Min/Max từ Text Excel (Ví dụ: 1<=2T, 3.5T, >15T)
import_excel_phu_cap_transaction(db_pool, df, current_user): Hàm Import Excel

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

File 6:declare_hq_manager.py (Khai báo hải quan, tờ khai,bảng giá hải quan, xuất excel báo cáo hải quan của công ty,
xuat_excel_hai_quan_continental: công ty có form mẫu riêng)
xuat_excel_hai_quan_continental(db, tu_ngay, den_ngay, khach_hang_id=None):
get_phu_phi_theo_khach_hang(db_pool, khach_hang_id): phụ phi khách hàng
get_don_gia_hq_tu_dong(db_pool, khach_hang_id, phan_loai_chi_tiet): get đơn giá hải quan tự động
save_to_khai_transaction(db_pool, tk_data, chi_tiet_phi_list, tk_id, current_user): lưu tơ khai hải quan
delete_to_khai_transaction(db_pool, tk_id, current_user): xoá tờ khai 
save_bang_gia_hai_quan_transaction(db_pool, data_dict, current_user): lưu bảng giá hải quan
update_bang_gia_hai_quan_transaction(db_pool, bg_id, data_dict, current_user): update bảng giá hải quan
elete_bang_gia_hai_quan_transaction(db_pool, bg_id, current_user): xoá bảng giá hải quan
xuat_excel_hai_quan_bao_tin(db, tu_ngay, den_ngay, tu_khoa_cong_ty): xuất báo cáo excel công ty Bảo Tín