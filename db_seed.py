from pymongo import MongoClient
from werkzeug.security import generate_password_hash
from faker import Faker
import random
from datetime import datetime, timedelta
from bson.objectid import ObjectId
import urllib.parse

# Khởi tạo Faker hỗ trợ tiếng Việt
fake = Faker('vi_VN')

client = MongoClient('mongodb://localhost:27017/')
db = client['LibManagerDB']

print("Đang xóa dữ liệu cũ...")
db.users.delete_many({})
db.books.delete_many({})
db.book_copies.delete_many({})
db.transactions.delete_many({})

print("Đang tạo Admin...")
# 1. TẠO ADMIN
db.users.insert_one({
    "username": "admin",
    "password": generate_password_hash("123"),
    "role": "admin",
    "fullname": "Quản Trị Viên (Thủ thư)",
    "email": "admin@ptit.edu.vn"
})

print("Đang tạo 200 Độc giả (Sinh viên PTIT)...")
# 2. TẠO ĐỘC GIẢ (USERS)
users = []
# Set để đảm bảo MSV không bị trùng
generated_msv = set()

while len(users) < 200:
    khoa = random.choice(['B19', 'B20', 'B21', 'B22', 'B23'])
    nganh = random.choice(['DCCN', 'DCAT', 'DCVT', 'DCKT', 'DCMR', 'DCPT'])
    msv = f"{khoa}{nganh}{str(random.randint(1, 999)).zfill(3)}"

    if msv not in generated_msv:
        generated_msv.add(msv)
        users.append({
            "username": msv,
            "msv": msv,
            "password": generate_password_hash("123"),
            "role": "user",
            "fullname": fake.name(),
            "email": f"{msv.lower()}@stu.ptit.edu.vn",
            "phone": fake.phone_number(),
            "created_at": fake.date_time_between(start_date='-13m', end_date='now')
        })
db.users.insert_many(users)
user_ids = [str(u['_id']) for u in db.users.find({'role': 'user'})]

print("Đang tạo 300 Đầu sách ngẫu nhiên và Bản sao...")
# 3. TẠO SÁCH (BOOKS) DYNAMIC GENERATOR
categories = ['CNTT', 'Kinh tế', 'Kỹ năng', 'Văn học', 'Ngoại ngữ', 'Chính trị', 'Thể dục']
bg_colors = ['4f46e5', '059669', 'ea580c', 'e11d48', '0891b2', '4c1d95', 'b45309']  # Màu nền ảnh bìa

generated_titles = set()
books_collection = []
copies_collection = []


def generate_book_info():
    """Hàm tự động trộn từ khóa tạo ra tên sách không trùng lặp"""
    cat = random.choices(categories, weights=[40, 20, 15, 10, 5, 5, 5])[0]
    if cat == 'CNTT':
        title = f"{random.choice(['Lập trình', 'Giáo trình', 'Cơ sở', 'Hệ thống', 'Làm chủ'])} {random.choice(['Python', 'Java', 'C++', 'AI', 'Mạng máy tính', 'Web', 'Mobile', 'Bảo mật', 'Cấu trúc dữ liệu', 'Hệ điều hành'])} {random.choice(['Cơ bản', 'Nâng cao', 'Toàn tập', 'Ứng dụng', 'Thực hành'])}"
    elif cat == 'Kinh tế':
        title = f"{random.choice(['Nguyên lý', 'Quản trị', 'Giáo trình', 'Phân tích', 'Cơ sở'])} {random.choice(['Kinh tế Vĩ mô', 'Marketing', 'Tài chính', 'Nhân sự', 'Kế toán', 'Chuỗi cung ứng', 'Logistics'])} {random.choice(['Hiện đại', 'Căn bản', 'Nâng cao', 'Ứng dụng', 'Toàn tập'])}"
    elif cat == 'Kỹ năng':
        title = f"{random.choice(['Kỹ năng', 'Nghệ thuật', 'Bí quyết', 'Tư duy', 'Sức mạnh'])} {random.choice(['Giao tiếp', 'Lãnh đạo', 'Quản lý thời gian', 'Thuyết trình', 'Đàm phán', 'Làm việc nhóm', 'Tập trung'])} {random.choice(['Hiệu quả', 'Đỉnh cao', 'Thành công', 'Cho Sinh Viên'])}"
    elif cat == 'Văn học':
        title = f"{random.choice(['Tiểu thuyết', 'Tuyển tập', 'Truyện ngắn', 'Ký sự'])} {fake.word().capitalize()} {fake.word().lower()}"
    else:
        title = f"{random.choice(['Giáo trình', 'Sổ tay', 'Tài liệu'])} {cat} {fake.year()}"

    # Đảm bảo không trùng tên sách
    while title in generated_titles:
        title += f" (Phần {random.randint(2, 5)})"
    generated_titles.add(title)
    return title, fake.name(), cat


for i in range(300):
    title, author, category = generate_book_info()
    isbn = f"978-84-{str(i + 1).zfill(4)}"
    qty = random.randint(3, 12)  # Mỗi sách có từ 3 đến 12 quyển

    # Tạo URL ảnh bìa từ placehold.co (Cần encode URL để hỗ trợ tiếng Việt có dấu)
    safe_title = urllib.parse.quote_plus(title)
    bg_color = random.choice(bg_colors)
    cover_url = f"https://placehold.co/400x600/{bg_color}/white?font=montserrat&text={safe_title}"

    books_collection.append({
        "isbn": isbn, "title": title, "author": author, "category": category,
        "image_url": cover_url,
        "qty_total": qty, "qty_avail": qty, "created_at": fake.date_time_between(start_date='-2y', end_date='-13m')
    })

    for j in range(qty):
        copies_collection.append({
            "isbn_ref": isbn, "barcode": f"{isbn}-{j + 1}", "status": "available",
            "location": f"Kệ {category}-{random.randint(1, 5)}"
        })

db.books.insert_many(books_collection)
db.book_copies.insert_many(copies_collection)
all_copies = list(db.book_copies.find())

print("Đang tạo 2000 Lịch sử Mượn/Trả sách trong 13 tháng qua...")
# 4. TẠO 2000 GIAO DỊCH MƯỢN TRẢ (TRANSACTIONS)
transactions = []
for _ in range(2000):
    user_id = random.choice(user_ids)
    copy = random.choice(all_copies)
    book_info = next((b for b in books_collection if b['isbn'] == copy['isbn_ref']), None)

    if not book_info: continue

    # Giả lập logic 1 số sách ít bị mượn để test Báo cáo thanh lý DSS
    if book_info['category'] in ['Chính trị', 'Thể dục'] and random.random() > 0.05:
        continue

        # Ngày mượn trong 13 tháng qua
    borrow_date = fake.date_time_between(start_date='-13m', end_date='now')
    due_date = borrow_date + timedelta(days=14)

    # Phân bổ trạng thái: 85% Đã trả, 10% Đang mượn, 5% Quá hạn
    status_roll = random.random()
    if status_roll < 0.85:
        # ĐÃ TRẢ SÁCH
        status = 'returned'
        # Trả đúng hạn (80%) hay trễ hạn (20%)
        if random.random() < 0.8:
            return_date = borrow_date + timedelta(days=random.randint(1, 14))
            fine, overdue_days = 0, 0
            fine_paid = True
        else:
            return_date = due_date + timedelta(days=random.randint(1, 30))
            overdue_days = (return_date - due_date).days
            fine = overdue_days * 1000
            # 90% đã đóng phạt, 10% chây ì nợ phạt
            fine_paid = True if random.random() < 0.9 else False

        transactions.append({
            'user_id': user_id, 'book_title': book_info['title'], 'barcode': copy['barcode'],
            'borrow_date': borrow_date, 'due_date': due_date, 'return_date': return_date,
            'status': status, 'fine': fine, 'overdue_days': overdue_days,
            'fine_paid': fine_paid, 'renew_count': random.randint(0, 1)
        })
    else:
        # ĐANG MƯỢN / QUÁ HẠN CHƯA TRẢ
        status = 'borrowing'
        db.book_copies.update_one({'_id': copy['_id']}, {'$set': {'status': 'borrowed'}})
        db.books.update_one({'isbn': copy['isbn_ref']}, {'$inc': {'qty_avail': -1}})

        if due_date < datetime.now():
            # Quá hạn chưa trả
            fine = (datetime.now() - due_date).days * 1000
            fine_paid = False
        else:
            # Vẫn trong hạn
            fine = 0
            fine_paid = True

        transactions.append({
            'user_id': user_id, 'book_title': book_info['title'], 'barcode': copy['barcode'],
            'borrow_date': borrow_date, 'due_date': due_date,
            'status': status, 'fine': fine, 'fine_paid': fine_paid, 'renew_count': 0
        })

db.transactions.insert_many(transactions)

print("=" * 50)
print("TẠO DỮ LIỆU THÀNH CÔNG!")
print(f"Đã tạo: 200 Độc giả, 300 Đầu sách, {len(all_copies)} Bản sao, {len(transactions)} Giao dịch")
print("Tài khoản Admin: admin / 123")
print("Tài khoản User: [Dùng bất kỳ MSV nào trong DB] / 123")
print("=" * 50)