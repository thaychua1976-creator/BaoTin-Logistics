import bcrypt

# Tạo mã băm cho mật khẩu "123456"
hashed = bcrypt.hashpw(b"123456", bcrypt.gensalt()).decode('utf-8')
print("Copy chuỗi này:", hashed)