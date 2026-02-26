"""
SchoolUs 가정통신문 API
- /api/letter/list: 목록
- /api/letter/create: 발송 (파일첨부 선택)
- /api/letter/detail: 상세 + 동의현황
- /api/letter/delete: 삭제
- /api/letter/reply: 학부모 동의/비동의
- /api/letter/consent-status: 동의현황
- /api/letter/download: 첨부파일 다운로드
- /api/letter/export: 동의현황 CSV
"""

from flask import Blueprint, request, jsonify, session, make_response
from utils.db import get_db_connection, sanitize_input, sanitize_html
from routes.subject_utils import sftp_upload_file, sftp_download_file, sftp_remove_file, allowed_file
import os
import csv
import io

letter_bp = Blueprint('letter', __name__)


# ============================================
# 가정통신문 목록
# ============================================
@letter_bp.route('/api/letter/list', methods=['GET'])
def get_letter_list():
    conn = None
    cursor = None
    try:
        school_id = session.get('school_id') or sanitize_input(request.args.get('school_id'), 50)
        class_grade = sanitize_input(request.args.get('class_grade'), 10)
        class_no = sanitize_input(request.args.get('class_no'), 10)
        keyword = sanitize_input(request.args.get('keyword'), 100)

        # class_grade/class_no 미전달 시 tea_all에서 조회
        teacher_id = session.get('user_id')
        if teacher_id and (not class_grade or not class_no):
            t_conn = get_db_connection()
            if t_conn:
                try:
                    t_cur = t_conn.cursor()
                    t_cur.execute("SELECT class_grade, class_no FROM tea_all WHERE member_id = %s", (teacher_id,))
                    t_row = t_cur.fetchone()
                    if t_row:
                        if not class_grade:
                            class_grade = str(t_row['class_grade']) if t_row['class_grade'] else None
                        if not class_no:
                            class_no = str(t_row['class_no']) if t_row['class_no'] else None
                    t_cur.close()
                finally:
                    t_conn.close()

        if not all([school_id, class_grade, class_no]):
            return jsonify({'success': False, 'message': '필수 정보가 누락되었습니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        query = """SELECT hl.id, hl.title, hl.require_consent, hl.consent_deadline,
                          hl.file_name, hl.created_at, m.member_name AS teacher_name
                   FROM home_letter hl
                   JOIN member m ON hl.teacher_id = m.member_id
                   WHERE hl.school_id = %s AND hl.class_grade = %s AND hl.class_no = %s"""
        params = [school_id, class_grade, class_no]

        if keyword:
            query += " AND (hl.title LIKE %s OR hl.content LIKE %s)"
            params.extend([f'%{keyword}%', f'%{keyword}%'])

        query += " ORDER BY hl.created_at DESC LIMIT 50"
        cursor.execute(query, params)

        letters = []
        for r in cursor.fetchall():
            letters.append({
                'id': r['id'],
                'title': r['title'],
                'teacher_name': r['teacher_name'] or '',
                'require_consent': bool(r['require_consent']),
                'consent_deadline': r['consent_deadline'].strftime('%Y-%m-%d') if r['consent_deadline'] else '',
                'has_file': bool(r['file_name']),
                'file_name': r['file_name'] or '',
                'created_at': r['created_at'].strftime('%Y-%m-%d %H:%M') if r['created_at'] else ''
            })

        return jsonify({'success': True, 'letters': letters})

    except Exception as e:
        print(f"가정통신문 목록 오류: {e}")
        return jsonify({'success': False, 'message': '조회 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 가정통신문 발송 (교사용)
# ============================================
@letter_bp.route('/api/letter/create', methods=['POST'])
def create_letter():
    conn = None
    cursor = None
    try:
        # JSON body와 form data 모두 지원
        data = request.get_json(silent=True) or {}
        def _get(key, default=''):
            return request.form.get(key, data.get(key, default))

        school_id = session.get('school_id') or sanitize_input(_get('school_id'), 50)
        class_grade = sanitize_input(_get('class_grade'), 10)
        class_no = sanitize_input(_get('class_no'), 10)
        teacher_id = session.get('user_id')
        title = sanitize_html(_get('title', ''), 200)
        content = sanitize_html(_get('content', ''), 10000)
        require_consent = _get('require_consent', '0') == '1' or _get('require_consent', False) is True
        consent_deadline = sanitize_input(_get('consent_deadline'), 10) or None

        # class_grade/class_no 미전달 시 tea_all에서 조회
        if teacher_id and (not class_grade or not class_no):
            t_conn = get_db_connection()
            if t_conn:
                try:
                    t_cur = t_conn.cursor()
                    t_cur.execute("SELECT class_grade, class_no FROM tea_all WHERE member_id = %s", (teacher_id,))
                    t_row = t_cur.fetchone()
                    if t_row:
                        if not class_grade:
                            class_grade = str(t_row['class_grade']) if t_row['class_grade'] else None
                        if not class_no:
                            class_no = str(t_row['class_no']) if t_row['class_no'] else None
                    t_cur.close()
                finally:
                    t_conn.close()

        if not school_id or not class_grade or not class_no:
            return jsonify({'success': False, 'message': '반 정보가 누락되었습니다. 담임 선생님만 가정통신문을 작성할 수 있습니다.'})
        if not title or not content:
            return jsonify({'success': False, 'message': '제목과 내용을 입력해주세요.'})

        # 파일 처리
        file_path = None
        file_name = None
        uploaded_file = request.files.get('file')
        if uploaded_file and uploaded_file.filename:
            if not allowed_file(uploaded_file.filename):
                return jsonify({'success': False, 'message': '허용되지 않는 파일 형식입니다.'})
            file_name = uploaded_file.filename

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        cursor.execute("""INSERT INTO home_letter
            (school_id, class_grade, class_no, teacher_id, title, content, require_consent, consent_deadline, file_path, file_name)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (school_id, class_grade, class_no, teacher_id, title, content,
             1 if require_consent else 0, consent_deadline, file_path, file_name))
        conn.commit()
        letter_id = cursor.lastrowid

        # 파일 SFTP 업로드
        if uploaded_file and file_name:
            remote_path = f'/schoolus/letters/{school_id}/{letter_id}/{file_name}'
            sftp_upload_file(uploaded_file, remote_path)
            cursor.execute("UPDATE home_letter SET file_path = %s WHERE id = %s", (remote_path, letter_id))
            conn.commit()

        # 푸시 알림
        try:
            from utils.push_helper import send_push_to_class
            send_push_to_class(
                school_id, class_grade, class_no,
                '가정통신문',
                title,
                '/highschool/fm_homeroom.html',
                ['parent']
            )
        except Exception as pe:
            print(f"[Letter] Push error: {pe}")

        return jsonify({'success': True, 'message': '가정통신문이 발송되었습니다.', 'id': letter_id})

    except Exception as e:
        print(f"가정통신문 발송 오류: {e}")
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': '발송 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 가정통신문 상세
# ============================================
@letter_bp.route('/api/letter/detail', methods=['GET'])
def get_letter_detail():
    conn = None
    cursor = None
    try:
        letter_id = sanitize_input(request.args.get('id'), 10)
        if not letter_id:
            return jsonify({'success': False, 'message': 'ID가 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        cursor.execute("""SELECT hl.*, m.member_name AS teacher_name
                          FROM home_letter hl
                          JOIN member m ON hl.teacher_id = m.member_id
                          WHERE hl.id = %s""", (letter_id,))
        letter = cursor.fetchone()
        if not letter:
            return jsonify({'success': False, 'message': '가정통신문을 찾을 수 없습니다.'})

        result = {
            'id': letter['id'],
            'title': letter['title'],
            'content': letter['content'],
            'teacher_name': letter['teacher_name'] or '',
            'teacher_id': letter['teacher_id'],
            'require_consent': bool(letter['require_consent']),
            'consent_deadline': letter['consent_deadline'].strftime('%Y-%m-%d') if letter['consent_deadline'] else '',
            'file_name': letter['file_name'] or '',
            'has_file': bool(letter['file_path']),
            'created_at': letter['created_at'].strftime('%Y-%m-%d %H:%M') if letter['created_at'] else ''
        }

        # 학부모 또는 학생인 경우 본인 응답 여부 확인
        if session.get('user_role') in ('parent', 'student'):
            user_id = session.get('user_id')
            cursor.execute("SELECT consent_status, reply_memo, created_at FROM home_letter_reply WHERE letter_id = %s AND parent_id = %s",
                           (letter_id, user_id))
            reply = cursor.fetchone()
            if reply:
                result['my_reply'] = {
                    'consent_status': reply['consent_status'],
                    'reply_memo': reply['reply_memo'] or '',
                    'replied_at': reply['created_at'].strftime('%Y-%m-%d %H:%M') if reply['created_at'] else ''
                }

        return jsonify({'success': True, 'letter': result})

    except Exception as e:
        print(f"가정통신문 상세 오류: {e}")
        return jsonify({'success': False, 'message': '조회 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 가정통신문 삭제 (교사용)
# ============================================
@letter_bp.route('/api/letter/delete', methods=['POST'])
def delete_letter():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        letter_id = sanitize_input(data.get('id'), 10)
        if not letter_id:
            return jsonify({'success': False, 'message': 'ID가 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        # 작성자 확인
        cursor.execute("SELECT teacher_id, file_path FROM home_letter WHERE id = %s", (letter_id,))
        letter = cursor.fetchone()
        if not letter:
            return jsonify({'success': False, 'message': '가정통신문을 찾을 수 없습니다.'})
        if letter['teacher_id'] != session.get('user_id'):
            return jsonify({'success': False, 'message': '본인이 작성한 통신문만 삭제할 수 있습니다.'})

        # 첨부파일 삭제
        if letter['file_path']:
            try:
                sftp_remove_file(letter['file_path'])
            except:
                pass

        # 응답 삭제 후 통신문 삭제
        cursor.execute("DELETE FROM home_letter_reply WHERE letter_id = %s", (letter_id,))
        cursor.execute("DELETE FROM home_letter WHERE id = %s", (letter_id,))
        conn.commit()

        return jsonify({'success': True, 'message': '삭제되었습니다.'})

    except Exception as e:
        print(f"가정통신문 삭제 오류: {e}")
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': '삭제 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 학부모 동의/비동의 응답
# ============================================
@letter_bp.route('/api/letter/reply', methods=['POST'])
def reply_letter():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        letter_id = sanitize_input(data.get('letter_id'), 10)
        consent_status = data.get('consent_status', '')
        reply_memo = sanitize_html(data.get('reply_memo', ''), 500)
        student_id = sanitize_input(data.get('student_id'), 50)
        parent_id = session.get('user_id')

        if not all([letter_id, consent_status, parent_id]):
            return jsonify({'success': False, 'message': '필수 정보가 누락되었습니다.'})

        if consent_status not in ('agreed', 'disagreed'):
            return jsonify({'success': False, 'message': '유효하지 않은 응답입니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        # 통신문 존재 확인
        cursor.execute("SELECT id FROM home_letter WHERE id = %s", (letter_id,))
        if not cursor.fetchone():
            return jsonify({'success': False, 'message': '가정통신문을 찾을 수 없습니다.'})

        cursor.execute("""
            INSERT INTO home_letter_reply (letter_id, parent_id, student_id, consent_status, reply_memo)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE consent_status=VALUES(consent_status), reply_memo=VALUES(reply_memo), created_at=NOW()
        """, (letter_id, parent_id, student_id or '', consent_status, reply_memo))
        conn.commit()

        status_text = '동의' if consent_status == 'agreed' else '미동의'
        return jsonify({'success': True, 'message': f'{status_text} 응답이 제출되었습니다.'})

    except Exception as e:
        print(f"가정통신문 응답 오류: {e}")
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': '응답 제출 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 동의현황 (교사용)
# ============================================
@letter_bp.route('/api/letter/consent-status', methods=['GET'])
def get_consent_status():
    conn = None
    cursor = None
    try:
        letter_id = sanitize_input(request.args.get('id'), 10)
        if not letter_id:
            return jsonify({'success': False, 'message': 'ID가 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        # 통신문 정보
        cursor.execute("SELECT school_id, class_grade, class_no FROM home_letter WHERE id = %s", (letter_id,))
        letter = cursor.fetchone()
        if not letter:
            return jsonify({'success': False, 'message': '가정통신문을 찾을 수 없습니다.'})

        # 반 전체 학생
        cursor.execute("""
            SELECT sa.member_id, m.member_name, sa.class_num
            FROM stu_all sa JOIN member m ON sa.member_id = m.member_id
            WHERE sa.school_id = %s AND sa.class_grade = %s AND sa.class_no = %s
            ORDER BY CAST(sa.class_num AS UNSIGNED)
        """, (letter['school_id'], letter['class_grade'], letter['class_no']))
        students = cursor.fetchall()

        # 응답 목록
        cursor.execute("""
            SELECT parent_id, student_id, consent_status, reply_memo,
                   created_at
            FROM home_letter_reply WHERE letter_id = %s
        """, (letter_id,))
        replies = {r['parent_id']: r for r in cursor.fetchall()}

        # 학부모 정보 매핑
        cursor.execute("""
            SELECT fa.member_id AS parent_id, m.member_name AS parent_name,
                   fa.child_name, fa.class_grade, fa.class_no
            FROM fm_all fa JOIN member m ON fa.member_id = m.member_id
            WHERE fa.school_id = %s AND fa.class_grade = %s AND fa.class_no = %s
        """, (letter['school_id'], letter['class_grade'], letter['class_no']))
        parents_map = {}
        for p in cursor.fetchall():
            parents_map[p['child_name']] = {
                'parent_id': p['parent_id'],
                'parent_name': p['parent_name']
            }

        result = []
        agreed_count = 0
        disagreed_count = 0
        no_reply_count = 0

        for stu in students:
            parent_info = parents_map.get(stu['member_name'], {})
            parent_id = parent_info.get('parent_id', '')
            reply = replies.get(parent_id)

            status = 'no_reply'
            if reply:
                status = reply['consent_status']
                if status == 'agreed':
                    agreed_count += 1
                else:
                    disagreed_count += 1
            else:
                no_reply_count += 1

            result.append({
                'student_name': stu['member_name'],
                'class_num': stu.get('class_num', ''),
                'parent_name': parent_info.get('parent_name', '-'),
                'consent_status': status,
                'reply_memo': reply['reply_memo'] if reply else '',
                'replied_at': reply['created_at'].strftime('%Y-%m-%d %H:%M') if reply and reply['created_at'] else ''
            })

        return jsonify({
            'success': True,
            'consent_list': result,
            'summary': {
                'total': len(students),
                'agreed': agreed_count,
                'disagreed': disagreed_count,
                'no_reply': no_reply_count
            }
        })

    except Exception as e:
        print(f"동의현황 조회 오류: {e}")
        return jsonify({'success': False, 'message': '조회 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 첨부파일 다운로드
# ============================================
@letter_bp.route('/api/letter/download', methods=['GET'])
def download_letter_file():
    try:
        letter_id = sanitize_input(request.args.get('id'), 10)
        if not letter_id:
            return jsonify({'success': False, 'message': 'ID가 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()
        cursor.execute("SELECT file_path, file_name FROM home_letter WHERE id = %s", (letter_id,))
        letter = cursor.fetchone()
        cursor.close()
        conn.close()

        if not letter or not letter['file_path']:
            return jsonify({'success': False, 'message': '첨부파일이 없습니다.'})

        file_data = sftp_download_file(letter['file_path'])
        if not file_data:
            return jsonify({'success': False, 'message': '파일을 찾을 수 없습니다.'})

        response = make_response(file_data)
        response.headers['Content-Type'] = 'application/octet-stream'
        response.headers['Content-Disposition'] = f'attachment; filename="{letter["file_name"]}"'
        return response

    except Exception as e:
        print(f"파일 다운로드 오류: {e}")
        return jsonify({'success': False, 'message': '다운로드 중 오류가 발생했습니다.'})


# ============================================
# 동의현황 CSV 내보내기
# ============================================
@letter_bp.route('/api/letter/export', methods=['GET'])
def export_consent_csv():
    try:
        letter_id = sanitize_input(request.args.get('id'), 10)
        if not letter_id:
            return jsonify({'success': False, 'message': 'ID가 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        cursor.execute("SELECT school_id, class_grade, class_no, title FROM home_letter WHERE id = %s", (letter_id,))
        letter = cursor.fetchone()
        if not letter:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'message': '가정통신문을 찾을 수 없습니다.'})

        cursor.execute("""
            SELECT sa.member_id, m.member_name, sa.class_num
            FROM stu_all sa JOIN member m ON sa.member_id = m.member_id
            WHERE sa.school_id = %s AND sa.class_grade = %s AND sa.class_no = %s
            ORDER BY CAST(sa.class_num AS UNSIGNED)
        """, (letter['school_id'], letter['class_grade'], letter['class_no']))
        students = cursor.fetchall()

        cursor.execute("SELECT parent_id, consent_status, reply_memo, created_at FROM home_letter_reply WHERE letter_id = %s", (letter_id,))
        replies = {r['parent_id']: r for r in cursor.fetchall()}

        cursor.execute("""
            SELECT fa.member_id AS parent_id, fa.child_name
            FROM fm_all fa
            WHERE fa.school_id = %s AND fa.class_grade = %s AND fa.class_no = %s
        """, (letter['school_id'], letter['class_grade'], letter['class_no']))
        parents_map = {p['child_name']: p['parent_id'] for p in cursor.fetchall()}

        cursor.close()
        conn.close()

        output = io.StringIO()
        output.write('\ufeff')  # BOM for Excel
        writer = csv.writer(output)
        writer.writerow(['번호', '학생명', '동의여부', '비고', '응답일시'])

        status_names = {'agreed': '동의', 'disagreed': '미동의', 'no_reply': '미응답'}

        for stu in students:
            parent_id = parents_map.get(stu['member_name'], '')
            reply = replies.get(parent_id)
            status = reply['consent_status'] if reply else 'no_reply'
            writer.writerow([
                stu.get('class_num', ''),
                stu['member_name'],
                status_names.get(status, '미응답'),
                reply['reply_memo'] if reply else '',
                reply['created_at'].strftime('%Y-%m-%d %H:%M') if reply and reply['created_at'] else ''
            ])

        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv; charset=utf-8'
        safe_title = letter['title'][:30].replace('"', '')
        from urllib.parse import quote
        encoded_name = quote(f'{safe_title}_동의현황.csv')
        response.headers['Content-Disposition'] = f"attachment; filename*=UTF-8''{encoded_name}"
        return response

    except Exception as e:
        print(f"CSV 내보내기 오류: {e}")
        return jsonify({'success': False, 'message': '내보내기 중 오류가 발생했습니다.'})
