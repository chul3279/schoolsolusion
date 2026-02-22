#!/usr/bin/env python3
"""
Academy expired class cleanup - run daily via systemd timer
Deletes classes where auto_delete_at <= today, along with related enrollments and attendance.
"""
import sys
sys.path.insert(0, '/var/www/web/html')

from utils.db import get_db_connection


def cleanup_expired_classes():
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if not conn:
            print("[academy_cleanup] DB 연결 실패")
            return

        cursor = conn.cursor()

        # Find classes where auto_delete_at has passed
        cursor.execute("""
            SELECT id, academy_id, class_name, auto_delete_at
            FROM academy_class
            WHERE auto_delete_at IS NOT NULL AND auto_delete_at <= CURDATE()
        """)
        expired = cursor.fetchall()

        if not expired:
            print("[academy_cleanup] 만료된 강좌 없음")
            return

        for cls in expired:
            cls_id = cls['id']
            print(f"[academy_cleanup] 삭제: class_id={cls_id}, name={cls['class_name']}, "
                  f"academy_id={cls['academy_id']}, auto_delete_at={cls['auto_delete_at']}")

            # Delete attendance records for enrollments in this class
            cursor.execute("""
                DELETE FROM academy_attendance
                WHERE enrollment_id IN (
                    SELECT id FROM academy_enrollment WHERE class_id = %s
                )
            """, (cls_id,))

            # Delete enrollments for this class
            cursor.execute("DELETE FROM academy_enrollment WHERE class_id = %s", (cls_id,))

            # Delete the class
            cursor.execute("DELETE FROM academy_class WHERE id = %s", (cls_id,))

        conn.commit()
        print(f"[academy_cleanup] 총 {len(expired)}개 만료 강좌 삭제 완료")

    except Exception as e:
        print(f"[academy_cleanup] 오류: {e}")
        if conn:
            conn.rollback()
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


if __name__ == '__main__':
    cleanup_expired_classes()
