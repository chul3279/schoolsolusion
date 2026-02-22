from flask import Blueprint, render_template, request, jsonify, session
import re
from utils.db import get_db_connection, sanitize_input

support_bp = Blueprint('support', __name__)

# ============================================
# 고객센터 페이지
# ============================================
@support_bp.route('/support')
def support_page():
    return render_template('support.html')

# ============================================
# 고객센터 문의 등록 API
# ============================================
@support_bp.route('/api/support/inquiry', methods=['POST'])
def create_support_inquiry():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        
        member_id = session.get('user_id')
        member_name = session.get('user_name')
        
        customer_name = sanitize_input(data.get('customer_name'), 100)
        customer_email = sanitize_input(data.get('customer_email'), 100)
        customer_phone = sanitize_input(data.get('customer_phone'), 20)
        
        type_code = sanitize_input(data.get('type_code'), 20)
        subject = sanitize_input(data.get('subject'), 200)
        message = sanitize_input(data.get('message'), 5000)
        privacy_agreed = data.get('privacy_agreed', False)
        
        if not all([customer_name, customer_email, type_code, subject, message]):
            return jsonify({'success': False, 'message': '모든 필수 항목을 입력해주세요.'})
        
        if not privacy_agreed:
            return jsonify({'success': False, 'message': '개인정보 처리방침에 동의해주세요.'})
        
        email_pattern = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
        if not re.match(email_pattern, customer_email):
            return jsonify({'success': False, 'message': '올바른 이메일 형식을 입력해주세요.'})
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        
        cursor = conn.cursor()
        
        insert_query = """
            INSERT INTO support_inquiries (
                member_id, member_name, customer_email, customer_phone,
                type_code, subject, message, privacy_agreed, status, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pending', NOW())
        """
        
        cursor.execute(insert_query, (member_id, member_name, customer_email, customer_phone, type_code, subject, message, privacy_agreed))
        inquiry_id = cursor.lastrowid
        conn.commit()
        
        return jsonify({'success': True, 'message': '문의가 성공적으로 접수되었습니다.', 'inquiry_id': inquiry_id}), 201
        
    except Exception as e:
        print(f"고객센터 문의 등록 오류: {e}")
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': '문의 접수 중 오류가 발생했습니다.'}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()
