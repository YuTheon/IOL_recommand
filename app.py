from flask import Flask, render_template, jsonify, request, redirect, url_for
import sqlite3

app = Flask(__name__, 
    static_url_path='', 
    static_folder='static',
    template_folder='templates')

# Function to initialize the SQLite database (run this once or when needed)
def init_db():
    conn = sqlite3.connect('results.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_name TEXT,
            patient_age INTEGER,
            left_eye_al REAL,
            left_eye_cr REAL,
            right_eye_al REAL,
            right_eye_cr REAL,
            affected_eye TEXT,
            se_value REAL,
            answered_questions TEXT,
            result TEXT
        )
    ''')
    conn.commit()
    conn.close()

def get_db_connection():
    conn = sqlite3.connect('results.db')  
    conn.row_factory = sqlite3.Row
    return conn
# Initialize the database
init_db()

# Mock data (you can move this to a separate database if needed)
astigmatism_questions = [
    {"question": "散光是否规则?", "options": [{"text": "是", "next": None, "res": "规则"}, {"text": "否", "next": None, "res": "不规则"}]},
    {"question": "散光度数是否大于0.75D?", "options": [{"text": "是", "next": None, "res": "大于0.75D"}, {"text": "否", "next": None, "res": "小于0.75D"}]},
]

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
        { "text": "充足", "next": 4, "res": None },
        { "text": "有限", "next": 7, "res": None}
    ]
    },
    4: {
    "question": "患者的工作和生活需求？",
    "options": [
        { "text": "基本戴镜，优先远处和近处的视力，费用适中。", "next": None, "res": 0},
        { "text": "完全脱镜，视力范围全面，但价格偏高。", "next": None, "res": 1 }
    ]
    },
    5: {# 这个选项被抛弃了
    "question": "患者眼轴长短？",
    "options": [
        { "text": "短眼轴", "next": None, "res": 1},
        { "text": "正常或长眼轴", "next": None, "res": 2 }
    ]
    },
    7: {
    "question": "是否是双眼白内障或缺乏协同双眼视功能",
    "options": [
        { "text": "是（双眼白内障或没有协同视功能）", "next": 10, "res": None},
        { "text": "否（单眼白内障且有协同视功能）", "next": 8, "res": None }
    ]
    },
    8: {
    "question": "患者是单眼白内障，是否有条件脱镜？",
    "options": [
        { "text": "没有条件脱镜", "next": 11, "res": None},
        { "text": "有条件脱镜", "next": 9, "res": None }
    ]
    },
    9: {
    "question": "可以做双眼单视，但需要区分以下情况",
    "options": [
        { "text": "有脱镜愿望，但年轻时非双眼单视且文化水平有限", "next": None, "res": 3},
        { "text": "原本为双眼单视（-1.0D~-1.5D），有强烈脱镜愿望且有一定学历", "next": None, "res": 4},
        { "text": "年轻时为双眼单视，相差在-2.0D以上", "next": None, "res": 5}
    ]
    },
    10: {
    "question": "年轻时视力状况",
    "options": [
        { "text": "远视", "next": None, "res": 6},
        { "text": "正视", "next": None, "res": 7},
        { "text": "近视", "next": None, "res": 8}
    ]
    },
    11: {
    "question": "对侧眼状况",
    "options": [
        { "text": "远视", "next": None, "res": 10},
        { "text": "正视", "next": None, "res": 10},
        { "text": "近视", "next": None, "res": 10}
    ]
    },
    12: {#ques 11本来引入到这，但是手术眼的眼轴长度可以被判断，所以这个问题被抛弃
    "question": "手术眼状况",
    "options": [
        { "text": "短眼轴", "next": None, "res": 6},
        { "text": "正常眼轴", "next": None, "res": 7},
        { "text": "长眼轴", "next": None, "res": 9}
    ]
    },
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
    10:"单焦点"
}
# 在现有的代码中添加新的函数和修改submit_answer路由

def get_single_focus_suggestion(axial_length, se_value=None):
    """根据眼轴长度和SE值给出单焦点IOL建议"""
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
    else:  # > 28mm
        return "建议预留 -3.0D"

def get_multi_focus_suggestion(se_value):
    """根据SE值给出多焦点IOL建议"""
    if se_value >= 1.0:
        return "判定为远视眼，建议多焦点IOL附加度数小 或 植入EDOF IOL"
    elif se_value <= -3.0:
        return "判定为近视眼，建议多焦点IOL附加度数大"
    else:  # -3.0 < se_value < 1.0
        return "可自由选择多焦点IOL"

def get_lens_model(result_text):
    """根据问卷结果推荐具体的晶体型号"""
    
    # 多焦点晶体推荐
    if "多焦点 双焦IOL" in result_text:
        return [
            "爱尔康 SV25T0(+2.5D)",
            "爱尔康 SN6AD1(+3.0D)"
        ]
    elif "多焦点 EDOF" in result_text:
        return [
            "强生眼力健 ZXR00 (新无极)"
        ]
    elif "多焦点 三焦点IOL" in result_text:
        return [
            "爱尔康 TFNT00 (Pan-Optix)"
        ]
    
    # 单焦点晶体推荐
    if any(keyword in result_text for keyword in ["单焦点", "预留"]):
        base_models = [
            "强生眼力健 ZMB00",
            "卡尔蔡司 AT LISA 839MP",
            "卡尔蔡司 AT LISA 809M"
        ]
        # 如果有散光矫正需求
        if "散光矫正" in result_text:
            base_models.append("卡尔蔡司 AT LISA TORIC 909M")
        return base_models
    
    return ["无匹配的晶体型号推荐"]

def get_formula_recommendation(axial_length):
    """根据眼轴长度推荐公式"""
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
    else:  # axial_length > 24.5
        return {
            "formula": "Holladay 2 或 Barrett Universal II",
            "links": {
                "Holladay 2": "https://www.hic-soap.com/calc",
                "Barrett Universal II": "https://calc.apacrs.org/barrett_universal2105/"
            }
        }


@app.route('/submit_answer', methods=['POST'])
def submit_answer():
    data = request.json
    result_id = data.get("res")
    flag = data.get("flag")
    affected_eye = data.get("affected_eye")
    axial_length = data.get("axial_length")
    se_value = data.get("se_value")
    
    # Validate required data
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

# Serve the index page
@app.route('/')
def index():
    return render_template('index.html')

# API to get questions by index
@app.route('/get_question/<int:question_index>', methods=['GET'])
def get_question(question_index):
    question = questions.get(question_index, None)
    if question:
        return jsonify(question)
    return jsonify({"error": "Question not found"}), 404

# # API to submit answers (you can enhance this with more logic)
# @app.route('/submit_answer', methods=['POST'])
# def submit_answer():
#     data = request.json
#     result_id = data.get("res")
#     flag = data.get("flag")
#     result = results.get(result_id, "Result not found")
#     # Add your logic here for processing answers
#     # Example: return result based on the res value
#     if flag == 1:
#         result += ", 建议植入散光矫正晶体。"
#     return jsonify({"result": result})

# API to save results
@app.route('/save_results', methods=['POST'])
def save_results():
    data = request.json
    patient_name = data.get('patientName')
    patient_age = data.get('patientAge')
    left_eye_al = data.get('leftEyeAL')
    left_eye_cr = data.get('leftEyeCR')
    right_eye_al = data.get('rightEyeAL')
    right_eye_cr = data.get('rightEyeCR')
    affected_eye = data.get('affectedEye')
    se_value = data.get('seValue')
    answered_questions = data.get('answeredQuestions')
    result = data.get('result')

    # 验证输入
    if not patient_name or not patient_age:
        return jsonify({"success": False, "error": "患者姓名和年龄为必填项"}), 400

    # 保存到 SQLite 数据库
    try:
        conn = sqlite3.connect('results.db')
        c = conn.cursor()
        c.execute('''
            INSERT INTO results (
                patient_name, patient_age, left_eye_al, left_eye_cr,
                right_eye_al, right_eye_cr, affected_eye, se_value,
                answered_questions, result
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            patient_name, patient_age, left_eye_al, left_eye_cr,
            right_eye_al, right_eye_cr, affected_eye, se_value,
            str(answered_questions), result
        ))
        conn.commit()
        conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/show_result')
def show_result():
    conn = get_db_connection()
    # 获取所有患者数据，包含新增的眼科测量数据
    patients = conn.execute('''
        SELECT id, patient_name, patient_age, 
               left_eye_al, left_eye_cr, 
               right_eye_al, right_eye_cr,
               affected_eye, se_value, result 
        FROM results
        ORDER BY id DESC
    ''').fetchall()
    
    # 处理患者数据，计算SE值
    formatted_patients = []
    for patient in patients:
        # 计算左眼SE值
        left_se = None
        if patient['left_eye_al'] and patient['left_eye_cr']:
            left_se = 43.86 - 14.73 * (patient['left_eye_al'] / patient['left_eye_cr'])
            
        # 计算右眼SE值
        right_se = None
        if patient['right_eye_al'] and patient['right_eye_cr']:
            right_se = 43.86 - 14.73 * (patient['right_eye_al'] / patient['right_eye_cr'])
            
        formatted_patients.append({
            'id': patient['id'],
            'patient_name': patient['patient_name'],
            'patient_age': patient['patient_age'],
            'left_eye': {
                'al': patient['left_eye_al'],
                'cr': patient['left_eye_cr'],
                'se': left_se
            },
            'right_eye': {
                'al': patient['right_eye_al'],
                'cr': patient['right_eye_cr'],
                'se': right_se
            },
            'affected_eye': patient['affected_eye'],
            'se_value': patient['se_value'],
            'result': patient['result']
        })
    
    conn.close()
    return render_template('patients.html', patients=formatted_patients)

# 修改查看患者详情的路由
@app.route('/patient/<int:id>')
def patient_detail(id):
    conn = get_db_connection()
    patient = conn.execute('SELECT * FROM results WHERE id = ?', (id,)).fetchone()
    conn.close()
    
    # 格式化眼睛数据以便显示
    eye_data = {
        'left_eye': {
            'al': patient['left_eye_al'],
            'cr': patient['left_eye_cr'],
            'se': calculate_se(patient['left_eye_al'], patient['left_eye_cr']) if patient['left_eye_al'] and patient['left_eye_cr'] else None
        },
        'right_eye': {
            'al': patient['right_eye_al'],
            'cr': patient['right_eye_cr'],
            'se': calculate_se(patient['right_eye_al'], patient['right_eye_cr']) if patient['right_eye_al'] and patient['right_eye_cr'] else None
        },
        'affected_eye': patient['affected_eye']
    }
    
    return render_template('patient_detail.html', patient=patient, eye_data=eye_data)


# 辅助函数：计算SE值
def calculate_se(al, cr):
    if al and cr:
        return 43.86 - 14.73 * (al / cr)
    return None

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80, debug=True)
