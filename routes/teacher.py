@teacher_bp.route('/api/device-change-requests', methods=['GET'])
def get_device_change_requests():
    conn = get_db_connection()
    try:
        requests = conn.execute("""
            SELECT id, student_id, student_name, new_device_id, reason, created_at
            FROM device_change_requests
            WHERE status = 'pending'
            ORDER BY id DESC
        """).fetchall()
        
        return jsonify({
            "status": "success",
            "data": [dict(r) for r in requests]
        })
    finally:
        conn.close()