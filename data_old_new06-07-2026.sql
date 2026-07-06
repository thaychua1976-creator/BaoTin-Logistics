-- MySQL dump 10.13  Distrib 8.0.19, for Win64 (x86_64)
--
-- Host: localhost    Database: logistics_app
-- ------------------------------------------------------
-- Server version	9.7.0

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;
SET @MYSQLDUMP_TEMP_LOG_BIN = @@SESSION.SQL_LOG_BIN;


--
-- GTID state at the beginning of the backup 
--



--
-- Table structure for table `audit_logs`
--

DROP TABLE IF EXISTS `audit_logs`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `audit_logs` (
  `id` int NOT NULL AUTO_INCREMENT,
  `phan_he` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'Tên phân hệ xảy ra thao tác (Ví dụ: QUAN_LY_TAI_KHOAN, QUAN_LY_CHUYEN_DI)',
  `record_id` int DEFAULT NULL COMMENT 'ID của dòng dữ liệu bị tác động (Ví dụ: user_id hoặc chuyen_di_id)',
  `nguoi_thuc_hien` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'Username của người thực hiện thao tác',
  `hanh_dong` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'Loại thao tác (Ví dụ: TAO_MOI, CAP_NHAT, XOA)',
  `chi_tiet` json DEFAULT NULL COMMENT 'Lưu thông tin chi tiết dưới dạng chuỗi JSON',
  `thoi_gian` datetime DEFAULT CURRENT_TIMESTAMP COMMENT 'Thời điểm thực hiện thao tác',
  PRIMARY KEY (`id`),
  KEY `idx_audit_phan_he` (`phan_he`),
  KEY `idx_audit_nguoi_thuc_hien` (`nguoi_thuc_hien`),
  KEY `idx_audit_thoi_gian` (`thoi_gian`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `audit_logs`
--

LOCK TABLES `audit_logs` WRITE;
/*!40000 ALTER TABLE `audit_logs` DISABLE KEYS */;
INSERT INTO `audit_logs` VALUES (1,'QUAN_LY_TAI_KHOAN',8,'BAO','TAO_MOI','{\"ho_ten\": \"LÊ THI\", \"quyen_han\": \"Admin\", \"trang_thai\": \"Dang_Hoat_Dong\", \"username_bi_tac_dong\": \"Admin\"}','2026-07-06 11:37:46'),(2,'QUAN_LY_TAI_KHOAN',9,'BAO','TAO_MOI','{\"ho_ten\": \"KIM TUYẾN\", \"quyen_han\": \"Admin\", \"trang_thai\": \"Dang_Hoat_Dong\", \"username_bi_tac_dong\": \"COI\"}','2026-07-06 11:38:17');
/*!40000 ALTER TABLE `audit_logs` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `cau_hinh_thuong`
--

DROP TABLE IF EXISTS `cau_hinh_thuong`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `cau_hinh_thuong` (
  `ma_tieu_chi` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `ten_tieu_chi` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `muc_thuong` decimal(15,2) DEFAULT '0.00',
  PRIMARY KEY (`ma_tieu_chi`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `cau_hinh_thuong`
--

LOCK TABLES `cau_hinh_thuong` WRITE;
/*!40000 ALTER TABLE `cau_hinh_thuong` DISABLE KEYS */;
INSERT INTO `cau_hinh_thuong` VALUES ('GOP_CHUYEN','Thưởng chạy gộp chuyến',150000.00),('TAI_TRONG_15T','Phụ cấp chạy xe nặng (Trên 15 Tấn)',200000.00),('TAI_TRONG_5T','Phụ cấp chạy xe trung (Từ 5 - 15 Tấn)',100000.00),('VE_KHUYA','Phụ cấp tài xế chạy về khuya (sau 22h)',150000.00);
/*!40000 ALTER TABLE `cau_hinh_thuong` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `chuyen_di`
--

DROP TABLE IF EXISTS `chuyen_di`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `chuyen_di` (
  `id` int NOT NULL AUTO_INCREMENT,
  `ngay_chuyen_di` date NOT NULL,
  `xe_id` int DEFAULT NULL,
  `ten_khach_hang` varchar(150) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `dia_diem_giao_nhan` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `khach_hang_id` int DEFAULT NULL,
  `tuyen_duong_id` int DEFAULT NULL,
  `so_km_thuc_te` decimal(10,2) DEFAULT '0.00',
  `cong_chuyen` decimal(15,2) DEFAULT '0.00',
  `trang_thai_chuyen` enum('Tao_Moi','Dang_Di','Quyet_Toan','Hoan_Thanh','Huy_Chuyen') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'Tao_Moi',
  `ghi_chu` text COLLATE utf8mb4_unicode_ci,
  `so_lit_xang` decimal(10,2) DEFAULT '0.00',
  `tien_xang` decimal(15,2) DEFAULT '0.00',
  `phi_hai_quan` decimal(15,2) DEFAULT '0.00',
  `phi_boc_xep` decimal(15,2) DEFAULT '0.00',
  `phi_khac` decimal(15,2) DEFAULT '0.00',
  `is_gop_chuyen` tinyint DEFAULT '0',
  `tien_them` decimal(15,2) DEFAULT '0.00',
  `ghi_chu_quyet_toan` text COLLATE utf8mb4_unicode_ci,
  `is_ve_khuya` tinyint DEFAULT '0',
  `khoi_luong_kg` decimal(10,2) DEFAULT '0.00',
  `the_tich_cbm` decimal(10,2) DEFAULT '0.00',
  PRIMARY KEY (`id`),
  KEY `khach_hang_id` (`khach_hang_id`),
  KEY `tuyen_duong_id` (`tuyen_duong_id`),
  KEY `idx_xe_id` (`xe_id`),
  KEY `idx_ngay_trang_thai` (`ngay_chuyen_di`,`trang_thai_chuyen`),
  KEY `idx_trangthai_ngay` (`trang_thai_chuyen`,`ngay_chuyen_di`),
  CONSTRAINT `chuyen_di_ibfk_1` FOREIGN KEY (`xe_id`) REFERENCES `xe` (`id`) ON DELETE SET NULL,
  CONSTRAINT `chuyen_di_ibfk_2` FOREIGN KEY (`khach_hang_id`) REFERENCES `khach_hang` (`id`) ON DELETE SET NULL,
  CONSTRAINT `chuyen_di_ibfk_3` FOREIGN KEY (`tuyen_duong_id`) REFERENCES `tuyen_duong` (`id`) ON DELETE SET NULL,
  CONSTRAINT `chk_khoi_luong` CHECK ((`khoi_luong_kg` >= 0))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `chuyen_di`
--

LOCK TABLES `chuyen_di` WRITE;
/*!40000 ALTER TABLE `chuyen_di` DISABLE KEYS */;
/*!40000 ALTER TABLE `chuyen_di` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `chuyen_di_tai_xe`
--

DROP TABLE IF EXISTS `chuyen_di_tai_xe`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `chuyen_di_tai_xe` (
  `id` int NOT NULL AUTO_INCREMENT,
  `chuyen_di_id` int NOT NULL,
  `tai_xe_id` int NOT NULL,
  `loai_tai_xe` enum('Tai_Chinh','Tai_Phu') COLLATE utf8mb4_unicode_ci DEFAULT 'Tai_Chinh',
  PRIMARY KEY (`id`),
  KEY `chuyen_di_id` (`chuyen_di_id`),
  KEY `tai_xe_id` (`tai_xe_id`),
  CONSTRAINT `chuyen_di_tai_xe_ibfk_1` FOREIGN KEY (`chuyen_di_id`) REFERENCES `chuyen_di` (`id`) ON DELETE CASCADE,
  CONSTRAINT `chuyen_di_tai_xe_ibfk_2` FOREIGN KEY (`tai_xe_id`) REFERENCES `nhan_vien` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `chuyen_di_tai_xe`
--

LOCK TABLES `chuyen_di_tai_xe` WRITE;
/*!40000 ALTER TABLE `chuyen_di_tai_xe` DISABLE KEYS */;
/*!40000 ALTER TABLE `chuyen_di_tai_xe` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `khach_hang`
--

DROP TABLE IF EXISTS `khach_hang`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `khach_hang` (
  `id` int NOT NULL AUTO_INCREMENT,
  `ten_khach_hang` varchar(150) COLLATE utf8mb4_unicode_ci NOT NULL,
  `ma_khach_hang` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `so_dien_thoai` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ma_khach_hang` (`ma_khach_hang`),
  KEY `idx_sdt_khach` (`so_dien_thoai`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `khach_hang`
--

LOCK TABLES `khach_hang` WRITE;
/*!40000 ALTER TABLE `khach_hang` DISABLE KEYS */;
/*!40000 ALTER TABLE `khach_hang` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `lich_su_bao_duong`
--

DROP TABLE IF EXISTS `lich_su_bao_duong`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `lich_su_bao_duong` (
  `id` int NOT NULL AUTO_INCREMENT,
  `xe_id` int DEFAULT NULL,
  `ngay_bao_duong` date DEFAULT NULL,
  `km_thuc_te` decimal(15,2) DEFAULT NULL,
  `hang_muc_sua_chua` text COLLATE utf8mb4_unicode_ci,
  `chi_phi` decimal(15,2) DEFAULT NULL,
  `don_vi_thuc_hien` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ghi_chu` text COLLATE utf8mb4_unicode_ci,
  PRIMARY KEY (`id`),
  KEY `xe_id` (`xe_id`),
  CONSTRAINT `lich_su_bao_duong_ibfk_1` FOREIGN KEY (`xe_id`) REFERENCES `xe` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `lich_su_bao_duong`
--

LOCK TABLES `lich_su_bao_duong` WRITE;
/*!40000 ALTER TABLE `lich_su_bao_duong` DISABLE KEYS */;
/*!40000 ALTER TABLE `lich_su_bao_duong` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `lich_su_thao_tac`
--

DROP TABLE IF EXISTS `lich_su_thao_tac`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `lich_su_thao_tac` (
  `id` int NOT NULL AUTO_INCREMENT,
  `chuyen_di_id` int DEFAULT NULL,
  `nguoi_dung` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT 'He_Thong',
  `hanh_dong` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `chi_tiet` text COLLATE utf8mb4_unicode_ci,
  `thoi_gian` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_lich_su_nguoi_dung` (`nguoi_dung`),
  KEY `idx_lich_su_thoi_gian` (`thoi_gian`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `lich_su_thao_tac`
--

LOCK TABLES `lich_su_thao_tac` WRITE;
/*!40000 ALTER TABLE `lich_su_thao_tac` DISABLE KEYS */;
/*!40000 ALTER TABLE `lich_su_thao_tac` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `nhan_vien`
--

DROP TABLE IF EXISTS `nhan_vien`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `nhan_vien` (
  `id` int NOT NULL AUTO_INCREMENT,
  `ma_nhan_vien` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `ho_ten` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `so_dien_thoai` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `loai_nhan_vien` enum('Tai_Chinh','Tai_Phu','Dieu_Hanh') COLLATE utf8mb4_unicode_ci DEFAULT 'Tai_Chinh',
  `trang_thai` enum('Dang_Lam_Viec','Nghi_Phep','Da_Nghi_Viec') COLLATE utf8mb4_unicode_ci DEFAULT 'Dang_Lam_Viec',
  `cccd` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `giay_phep_lai_xe` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `hang_gplx` varchar(10) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `han_gplx` date DEFAULT NULL,
  `han_the_tap_huan` date DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ma_nhan_vien` (`ma_nhan_vien`),
  KEY `idx_sdt_nhanvien` (`so_dien_thoai`)
) ENGINE=InnoDB AUTO_INCREMENT=46 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `nhan_vien`
--

LOCK TABLES `nhan_vien` WRITE;
/*!40000 ALTER TABLE `nhan_vien` DISABLE KEYS */;
INSERT INTO `nhan_vien` VALUES (1,'NV_80092008163.0','HUỲNH THÁI BÌNH','0783485521','Tai_Chinh','Dang_Lam_Viec','80092008163.0','720120009595.0','C','2030-10-11','2027-04-30'),(2,'NV_72072010392.0','NGUYỄN VĂN SANG','0983880334','Tai_Chinh','Dang_Lam_Viec','72072010392.0','720942000181.0','A1,B2','2034-09-04','2026-12-01'),(3,'NV_72093008551.0','THIỀU HOÀNG TÚ','0704437920','Tai_Chinh','Dang_Lam_Viec','72093008551.0','790141570189.0','B2','2034-12-04','2026-12-01'),(4,'NV_79070023889.0','PHAN VĂN CƯỜNG','0768652643','Tai_Chinh','Dang_Lam_Viec','79070023889.0','790070234756.0','A1, B2','2035-04-20','2026-12-01'),(5,'NV_72085014404.0','ĐINH BẢO ÂN','0868927126','Tai_Chinh','Dang_Lam_Viec','72085014404.0','790108245280.0','D2','2031-03-16','2026-12-01'),(6,'NV_72079005199.0','TRẦN PHÚ QUỐC','0339676113','Tai_Chinh','Dang_Lam_Viec','72079005199.0','790073225812.0','B2','2034-11-29','2026-12-01'),(7,'NV_72076003692.0','TRẦN VĂN TRIỂN','0398726595','Tai_Chinh','Dang_Lam_Viec','72076003692.0','790081020645.0','B2','2033-10-09','2027-04-30'),(8,'NV_72089012430.0','PHAN LÊ VÂN AN','0962493882','Tai_Chinh','Dang_Lam_Viec','72089012430.0','720146003108.0','B2','2034-07-08','2027-04-30'),(9,'NV_72094005653.0','NGUYỄN PHƯỚC HẬU','0339693711','Tai_Chinh','Dang_Lam_Viec','72094005653.0','720149006937.0','C','2029-07-26','2027-04-30'),(10,'NV_79076000742.0','NGUYỄN KHƯƠNG ĐẠI','0707567555','Tai_Chinh','Dang_Lam_Viec','79076000742.0','790138800262.0','E','2028-03-23','2026-08-01'),(11,'NV_72076000267.0','TRẦN THANH ÚT','0986971361','Tai_Chinh','Dang_Lam_Viec','72076000267.0','790101223610.0','B2','2034-08-26','2027-12-27'),(12,'NV_72090011104.0','PHAN PHƯƠNG TÙNG','0941235825','Tai_Chinh','Dang_Lam_Viec','72090011104.0','790173120006.0','C','2027-06-13','2028-08-12'),(13,'NV_72076010309.0','TRẦN VĂN THÍCH','0907190209','Tai_Chinh','Dang_Lam_Viec','72076010309.0','720978000283.0','B2','2034-04-23','2028-09-05'),(14,'NV_72080000380.0','ĐOÀN THANH HÙNG','0906644222','Tai_Chinh','Dang_Lam_Viec','72080000380.0','790064015781.0','C','2029-03-15','2027-05-15'),(15,'NV_72077005330.0','VÕ MINH TRÂN','0946761950','Tai_Chinh','Dang_Lam_Viec','72077005330.0','790080007775.0','B2','2033-03-30','2026-12-01'),(16,'NV_52088010875.0','TRẦN MỪNG','0967755571','Tai_Chinh','Dang_Lam_Viec','52088010875.0','790142955912.0','C','2029-09-13','2026-12-01'),(17,'NV_72089007081.0','LÊ HÀ TÂM','0936243429','Tai_Chinh','Dang_Lam_Viec','72089007081.0','790132430753.0','C','2030-10-15','2026-12-01'),(18,'NV_72075010699.0','TRẦN VĂN TRÒN','0977949611','Tai_Chinh','Dang_Lam_Viec','72075010699.0','720032016689.0','D','2026-10-27','2027-05-15'),(19,'NV_72081002604.0','DƯƠNG MINH QUÝ','0983344692','Tai_Chinh','Dang_Lam_Viec','72081002604.0','790211094289.0','C','2026-12-20','2026-12-01'),(20,'NV_72094000833.0','NGUYỄN THANH VŨ','0985464994','Tai_Chinh','Dang_Lam_Viec','72094000833.0','720236008860.0','C','2028-10-28','2028-08-12'),(21,'NV_72088005506.0','TIẾT MINH QUÂN','0855227936','Tai_Chinh','Dang_Lam_Viec','72088005506.0','790161129600.0','C','2031-05-06','2027-04-30'),(22,'NV_72084018700.0','ĐẶNG VIỆT THẮNG','0783286836','Tai_Chinh','Dang_Lam_Viec','72084018700.0','790150248248.0','C','2030-08-25','2026-12-01'),(23,'NV_72092012203.0','BÙI MINH THIỆN','0396500065','Tai_Chinh','Dang_Lam_Viec','72092012203.0','790137033083.0','E','2029-01-05','2026-08-28'),(24,'NV_72087010876.0','PHAN THANH PHONG','0908340048','Tai_Chinh','Dang_Lam_Viec','72087010876.0','790149950257.0','C','2029-05-17','2027-04-30'),(25,'NV_87093009730.0','PHẠM VĂN BÉ BA','0859997505','Tai_Chinh','Dang_Lam_Viec','87093009730.0','790178024170.0','C','2029-01-23','2027-04-30'),(26,'NV_72084002395.0','TRẦN VĂN HƯNG','0909339181','Tai_Chinh','Dang_Lam_Viec','72084002395.0','790162254747.0','E','2026-12-13','2026-01-09'),(27,'NV_86083000288.0','NGUYỄN TÂM EM','0979221419','Tai_Chinh','Dang_Lam_Viec','86083000288.0','790115017865.0','D','2027-04-19',NULL),(28,'NV_72083006586.0','VÕ QUỐC THIỆN','0977949611','Tai_Chinh','Dang_Lam_Viec','72083006586.0','790045002238.0','C','2027-10-17',NULL),(29,'NV_72084000220.0','LÊ LONG BẰNG','0886699378','Tai_Chinh','Dang_Lam_Viec','72084000220.0','790144690215.0','E','2029-12-02','2026-12-01'),(30,'NV_83088008778.0','NGUYỄN VĂN BÉ THẢO','0972118773','Tai_Chinh','Dang_Lam_Viec','83088008778.0','790187160591.0','C','2028-08-28','2026-12-19'),(31,'NV_72087013900.0','PHẠM MINH TRUNG','0902261852','Tai_Chinh','Dang_Lam_Viec','72087013900.0','790161094320.0','D','2030-08-06','2026-09-21'),(32,'NV_36076011584.0','BÙI ANH TUẤN','0933821907','Tai_Chinh','Dang_Lam_Viec','36076011584.0','790051024220.0','C','2028-10-26','2026-12-01'),(33,'NV_72095008257.0','NGUYỄN THẾ KIỆT','0798865924','Tai_Chinh','Dang_Lam_Viec','72095008257.0','790160057294.0','C','2027-12-15','2026-12-01'),(34,'NV_89092025061.0','THIỀU VĂN THÀNH','0704827307','Tai_Chinh','Dang_Lam_Viec','89092025061.0','790111286700.0','C','2029-07-03','2026-12-01'),(35,'NV_72092005814.0','VÕ TUẤN VŨ','0904048483','Tai_Chinh','Dang_Lam_Viec','72092005814.0','720119003906.0','C','2027-04-04','2027-07-11'),(36,'NV_72094004604.0','TRẦN VĂN TRIỂN','0901234852','Tai_Chinh','Dang_Lam_Viec','72094004604.0','790144018329.0','FC','2027-06-14','2026-09-05'),(37,'NV_72092002549.0','PHẠM LÂM TỰ','0774344993','Tai_Chinh','Dang_Lam_Viec','72092002549.0','790171013454.0','FC','2027-09-21','2026-12-01'),(38,'NV_72092009590.0','PHẠM VĂN TÝ','0355149749','Tai_Chinh','Dang_Lam_Viec','72092009590.0','790145801726.0','FC','2027-09-07','2026-12-01'),(39,'NV_84091011551.0','NGUYỄN MINH TÚ','0387323331','Tai_Chinh','Dang_Lam_Viec','84091011551.0','790133422168.0','FC','2028-06-08','2026-12-01'),(40,'NV_84092013085.0','THẠCH NGỌC PHƯỜNG','0327887880','Tai_Chinh','Dang_Lam_Viec','84092013085.0','790203125999.0','FC','2029-03-22','2026-12-01'),(41,'NV_72089013562.0','BÙI MINH TIẾN','0399991114','Tai_Chinh','Dang_Lam_Viec','72089013562.0','790078226708.0','E,FC','2028-06-08','2026-08-28'),(42,'NV_72085016635.0','LÂM PHONG VŨ','0938749079','Tai_Chinh','Dang_Lam_Viec','72085016635.0','720079000580.0','C','2028-04-21','2026-12-01'),(43,'NV_72092004669.0','HỒ VĂN KHIÊM',NULL,'Tai_Chinh','Dang_Lam_Viec','72092004669.0','790144810914.0','CE','2031-04-13',NULL),(44,'NV_72077000327.0','LÊ BẢO BÌNH','0\'0908648123','Tai_Chinh','Dang_Lam_Viec','72077000327.0','790105027441.0','A1,B2','2034-09-04',NULL),(45,'NV_72076012817.0','NGUYỄN QUỐC HẬN','0918380935','Tai_Chinh','Dang_Lam_Viec','72076012817.0','720030005229.0','D','2030-04-19',NULL);
/*!40000 ALTER TABLE `nhan_vien` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `tuyen_duong`
--

DROP TABLE IF EXISTS `tuyen_duong`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `tuyen_duong` (
  `id` int NOT NULL AUTO_INCREMENT,
  `ten_tuyen` varchar(150) COLLATE utf8mb4_unicode_ci NOT NULL,
  `so_km_chuan` decimal(10,2) DEFAULT '0.00',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `tuyen_duong`
--

LOCK TABLES `tuyen_duong` WRITE;
/*!40000 ALTER TABLE `tuyen_duong` DISABLE KEYS */;
/*!40000 ALTER TABLE `tuyen_duong` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `users`
--

DROP TABLE IF EXISTS `users`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `users` (
  `id` int NOT NULL AUTO_INCREMENT,
  `username` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `password` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `role` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ho_ten` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `trang_thai` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT 'Dang_Hoat_Dong',
  PRIMARY KEY (`id`),
  UNIQUE KEY `username` (`username`)
) ENGINE=InnoDB AUTO_INCREMENT=10 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `users`
--

LOCK TABLES `users` WRITE;
/*!40000 ALTER TABLE `users` DISABLE KEYS */;
INSERT INTO `users` VALUES (3,'BAO','$2b$12$c3loV7pP0x4hvazTzW5WNetpeP1c07IqLDKNNYD3WiKhVg9pRs7ry','Admin','QUỐC BẢO','Dang_Hoat_Dong'),(8,'Admin','$2b$12$kibyP1sIs5qOMmPt/nxpQOz/vTNzC71BnMe/XhV3buqu7.EMuZwiC','Admin','LÊ THI','Dang_Hoat_Dong'),(9,'COI','$2b$12$Cx0Plz6UqWW4VvDJH59C9ubUOt72ihoSGNyxFE9Bo4rRO/SulbJNa','Admin','KIM TUYẾN','Dang_Hoat_Dong');
/*!40000 ALTER TABLE `users` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `xe`
--

DROP TABLE IF EXISTS `xe`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `xe` (
  `id` int NOT NULL AUTO_INCREMENT,
  `bien_so_xe` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `tai_trong_thiet_ke` double DEFAULT NULL,
  `loai_xe` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `dinh_muc_bao_duong` decimal(10,2) DEFAULT '5000.00',
  `km_bao_duong_gan_nhat` decimal(10,2) DEFAULT '0.00',
  `ngay_bao_duong_gan_nhat` date DEFAULT NULL,
  `trang_thai` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT 'Dang_Hoat_Dong',
  `dinh_muc_nhien_lieu` decimal(10,2) DEFAULT '0.00',
  `ma_dinh_vi` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `nha_cung_cap_gps` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `phu_hieu_xe` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `han_phu_hieu` date DEFAULT NULL,
  `sdt_xac_thuc` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `email_xac_thuc` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `quy_cach_thung` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `cua_xe_bam_seal` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `han_dang_kiem` date DEFAULT NULL,
  `han_bao_hiem_ds` date DEFAULT NULL,
  `nhan_hieu_xe` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `dung_tich_cbm` double DEFAULT NULL,
  `tai_xe_co_dinh_id` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `bien_so_xe` (`bien_so_xe`)
) ENGINE=InnoDB AUTO_INCREMENT=60 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `xe`
--

LOCK TABLES `xe` WRITE;
/*!40000 ALTER TABLE `xe` DISABLE KEYS */;
INSERT INTO `xe` VALUES (1,'70C-092.35',1,'XE TẢI THÙNG',5000.00,0.00,NULL,'Dang_Hoat_Dong',0.00,NULL,NULL,'CÔNG TY TNHH THƯƠNG MẠI VÀ GIAO NHẬN VẬN TẢI BẢO TÍN','2032-12-03','0783485521','bao@truckingbaotin.com','3.17X1.72X1.70','2','2026-11-10','2026-11-16','ISUZU',6,1),(2,'70C-042.11',2,'XE TẢI THÙNG',5000.00,0.00,NULL,'Dang_Hoat_Dong',0.00,NULL,NULL,'CÔNG TY TNHH THƯƠNG MẠI VÀ GIAO NHẬN VẬN TẢI BẢO TÍN','2032-12-03','0983880334','bao@truckingbaotin.com','4.47X1.72X1.87','2','2026-11-27','2027-01-08','MITSUBISHI',11,2),(3,'70H-043.32',2,'XE TẢI THÙNG',5000.00,0.00,NULL,'Dang_Hoat_Dong',0.00,NULL,NULL,'DỊCH VỤ VẬN TẢI QUANG MINH','2031-05-03','0704437920','bao@truckingbaotin.com','4.47X1.86X1.87','2','2026-11-03','2027-04-05','ISUZU',11,3),(4,'70C-172.32',2,'XE TẢI THÙNG',5000.00,0.00,NULL,'Dang_Hoat_Dong',0.00,NULL,NULL,'DỊCH DỤ VẬN TẢI ĐỒNG TÂM','2028-07-02','0768652643','bao@truckingbaotin.com','4.26X1.74X1.80','2','2026-08-24','2027-02-18','MITSUBISHI',11,4),(5,'70C-060.00',2,'XE TẢI THÙNG',5000.00,0.00,NULL,'Dang_Hoat_Dong',0.00,NULL,NULL,'DỊCH DỤ VẬN TẢI ĐỒNG TÂM','2028-07-02','0868927126','bao@truckingbaotin.com','4.50X1.85X1.95','2','2026-07-18','2027-01-15','ISUZU',11,5),(6,'70H-016.04',2,'XE TẢI THÙNG',5000.00,0.00,NULL,'Dang_Hoat_Dong',0.00,NULL,NULL,'DỊCH DỤ VẬN TẢI ĐỒNG TÂM','2028-07-02','0339676113','bao@truckingbaotin.com','4.33X1.75X1.90','2','2026-11-07','2026-12-17','ISUZU',11,6),(7,'70H-007.72',2,'XE TẢI THÙNG',5000.00,0.00,NULL,'Dang_Hoat_Dong',0.00,NULL,NULL,'DỊCH DỤ VẬN TẢI ĐỒNG TÂM','2028-07-02','0398726595','bao@truckingbaotin.com','4.47X1.86X1.87','2','2026-09-06','2026-09-17','MITSUBISHI',11,7),(8,'70H-051.47',2,'XE TẢI THÙNG',5000.00,0.00,NULL,'Dang_Hoat_Dong',0.00,NULL,NULL,'DỊCH VỤ VẬN TẢI NAM THỊNH','2031-07-10','0962493882','bao@truckingbaotin.com','4.47X1.86X1.86','2','2026-07-05','2027-04-16','ISUZU',11,8),(9,'70H-051.44',2,'XE TẢI THÙNG',5000.00,0.00,NULL,'Dang_Hoat_Dong',0.00,NULL,NULL,'DỊCH VỤ VẬN TẢI NAM THỊNH','2031-09-04','0339693711','bao@truckingbaotin.com','4.52X1.88X1.87',NULL,'2026-08-24','2026-08-31','ISUZU',11,9),(10,'70H-077.21',2,'XE TẢI THÙNG',5000.00,0.00,NULL,'Dang_Hoat_Dong',0.00,NULL,NULL,'HỢP TÁC XÃ DU LỊCH VẬN TẢI ĐƯỜNG VIỆT','2032-08-19','0707567555','bao@truckingbaotin.com','4.44X1.89X1.87',NULL,'2026-09-04','2026-08-18','ISUZU',11,10),(11,'70H-056.76',1,'XE TẢI THÙNG',5000.00,0.00,NULL,'Dang_Hoat_Dong',0.00,NULL,NULL,'DỊCH VỤ VẬN TẢI NAM THỊNH','2031-11-10','0986971361','bao@truckingbaotin.com','3.12X1.72X1.68',NULL,'2026-11-05','2026-11-07','ISUZU',6,11),(12,'70H-072.94',3.5,'XE TẢI THÙNG',5000.00,0.00,NULL,'Dang_Hoat_Dong',0.00,NULL,NULL,'DỊCH VỤ VẬN TẢI NAM THỊNH','2032-04-16','0941235825','bao@truckingbaotin.com','5.23X2.07X2.17',NULL,'2026-10-10','2027-04-11','ISUZU',18,12),(13,'70H-072.91',3.5,'XE TẢI THÙNG',5000.00,0.00,NULL,'Dang_Hoat_Dong',0.00,NULL,NULL,'DỊCH VỤ VẬN TẢI NAM THỊNH','2032-04-11','0907190209','bao@truckingbaotin.com','4.40X1.90X2.25',NULL,'2026-10-08','2027-04-11','MITSUBISHI',18,13),(14,'70H-077.25',3.5,'XE TẢI THÙNG',5000.00,0.00,NULL,'Dang_Hoat_Dong',0.00,NULL,NULL,'HỢP TÁC XÃ DU LỊCH VẬN TẢI ĐƯỜNG VIỆT','2032-08-11','0906644222','bao@truckingbaotin.com','5.32X2.02X2.20',NULL,'2026-08-06','2026-08-07','ISUZU',18,14),(15,'70C-093.73',3.5,'XE TẢI THÙNG',5000.00,0.00,NULL,'Dang_Hoat_Dong',0.00,NULL,NULL,'CÔNG TY TNHH THƯƠNG MẠI VÀ GIAO NHẬN VẬN TẢI BẢO TÍN','2032-12-03','0946761950','bao@truckingbaotin.com','5.23X2.07X2.17','1','2026-11-22','2027-07-10','ISUZU',18,15),(16,'70H-016.20',5,'XE TẢI THÙNG',5000.00,0.00,NULL,'Dang_Hoat_Dong',0.00,NULL,NULL,'DỊCH DỤ VẬN TẢI ĐỒNG TÂM','2028-07-02','0967755571','bao@truckingbaotin.com','5.70 X2.15X2.08','2','2026-11-13','2026-11-20','ISUZU',22,16),(17,'70C-095.28',5,'XE TẢI THÙNG',5000.00,0.00,NULL,'Dang_Hoat_Dong',0.00,NULL,NULL,'CÔNG TY TNHH THƯƠNG MẠI VÀ GIAO NHẬN VẬN TẢI BẢO TÍN','2032-12-03','0936243429','bao@truckingbaotin.com','6.10X2.70X2.05','2','2026-11-26','2027-07-23','ISUZU',22,17),(18,'70H-036.90',5,'XE TẢI THÙNG',5000.00,0.00,NULL,'Dang_Hoat_Dong',0.00,NULL,NULL,'DỊCH DỤ VẬN TẢI ĐỒNG TÂM','2028-07-02','0977949611','bao@truckingbaotin.com','5.90X2.15X2.20','1','2026-12-07','2027-06-17','ISUZU',22,18),(19,'70H-046.47',5,'XE TẢI THÙNG',5000.00,0.00,NULL,'Dang_Hoat_Dong',0.00,NULL,NULL,'DỊCH DỤ VẬN TẢI ĐỒNG TÂM','2027-07-25','0983344692','bao@truckingbaotin.com','6.16X2.10X2.05','2','2026-06-25','2027-07-01','ISUZU',22,19),(20,'70H-017.63',5,'XE TẢI THÙNG',5000.00,0.00,NULL,'Dang_Hoat_Dong',0.00,NULL,NULL,'DỊCH DỤ VẬN TẢI ĐỒNG TÂM','2028-07-02','0985464994','bao@truckingbaotin.com','5.61X2.11X2.05','2','2026-11-14','2027-07-11','ISUZU',22,20),(21,'70H-046.38',6,'XE TẢI THÙNG',5000.00,0.00,NULL,'Dang_Hoat_Dong',0.00,NULL,NULL,'DỊCH VỤ VẬN TẢI NAM THỊNH','2031-06-12','0855227936','bao@truckingbaotin.com','6.63X2.30X2.33',NULL,'2026-12-08','2026-12-30','HINO',28,21),(22,'70G-004.56',6,'XE TẢI THÙNG',5000.00,0.00,NULL,'Dang_Hoat_Dong',0.00,NULL,NULL,'DỊCH VỤ VẬN TẢI THIÊN PHƯƠNG','2030-11-28','0783286836','bao@truckingbaotin.com','6.70X2.24X2.42','1','2026-11-10','2026-11-10','ISUZU',28,22),(23,'70G-004.66',6,'XE TẢI THÙNG',5000.00,0.00,NULL,'Dang_Hoat_Dong',0.00,NULL,NULL,'DỊCH VỤ VẬN TẢI QUANG MINH','2031-03-15','0396500065','bao@truckingbaotin.com','6.65X2.31X2.32',NULL,'2026-09-09','2027-03-07','HINO',28,23),(24,'70H-019.08',8,'XE TẢI THÙNG',5000.00,0.00,NULL,'Dang_Hoat_Dong',0.00,NULL,NULL,'THƯƠNG MẠI DỊCH VỤ VẬN TẢI PHÚC ĐẠI PHÁT','2031-12-27','0908340048','bao@truckingbaotin.com','7.10X2.32X2.38','3','2026-11-13','2027-05-22','HINO',33,24),(25,'70H-003.08',8,'XE TẢI THÙNG',5000.00,0.00,NULL,'Dang_Hoat_Dong',0.00,NULL,NULL,'DỊCH DỤ VẬN TẢI ĐỒNG TÂM','2028-07-02','0859997505','bao@truckingbaotin.com','8.80X2.33X2.32','3','2026-11-09','2027-04-05','HINO',33,25),(26,'70F-006.79',8,'XE TẢI THÙNG',5000.00,0.00,NULL,'Dang_Hoat_Dong',0.00,NULL,NULL,'DỊCH VỤ VẬN TẢI QUANG MINH','2031-01-26','0909339181','bao@truckingbaotin.com','6.15X2.10X2.20','2','2026-07-20','2027-01-23','ISUZU',33,26),(27,'70C-155.53',8,'XE TẢI THÙNG',5000.00,0.00,NULL,'Dang_Hoat_Dong',0.00,NULL,NULL,'VẬN TẢI HÀNH KHÁCH VÀ HÀNG HÓA ĐƯỜNG BỘ TÂN BIÊN','2026-11-08','0979221419','bao@truckingbaotin.com','8.62X2.34X2.15','mui bạc','2027-02-26','2026-09-22','HINO',33,27),(28,'70H-056.06',8,'XE TẢI THÙNG',5000.00,0.00,NULL,'Dang_Hoat_Dong',0.00,NULL,NULL,'DỊCH VỤ VẬN TẢI NAM THỊNH','2031-11-07','0977949611','bao@truckingbaotin.com','7.60X2.36X2.52',NULL,'2026-11-03','2026-11-07','ISUZU',33,28),(29,'70H-040.50',8,'XE TẢI THÙNG',5000.00,0.00,NULL,'Dang_Hoat_Dong',0.00,NULL,NULL,'HỢP TÁC XÃ TRƯỜNG THỊNH','2026-08-22','0886699378','bao@truckingbaotin.com','8.20X2.43X2.32','3','2026-09-10','2026-09-20','CHENGLONG',33,29),(30,'70H-075.77',8,'XE TẢI THÙNG',5000.00,0.00,NULL,'Dang_Hoat_Dong',0.00,NULL,NULL,'HỢP TÁC XÃ DỊCH VỤ VẬN TẢI CÔNG NÔNG','2032-12-17','0972118773','bao@truckingbaotin.com','8.00X2.40X2.40',NULL,'2026-12-16','2027-04-08','ISUZU',33,30),(31,'70H-060.31',8,'XE TẢI THÙNG',5000.00,0.00,NULL,'Dang_Hoat_Dong',0.00,NULL,NULL,'HỢP TÁC XÃ DỊCH VỤ VẬN TẢI CÔNG NÔNG','2032-12-18','0902261852','bao@truckingbaotin.com','7.55X2.40X2.32',NULL,'2026-12-17','2027-07-08','ISUZU',33,31),(32,'70F-006.59',14,'XE TẢI THÙNG',5000.00,0.00,NULL,'Dang_Hoat_Dong',0.00,NULL,NULL,'DỊCH VỤ VẬN TẢI THIÊN PHƯƠNG','2030-11-28','0933821907','bao@truckingbaotin.com','9.30X2.40X2.52',NULL,'2026-11-10','2027-06-29','HINO',47,32),(33,'70H-045.91',14,'XE TẢI THÙNG',5000.00,0.00,NULL,'Dang_Hoat_Dong',0.00,NULL,NULL,'DỊCH VỤ VẬN TẢI THIÊN PHƯƠNG','2027-12-10','0798865924','bao@truckingbaotin.com','9.30X2.35X2.30','2','2026-07-24','2027-07-28','ISUZU',47,33),(34,'70H-036.79',14,'XE TẢI THÙNG',5000.00,0.00,NULL,'Dang_Hoat_Dong',0.00,NULL,NULL,'DỊCH DỤ VẬN TẢI ĐỒNG TÂM','2028-07-02','0704827307','bao@truckingbaotin.com','9.90X2.43X2.58','4','2027-06-07','2027-06-07','CHENGLONG',47,34),(35,'70H-046.34',14,'XE TẢI THÙNG',5000.00,0.00,NULL,'Dang_Hoat_Dong',0.00,NULL,NULL,'DỊCH DỤ VẬN TẢI ĐỒNG TÂM','2027-07-25','0904048483','bao@truckingbaotin.com','9.17X2.35X2.20','2','2026-07-18','2027-07-22','HINO',47,35),(36,'70H-032.25',0,'ĐẦU KÉO',5000.00,0.00,NULL,'Dang_Hoat_Dong',0.00,NULL,NULL,'VẬN TẢI HÀNH KHÁCH VÀ HÀNG HÓA ĐƯỜNG BỘ TÂN BIÊN','2026-11-08','0901234852','bao@truckingbaotin.com',NULL,NULL,'2026-10-28','2027-05-20','CHENGLONG',0,36),(37,'70H-036.84',0,'ĐẦU KÉO',5000.00,0.00,NULL,'Dang_Hoat_Dong',0.00,NULL,NULL,'DỊCH VỤ VẬN TẢI VẠN PHÁT','2027-09-06','0774344993','bao@truckingbaotin.com',NULL,NULL,'2026-08-21','2026-08-24','FAW',0,37),(38,'70G-004.95',0,'ĐẦU KÉO',5000.00,0.00,NULL,'Dang_Hoat_Dong',0.00,NULL,NULL,'DỊCH VỤ VẬN TẢI BẢO KHÔI','2030-12-08','0355149749','bao@truckingbaotin.com',NULL,NULL,'2026-11-29','2026-10-07','HYUNDAI',0,38),(39,'70H-065.92',0,'ĐẦU KÉO',5000.00,0.00,NULL,'Dang_Hoat_Dong',0.00,NULL,NULL,'DỊCH VỤ VẬN TẢI NAM THỊNH','2032-04-11','0387323331','bao@truckingbaotin.com',NULL,NULL,'2026-10-05','2027-04-11',NULL,0,39),(40,'70H-077.02',0,'ĐẦU KÉO',5000.00,0.00,NULL,'Dang_Hoat_Dong',0.00,NULL,NULL,'HỢP TÁC XÃ DU LỊCH VẬN TẢI ĐƯỜNG VIỆT','2032-06-20','0327887880','bao@truckingbaotin.com',NULL,NULL,'2027-06-17','2026-09-17',NULL,0,40),(41,'70H-077.09',0,'ĐẦU KÉO',5000.00,0.00,NULL,'Dang_Hoat_Dong',0.00,NULL,NULL,'HỢP TÁC XÃ DU LỊCH VẬN TẢI ĐƯỜNG VIỆT','2032-08-11','0399991114','bao@truckingbaotin.com',NULL,NULL,'2026-08-08','2026-08-07','FAW',0,41),(42,'70H-135.60',0,'ĐẦU KÉO',5000.00,0.00,NULL,'Dang_Hoat_Dong',0.00,NULL,NULL,'DỊCH DỤ VẬN TẢI ĐỒNG TÂM',NULL,'0938749079','bao@truckingbaotin.com',NULL,NULL,'2027-01-22','2027-01-23',NULL,0,42),(43,'70H-135.31',0,'ĐẦU KÉO',5000.00,0.00,NULL,'Dang_Hoat_Dong',0.00,NULL,NULL,'HỢP TÁC XÃ DỊCH VỤ VẬN TẢI CÔNG NÔNG','2033-05-13',NULL,'bao@truckingbaotin.com',NULL,NULL,'2026-11-19',NULL,'UD TRUCKS',0,43),(44,'70A-303.27',0,'4 CHỖ',5000.00,0.00,NULL,'Dang_Hoat_Dong',0.00,NULL,NULL,NULL,NULL,'0\'0908648123','bao@truckingbaotin.com',NULL,NULL,NULL,'2027-04-06',NULL,0,44),(45,'70A-388.81',0,'7 CHỖ',5000.00,0.00,NULL,'Dang_Hoat_Dong',0.00,NULL,NULL,NULL,NULL,'0918380935','bao@truckingbaotin.com',NULL,NULL,'2027-03-23','2027-02-02',NULL,0,45),(46,'70RM-00030',0,'REMOOC',5000.00,0.00,NULL,'Dang_Hoat_Dong',0.00,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2026-11-02',NULL,'DOOSUNG',0,NULL),(47,'70RM-000040',5,'REMOOC',5000.00,0.00,NULL,'Dang_Hoat_Dong',0.00,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2026-11-02',NULL,NULL,22,NULL),(48,'70RM-005.75',8,'REMOOC',5000.00,0.00,NULL,'Dang_Hoat_Dong',0.00,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2026-08-08',NULL,NULL,33,NULL),(49,'70RM-008.16',10,'REMOOC',5000.00,0.00,NULL,'Dang_Hoat_Dong',0.00,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2026-08-08',NULL,NULL,40,NULL),(50,'70R-02580',14,'REMOOC',5000.00,0.00,NULL,'Dang_Hoat_Dong',0.00,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2026-11-02',NULL,NULL,50,NULL),(51,'70RM-008.15',0,'REMOOC',5000.00,0.00,NULL,'Dang_Hoat_Dong',0.00,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2027-05-17',NULL,NULL,0,NULL),(52,'70RM-008.11T',0,'REMOOC',5000.00,0.00,NULL,'Dang_Hoat_Dong',0.00,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2027-05-19',NULL,NULL,0,NULL),(53,'70RM-006.22T',0,'REMOOC',5000.00,0.00,NULL,'Dang_Hoat_Dong',0.00,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2027-05-25',NULL,NULL,0,NULL),(54,'70R-02576',0,'REMOOC',5000.00,0.00,NULL,'Dang_Hoat_Dong',0.00,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,NULL),(55,'70R-02566',0,'REMOOC',5000.00,0.00,NULL,'Dang_Hoat_Dong',0.00,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,NULL),(56,'70R-02581',0,'REMOOC',5000.00,0.00,NULL,'Dang_Hoat_Dong',0.00,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,NULL),(57,'CIDU6278067',0,'CONT RỖNG',5000.00,0.00,NULL,'Dang_Hoat_Dong',0.00,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,NULL),(58,'UACU5103307',0,'CONT RỖNG',5000.00,0.00,NULL,'Dang_Hoat_Dong',0.00,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,NULL),(59,'MKSKU9252307',0,'CONT RỖNG',5000.00,0.00,NULL,'Dang_Hoat_Dong',0.00,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,NULL);
/*!40000 ALTER TABLE `xe` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Dumping routines for database 'logistics_app'
--

/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-07-06 12:48:04
