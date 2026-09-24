import mysql.connector
from dotenv import load_dotenv
import os

# Nạp biến môi trường
load_dotenv()

print(f"Đang thử kết nối đến Host: {os.getenv('DB_HOST')} ...")

try:
    conn = mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT", 16553)),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASS"),
        database=os.getenv("DB_NAME"),
        ssl_ca="ca.pem",
        ssl_disabled=False
    )
    print("✅ KẾT NỐI THÀNH CÔNG! IP của bạn đã được Aiven chấp nhận và file SSL hợp lệ.")
    conn.close()
    
except Exception as e:
    print(f"❌ KẾT NỐI THẤT BẠI. Nguyên nhân gốc rễ:\n{e}")