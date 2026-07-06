import os
from dotenv import load_dotenv

# Tải biến môi trường
load_dotenv()

print("HOST lấy được là:", os.getenv("DB_HOST"))
print("PORT lấy được là:", os.getenv("DB_PORT"))