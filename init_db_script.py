import sqlite3
from werkzeug.security import generate_password_hash


def init_database():
    """初始化数据库并创建所有表"""
    conn = sqlite3.connect('results.db')
    c = conn.cursor()

    print("正在初始化数据库...")

    # 创建用户表（添加新字段）
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
    print("✓ 用户表创建成功")

    # 创建结果表（添加新字段）
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
    print("✓ 结果表创建成功")

    conn.commit()

    # 检查是否已有用户
    existing_users = c.execute('SELECT COUNT(*) FROM users').fetchone()[0]

    if existing_users == 0:
        # 创建默认管理员账户
        admin_password = generate_password_hash('admin123')
        c.execute('''
            INSERT INTO users (username, password, email, full_name, role)
            VALUES (?, ?, ?, ?, ?)
        ''', ('admin', admin_password, 'admin@example.com', '系统管理员', 'admin'))

        # 创建测试医生账户
        doctor_password = generate_password_hash('doctor123')
        c.execute('''
            INSERT INTO users (username, password, email, full_name, role)
            VALUES (?, ?, ?, ?, ?)
        ''', ('doctor', doctor_password, 'doctor@example.com', '李医生', 'doctor'))

        conn.commit()
        print("\n✓ 默认账户创建成功:")
        print("  管理员账户:")
        print("    用户名: admin")
        print("    密码: admin123")
        print("  医生账户:")
        print("    用户名: doctor")
        print("    密码: doctor123")
        print("\n⚠️  请登录后立即修改默认密码！")
    else:
        print(f"\n✓ 数据库中已存在 {existing_users} 个用户")

    conn.close()
    print("\n数据库初始化完成！\n")


def upgrade_database():
    """升级现有数据库（添加新字段到旧表）"""
    conn = sqlite3.connect('results.db')
    c = conn.cursor()

    print("正在升级数据库...")

    try:
        # 检查 users 表是否需要升级
        c.execute("PRAGMA table_info(users)")
        user_columns = [column[1] for column in c.fetchall()]

        if 'role' not in user_columns:
            print("添加 role 字段到 users 表...")
            c.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'doctor'")
            print("✓ role 字段添加成功")

        if 'is_active' not in user_columns:
            print("添加 is_active 字段到 users 表...")
            c.execute("ALTER TABLE users ADD COLUMN is_active INTEGER DEFAULT 1")
            print("✓ is_active 字段添加成功")

        # 检查 results 表是否需要升级
        c.execute("PRAGMA table_info(results)")
        result_columns = [column[1] for column in c.fetchall()]

        if 'patient_phone' not in result_columns:
            print("添加 patient_phone 字段到 results 表...")
            c.execute("ALTER TABLE results ADD COLUMN patient_phone TEXT")
            print("✓ patient_phone 字段添加成功")

        if 'patient_gender' not in result_columns:
            print("添加 patient_gender 字段到 results 表...")
            c.execute("ALTER TABLE results ADD COLUMN patient_gender TEXT")
            print("✓ patient_gender 字段添加成功")

        if 'doctor_notes' not in result_columns:
            print("添加 doctor_notes 字段到 results 表...")
            c.execute("ALTER TABLE results ADD COLUMN doctor_notes TEXT")
            print("✓ doctor_notes 字段添加成功")

        if 'updated_at' not in result_columns:
            print("添加 updated_at 字段到 results 表...")
            c.execute("ALTER TABLE results ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
            print("✓ updated_at 字段添加成功")

        conn.commit()
        print("\n✓ 数据库升级完成！\n")

    except Exception as e:
        print(f"\n✗ 升级过程中出现错误: {e}\n")
        conn.rollback()
    finally:
        conn.close()


def reset_database():
    """重置数据库（删除所有数据）"""
    response = input("⚠️  警告：此操作将删除所有数据，是否继续？(yes/no): ")
    if response.lower() != 'yes':
        print("操作已取消")
        return

    conn = sqlite3.connect('results.db')
    c = conn.cursor()

    c.execute('DROP TABLE IF EXISTS results')
    c.execute('DROP TABLE IF EXISTS users')

    conn.commit()
    conn.close()

    print("✓ 数据库已重置")
    print("请运行 'python init_db_script.py init' 重新初始化\n")


def show_users():
    """显示所有用户"""
    conn = sqlite3.connect('results.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    try:
        users = c.execute('''
            SELECT id, username, email, full_name, role, is_active, created_at 
            FROM users
        ''').fetchall()

        print("\n" + "=" * 100)
        print("用户列表".center(100))
        print("=" * 100)
        print(f"{'ID':<5} {'用户名':<15} {'姓名':<15} {'邮箱':<25} {'角色':<10} {'状态':<8} {'创建时间'}")
        print("-" * 100)

        for user in users:
            role_text = "管理员" if user['role'] == 'admin' else "医生"
            status_text = "激活" if user['is_active'] else "禁用"
            print(f"{user['id']:<5} {user['username']:<15} {user['full_name'] or 'N/A':<15} "
                  f"{user['email'] or 'N/A':<25} {role_text:<10} {status_text:<8} {user['created_at'][:19]}")

        print("=" * 100 + "\n")

    except Exception as e:
        print(f"✗ 查询失败: {e}\n")
    finally:
        conn.close()


def show_stats():
    """显示系统统计信息"""
    conn = sqlite3.connect('results.db')
    c = conn.cursor()

    try:
        # 基本统计
        user_count = c.execute('SELECT COUNT(*) FROM users').fetchone()[0]
        active_users = c.execute('SELECT COUNT(*) FROM users WHERE is_active = 1').fetchone()[0]
        admin_count = c.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'").fetchone()[0]
        patient_count = c.execute('SELECT COUNT(*) FROM results').fetchone()[0]

        print("\n" + "=" * 60)
        print("系统统计信息".center(60))
        print("=" * 60)
        print(f"总用户数:       {user_count}")
        print(f"  - 激活用户:   {active_users}")
        print(f"  - 管理员:     {admin_count}")
        print(f"  - 医生:       {user_count - admin_count}")
        print(f"患者记录数:     {patient_count}")
        print("-" * 60)

        # 每个用户的患者数量
        user_stats = c.execute('''
            SELECT u.username, u.full_name, u.role, COUNT(r.id) as patient_count
            FROM users u
            LEFT JOIN results r ON u.id = r.user_id
            GROUP BY u.id
            ORDER BY patient_count DESC
        ''').fetchall()

        print("\n用户活跃度:")
        print(f"{'用户名':<15} {'姓名':<15} {'角色':<10} {'患者数'}")
        print("-" * 60)
        for username, full_name, role, count in user_stats:
            role_text = "管理员" if role == 'admin' else "医生"
            display_name = full_name or username
            print(f"{username:<15} {display_name:<15} {role_text:<10} {count}")

        print("=" * 60 + "\n")

    except Exception as e:
        print(f"✗ 统计失败: {e}\n")
    finally:
        conn.close()


def show_tables():
    """显示数据库表结构"""
    conn = sqlite3.connect('results.db')
    c = conn.cursor()

    try:
        print("\n" + "=" * 80)
        print("数据库表结构".center(80))
        print("=" * 80)

        # Users 表
        print("\n【users 表】")
        c.execute("PRAGMA table_info(users)")
        print(f"{'列名':<20} {'类型':<15} {'非空':<8} {'默认值':<20}")
        print("-" * 80)
        for col in c.fetchall():
            not_null = "是" if col[3] else "否"
            default = col[4] if col[4] else "N/A"
            print(f"{col[1]:<20} {col[2]:<15} {not_null:<8} {str(default):<20}")

        # Results 表
        print("\n【results 表】")
        c.execute("PRAGMA table_info(results)")
        print(f"{'列名':<20} {'类型':<15} {'非空':<8} {'默认值':<20}")
        print("-" * 80)
        for col in c.fetchall():
            not_null = "是" if col[3] else "否"
            default = col[4] if col[4] else "N/A"
            print(f"{col[1]:<20} {col[2]:<15} {not_null:<8} {str(default):<20}")

        print("=" * 80 + "\n")

    except Exception as e:
        print(f"✗ 查询失败: {e}\n")
    finally:
        conn.close()


def create_test_data():
    """创建测试数据"""
    response = input("是否创建测试数据？(yes/no): ")
    if response.lower() != 'yes':
        print("操作已取消")
        return

    conn = sqlite3.connect('results.db')
    c = conn.cursor()

    try:
        # 获取医生用户ID
        doctor = c.execute("SELECT id FROM users WHERE role = 'doctor' LIMIT 1").fetchone()

        if not doctor:
            print("✗ 未找到医生用户，请先创建用户")
            return

        doctor_id = doctor[0]

        # 创建测试患者
        test_patients = [
            ('张三', 65, '13800138001', 'male', 23.5, 7.8, 23.6, 7.85, 'left', -2.5),
            ('李四', 72, '13800138002', 'female', 24.2, 7.7, 24.1, 7.72, 'right', -3.2),
            ('王五', 58, None, 'male', 22.8, 7.9, 22.9, 7.88, 'left', -1.8),
        ]

        for patient in test_patients:
            c.execute('''
                INSERT INTO results (
                    user_id, patient_name, patient_age, patient_phone, patient_gender,
                    left_eye_al, left_eye_cr, right_eye_al, right_eye_cr,
                    affected_eye, se_value, answered_questions, result
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                doctor_id, patient[0], patient[1], patient[2], patient[3],
                patient[4], patient[5], patient[6], patient[7],
                patient[8], patient[9],
                '[{"question": "是否有脱镜需求？", "answer": "是"}]',
                '单焦点 建议预留 -0.5D'
            ))

        conn.commit()
        print(f"\n✓ 成功创建 {len(test_patients)} 条测试患者记录\n")

    except Exception as e:
        print(f"✗ 创建失败: {e}\n")
        conn.rollback()
    finally:
        conn.close()


def main():
    """主函数"""
    import sys

    print("\n" + "=" * 60)
    print("IOL Assistant - 数据库管理工具".center(60))
    print("=" * 60 + "\n")

    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == 'init':
            init_database()
        elif command == 'upgrade':
            upgrade_database()
        elif command == 'reset':
            reset_database()
        elif command == 'users':
            show_users()
        elif command == 'stats':
            show_stats()
        elif command == 'tables':
            show_tables()
        elif command == 'testdata':
            create_test_data()
        else:
            print(f"未知命令: {command}\n")
            print_help()
    else:
        # 默认执行初始化
        init_database()


def print_help():
    """打印帮助信息"""
    print("可用命令:")
    print("  python init_db_script.py init      - 初始化数据库（首次使用）")
    print("  python init_db_script.py upgrade   - 升级现有数据库（添加新字段）")
    print("  python init_db_script.py reset     - 重置数据库（删除所有数据）")
    print("  python init_db_script.py users     - 查看用户列表")
    print("  python init_db_script.py stats     - 查看系统统计")
    print("  python init_db_script.py tables    - 查看表结构")
    print("  python init_db_script.py testdata  - 创建测试数据")
    print()


if __name__ == '__main__':
    main()