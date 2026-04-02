import csv
import copy
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from io import StringIO
from flask import Response
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from bson.objectid import ObjectId
from flask_cors import CORS

app = Flask(__name__)
app.secret_key = 'PTIT_LIB_SECURE_KEY_2025'  # Key bảo mật session
CORS(app)

# KẾT NỐI MONGODB
client = MongoClient('mongodb://localhost:27017/')
db = client['LibManagerDB']

# --- ROUTING (ĐIỀU HƯỚNG HTML) ---
@app.route('/')
def home():
    # Nếu chưa đăng nhập
    if 'user_id' not in session:
        # SỬA Ở ĐÂY: Thay 'login.html' bằng tên file HTML thực tế chứa giao diện đăng nhập của bạn.
        # (Thường sẽ là 'index.html' hoặc 'user_home.html')
        return render_template('user_home.html')

        # Nếu đã đăng nhập và là Admin hoặc Nhân viên
    if session.get('role') in ['admin', 'employee']:
        return redirect('/admin')

    # Nếu đã đăng nhập và là Sinh viên
    return render_template('user_home.html')


@app.route('/book/<isbn>')
def user_book_detail(isbn):
    return render_template('user_book_detail.html', isbn=isbn)


@app.route('/admin')
def admin_dashboard():
    if session.get('role') not in ['admin', 'employee']:
        return redirect('/')
    return render_template('admin_dashboard.html')


@app.route('/admin/book/<isbn>')
def admin_book_detail(isbn):
    if session.get('role') not in ['admin', 'employee']:
        return redirect('/')
    return render_template('admin_book_detail.html', isbn=isbn)

@app.route('/admin/books')
def admin_books():
    if session.get('role') not in ['admin', 'employee']:
        return redirect('/')
    return render_template('admin_books.html')
@app.route('/admin/finance')
def admin_finance():
    if session.get('role') not in ['admin', 'employee']:
        return redirect('/')
    return render_template('admin_finance.html')

@app.route('/admin/hr')
def admin_hr():
    if session.get('role') not in ['admin', 'employee']:
        return redirect('/')
    return render_template('admin_hr.html')
# --- API OAS: GỬI EMAIL TỰ ĐỘNG (OFFICE AUTOMATION SYSTEM) ---

# TODO: ĐIỀN EMAIL VÀ MẬT KHẨU ỨNG DỤNG CỦA BẠN VÀO ĐÂY
SENDER_EMAIL = "dangconghau13032004@gmail.com"
SENDER_PASSWORD = "zfgd zfhf ebqw idub"


@app.route('/api/admin/oas/send-warning-email', methods=['POST'])
def oas_send_warning_email():
    if session.get('role') not in ['admin', 'employee']:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403

    data = request.json
    msv = data.get('msv')
    total_fine = data.get('total_fine', 0)
    overdue_books = data.get('overdue_books', 0)

    # 1. Lấy thông tin sinh viên từ DB
    user = db.users.find_one({'msv': msv})
    if not user or not user.get('email'):
        return jsonify({'status': 'error', 'message': 'Không tìm thấy thông tin email sinh viên!'}), 404

    receiver_email = user['email']
    fine_fmt = "{:,}".format(int(total_fine))

    # 2. Xây dựng nội dung GỐC của bạn đưa vào Template
    # Giữ nguyên các câu chữ: "Hệ thống tự động...", "Yêu cầu bạn mang sách...", "Việc chậm trễ..."
    body_content = f"""
        <p>Chào bạn <b>{user['fullname']}</b> (MSV: {user['msv']}),</p>
        <p>Hệ thống tự động của Thư viện ghi nhận bạn hiện đang có:</p>
        <ul style="color: #6366f1; font-weight: bold; list-style-type: none; padding-left: 0;">
            <li style="margin-bottom: 8px;">• {overdue_books} cuốn sách đang quá hạn trả.</li>
            <li>• Tổng số tiền phạt trễ hạn: {fine_fmt} VNĐ.</li>
        </ul>
        <p>Yêu cầu bạn mang sách đến thư viện để hoàn tất thủ tục trả sách và đóng phạt trong thời gian sớm nhất.</p>
        <p style="background: #fff1f2; padding: 12px; border-radius: 8px; color: #e11d48; font-size: 14px; border: 1px solid #fecdd3;">
            <b>CẢNH BÁO:</b> Việc chậm trễ có thể dẫn đến việc tài khoản mượn sách của bạn bị khóa vĩnh viễn.
        </p>
    """

    # Render vào template Indigo
    try:
        html_content = render_template(
            'email_template.html',
            fullname=user['fullname'],
            body_content=body_content,
            button_text="Xem chi tiết tài khoản",
            button_url="http://localhost:5000/login"
        )
    except Exception as e:
        return jsonify({'status': 'error', 'message': 'Lỗi hệ thống template!'}), 500

    # 3. Gửi Email và Ghi Log
    status_log = "Thành công"
    error_log = ""

    try:
        msg = MIMEMultipart()
        msg['From'] = f"Thư Viện PTIT <{SENDER_EMAIL}>"
        msg['To'] = receiver_email
        msg['Subject'] = "[QUAN TRỌNG] Thông báo trả sách và thanh toán nợ phạt Thư viện"
        msg.attach(MIMEText(html_content, 'html'))

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.send_message(msg)
        server.quit()

        # Cập nhật số lần nhắc nhở
        db.users.update_one({'msv': msv}, {'$inc': {'warning_count': 1}})

    except Exception as e:
        status_log = "Thất bại"
        error_log = str(e)

    # 4. Lưu Log hệ thống (Chuẩn OAS)
    db.email_logs.insert_one({
        'msv': msv,
        'recipient': receiver_email,
        'type': 'Nhắc nợ (Template)',
        'sent_at': datetime.now(),
        'status': status_log,
        'error_detail': error_log
    })

    if status_log == "Thành công":
        return jsonify({'status': 'success', 'message': f'Đã gửi email thành công tới {receiver_email}'})
    else:
        return jsonify({'status': 'error', 'message': 'Gửi mail thất bại.'}), 500

# --- API OAS: GỬI THÔNG BÁO HÀNG LOẠT TỚI TOÀN BỘ ĐỘC GIẢ ---

@app.route('/api/admin/oas/send-mass-email', methods=['POST'])
def oas_send_mass_email():
    """
    Hệ thống OAS: Gửi thông báo hàng loạt tới toàn bộ độc giả.
    Sử dụng Template chuyên nghiệp và ghi lại nhật ký chiến dịch (Logging).
    """
    if session.get('role') not in ['admin', 'employee']:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403

    data = request.json
    subject = data.get('subject', 'Thông báo từ Thư viện PTIT')
    content = data.get('content', '')

    # 1. Lấy danh sách email của tất cả độc giả (role='user')
    users = list(db.users.find({'role': 'user', 'email': {'$exists': True, '$ne': ''}}))
    if not users:
        return jsonify({'status': 'error', 'message': 'Không có độc giả nào có email hợp lệ.'}), 400

    recipient_emails = [u['email'] for u in users]

    # 2. Xây dựng nội dung Email bằng Template Indigo
    # Chuyển đổi ký tự xuống dòng (\n) thành thẻ <br> để hiển thị đúng trong HTML
    html_formatted_content = content.replace('\n', '<br>')

    # Nội dung gửi đi (có thể tùy biến thêm lời chào chung)
    body_content = f"""
        <p>Chào các bạn sinh viên và độc giả của Thư viện PTIT,</p>
        <p>{html_formatted_content}</p>
        <p style="margin-top: 20px;">Trân trọng,<br><b>Ban quản lý Thư viện</b></p>
    """

    try:
        # Sử dụng render_template để tạo email chuyên nghiệp
        html_email = render_template(
            'email_template.html',
            fullname="Các bạn Độc giả",
            body_content=body_content,
            button_text="Truy cập Website Thư viện",
            button_url="http://localhost:5000"  # Thay đổi link khi chạy thực tế
        )
    except Exception as e:
        print(f"Lỗi render template: {e}")
        return jsonify({'status': 'error', 'message': 'Lỗi hệ thống template!'}), 500

    # 3. Gửi Email đồng loạt và Ghi nhật ký
    status_log = "Thành công"
    error_log = ""

    try:
        msg = MIMEMultipart()
        msg['From'] = f"Thư Viện PTIT <{SENDER_EMAIL}>"
        msg['Subject'] = subject
        msg.attach(MIMEText(html_email, 'html'))

        # Kết nối và gửi qua SMTP Gmail
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)

        # Gửi theo phương thức BCC (giấu danh sách người nhận lẫn nhau)
        server.sendmail(SENDER_EMAIL, recipient_emails, msg.as_string())
        server.quit()

    except Exception as e:
        print("Lỗi gửi mail hàng loạt:", e)
        status_log = "Thất bại"
        error_log = str(e)

    # 4. LƯU NHẬT KÝ CHIẾN DỊCH (OAS Logging)
    db.email_logs.insert_one({
        'type': 'Thông báo hàng loạt',
        'subject': subject,
        'recipients_count': len(recipient_emails),
        'sent_at': datetime.now(),
        'status': status_log,
        'error_detail': error_log
    })

    if status_log == "Thành công":
        return jsonify({
            'status': 'success',
            'message': f'Hệ thống OAS đã gửi thông báo thành công tới {len(recipient_emails)} độc giả!'
        })
    else:
        return jsonify({
            'status': 'error',
            'message': 'Gửi thông báo thất bại. Vui lòng kiểm tra Log hệ thống.'
        }), 500


# --- ROUTE & API XEM NHẬT KÝ GỬI THƯ (OAS LOGS) ---

@app.route('/admin/oas/logs')
def admin_email_logs_page():
    """Mở trang giao diện Nhật ký gửi thư"""
    if session.get('role') not in ['admin', 'employee']: return redirect('/')
    return render_template('admin_email_logs.html')


@app.route('/api/admin/oas/logs-data')
def get_email_logs_api():
    """API lấy danh sách log từ MongoDB trả về cho giao diện"""
    if session.get('role') not in ['admin', 'employee']: return jsonify([]), 403

    # Lấy toàn bộ log, sắp xếp cái mới nhất hiện lên đầu
    logs = list(db.email_logs.find().sort('sent_at', -1))

    for log in logs:
        log['_id'] = str(log['_id'])
        # Định dạng lại ngày giờ cho đẹp: HH:mm - DD/MM/YYYY
        if 'sent_at' in log:
            log['sent_at_fmt'] = log['sent_at'].strftime("%H:%M - %d/%m/%Y")

    return jsonify(logs)
# --- API DSS: EXPORT BÁO CÁO NGOẠI LỆ RA FILE EXCEL/CSV ---

@app.route('/api/admin/dss/export/high-risk', methods=['GET'])
def dss_export_high_risk():
    """Xuất danh sách Độc giả rủi ro cao ra file CSV"""
    if session.get('role') not in ['admin', 'employee']: return redirect('/')

    # Tái sử dụng logic Aggregation của High-Risk Users
    pipeline = [
        {'$match': {
            '$or': [
                {'fine_paid': False, 'fine': {'$gt': 0}},
                {'status': 'borrowing', 'due_date': {'$lt': datetime.now()}}
            ]
        }},
        {'$group': {
            '_id': '$user_id',
            'total_unpaid_fine': {'$sum': {'$cond': [{'$eq': ['$fine_paid', False]}, '$fine', 0]}},
            'overdue_books_count': {'$sum': {'$cond': [{'$eq': ['$status', 'borrowing']}, 1, 0]}}
        }},
        {'$match': {
            '$or': [
                {'total_unpaid_fine': {'$gte': 20000}},
                {'overdue_books_count': {'$gte': 2}}
            ]
        }},
        {'$sort': {'total_unpaid_fine': -1}}
    ]
    risky_users_data = list(db.transactions.aggregate(pipeline))

    # Hàm tạo dữ liệu CSV
    def generate():
        data = StringIO()
        data.write('\ufeff')  # Thêm BOM để Excel hiển thị đúng font Tiếng Việt
        writer = csv.writer(data)

        # Viết Header
        writer.writerow(['Mã sinh viên', 'Họ và tên', 'Tổng nợ phạt (VNĐ)', 'Số sách đang quá hạn'])

        # Viết Data
        for u in risky_users_data:
            user_info = db.users.find_one({'_id': ObjectId(u['_id'])})
            if user_info:
                writer.writerow([
                    user_info.get('msv', 'N/A'),
                    user_info.get('fullname', 'N/A'),
                    u['total_unpaid_fine'],
                    u['overdue_books_count']
                ])
        yield data.getvalue()
        data.seek(0)
        data.truncate(0)

    # Trả về file cho trình duyệt tải xuống
    response = Response(generate(), mimetype='text/csv')
    response.headers.set("Content-Disposition", "attachment", filename="Bao_Cao_Doc_Gia_Rui_Ro.csv")
    return response


@app.route('/api/admin/dss/export/unused-books', methods=['GET'])
def dss_export_unused_books():
    """Xuất danh sách Sách cần thanh lý ra file CSV"""
    if session.get('role') not in ['admin', 'employee']: return redirect('/')

    borrowed_titles = db.transactions.distinct('book_title')
    unused_books = list(db.books.find({
        'title': {'$nin': borrowed_titles}
    }).sort('created_at', 1))

    def generate():
        data = StringIO()
        data.write('\ufeff')
        writer = csv.writer(data)

        writer.writerow(['Mã ISBN', 'Tên cuốn sách', 'Tác giả', 'Thể loại', 'Số lượng tồn kho'])

        for b in unused_books:
            writer.writerow([
                b.get('isbn', ''),
                b.get('title', ''),
                b.get('author', ''),
                b.get('category', ''),
                b.get('qty_total', 0)
            ])
        yield data.getvalue()
        data.seek(0)
        data.truncate(0)

    response = Response(generate(), mimetype='text/csv')
    response.headers.set("Content-Disposition", "attachment", filename="Bao_Cao_Sach_Ton_Kho.csv")
    return response


@app.route('/api/admin/eis/kpis', methods=['GET'])
def get_eis_kpis():
    if session.get('role') not in ['admin', 'employee']:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403

    # 1. Tỷ lệ khai thác tài nguyên (Resource Utilization)
    total_copies = db.book_copies.count_documents({})
    borrowed_copies = db.book_copies.count_documents({'status': {'$in': ['borrowed', 'pending']}})
    utilization_rate = round((borrowed_copies / total_copies) * 100, 1) if total_copies > 0 else 0

    # 2. Tỷ lệ Độc giả tích cực (Active Users trong 30 ngày qua)
    thirty_days_ago = datetime.now() - timedelta(days=30)
    active_users = len(db.transactions.distinct('user_id', {'borrow_date': {'$gte': thirty_days_ago}}))
    total_users = db.users.count_documents({'role': 'user'})
    active_user_rate = round((active_users / total_users) * 100, 1) if total_users > 0 else 0

    # 3. Tỷ lệ rủi ro quá hạn (Overdue Risk Rate)
    active_loans = db.transactions.count_documents({'status': 'borrowing'})
    overdue_loans = db.transactions.count_documents({
        'status': 'borrowing',
        'due_date': {'$lt': datetime.now()}
    })
    overdue_rate = round((overdue_loans / active_loans) * 100, 1) if active_loans > 0 else 0

    # 4. Phân tích Tài chính (SỬA LẠI ĐỂ ĐỒNG BỘ VỚI DB_SEED)

    # Tính tiền đã thu và nợ đọng từ bảng 'transactions' (Dữ liệu của db_seed)
    trans_paid = list(db.transactions.aggregate([
        {'$match': {'fine_paid': True, 'fine': {'$gt': 0}}},
        {'$group': {'_id': None, 'total': {'$sum': '$fine'}}}
    ]))
    trans_unpaid = list(db.transactions.aggregate([
        {'$match': {'fine_paid': False, 'fine': {'$gt': 0}}},
        {'$group': {'_id': None, 'total': {'$sum': '$fine'}}}
    ]))

    # Tính tiền đã thu và nợ đọng từ bảng 'fines' (Phiếu phạt thủ công mới)
    manual_paid = list(db.fines.aggregate([
        {'$match': {'status': 'paid'}},
        {'$group': {'_id': None, 'total': {'$sum': '$amount'}}}
    ]))
    manual_unpaid = list(db.fines.aggregate([
        {'$match': {'status': 'unpaid'}},
        {'$group': {'_id': None, 'total': {'$sum': '$amount'}}}
    ]))

    # Cộng gộp 2 nguồn lại với nhau
    total_paid = (trans_paid[0]['total'] if trans_paid else 0) + (manual_paid[0]['total'] if manual_paid else 0)
    total_unpaid = (trans_unpaid[0]['total'] if trans_unpaid else 0) + (
        manual_unpaid[0]['total'] if manual_unpaid else 0)

    return jsonify({
        'utilization_rate': utilization_rate,
        'active_user_rate': active_user_rate,
        'overdue_rate': overdue_rate,
        'financial': {
            'collected': total_paid,
            'outstanding': total_unpaid
        }
    })
# --- API DSS: PHÂN TÍCH XU HƯỚNG (TREND ANALYSIS) ---
@app.route('/api/admin/dss/category-trends', methods=['GET'])
def dss_category_trends():
    if session.get('role') not in ['admin', 'employee']: return jsonify({}), 403

    # Lấy tham số thời gian từ URL (Mặc định là 'all' - Tất cả)
    period = request.args.get('period', 'all')

    # 1. Khởi tạo bộ lọc cơ bản (Chỉ tính sách đang mượn hoặc đã trả)
    match_stage = {'status': {'$in': ['borrowing', 'returned']}}

    # 2. Xử lý logic thời gian
    if period != 'all':
        now = datetime.now()
        if period == 'month':
            start_date = now - timedelta(days=30)
        elif period == 'quarter':
            start_date = now - timedelta(days=90)
        elif period == 'year':
            start_date = now - timedelta(days=365)
        else:
            start_date = None

        if start_date:
            match_stage['borrow_date'] = {'$gte': start_date}

    # 3. Aggregation Pipeline
    pipeline = [
        {'$match': match_stage},
        {'$lookup': {
            'from': 'books',
            'localField': 'book_title',
            'foreignField': 'title',
            'as': 'book_info'
        }},
        {'$unwind': '$book_info'},
        {'$group': {
            '_id': '$book_info.category',
            'borrow_count': {'$sum': 1}
        }},
        {'$sort': {'borrow_count': -1}}
    ]

    trends = list(db.transactions.aggregate(pipeline))

    labels = [t['_id'] for t in trends]
    data = [t['borrow_count'] for t in trends]

    return jsonify({
        'labels': labels,
        'data': data
    })
# --- API DSS: BÁO CÁO NGOẠI LỆ (EXCEPTION REPORTS) ---

@app.route('/api/admin/dss/unused-books', methods=['GET'])
def dss_unused_books():
    """
    Báo cáo ngoại lệ 1: Các đầu sách chưa từng được mượn lần nào.
    Mục đích (DSS): Hỗ trợ ra quyết định thanh lý hoặc chuyển kho, dừng nhập thêm sách này.
    """
    if session.get('role') not in ['admin', 'employee']: return jsonify([]), 403

    # Lấy danh sách tên sách đã từng được mượn ít nhất 1 lần
    borrowed_titles = db.transactions.distinct('book_title')

    # Tìm các đầu sách KHÔNG nằm trong danh sách đã mượn
    unused_books = list(db.books.find({
        'title': {'$nin': borrowed_titles}
    }, {'_id': 0, 'isbn': 1, 'title': 1, 'category': 1, 'qty_total': 1, 'created_at': 1}))

    # Format lại ngày tháng cho dễ đọc
    for b in unused_books:
        b['created_at_fmt'] = b.get('created_at', datetime.now()).strftime('%d/%m/%Y')

    return jsonify(unused_books)


@app.route('/api/admin/dss/high-risk-users', methods=['GET'])
def dss_high_risk_users():
    """
    Báo cáo ngoại lệ 2: Độc giả rủi ro cao (Nợ tiền phạt lớn hoặc quá hạn nhiều sách).
    Mục đích (DSS): Ra quyết định khóa tài khoản hoặc gửi email cảnh báo đặc biệt.
    """
    if session.get('role') not in ['admin', 'employee']: return jsonify([]), 403

    # Sử dụng MongoDB Aggregation để gom nhóm và tính tổng nợ theo user
    pipeline = [
        # Lọc các giao dịch chưa trả tiền phạt hoặc đang quá hạn
        {'$match': {
            '$or': [
                {'fine_paid': False, 'fine': {'$gt': 0}},
                {'status': 'borrowing', 'due_date': {'$lt': datetime.now()}}
            ]
        }},
        # Gom nhóm theo user_id
        {'$group': {
            '_id': '$user_id',
            'total_unpaid_fine': {'$sum': {'$cond': [{'$eq': ['$fine_paid', False]}, '$fine', 0]}},
            'overdue_books_count': {'$sum': {'$cond': [{'$eq': ['$status', 'borrowing']}, 1, 0]}}
        }},
        # Lọc ra những người nợ trên 20.000đ hoặc đang quá hạn từ 2 cuốn trở lên
        {'$match': {
            '$or': [
                {'total_unpaid_fine': {'$gte': 20000}},
                {'overdue_books_count': {'$gte': 2}}
            ]
        }},
        {'$sort': {'total_unpaid_fine': -1}}
    ]

    risky_users_data = list(db.transactions.aggregate(pipeline))

    # Kết hợp thông tin từ bảng users
    result = []
    for u in risky_users_data:
        user_info = db.users.find_one({'_id': ObjectId(u['_id'])})
        if user_info:
            result.append({
                'msv': user_info.get('msv', 'N/A'),
                'fullname': user_info.get('fullname', 'N/A'),
                'total_fine': u['total_unpaid_fine'],
                'overdue_books': u['overdue_books_count'],
                'warning_count': user_info.get('warning_count', 0)
            })

    return jsonify(result)
# --- API AUTHENTICATION ---
@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'status': 'error', 'message': 'Vui lòng nhập đầy đủ thông tin!'}), 400

    # Tìm user trong database
    user = db.users.find_one({'username': username})
    if not user:
        return jsonify({'status': 'error', 'message': 'Tài khoản không tồn tại!'}), 404

    # Kiểm tra tài khoản có bị khóa do nhập sai nhiều lần không
    if user.get('locked_until') and user['locked_until'] > datetime.now():
        return jsonify({'status': 'error', 'message': 'Tài khoản đang bị khóa tạm thời. Vui lòng thử lại sau!'}), 403

    # Kiểm tra mật khẩu
    if check_password_hash(user['password'], password):
        # Đăng nhập thành công -> Reset số lần đăng nhập sai
        db.users.update_one({'_id': user['_id']}, {'$set': {'failed_attempts': 0, 'locked_until': None}})

        # Lưu thông tin vào phiên làm việc (Session)
        session['user_id'] = str(user['_id'])
        session['fullname'] = user.get('fullname', username)
        session['role'] = user.get('role', 'user')

        # CHỐT CHẶN QUAN TRỌNG: Xác định trang đích để Frontend chuyển hướng
        target_url = '/'
        if user['role'] in ['admin', 'employee']:
            target_url = '/admin'

        return jsonify({
            'status': 'success',
            'message': 'Đăng nhập thành công!',
            'role': user['role'],
            'redirect': target_url  # Trả về link để Javascript tự động chuyển trang
        })
    else:
        # Đăng nhập thất bại -> Tăng số lần sai
        failed_attempts = user.get('failed_attempts', 0) + 1
        update_data = {'failed_attempts': failed_attempts}

        # Nếu sai 5 lần thì khóa 15 phút
        if failed_attempts >= 5:
            update_data['locked_until'] = datetime.now() + timedelta(minutes=15)

        db.users.update_one({'_id': user['_id']}, {'$set': update_data})

        return jsonify({'status': 'error', 'message': 'Sai mật khẩu!'}), 401

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'status': 'success'})

@app.route('/admin/circulation')
def admin_circulation():
    if session.get('role') not in ['admin', 'employee']: return redirect('/')
    return render_template('admin_circulation.html')
# --- ROUTING MỚI CHO PHẦN 2 ---
@app.route('/admin/users')
def admin_users():
    if session.get('role') not in ['admin', 'employee']: return redirect('/')
    return render_template('admin_users.html')


@app.route('/profile')
def user_profile():
    if 'user_id' not in session: return redirect('/')
    return render_template('user_profile.html')


# --- API QUẢN LÝ ĐỘC GIẢ (ADMIN) ---
@app.route('/api/admin/users', methods=['GET'])
def get_users():
    if session.get('role') not in ['admin', 'employee']: return jsonify([]), 403

    q = request.args.get('q', '')
    page = int(request.args.get('page', 1))
    limit = 12
    skip = (page - 1) * limit

    query = {'role': 'user'}
    if q:
        query['$or'] = [
            {'fullname': {'$regex': q, '$options': 'i'}},
            {'msv': {'$regex': q, '$options': 'i'}},
            {'email': {'$regex': q, '$options': 'i'}}
        ]

    total_items = db.users.count_documents(query)
    users = list(db.users.find(query, {'password': 0}).skip(skip).limit(limit))

    for u in users:
        u['_id'] = str(u['_id'])
        u['borrow_count'] = db.transactions.count_documents({'user_id': str(u['_id']), 'status': 'borrowing'})
        u['total_fine'] = 0  # Có thể bổ sung logic tính tổng nợ nếu cần

    return jsonify({
        'data': users,
        'total_pages': (total_items + limit - 1) // limit,
        'current_page': page
    })


@app.route('/api/admin/user', methods=['POST'])
def create_user():
    if session.get('role') not in ['admin', 'employee']: return jsonify({'status': 'error'}), 403
    data = request.json

    # Kiểm tra trùng MSV hoặc Username
    if db.users.find_one({'$or': [{'username': data['msv']}, {'email': data['email']}]}):
        return jsonify({'status': 'error', 'message': 'MSV hoặc Email đã tồn tại!'}), 400

    new_user = {
        "username": data['msv'],  # Username mặc định là MSV
        "msv": data['msv'],
        "password": generate_password_hash("123456"),  # Mặc định 123456
        "role": "user",
        "fullname": data['fullname'],
        "email": data['email'],
        "phone": data.get('phone', ''),
        "created_at": datetime.now()
    }
    db.users.insert_one(new_user)
    return jsonify({'status': 'success', 'message': 'Thêm độc giả thành công!'})


@app.route('/api/admin/user/<uid>/reset-pass', methods=['POST'])
def reset_pass(uid):
    if session.get('role') not in ['admin', 'employee']: return jsonify({'status': 'error'}), 403

    # Reset mật khẩu về 123456
    db.users.update_one({'_id': ObjectId(uid)}, {'$set': {'password': generate_password_hash('123456')}})
    return jsonify({'status': 'success', 'message': 'Đã reset mật khẩu về 123456'})


# --- API HỒ SƠ CÁ NHÂN (USER) ---
@app.route('/api/user/profile', methods=['GET'])
def get_my_profile():
    if 'user_id' not in session: return jsonify({'status': 'error'}), 401

    u = db.users.find_one({'_id': ObjectId(session['user_id'])}, {'password': 0})
    u['_id'] = str(u['_id'])

    # Lấy lịch sử mượn
    history = list(db.transactions.find({'user_id': session['user_id']}).sort('borrow_date', -1).limit(10))
    for h in history:
        h['_id'] = str(h['_id'])

    return jsonify({'user': u, 'history': history})


@app.route('/api/user/change-password', methods=['POST'])
def change_pass():
    if 'user_id' not in session: return jsonify({'status': 'error'}), 401
    data = request.json

    user = db.users.find_one({'_id': ObjectId(session['user_id'])})
    if not check_password_hash(user['password'], data['old_pass']):
        return jsonify({'status': 'error', 'message': 'Mật khẩu cũ không đúng!'}), 400

    # Kiểm tra độ mạnh mật khẩu (Tối thiểu 8 ký tự) - có thể thêm regex
    if len(data['new_pass']) < 8:
        return jsonify({'status': 'error', 'message': 'Mật khẩu mới phải trên 8 ký tự!'}), 400

    db.users.update_one({'_id': ObjectId(session['user_id'])}, {
        '$set': {'password': generate_password_hash(data['new_pass'])}
    })
    return jsonify({'status': 'success', 'message': 'Đổi mật khẩu thành công!'})
# --- API SÁCH ---
@app.route('/api/books', methods=['GET'])
def get_books():
    q = request.args.get('q', '')
    page = int(request.args.get('page', 1))
    limit = 12
    skip = (page - 1) * limit

    query = {}
    if q:
        query = {
            '$or': [
                {'title': {'$regex': q, '$options': 'i'}},
                {'author': {'$regex': q, '$options': 'i'}},
                {'isbn': {'$regex': q, '$options': 'i'}}
            ]
        }

    total_items = db.books.count_documents(query)
    books = list(db.books.find(query, {'_id': 0}).skip(skip).limit(limit))

    return jsonify({
        'data': books,
        'total_pages': (total_items + limit - 1) // limit,
        'current_page': page
    })

@app.route('/api/book/<isbn>', methods=['GET'])
def get_book_detail(isbn):
    book = db.books.find_one({'isbn': isbn}, {'_id': 0})
    if not book: return jsonify({'status': 'error'}), 404

    copies = list(db.book_copies.find({'isbn_ref': isbn}, {'_id': 0}))
    return jsonify({'book': book, 'copies': copies})


# --- API ADMIN QUẢN LÝ SÁCH ---

@app.route('/api/admin/book', methods=['POST'])
def add_book():
    if session.get('role') not in ['admin', 'employee']:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403

    data = request.json
    isbn = data.get('isbn')
    qty = int(data.get('qty', 1))

    if db.books.find_one({'isbn': isbn}):
        return jsonify({'status': 'error', 'message': 'Mã ISBN này đã tồn tại!'}), 400

    new_book = {
        'isbn': isbn,
        'title': data.get('title'),
        'author': data.get('author'),
        'category': data.get('category'),
        'publisher': data.get('publisher'),
        'year': data.get('year'),
        'price': int(data.get('price', 0) or 0),
        'language': data.get('language'),
        'location': data.get('location'),
        'image_url': data.get('image_url'),
        'qty_total': qty,
        'qty_avail': qty,
        'created_at': datetime.now()
    }
    db.books.insert_one(new_book)

    copies = []
    for i in range(qty):
        copies.append({
            'isbn_ref': isbn,
            'barcode': f"{isbn}-{i + 1}",
            'status': 'available',
            'location': data.get('location')
        })
    if copies:
        db.book_copies.insert_many(copies)

    # ---> LOGIC MIS: Ghi Log Nhân sự
    log_admin_action('THÊM_SÁCH', f"Thêm {qty} cuốn '{data.get('title')}' (ISBN: {isbn})")

    # ---> LOGIC MIS: Ghi nhận Chi phí Tài chính (Nếu sách có nhập giá tiền)
    total_cost = int(data.get('price', 0)) * qty
    if total_cost > 0:
        db.expenses.insert_one({
            'amount': total_cost,
            'category': 'book_purchase',
            'description': f"Nhập {qty} cuốn '{data.get('title')}'",
            'recorded_by': session.get('fullname'),
            'date': datetime.now()
        })

    return jsonify({'status': 'success', 'message': 'Thêm sách thành công'})
@app.route('/api/admin/book/<isbn>', methods=['DELETE'])
def delete_book(isbn):
    if session.get('role') not in ['admin', 'employee']:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403

    if db.book_copies.find_one({'isbn_ref': isbn, 'status': 'borrowed'}):
        return jsonify({'status': 'error', 'message': 'Không thể xóa: Có bản lưu đang được mượn!'}), 400

    # 1. TRÍCH XUẤT OLD_VALUES TRƯỚC KHI XÓA
    book_to_delete = db.books.find_one({'isbn': isbn})
    if not book_to_delete:
        return jsonify({'status': 'error', 'message': 'Không tìm thấy sách!'}), 404

    book_title = book_to_delete['title']
    doc_id = book_to_delete['_id']

    # 2. Thực hiện hành động xóa
    db.books.delete_one({'isbn': isbn})
    db.book_copies.delete_many({'isbn_ref': isbn})

    # 3. GHI LOG KIỂM TOÁN VỚI DỮ LIỆU CŨ
    log_admin_action(
        action_type='XÓA_SÁCH',
        details=f"Xóa đầu sách: '{book_title}' (ISBN: {isbn})",
        collection_name='books',
        document_id=doc_id,
        old_values=book_to_delete, # Lưu lại toàn bộ cục data của cuốn sách vừa bốc hơi
        new_values=None            # Bị xóa nên không có giá trị mới
    )

    return jsonify({'status': 'success', 'message': 'Đã xóa sách'})
# --- API NGHIỆP VỤ MƯỢN - TRẢ - GIA HẠN (ADMIN) ---

# 1. API Tìm kiếm Độc giả (Cho autocomplete)
@app.route('/api/admin/find-user', methods=['GET'])
def find_user():
    q = request.args.get('q', '')
    if not q: return jsonify([])
    # Tìm theo tên hoặc MSV
    users = list(db.users.find({
        'role': 'user',
        '$or': [{'fullname': {'$regex': q, '$options': 'i'}}, {'msv': {'$regex': q, '$options': 'i'}}]
    }, {'password': 0, 'role': 0}).limit(5))

    for u in users:
        u['_id'] = str(u['_id'])
        # Đếm sách đang mượn
        u['borrow_count'] = db.transactions.count_documents({'user_id': str(u['_id']), 'status': 'borrowing'})
    return jsonify(users)


# 2. API Lấy thông tin sách qua Mã vạch (Khi quét mã)
@app.route('/api/admin/check-book/<barcode>', methods=['GET'])
def check_book_barcode(barcode):
    # Tìm bản lưu trong kho
    copy = db.book_copies.find_one({'barcode': barcode})
    if not copy: return jsonify({'status': 'error', 'message': 'Không tìm thấy mã vạch này!'}), 404

    # Lấy thông tin đầu sách
    book_info = db.books.find_one({'isbn': copy['isbn_ref']})

    return jsonify({
        'status': 'success',
        'book': {
            'title': book_info['title'],
            'author': book_info['author'],
            'barcode': barcode,
            'copy_status': copy['status']
        }
    })


# 3. API Thực hiện Mượn Sách (Submit phiếu mượn)
# Tìm hàm @app.route('/api/admin/borrow', methods=['POST']) và THAY THẾ TOÀN BỘ nội dung hàm bằng:
@app.route('/api/admin/borrow', methods=['POST'])
def admin_borrow():
    if session.get('role') not in ['admin', 'employee']: return jsonify({'status': 'error'}), 403
    data = request.json
    user_id = data.get('user_id')
    barcodes = data.get('barcodes', [])

    if not user_id or not barcodes:
        return jsonify({'status': 'error', 'message': 'Thiếu thông tin!'}), 400

    # Đếm số sách đang mượn (trừ trạng thái pending vì pending sẽ được chuyển thành borrowing hoặc hủy)
    current_loans = db.transactions.count_documents({'user_id': user_id, 'status': 'borrowing'})

    # Logic kiểm tra số lượng có thể thay đổi tùy nhu cầu, ở đây tạm bỏ qua để đơn giản hóa việc fix lỗi

    success_count = 0
    for code in barcodes:
        # 1. Tìm bản lưu (Copy)
        copy = db.book_copies.find_one({'barcode': code})
        if not copy: continue

        # 2. Xử lý trường hợp sách đang AVAILABLE (Mượn trực tiếp)
        if copy['status'] == 'available':
            db.book_copies.update_one({'_id': copy['_id']}, {'$set': {'status': 'borrowed'}})
            db.books.update_one({'isbn': copy['isbn_ref']}, {'$inc': {'qty_avail': -1}})

            db.transactions.insert_one({
                'user_id': user_id,
                'barcode': code,
                'book_title': db.books.find_one({'isbn': copy['isbn_ref']})['title'],
                'borrow_date': datetime.now(),
                'due_date': datetime.now() + timedelta(days=14),
                'status': 'borrowing',
                'renew_count': 0
            })
            success_count += 1

        # 3. Xử lý trường hợp sách đang PENDING (User đã đặt online)
        elif copy['status'] == 'pending':
            # Tìm giao dịch pending của đúng user này với mã vạch này
            pending_trans = db.transactions.find_one({
                'user_id': user_id,
                'barcode': code,
                'status': 'pending'
            })

            if pending_trans:
                # Cập nhật giao dịch pending thành borrowing
                db.transactions.update_one({'_id': pending_trans['_id']}, {
                    '$set': {
                        'status': 'borrowing',
                        'borrow_date': datetime.now(),
                        'due_date': datetime.now() + timedelta(days=14)
                    }
                })
                # Cập nhật trạng thái copy
                db.book_copies.update_one({'_id': copy['_id']}, {'$set': {'status': 'borrowed'}})
                success_count += 1
            else:
                # Sách pending nhưng của người khác -> Bỏ qua hoặc báo lỗi (ở đây ta bỏ qua)
                pass

    return jsonify({'status': 'success', 'message': f'Đã mượn thành công {success_count} cuốn sách!'})


# 5. API Lấy sách đang mượn của User (Để Gia hạn)
@app.route('/api/admin/user-loans/<uid>', methods=['GET'])
def get_user_loans(uid):
    loans = list(db.transactions.find({'user_id': uid, 'status': 'borrowing'}))
    for l in loans:
        l['_id'] = str(l['_id'])
        l['borrow_date'] = l['borrow_date'].strftime('%d/%m/%Y')
        l['due_date_fmt'] = l['due_date'].strftime('%d/%m/%Y')
        l['is_overdue'] = datetime.now() > l['due_date']
    return jsonify(loans)


# 6. API Gia hạn sách
@app.route('/api/admin/renew', methods=['POST'])
def renew_book():
    if session.get('role') not in ['admin', 'employee']: return jsonify({'status': 'error'}), 403
    trans_id = request.json.get('trans_id')

    trans = db.transactions.find_one({'_id': ObjectId(trans_id)})

    # Kiểm tra điều kiện (Chưa quá hạn, chưa gia hạn quá 1 lần)
    if trans['renew_count'] >= 1:
        return jsonify({'status': 'error', 'message': 'Sách này đã gia hạn 1 lần, không thể gia hạn thêm!'}), 400

    if datetime.now() > trans['due_date']:
        return jsonify({'status': 'error', 'message': 'Sách đã quá hạn, không thể gia hạn!'}), 400

    # Gia hạn thêm 7 ngày
    new_due = trans['due_date'] + timedelta(days=7)
    db.transactions.update_one({'_id': trans['_id']}, {
        '$set': {'due_date': new_due},
        '$inc': {'renew_count': 1}
    })

    return jsonify({'status': 'success', 'message': 'Gia hạn thành công thêm 7 ngày!'})
# --- API MƯỢN SÁCH ---
@app.route('/api/borrow', methods=['POST'])
def borrow_book():
    if 'user_id' not in session: return jsonify({'status': 'error', 'message': 'Chưa đăng nhập'}), 401

    data = request.json
    isbn = data.get('isbn')

    # 1. Kiểm tra giới hạn mượn (Max 5)
    current_loans = db.transactions.count_documents({'user_id': session['user_id'], 'status': 'borrowing'})
    if current_loans >= 5:
        return jsonify({'status': 'error', 'message': 'Bạn đã đạt giới hạn mượn 5 cuốn!'}), 400

    # 2. Tìm một cuốn sách "available"
    copy = db.book_copies.find_one({'isbn_ref': isbn, 'status': 'available'})
    if not copy:
        return jsonify({'status': 'error', 'message': 'Sách này đã hết bản lưu!'}), 400

    # 3. Thực hiện mượn
    # Update trạng thái copy
    db.book_copies.update_one({'_id': copy['_id']}, {'$set': {'status': 'borrowed'}})
    # Giảm số lượng khả dụng ở đầu sách
    db.books.update_one({'isbn': isbn}, {'$inc': {'qty_avail': -1}})

    # Tạo transaction
    db.transactions.insert_one({
        'user_id': session['user_id'],
        'book_title': db.books.find_one({'isbn': isbn})['title'],
        'book_barcode': copy['barcode'],
        'borrow_date': datetime.now(),
        'due_date': datetime.now() + timedelta(days=14),
        'status': 'borrowing',
        'renew_count': 0
    })

    return jsonify({'status': 'success', 'message': 'Mượn sách thành công!'})


# --- API THỐNG KÊ (ADMIN) ---
# --- Cập nhật API Thống kê tổng quan (Dashboard Cards) ---
@app.route('/api/stats', methods=['GET'])
def get_stats():
    if session.get('role') not in ['admin', 'employee']: return jsonify({'status': 'error'}), 403

    # 1. Tính tổng doanh thu thực tế từ bảng 'fines'
    # Chỉ tính những phiếu có status = 'paid'
    pipeline = [
        {'$match': {'status': 'paid'}},
        {'$group': {'_id': None, 'total': {'$sum': '$amount'}}}
    ]
    result = list(db.fines.aggregate(pipeline))

    # Nếu có dữ liệu thì lấy tổng, nếu không thì bằng 0
    total_revenue = result[0]['total'] if result else 0

    # Format số tiền cho đẹp (VD: 100000 -> "100.000")
    revenue_formatted = "{:,.0f}".format(total_revenue).replace(",", ".")

    return jsonify({
        'total_books': db.books.count_documents({}),
        'borrowing': db.transactions.count_documents({'status': 'borrowing'}),
        # Đếm số sách đang mượn mà ngày hiện tại > ngày hết hạn
        'overdue': db.transactions.count_documents({
            'status': 'borrowing',
            'due_date': {'$lt': datetime.now()}
        }),
        'revenue': revenue_formatted
    })
# --- API GIỎ HÀNG (DATABASE) ---

@app.route('/api/cart', methods=['GET'])
def get_cart():
    """Lấy danh sách sách trong giỏ của User"""
    if 'user_id' not in session: return jsonify([])

    cart = db.carts.find_one({'user_id': session['user_id']})
    # Trả về list items hoặc list rỗng nếu chưa có cart
    return jsonify(cart.get('items', []) if cart else [])


@app.route('/api/cart/add', methods=['POST'])
def add_to_cart():
    """Thêm sách vào giỏ DB"""
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'Vui lòng đăng nhập!'}), 401

    data = request.json
    isbn = data.get('isbn')

    # 1. Kiểm tra giới hạn giỏ hàng (Max 5)
    cart = db.carts.find_one({'user_id': session['user_id']})
    current_items = cart.get('items', []) if cart else []

    if len(current_items) >= 5:
        return jsonify({'status': 'error', 'message': 'Giỏ sách đã đầy (Max 5 cuốn)!'}), 400

    # 2. Kiểm tra trùng sách
    if any(item['isbn'] == isbn for item in current_items):
        return jsonify({'status': 'error', 'message': 'Sách này đã có trong giỏ!'}), 400

    # 3. Thêm vào DB (Dùng $push và upsert=True để tự tạo nếu chưa có)
    new_item = {
        'isbn': isbn,
        'title': data.get('title'),
        'author': data.get('author')
    }
    db.carts.update_one(
        {'user_id': session['user_id']},
        {'$push': {'items': new_item}},
        upsert=True
    )

    return jsonify({'status': 'success', 'message': 'Đã thêm vào giỏ!'})


@app.route('/api/cart/remove', methods=['POST'])
def remove_from_cart():
    """Xóa sách khỏi giỏ DB"""
    if 'user_id' not in session: return jsonify({'status': 'error'}), 401
    data = request.json

    # Dùng $pull để xóa item có isbn khớp
    db.carts.update_one(
        {'user_id': session['user_id']},
        {'$pull': {'items': {'isbn': data.get('isbn')}}}
    )
    return jsonify({'status': 'success'})


@app.route('/api/user/checkout-db', methods=['POST'])
def checkout_db():
    """Xử lý đăng ký mượn từ Giỏ hàng trong DB"""
    if 'user_id' not in session: return jsonify({'status': 'error'}), 401

    # 1. Lấy sách từ DB Cart
    cart = db.carts.find_one({'user_id': session['user_id']})
    if not cart or not cart.get('items'):
        return jsonify({'status': 'error', 'message': 'Giỏ hàng trống!'}), 400

    items = cart['items']

    # 2. Kiểm tra giới hạn mượn (Tổng đang mượn + Giỏ hàng <= 5)
    current_borrowing = db.transactions.count_documents({
        'user_id': session['user_id'],
        'status': {'$in': ['borrowing', 'pending']}
    })

    if current_borrowing + len(items) > 5:
        return jsonify({'status': 'error', 'message': f'Quá giới hạn! Bạn đang mượn {current_borrowing} cuốn.'}), 400

    success_count = 0

    # 3. Duyệt từng sách để đăng ký
    for item in items:
        isbn = item['isbn']
        # Tìm bản lưu có sẵn
        copy = db.book_copies.find_one({'isbn_ref': isbn, 'status': 'available'})

        if copy:
            # Update trạng thái
            db.book_copies.update_one({'_id': copy['_id']}, {'$set': {'status': 'pending'}})
            db.books.update_one({'isbn': isbn}, {'$inc': {'qty_avail': -1}})

            # Tạo Transaction Pending
            db.transactions.insert_one({
                'user_id': session['user_id'],
                'book_title': item['title'],
                'barcode': copy['barcode'],
                'borrow_date': datetime.now(),
                'due_date': datetime.now() + timedelta(days=2),
                'status': 'pending',
                'renew_count': 0
            })
            success_count += 1

    # 4. Nếu thành công ít nhất 1 cuốn -> Xóa giỏ hàng
    if success_count > 0:
        db.carts.delete_one({'user_id': session['user_id']})
        return jsonify({'status': 'success',
                        'message': f'Đăng ký thành công {success_count} cuốn! Vui lòng đến thư viện nhận sách.'})
    else:
        return jsonify({'status': 'error', 'message': 'Các sách trong giỏ đều đã hết bản lưu!'}), 400
# --- ROUTE CHO USER (Thêm vào app.py) ---
@app.route('/my-books')
def user_loans_page():
    # Kiểm tra đăng nhập
    if 'user_id' not in session: return redirect('/')
    # Trả về giao diện html
    return render_template('user_loans.html')


# --- CÁC API CÒN THIẾU CHO USER (Chèn vào trước app.run) ---

@app.route('/api/user/my-loans', methods=['GET'])
def get_my_loans():
    if 'user_id' not in session: return jsonify([]), 401

    # Lấy cả sách đang mượn và sách đang chờ lấy (pending)
    loans = list(db.transactions.find({
        'user_id': session['user_id'],
        'status': {'$in': ['borrowing', 'pending']}
    }).sort('borrow_date', -1))

    for l in loans:
        l['_id'] = str(l['_id'])
        l['borrow_date_fmt'] = l['borrow_date'].strftime('%d/%m/%Y')
        l['due_date_fmt'] = l['due_date'].strftime('%d/%m/%Y')
        l['is_overdue'] = datetime.now() > l['due_date']

        # Tính số ngày còn lại
        delta = l['due_date'] - datetime.now()
        l['days_left'] = delta.days if delta.days > 0 else 0

    return jsonify(loans)


@app.route('/api/user/renew', methods=['POST'])
def user_renew():
    if 'user_id' not in session: return jsonify({'status': 'error'}), 401

    trans_id = request.json.get('trans_id')
    trans = db.transactions.find_one({'_id': ObjectId(trans_id), 'user_id': session['user_id']})

    if not trans: return jsonify({'status': 'error', 'message': 'Giao dịch không tồn tại!'}), 404

    # Kiểm tra điều kiện gia hạn
    if trans['status'] != 'borrowing':
        return jsonify({'status': 'error', 'message': 'Chỉ có thể gia hạn sách đang mượn!'}), 400

    if trans['renew_count'] >= 1:
        return jsonify({'status': 'error', 'message': 'Bạn đã hết lượt gia hạn cho sách này!'}), 400

    if datetime.now() > trans['due_date']:
        return jsonify({'status': 'error', 'message': 'Sách đã quá hạn, vui lòng mang trả!'}), 400

    # Gia hạn thêm 7 ngày
    new_due = trans['due_date'] + timedelta(days=7)
    db.transactions.update_one({'_id': trans['_id']}, {
        '$set': {'due_date': new_due},
        '$inc': {'renew_count': 1}
    })

    return jsonify({'status': 'success', 'message': 'Gia hạn thành công thêm 7 ngày!'})


# --- ROUTE MỚI ---
@app.route('/admin/fines')
def admin_fines():
    if session.get('role') not in ['admin', 'employee']: return redirect('/')
    return render_template('admin_fines.html')


# --- Cập nhật API lấy dữ liệu Biểu đồ (Sử dụng số liệu thật) ---
@app.route('/api/admin/chart-data', methods=['GET'])
def get_chart_data():
    if session.get('role') not in ['admin', 'employee']: return jsonify({'status': 'error'}), 403

    # 1. BIỂU ĐỒ TRÒN (PIE): Tình trạng sách
    # Đếm số lượng thực tế từ DB
    total_copies = db.book_copies.count_documents({})
    # Những cuốn không phải 'available' tức là đang mượn hoặc chờ xử lý
    borrowed = db.book_copies.count_documents({'status': {'$ne': 'available'}})
    available = total_copies - borrowed

    # 2. BIỂU ĐỒ CỘT (BAR): Doanh thu 6 tháng gần nhất
    bar_labels = []
    bar_data = []

    today = datetime.now()

    # Vòng lặp lấy 6 tháng gần nhất (từ tháng hiện tại lùi về 5 tháng trước)
    for i in range(5, -1, -1):
        # Tính tháng cần query
        # Lưu ý: Cách tính này tương đối, để chính xác tuyệt đối cần dùng thư viện dateutil
        # nhưng ở đây dùng logic đơn giản để không cần cài thêm thư viện.
        date_cursor = today.replace(day=1)

        # Lùi lại i tháng (Logic xử lý năm)
        target_month = date_cursor.month - i
        target_year = date_cursor.year
        if target_month <= 0:
            target_month += 12
            target_year -= 1

        # Tạo label hiển thị (VD: 12/2024)
        label = f"{target_month:02d}/{target_year}"
        bar_labels.append(label)

        # Xác định ngày đầu tháng và ngày đầu tháng sau (để kẹp khoảng thời gian)
        start_date = datetime(target_year, target_month, 1)
        if target_month == 12:
            end_date = datetime(target_year + 1, 1, 1)
        else:
            end_date = datetime(target_year, target_month + 1, 1)

        # Query Aggregation: Tính tổng tiền phạt (status='paid') trong khoảng thời gian này
        # Dùng bảng 'fines' (đã tạo ở bước trước)
        pipeline = [
            {
                '$match': {
                    'status': 'paid',
                    'payment_date': {'$gte': start_date, '$lt': end_date}
                }
            },
            {
                '$group': {
                    '_id': None,
                    'total_revenue': {'$sum': '$amount'}
                }
            }
        ]

        result = list(db.fines.aggregate(pipeline))

        # Nếu có kết quả thì lấy, không thì bằng 0
        monthly_total = result[0]['total_revenue'] if result else 0
        bar_data.append(monthly_total)

    return jsonify({
        'pie_data': [available, borrowed],
        'bar_labels': bar_labels,
        'bar_data': bar_data
    })
# --- API QUẢN LÝ BẢN LƯU (COPY) TRONG CHI TIẾT SÁCH ---

@app.route('/api/admin/book/add-copy', methods=['POST'])
def add_book_copy():
    if session.get('role') not in ['admin', 'employee']: return jsonify({'status': 'error'}), 403

    data = request.json
    isbn = data.get('isbn')
    qty_to_add = int(data.get('qty', 1))  # Số lượng cần thêm
    location = data.get('location', 'Kho chung')

    book = db.books.find_one({'isbn': isbn})
    if not book: return jsonify({'status': 'error', 'message': 'Không tìm thấy sách!'}), 404

    # Tính toán mã vạch tiếp theo (Dựa trên số lượng hiện có để tránh trùng)
    # Ví dụ: Đang có 978-1-5 -> Cái tiếp theo là 978-1-6
    current_count = db.book_copies.count_documents({'isbn_ref': isbn})

    new_copies = []
    for i in range(qty_to_add):
        current_count += 1
        new_copies.append({
            'isbn_ref': isbn,
            'barcode': f"{isbn}-{current_count}",
            'status': 'available',
            'location': location
        })

    if new_copies:
        db.book_copies.insert_many(new_copies)
        # Cập nhật lại tổng số lượng và khả dụng trong bảng books
        db.books.update_one({'isbn': isbn}, {
            '$inc': {'qty_total': qty_to_add, 'qty_avail': qty_to_add}
        })

    return jsonify({'status': 'success', 'message': f'Đã thêm {qty_to_add} bản lưu mới!'})


@app.route('/api/admin/book/copy/<barcode>', methods=['DELETE'])
def delete_book_copy(barcode):
    if session.get('role') not in ['admin', 'employee']: return jsonify({'status': 'error'}), 403

    # Kiểm tra trạng thái sách
    copy = db.book_copies.find_one({'barcode': barcode})
    if not copy: return jsonify({'status': 'error', 'message': 'Không tìm thấy bản lưu này!'}), 404

    if copy['status'] != 'available':
        return jsonify({'status': 'error', 'message': 'Không thể xóa: Sách này đang được mượn hoặc chờ xử lý!'}), 400

    # Xóa bản lưu
    db.book_copies.delete_one({'_id': copy['_id']})

    # Cập nhật giảm số lượng trong bảng books
    db.books.update_one({'isbn': copy['isbn_ref']}, {
        '$inc': {'qty_total': -1, 'qty_avail': -1}
    })

    return jsonify({'status': 'success', 'message': 'Đã xóa bản lưu thành công!'})


# --- LOGIC QUẢN LÝ PHẠT (NÂNG CẤP) ---

@app.route('/api/admin/fines', methods=['GET'])
def get_fines_list():
    if session.get('role') not in ['admin', 'employee']: return jsonify([]), 403

    # Lấy tham số tìm kiếm và phân trang từ request
    q = request.args.get('q', '').lower()
    page = int(request.args.get('page', 1))
    limit = 12

    all_fines = []

    # 1. LẤY NỢ TỪ GIAO DỊCH TRỄ HẠN TỰ ĐỘNG (BẢNG transactions)
    transactions_with_fines = list(db.transactions.find({'fine': {'$gt': 0}}))
    for t in transactions_with_fines:
        user = db.users.find_one({'_id': ObjectId(t['user_id'])})
        all_fines.append({
            '_id': str(t['_id']),
            'type': 'transaction',  # Đánh dấu nguồn gốc để lúc thu tiền xử lý cho đúng
            'user_name': user['fullname'] if user else 'Khách',
            'user_msv': user['msv'] if user else 'N/A',
            'amount': t.get('fine', 0),
            'reason': 'overdue',
            'description': f"Trễ hạn sách: {t.get('book_title', '')}",
            'status': 'paid' if t.get('fine_paid') else 'unpaid',
            'created_at': t.get('return_date', t.get('borrow_date')).strftime('%d/%m/%Y'),
            'is_paid': t.get('fine_paid', False)
        })

    # 2. LẤY NỢ TỪ PHIẾU PHẠT THỦ CÔNG (BẢNG fines)
    manual_fines = list(db.fines.find({}))
    for f in manual_fines:
        f['_id'] = str(f['_id'])
        f['type'] = 'manual'  # Đánh dấu nguồn gốc
        f['created_at'] = f['created_at'].strftime('%d/%m/%Y')
        f['is_paid'] = (f.get('status') == 'paid')
        all_fines.append(f)

    # 3. LỌC DỮ LIỆU TÌM KIẾM (Search)
    filtered_fines = []
    if q:
        for f in all_fines:
            # Tìm từ khóa không phân biệt hoa thường trong Tên, MSV hoặc Nội dung phạt
            if (q in str(f.get('user_name', '')).lower() or
                    q in str(f.get('user_msv', '')).lower() or
                    q in str(f.get('description', '')).lower()):
                filtered_fines.append(f)
    else:
        filtered_fines = all_fines

    # 4. SẮP XẾP LẠI: Đưa các khoản "Chưa thanh toán" (unpaid) lên đầu tiên
    filtered_fines.sort(key=lambda x: (x['is_paid'], -int(x['_id'][:8], 16) if len(x['_id']) == 24 else 0))

    # 5. XỬ LÝ PHÂN TRANG (Pagination)
    total_items = len(filtered_fines)
    total_pages = (total_items + limit - 1) // limit

    # Dùng List Slicing để lấy đúng 12 item cho trang hiện tại
    skip = (page - 1) * limit
    paginated_data = filtered_fines[skip: skip + limit]

    # Trả về format chuẩn để JS xử lý được phân trang
    return jsonify({
        'data': paginated_data,
        'total_pages': total_pages,
        'current_page': page
    })


@app.route('/api/admin/fine/create', methods=['POST'])
def create_manual_fine():
    if session.get('role') not in ['admin', 'employee']: return jsonify({'status': 'error'}), 403
    data = request.json

    user_id = data.get('user_id')
    amount = int(data.get('amount', 0))
    reason = data.get('reason')
    note = data.get('note', '')

    if not user_id or amount <= 0: return jsonify({'status': 'error', 'message': 'Dữ liệu không hợp lệ!'}), 400

    user = db.users.find_one({'_id': ObjectId(user_id)})
    if not user: return jsonify({'status': 'error', 'message': 'Không tìm thấy độc giả!'}), 404

    new_fine = {
        'user_id': user_id,
        'user_name': user['fullname'],
        'user_msv': user['msv'],
        'amount': amount,
        'reason': reason,
        'description': note,
        'status': 'unpaid',
        'created_at': datetime.now()
    }

    # 1. Chèn vào DB
    insert_result = db.fines.insert_one(new_fine)

    # Lấy _id vừa tạo gán vào dict để ghi log
    new_fine['_id'] = insert_result.inserted_id

    # 2. GHI LOG KIỂM TOÁN DỮ LIỆU VỪA SINH RA
    log_admin_action(
        action_type='TẠO_PHIẾU_PHẠT',
        details=f"Phạt {new_fine['user_name']} số tiền {amount:,.0f}đ",
        collection_name='fines',
        document_id=insert_result.inserted_id,
        old_values=None,  # Mới tạo nên không có giá trị cũ
        new_values=new_fine  # Lưu lại nguyên văn phiếu phạt vừa sinh ra
    )

    return jsonify({'status': 'success', 'message': 'Đã lập phiếu phạt thành công!'})


@app.route('/api/admin/pay-fine', methods=['POST'])
def pay_fine():
    if session.get('role') not in ['admin', 'employee']: return jsonify({'status': 'error'}), 403

    record_id = request.json.get('id')
    user_id_to_check = None
    amount_collected = 0

    old_record = None
    new_record = None
    collection_impacted = None

    # Tìm ở bảng transactions trước
    trans = db.transactions.find_one({'_id': ObjectId(record_id)})
    if trans:
        old_record = copy.deepcopy(trans)
        collection_impacted = 'transactions'

        db.transactions.update_one({'_id': ObjectId(record_id)}, {
            '$set': {'fine_paid': True, 'payment_date': datetime.now()}
        })

        # Lấy record sau khi đã update
        new_record = db.transactions.find_one({'_id': ObjectId(record_id)})

        user_id_to_check = trans['user_id']
        amount_collected = trans.get('fine', 0)
    else:
        fine = db.fines.find_one({'_id': ObjectId(record_id)})
        if fine:
            old_record = copy.deepcopy(fine)
            collection_impacted = 'fines'

            db.fines.update_one({'_id': ObjectId(record_id)}, {
                '$set': {'status': 'paid'}
            })

            new_record = db.fines.find_one({'_id': ObjectId(record_id)})

            user_id_to_check = fine['user_id']
            amount_collected = fine.get('amount', 0)
        else:
            return jsonify({'status': 'error', 'message': 'Không tìm thấy khoản nợ này!'}), 404

    # Logic xóa cảnh báo user...
    if user_id_to_check:
        remaining_debt_trans = db.transactions.count_documents({'user_id': user_id_to_check,
                                                                '$or': [{'fine_paid': False, 'fine': {'$gt': 0}},
                                                                        {'status': 'borrowing',
                                                                         'due_date': {'$lt': datetime.now()}}]})
        remaining_debt_fines = db.fines.count_documents({'user_id': user_id_to_check, 'status': 'unpaid'})
        if remaining_debt_trans == 0 and remaining_debt_fines == 0:
            db.users.update_one({'_id': ObjectId(user_id_to_check)}, {'$set': {'warning_count': 0}})

    # GHI LOG KIỂM TOÁN THU TIỀN (So sánh Before / After)
    log_admin_action(
        action_type='THU_TIỀN',
        details=f"Xác nhận thu {amount_collected:,.0f}đ tiền phạt (ID: {record_id})",
        collection_name=collection_impacted,
        document_id=record_id,
        old_values=old_record,
        new_values=new_record
    )

    return jsonify({'status': 'success', 'message': 'Đã xác nhận thu tiền và cập nhật trạng thái!'})
# =====================================================================
# --- PHÂN HỆ MIS CHỨC NĂNG: TÀI CHÍNH (FINANCIAL MIS) ---
# =====================================================================

@app.route('/api/admin/finance/add-expense', methods=['POST'])
def add_expense():
    """Ghi nhận khoản chi mới (Mua sách, bảo trì, v.v...)"""
    if session.get('role') not in ['admin', 'employee']: return jsonify({'status': 'error'}), 403
    data = request.json

    new_expense = {
        'amount': int(data.get('amount', 0)),
        'category': data.get('category'),  # 'book_purchase', 'maintenance', 'salary', 'other'
        'description': data.get('description', ''),
        'recorded_by': session.get('fullname'),
        'date': datetime.now()
    }

    if new_expense['amount'] > 0:
        db.expenses.insert_one(new_expense)
        # Tự động ghi log nhân sự (Ai đã chi tiền)
        log_admin_action("CHI_TIỀN", f"Chi {new_expense['amount']:,.0f}đ cho: {new_expense['description']}")
        return jsonify({'status': 'success', 'message': 'Đã ghi nhận khoản chi.'})
    return jsonify({'status': 'error', 'message': 'Số tiền không hợp lệ.'}), 400


@app.route('/api/admin/finance/report', methods=['GET'])
def get_financial_report():
    """Báo cáo Thu - Chi tổng thể"""
    if session.get('role') not in ['admin', 'employee']: return jsonify({}), 403

    # 1. TỔNG THU (Từ tiền phạt đã đóng)
    # Lấy từ transactions
    trans_income = list(db.transactions.aggregate([
        {'$match': {'fine_paid': True, 'fine': {'$gt': 0}}},
        {'$group': {'_id': None, 'total': {'$sum': '$fine'}}}
    ]))
    # Lấy từ fines (Phiếu thủ công)
    manual_income = list(db.fines.aggregate([
        {'$match': {'status': 'paid'}},
        {'$group': {'_id': None, 'total': {'$sum': '$amount'}}}
    ]))
    total_income = (trans_income[0]['total'] if trans_income else 0) + (
        manual_income[0]['total'] if manual_income else 0)

    # 2. TỔNG CHI (Từ bảng expenses)
    expense_result = list(db.expenses.aggregate([
        {'$group': {'_id': None, 'total': {'$sum': '$amount'}}}
    ]))
    total_expense = expense_result[0]['total'] if expense_result else 0

    # 3. LỢI NHUẬN RÒNG (ROI)
    net_profit = total_income - total_expense

    return jsonify({
        'total_income': total_income,
        'total_expense': total_expense,
        'net_profit': net_profit,
        'status': 'Lãi' if net_profit >= 0 else 'Lỗ'
    })


# =====================================================================
# --- PHÂN HỆ MIS CHỨC NĂNG: NHÂN SỰ & KIỂM TOÁN (HR & AUDIT MIS) ---
# =====================================================================

def log_admin_action(action_type, details, collection_name=None, document_id=None, old_values=None, new_values=None):
    """
    Hàm lưu vết kiểm toán (Audit Trail) nâng cao chống gian lận.
    Lưu ý: Cần import copy ở đầu file app.py nếu chưa có.
    """
    try:
        # Clone dữ liệu để tránh reference lỗi khi biến đổi ObjectId thành chuỗi
        old_data = copy.deepcopy(old_values) if old_values else None
        new_data = copy.deepcopy(new_values) if new_values else None

        # Format lại ObjectId thành string để có thể lưu mượt mà hoặc jsonify sau này
        if old_data and '_id' in old_data: old_data['_id'] = str(old_data['_id'])
        if new_data and '_id' in new_data: new_data['_id'] = str(new_data['_id'])

        audit_record = {
            'admin_id': session.get('user_id'),
            'admin_name': session.get('fullname', 'Unknown'),
            'action_type': action_type,
            'details': details,
            'collection': collection_name,       # Bảng nào bị tác động (books, fines...)
            'document_id': str(document_id) if document_id else None, # ID của dòng dữ liệu
            'old_values': old_data,              # Dữ liệu GỐC trước khi bị tác động
            'new_values': new_data,              # Dữ liệu MỚI sau khi bị tác động
            'timestamp': datetime.now()
        }
        db.audit_logs.insert_one(audit_record)
    except Exception as e:
        print("Lỗi ghi Audit Log:", e)


@app.route('/api/admin/hr/audit-logs', methods=['GET'])
def get_audit_logs():
    """Lấy lịch sử thao tác của nhân viên thư viện"""
    if session.get('role') != 'admin': return jsonify([]), 403

    # Lấy 100 log gần nhất
    logs = list(db.audit_logs.find({}).sort('timestamp', -1).limit(100))
    for log in logs:
        log['_id'] = str(log['_id'])
        log['time_fmt'] = log['timestamp'].strftime('%H:%M:%S %d/%m/%Y')

    return jsonify(logs)


@app.route('/api/admin/hr/kpi', methods=['GET'])
def get_admin_kpi():
    """Thống kê KPI (Hiệu suất làm việc) của từng Admin"""
    if session.get('role') != 'admin': return jsonify([]), 403

    # Đếm số lượng thao tác của mỗi Admin trong tháng này
    pipeline = [
        {'$match': {'timestamp': {'$gte': datetime.now() - timedelta(days=30)}}},
        {'$group': {
            '_id': '$admin_name',
            'total_actions': {'$sum': 1},
            # Có thể phân loại sâu hơn (Ví dụ: Đếm số lần thu tiền, đếm số sách thêm mới)
        }},
        {'$sort': {'total_actions': -1}}
    ]

    kpi_data = list(db.audit_logs.aggregate(pipeline))
    return jsonify(kpi_data)
# --- API DSS: WHAT-IF ANALYSIS (MÔ PHỎNG KỊCH BẢN) ---
@app.route('/api/admin/dss/what-if', methods=['POST'])
def dss_what_if():
    if session.get('role') not in ['admin', 'employee']: return jsonify({}), 403

    data = request.json
    new_max_days = int(data.get('max_days', 14))
    new_fine_rate = int(data.get('fine_rate', 1000))
    period = data.get('period', 'all')  # Nhận mốc thời gian từ Frontend

    # 1. Lọc giao dịch theo mốc thời gian
    match_stage = {'status': 'returned'}  # Giả lập trên các đơn đã hoàn tất
    if period != 'all':
        now = datetime.now()
        if period == 'month':
            start_date = now - timedelta(days=30)
        elif period == 'quarter':
            start_date = now - timedelta(days=90)
        elif period == 'year':
            start_date = now - timedelta(days=365)
        else:
            start_date = None
        if start_date: match_stage['borrow_date'] = {'$gte': start_date}

    transactions = list(db.transactions.find(match_stage))

    # 2. Tính toán doanh thu thực tế vs Doanh thu giả lập
    actual_revenue = 0
    projected_revenue = 0

    for t in transactions:
        actual_revenue += t.get('fine', 0)

        # Giả lập: Tính số ngày mượn thực tế
        borrow_date = t.get('borrow_date')
        return_date = t.get('return_date')
        if not borrow_date or not return_date: continue

        borrow_duration = (return_date - borrow_date).days

        # Nếu số ngày mượn vượt quá quy định MỚI -> Bị phạt theo mức MỚI
        if borrow_duration > new_max_days:
            overdue_days = borrow_duration - new_max_days
            projected_revenue += overdue_days * new_fine_rate

    # 3. Tính % thay đổi
    diff_percent = 0
    if actual_revenue > 0:
        diff_percent = round(((projected_revenue - actual_revenue) / actual_revenue) * 100, 1)
    elif projected_revenue > 0:
        diff_percent = 100  # Tăng từ 0 lên có tiền

    return jsonify({
        'projected_revenue': projected_revenue,
        'diff_percent': diff_percent,
        'baseline_revenue': actual_revenue
    })
# --- API DSS: DRILL-DOWN (ĐÀO SÂU DỮ LIỆU BIỂU ĐỒ) ---
@app.route('/api/admin/dss/drilldown', methods=['GET'])
def dss_drilldown():
    """
    Phân tích Drill-down: Trả về Top 5 sách mượn nhiều nhất của một thể loại cụ thể.
    """
    if session.get('role') not in ['admin', 'employee']: return jsonify([]), 403
    category = request.args.get('category')

    pipeline = [
        {'$match': {'status': {'$in': ['borrowing', 'returned']}}},
        {'$lookup': {
            'from': 'books',
            'localField': 'book_title',
            'foreignField': 'title',
            'as': 'book_info'
        }},
        {'$unwind': '$book_info'},
        # Lọc đúng thể loại Admin click vào
        {'$match': {'book_info.category': category}},
        {'$group': {
            '_id': '$book_title',
            'borrow_count': {'$sum': 1}
        }},
        {'$sort': {'borrow_count': -1}},
        {'$limit': 5}  # Chỉ lấy Top 5
    ]

    drilldown_data = list(db.transactions.aggregate(pipeline))

    # Format lại dữ liệu trả về Frontend
    return jsonify([
        {'title': d['_id'], 'count': d['borrow_count']}
        for d in drilldown_data
    ])
# --- CẬP NHẬT LẠI HÀM TRẢ SÁCH (admin_return) ĐỂ TỰ ĐỘNG TẠO PHẠT ---
# Tìm hàm admin_return cũ và thay thế bằng hàm này
@app.route('/api/admin/return', methods=['POST'])
def admin_return():
    if session.get('role') not in ['admin', 'employee']: return jsonify({'status': 'error'}), 403
    barcode = request.json.get('barcode')

    trans = db.transactions.find_one({'barcode': barcode, 'status': 'borrowing'})
    if not trans:
        return jsonify({'status': 'error', 'message': 'Sách này không ở trạng thái đang mượn!'}), 400

    # Tính phạt quá hạn
    overdue_days = 0
    fine_amount = 0
    if datetime.now() > trans['due_date']:
        delta = datetime.now() - trans['due_date']
        overdue_days = delta.days
        fine_amount = overdue_days * 1000  # 1000đ/ngày

    # Update Transaction
    update_data = {
        'status': 'returned',
        'return_date': datetime.now(),
        'fine': fine_amount,
        'overdue_days': overdue_days
    }
    db.transactions.update_one({'_id': trans['_id']}, {'$set': update_data})

    # Update Kho sách
    db.book_copies.update_one({'barcode': barcode}, {'$set': {'status': 'available'}})
    copy = db.book_copies.find_one({'barcode': barcode})
    db.books.update_one({'isbn': copy['isbn_ref']}, {'$inc': {'qty_avail': 1}})

    # === LOGIC MỚI: TẠO PHIẾU PHẠT TỰ ĐỘNG ===
    if fine_amount > 0:
        user = db.users.find_one({'_id': ObjectId(trans['user_id'])})
        db.fines.insert_one({
            'user_id': trans['user_id'],
            'user_name': user['fullname'],
            'user_msv': user['msv'],
            'amount': fine_amount,
            'reason': 'overdue',
            'description': f"Quá hạn {overdue_days} ngày - Sách: {trans['book_title']}",
            'status': 'unpaid',
            'created_at': datetime.now()
        })

    return jsonify({
        'status': 'success',
        'message': 'Trả sách thành công!',
        'fine': fine_amount,
        'overdue': overdue_days
    })


# =====================================================================
# --- PHÂN HỆ QUẢN LÝ NHÂN SỰ / NHÂN VIÊN (RBAC) ---
# =====================================================================

@app.route('/admin/employees')
def admin_employees_page():
    """Giao diện Quản lý Danh sách Nhân viên (Chỉ Admin mới được vào)"""
    if session.get('role') != 'admin': return redirect('/')
    return render_template('admin_employees.html')


@app.route('/api/admin/employees', methods=['GET'])
def get_employees():
    """API lấy danh sách nhân viên và quản lý"""
    if session.get('role') != 'admin': return jsonify([]), 403

    # Lấy danh sách user có role là admin hoặc employee (bỏ qua sinh viên 'user')
    staff = list(db.users.find({'role': {'$in': ['admin', 'employee']}}, {'password': 0}))
    for s in staff:
        s['_id'] = str(s['_id'])
        s['created_at_fmt'] = s.get('created_at', datetime.now()).strftime('%d/%m/%Y')

    return jsonify(staff)


@app.route('/api/admin/employee', methods=['POST'])
def create_employee():
    """API Cấp tài khoản mới cho Nhân viên"""
    if session.get('role') != 'admin': return jsonify({'status': 'error'}), 403
    data = request.json

    # Kiểm tra xem tên đăng nhập đã tồn tại chưa
    if db.users.find_one({'username': data['username']}):
        return jsonify({'status': 'error', 'message': 'Tên đăng nhập đã tồn tại!'}), 400

    new_staff = {
        "username": data['username'],
        "password": generate_password_hash(data.get('password', '123456')),
        "role": data['role'],  # 'admin' hoặc 'employee'
        "fullname": data['fullname'],
        "email": data.get('email', ''),
        "created_at": datetime.now()
    }

    db.users.insert_one(new_staff)

    # Ghi Audit Log tự động
    log_admin_action('THÊM_NHÂN_SỰ', f"Tạo tài khoản {data['role']}: {data['username']}")

    return jsonify({'status': 'success', 'message': 'Cấp tài khoản nhân sự thành công!'})


@app.route('/api/admin/employee/<uid>', methods=['DELETE'])
def delete_employee(uid):
    """API Khóa/Xóa tài khoản nhân viên cũ"""
    if session.get('role') != 'admin': return jsonify({'status': 'error'}), 403

    # Không cho phép admin tự xóa chính mình
    if uid == session.get('user_id'):
        return jsonify({'status': 'error', 'message': 'Không thể tự xóa chính mình!'}), 400

    user_to_del = db.users.find_one({'_id': ObjectId(uid)})
    db.users.delete_one({'_id': ObjectId(uid)})

    if user_to_del:
        log_admin_action('XÓA_NHÂN_SỰ', f"Xóa/Thu hồi tài khoản: {user_to_del.get('username')}")

    return jsonify({'status': 'success', 'message': 'Đã thu hồi quyền của nhân sự này!'})
if __name__ == '__main__':
    app.run(debug=True, port=5000)