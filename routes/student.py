@student_bp.route('/api/request-device-change', methods=['POST'])
def request_device_change():
    data = request.get_json() or {}
    student_id = data.get('student_id', '').strip()
    student_name = data.get('student_name', '').strip()
    new_device_id = data.get('new_device_id', '').strip()
    reason = data.get('reason', 'Đổi thiết bị do sự cố kỹ thuật')

    if not student_id:
        return jsonify({"status": "error", "message": "Thiếu mã số sinh viên"}), 400

    conn = get_db_connection()
    try:
        # Hủy các yêu cầu pending cũ nếu có
        conn.execute(
            "UPDATE device_change_requests SET status = 'cancelled' WHERE student_id = ? AND status = 'pending'",
            (student_id,)
        )
        # Thêm yêu cầu mới với thời gian chuẩn
        conn.execute("""
            INSERT INTO device_change_requests (student_id, student_name, new_device_id, reason, status, created_at)
            VALUES (?, ?, ?, ?, 'pending', datetime('now', 'localtime'))
        """, (student_id, student_name, new_device_id, reason))
        
        conn.commit()
        return jsonify({"status": "success", "message": "Đã gửi yêu cầu đổi máy thành công"})
    except Exception as e:
        conn.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()