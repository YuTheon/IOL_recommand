from flask import Flask, render_template, jsonify, request, redirect, url_for, session
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import secrets
from datetime import datetime
import json  # 确保在文件顶部导入


app = Flask(__name__,
            static_url_path='',
            static_folder='static',
            template_folder='templates')

app.secret_key = secrets.token_hex(16)


def init_db():
    conn = sqlite3.connect('results.db')
    c = conn.cursor()

    # 创建用户表（添加角色字段）
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            email TEXT,
            full_name TEXT,
            role TEXT DEFAULT 'doctor',
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 创建结果表
    c.execute('''
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            patient_name TEXT,
            patient_age INTEGER,
            patient_phone TEXT,
            patient_gender TEXT,
            left_eye_al REAL,
            left_eye_cr REAL,
            right_eye_al REAL,
            right_eye_cr REAL,
            affected_eye TEXT,
            se_value REAL,
            answered_questions TEXT,
            result TEXT,
            doctor_notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    conn.commit()
    conn.close()


def get_db_connection():
    conn = sqlite3.connect('results.db')
    conn.row_factory = sqlite3.Row
    return conn


init_db()


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)

    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'admin':
            return jsonify({"success": False, "message": "需要管理员权限"}), 403
        return f(*args, **kwargs)

    return decorated_function


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.json
        username = data.get('username')
        password = data.get('password')

        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ? AND is_active = 1',
                            (username,)).fetchone()
        conn.close()

        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['full_name'] = user['full_name']
            session['role'] = user['role']
            return jsonify({"success": True, "message": "登录成功"})
        else:
            return jsonify({"success": False, "message": "用户名或密码错误"}), 401

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = request.json
        username = data.get('username')
        password = data.get('password')
        email = data.get('email')
        full_name = data.get('full_name')
        role = data.get('role', 'doctor')

        if not username or not password:
            return jsonify({"success": False, "message": "用户名和密码不能为空"}), 400

        if len(password) < 6:
            return jsonify({"success": False, "message": "密码长度至少为6位"}), 400

        conn = get_db_connection()
        existing_user = conn.execute('SELECT * FROM users WHERE username = ?',
                                     (username,)).fetchone()
        if existing_user:
            conn.close()
            return jsonify({"success": False, "message": "用户名已存在"}), 400

        hashed_password = generate_password_hash(password)
        try:
            conn.execute('''
                INSERT INTO users (username, password, email, full_name, role)
                VALUES (?, ?, ?, ?, ?)
            ''', (username, hashed_password, email, full_name, role))
            conn.commit()
            conn.close()
            return jsonify({"success": True, "message": "注册成功"})
        except Exception as e:
            conn.close()
            return jsonify({"success": False, "message": str(e)}), 500

    return render_template('register.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# 管理员路由
@app.route('/admin/users', methods=['GET'])
@login_required
@admin_required
def admin_users():
    conn = get_db_connection()
    users = conn.execute('''
        SELECT u.*, COUNT(r.id) as patient_count
        FROM users u
        LEFT JOIN results r ON u.id = r.user_id
        GROUP BY u.id
        ORDER BY u.created_at DESC
    ''').fetchall()
    conn.close()

    return render_template('admin_users.html', users=users,
                           username=session.get('full_name') or session.get('username'))


@app.route('/admin/all-patients', methods=['GET'])
@login_required
@admin_required
def admin_all_patients():
    conn = get_db_connection()
    patients = conn.execute('''
        SELECT r.*, u.username, u.full_name as doctor_name
        FROM results r
        JOIN users u ON r.user_id = u.id
        ORDER BY r.created_at DESC
    ''').fetchall()

    formatted_patients = format_patient_list(patients, include_doctor=True)
    conn.close()

    return render_template('admin_patients.html', patients=formatted_patients,
                           username=session.get('full_name') or session.get('username'))


@app.route('/admin/toggle-user/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def toggle_user_status(user_id):
    conn = get_db_connection()
    user = conn.execute('SELECT is_active FROM users WHERE id = ?', (user_id,)).fetchone()

    if user:
        new_status = 0 if user['is_active'] else 1
        conn.execute('UPDATE users SET is_active = ? WHERE id = ?', (new_status, user_id))
        conn.commit()
        conn.close()
        return jsonify({"success": True})

    conn.close()
    return jsonify({"success": False, "message": "用户不存在"}), 404


@app.route('/admin/toggle-admin/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def toggle_admin_role(user_id):
    if user_id == session['user_id']:
        return jsonify({"success": False, "message": "不能修改自己的权限"}), 400

    conn = get_db_connection()
    user = conn.execute('SELECT role FROM users WHERE id = ?', (user_id,)).fetchone()

    if user:
        new_role = 'doctor' if user['role'] == 'admin' else 'admin'
        conn.execute('UPDATE users SET role = ? WHERE id = ?', (new_role, user_id))
        conn.commit()
        conn.close()
        return jsonify({"success": True})

    conn.close()
    return jsonify({"success": False, "message": "用户不存在"}), 404


# 决策树相关
questions = {
    0: {
        "question": "是否有脱镜需求？",
        "options": [
            {"text": "是", "next": 1, "res": None},
            {"text": "否", "next": 7, "res": None}
        ]
    },
    1: {
        "question": "眼功能是否正常？（包括角膜正常，黄斑正常）",
        "options": [
            {"text": "是", "next": 3, "res": None},
            {"text": "否", "next": 7, "res": None}
        ]
    },
    3: {
        "question": "预期费用？",
        "options": [
            {"text": "充足", "next": 4, "res": None},
            {"text": "有限", "next": 7, "res": None}
        ]
    },
    4: {
        "question": "患者的工作和生活需求？",
        "options": [
            {"text": "基本戴镜，优先远处和近处的视力，费用适中。", "next": None, "res": 0},
            {"text": "完全脱镜，视力范围全面，但价格昂贵。", "next": None, "res": 1}
        ]
    },
    7: {
        "question": "是否是双眼白内障或缺乏双同双眼视功能",
        "options": [
            {"text": "是（双眼白内障或没有双同视功能）", "next": 10, "res": None},
            {"text": "否（单眼白内障且有双同视功能）", "next": 8, "res": None}
        ]
    },
    8: {
        "question": "患者是单眼白内障，是否有条件脱镜？",
        "options": [
            {"text": "没有条件脱镜", "next": 11, "res": None},
            {"text": "有条件脱镜", "next": 9, "res": None}
        ]
    },
    9: {
        "question": "可以做双眼单视，但需要区分以下情况",
        "options": [
            {"text": "有脱镜愿望，但年轻时非双眼单视且文化水平有限", "next": None, "res": 3},
            {"text": "原本为双眼单视（-1.0D~-1.5D），有强烈脱镜愿望且有一定学历", "next": None, "res": 4},
            {"text": "年轻时为双眼单视，相差在-2.0D以上", "next": None, "res": 5}
        ]
    },
    10: {
        "question": "年轻时视力状况",
        "options": [
            {"text": "远视", "next": None, "res": 6},
            {"text": "正视", "next": None, "res": 7},
            {"text": "近视", "next": None, "res": 8}
        ]
    },
    11: {
        "question": "对侧眼状况",
        "options": [
            {"text": "远视", "next": None, "res": 10},
            {"text": "正视", "next": None, "res": 10},
            {"text": "近视", "next": None, "res": 10}
        ]
    }
}

results = {
    0: "多焦点 双焦IOL",
    1: "多焦点",
    2: "多焦点 三焦点IOL",
    3: "单焦点 微单视",
    4: "单焦点 中单视",
    5: "单焦点 全单视",
    6: "单焦点 ",
    7: "单焦点 ",
    8: "单焦点 ",
    9: "单焦点 ",
    10: "单焦点"
}


def get_single_focus_suggestion(axial_length, se_value=None):
    if axial_length <= 22.5:
        return "建议预留 0 ~ +0.5D"
    elif 22.5 < axial_length <= 24:
        return "建议预留 -0.5D"
    elif 24 < axial_length <= 26:
        if se_value is not None:
            if -3.0 <= se_value <= 0.5:
                return "建议预留 -0.5D ~ 0D"
            elif -6.0 <= se_value < -3.0:
                return "建议预留 -1.0D ~ -0.5D"
        return "需要SE值来确定具体建议"
    elif 26 < axial_length <= 27:
        return "建议预留 -1.0D"
    elif 27 < axial_length <= 28:
        return "建议预留 -2.5D ~ -2.0D"
    else:
        return "建议预留 -3.0D"


def get_multi_focus_suggestion(se_value):
    if se_value >= 1.0:
        return "判定为远视眼，建议多焦点IOL附加度数小 或 植入EDOF IOL"
    elif se_value <= -3.0:
        return "判定为近视眼，建议多焦点IOL附加度数大"
    else:
        return "可自由选择多焦点IOL"


def get_lens_model(result_text):
    if "多焦点 双焦IOL" in result_text:
        return ["爱尔康 SV25T0(+2.5D)", "爱尔康 SN6AD1(+3.0D)"]
    elif "多焦点 EDOF" in result_text:
        return ["强生眼力健 ZXR00 (新无极)"]
    elif "多焦点 三焦点IOL" in result_text:
        return ["爱尔康 TFNT00 (Pan-Optix)"]

    if any(keyword in result_text for keyword in ["单焦点", "预留"]):
        base_models = ["强生眼力健 ZMB00", "卡尔蔡司 AT LISA 839MP", "卡尔蔡司 AT LISA 809M"]
        if "散光矫正" in result_text:
            base_models.append("卡尔蔡司 AT LISA TORIC 909M")
        return base_models

    return ["无匹配的晶体型号推荐"]


def get_formula_recommendation(axial_length):
    if axial_length < 22:
        return {
            "formula": "Hoffer Q 或 Barrett Universal II",
            "links": {
                "Hoffer Q": "https://hofferqst.com/",
                "Barrett Universal II": "https://calc.apacrs.org/barrett_universal2105/"
            }
        }
    elif 22 <= axial_length <= 24.5:
        return {
            "formula": "SRK/T、Holladay 1 或 Barrett Universal II",
            "links": {
                "SRK/T": "http://eyecalc.org/srk-t/",
                "Holladay 1": "https://www.calculatorultra.com/zh/tool/holladay-1-formula-calculator.html",
                "Barrett Universal II": "https://calc.apacrs.org/barrett_universal2105/"
            }
        }
    else:
        return {
            "formula": "Holladay 2 或 Barrett Universal II",
            "links": {
                "Holladay 2": "https://www.hic-soap.com/calc",
                "Barrett Universal II": "https://calc.apacrs.org/barrett_universal2105/"
            }
        }


@app.route('/')
@login_required
def index():
    return render_template('index.html',
                           username=session.get('full_name') or session.get('username'),
                           role=session.get('role'))


@app.route('/get_question/<int:question_index>', methods=['GET'])
@login_required
def get_question(question_index):
    question = questions.get(question_index, None)
    if question:
        return jsonify(question)
    return jsonify({"error": "Question not found"}), 404


@app.route('/submit_answer', methods=['POST'])
@login_required
def submit_answer():
    data = request.json
    result_id = data.get("res")
    flag = data.get("flag")
    affected_eye = data.get("affected_eye")
    axial_length = data.get("axial_length")
    se_value = data.get("se_value")

    if not affected_eye:
        return jsonify({"error": "请选择患病眼！"}), 400

    if axial_length is None:
        return jsonify({"error": "请填写眼轴长度！"}), 400

    if se_value is None:
        return jsonify({"error": "请完整填写眼轴长度和角膜曲率半径以计算SE值！"}), 400

    try:
        axial_length = float(axial_length)
        se_value = float(se_value) if se_value is not None else None
    except (ValueError, TypeError):
        return jsonify({"error": "眼轴长度或SE值格式不正确！"}), 400

    base_result = results.get(result_id, "Result not found")

    if "单" in base_result:
        additional_suggestion = get_single_focus_suggestion(axial_length, se_value)
    elif any(keyword in base_result for keyword in ["多焦", "EDOF", "三焦"]):
        additional_suggestion = get_multi_focus_suggestion(se_value)
    else:
        additional_suggestion = ""

    final_result = f"{base_result}\n{additional_suggestion}"

    if flag == 1:
        final_result += "\n建议植入散光矫正晶体"

    recommended_models = get_lens_model(final_result)
    model_recommendations = "\n推荐晶体型号：\n" + "\n".join(f"- {model}" for model in recommended_models)

    final_result += model_recommendations

    formula_recommendation = get_formula_recommendation(axial_length)
    formula_text = f"\n推荐公式: {formula_recommendation['formula']}"
    formula_links = "\n相关链接:\n" + "\n".join(
        [f"- {name}: {url}" for name, url in formula_recommendation["links"].items()]
    )
    final_result += formula_text + formula_links

    return jsonify({"result": final_result})


@app.route('/save_results', methods=['POST'])
@login_required
def save_results():
    data = request.json
    patient_name = data.get('patientName')
    patient_age = data.get('patientAge')
    patient_phone = data.get('patientPhone', '')
    patient_gender = data.get('patientGender', '')
    left_eye_al = data.get('leftEyeAL')
    left_eye_cr = data.get('leftEyeCR')
    right_eye_al = data.get('rightEyeAL')
    right_eye_cr = data.get('rightEyeCR')
    affected_eye = data.get('affectedEye')
    se_value = data.get('seValue')
    answered_questions = data.get('answeredQuestions')
    result = data.get('result')

    if not patient_name or not patient_age:
        return jsonify({"success": False, "error": "患者姓名和年龄为必填项"}), 400

    try:
        conn = sqlite3.connect('results.db')
        c = conn.cursor()
        c.execute('''
            INSERT INTO results (
                user_id, patient_name, patient_age, patient_phone, patient_gender,
                left_eye_al, left_eye_cr, right_eye_al, right_eye_cr, 
                affected_eye, se_value, answered_questions, result
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            session['user_id'], patient_name, patient_age, patient_phone, patient_gender,
            left_eye_al, left_eye_cr, right_eye_al, right_eye_cr,
            affected_eye, se_value, str(answered_questions), result
        ))
        conn.commit()
        conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


def format_patient_list(patients, include_doctor=False):
    """格式化患者列表数据，安全处理sqlite3.Row对象"""
    formatted_patients = []

    for patient in patients:
        # 安全获取字段值
        def safe_get(row, key, default=None):
            try:
                value = row[key]
                return value if value is not None else default
            except (KeyError, IndexError, TypeError):
                return default

        # 计算左眼SE值
        left_se = None
        left_al = safe_get(patient, 'left_eye_al')
        left_cr = safe_get(patient, 'left_eye_cr')
        if left_al and left_cr:
            try:
                left_se = 43.86 - 14.73 * (float(left_al) / float(left_cr))
            except (ValueError, ZeroDivisionError):
                left_se = None

        # 计算右眼SE值
        right_se = None
        right_al = safe_get(patient, 'right_eye_al')
        right_cr = safe_get(patient, 'right_eye_cr')
        if right_al and right_cr:
            try:
                right_se = 43.86 - 14.73 * (float(right_al) / float(right_cr))
            except (ValueError, ZeroDivisionError):
                right_se = None

        # 构建患者数据
        patient_data = {
            'id': patient['id'],
            'patient_name': patient['patient_name'],
            'patient_age': patient['patient_age'],
            'patient_phone': safe_get(patient, 'patient_phone', ''),
            'patient_gender': safe_get(patient, 'patient_gender', ''),
            'left_eye': {
                'al': left_al,
                'cr': left_cr,
                'se': left_se
            },
            'right_eye': {
                'al': right_al,
                'cr': right_cr,
                'se': right_se
            },
            'affected_eye': safe_get(patient, 'affected_eye'),
            'se_value': safe_get(patient, 'se_value'),
            'result': safe_get(patient, 'result', ''),
            'created_at': safe_get(patient, 'created_at', '')
        }

        if include_doctor:
            doctor_name = safe_get(patient, 'doctor_name') or safe_get(patient, 'username', '未知医生')
            patient_data['doctor_name'] = doctor_name

        formatted_patients.append(patient_data)

    return formatted_patients

@app.route('/show_result')
@login_required
def show_result():
    conn = get_db_connection()
    patients = conn.execute('''
        SELECT * FROM results
        WHERE user_id = ?
        ORDER BY created_at DESC
    ''', (session['user_id'],)).fetchall()

    formatted_patients = format_patient_list(patients)
    conn.close()

    return render_template('patients.html', patients=formatted_patients,
                           username=session.get('full_name') or session.get('username'),
                           role=session.get('role'))




@app.route('/patient/<int:id>')
@login_required
def patient_detail(id):
    conn = get_db_connection()

    # 根据角色权限查询
    if session.get('role') == 'admin':
        patient = conn.execute('''
            SELECT r.*, u.username, u.full_name as doctor_name
            FROM results r
            JOIN users u ON r.user_id = u.id
            WHERE r.id = ?
        ''', (id,)).fetchone()
    else:
        patient = conn.execute('''
            SELECT * FROM results 
            WHERE id = ? AND user_id = ?
        ''', (id, session['user_id'])).fetchone()

    conn.close()

    if not patient:
        return redirect(url_for('show_result'))

    # 将 sqlite3.Row 转换为字典
    patient_dict = dict(patient)

    # 解析 answered_questions JSON 字符串
    if patient_dict.get('answered_questions'):
        try:
            # 处理单引号 JSON
            questions_str = patient_dict['answered_questions'].replace("'", '"')
            patient_dict['answered_questions_list'] = json.loads(questions_str)
        except (json.JSONDecodeError, AttributeError, TypeError):
            patient_dict['answered_questions_list'] = []
    else:
        patient_dict['answered_questions_list'] = []

    return render_template('patient_detail.html',
                           patient=patient_dict,
                           username=session.get('full_name') or session.get('username'),
                           role=session.get('role'))

@app.route('/patient/<int:id>/update-notes', methods=['POST'])
@login_required
def update_patient_notes(id):
    data = request.json
    notes = data.get('notes', '')

    conn = get_db_connection()

    # 检查权限
    if session.get('role') == 'admin':
        patient = conn.execute('SELECT id FROM results WHERE id = ?', (id,)).fetchone()
    else:
        patient = conn.execute('SELECT id FROM results WHERE id = ? AND user_id = ?',
                               (id, session['user_id'])).fetchone()

    if not patient:
        conn.close()
        return jsonify({"success": False, "message": "无权限或患者不存在"}), 403

    conn.execute('''
        UPDATE results 
        SET doctor_notes = ?, updated_at = CURRENT_TIMESTAMP 
        WHERE id = ?
    ''', (notes, id))
    conn.commit()
    conn.close()

    return jsonify({"success": True})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80, debug=True)