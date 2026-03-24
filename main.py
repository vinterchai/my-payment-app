import streamlit as st
import datetime
import pandas as pd
import firebase_admin
from firebase_admin import credentials, firestore
import json

# ==========================================
# 🌟 1. 连网与初始化 (从云端保险柜读取金钥匙)
# ==========================================
if not firebase_admin._apps:
    # 魔法：去云端保险柜里找一个叫 "FIREBASE_KEY" 的秘密文件
    key_dict = json.loads(st.secrets["FIREBASE_KEY"])
    cred = credentials.Certificate(key_dict)
    firebase_admin.initialize_app(cred)
db = firestore.client()

# ...(后面的代码保持不变，不用动)...

# 💡 魔法：如果云端还没有任何用户，自动建一个“老板账号”方便你第一次登录
users_ref = db.collection("users").limit(1).get()
if len(users_ref) == 0:
    db.collection("users").document("admin").set({
        "password": "123",
        "role": "管理员"
    })

# ==========================================
# 🌟 2. 门卫大爷：检查是否有“通行证” (Session State)
# ==========================================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.role = ""

# ==========================================
# 🌟 3. 防盗门：登录界面
# ==========================================
if not st.session_state.logged_in:
    # 这里是门外的景象
    st.title("🔒 欢迎登录：工程款项记录系统")
    pip install streamlit
    # 画一个登录框
    with st.form("login_form"):
        username = st.text_input("账号")
        password = st.text_input("密码", type="password")
        submitted = st.form_submit_button("开门进入")
        
        if submitted:
            # 拿着输入的账号密码，去云端的 "users" 档案柜核对
            user_doc = db.collection("users").document(username).get()
            if user_doc.exists:
                user_data = user_doc.to_dict()
                if user_data["password"] == password:
                    # 密码正确，发通行证！
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.session_state.role = user_data["role"]
                    st.success("验证通过！正在进入...")
                    st.rerun() # 瞬间刷新网页，带着通行证进入大厅
                else:
                    st.error("❌ 密码错误！")
            else:
                st.error("❌ 账号不存在，请联系管理员开通！")
                
    # 🛑 核心绝招：如果没有登录，程序就在这里强行停下，绝不执行后面的代码！
    st.stop()


# ==========================================
# 🌟 4. 成功进入后的主界面 (只有拿了通行证才会运行到这里)
# ==========================================
# 侧边栏展示当前登录的员工信息
st.sidebar.success(f"👤 当前登录: {st.session_state.username}")
st.sidebar.caption(f"🔑 身份权限: {st.session_state.role}")
if st.sidebar.button("退出登录"):
    st.session_state.logged_in = False
    st.rerun()

st.sidebar.divider() # 画一条分割线

# --- 菜单与权限过滤系统 ---
all_menus = ["📝 录入新账单", "📊 查阅数据与图表", "⚙️ 管理员面板"]
allowed_menus = []

# 根据身份，没收不该看的菜单
if st.session_state.role == "管理员":
    allowed_menus = all_menus # 老板全都有
elif st.session_state.role == "第二种：查阅和修改":
    allowed_menus = ["📊 查阅数据与图表"] # 目前先给查阅，下一步我们再加“修改”功能
elif st.session_state.role == "第三种：仅录入和查阅":
    allowed_menus = ["📝 录入新账单", "📊 查阅数据与图表"]

menu = st.sidebar.radio("请选择功能：", allowed_menus)

st.title("👷‍♂️ 工程款项记录系统")

# 🔴 模块 1：录入账单 (写入云端的 payments 集合)
if menu == "📝 录入新账单":
    st.subheader("新增收款记录")
    project_name = st.text_input("项目名称")
    worker_name = st.text_input("工人姓名")
    amount = st.number_input("收款金额 (元)", min_value=0.0, step=100.0)
    record_date = st.date_input("收款日期", datetime.date.today())
    
    if st.button("提交记录"):
        data_package = {
            "project_name": project_name,
            "worker_name": worker_name,
            "amount": amount,
            "date": str(record_date),
            "recorded_by": st.session_state.username, # 记录是谁填的这笔账
            "timestamp": firestore.SERVER_TIMESTAMP
        }
        db.collection("payments").add(data_package)
        st.success(f"✅ 成功写入云端！记录员：{st.session_state.username}")

# 🔴 模块 2：查阅数据与图表 (从云端拉取)
elif menu == "📊 查阅数据与图表":
    st.subheader("数据总览")
    docs = db.collection("payments").stream()
    records = [doc.to_dict() for doc in docs]
        
    if records:
        df = pd.DataFrame(records)
        # 如果有 recorded_by 这个字段，就显示出来，没有就留空
        if "recorded_by" not in df.columns:
            df["recorded_by"] = "未知"
            
        df = df[["date", "project_name", "worker_name", "amount", "recorded_by"]]
        df.columns = ["收款日期", "项目名称", "工人姓名", "金额(元)", "录入人"]
        st.dataframe(df, use_container_width=True)
        
        st.write("📈 每日总收款走势图")
        chart_data = df.groupby("收款日期")["金额(元)"].sum()
        st.bar_chart(chart_data)
    else:
        st.info("📭 目前还没有账单数据。")

# 🔴 模块 3：管理员面板 (真正把新员工写入云端！)
elif menu == "⚙️ 管理员面板":
    st.subheader("⚙️ 权限管理 (添加新员工账号)")
    
    new_user = st.text_input("新员工账号名")
    new_pwd = st.text_input("设置初始密码", type="password")
    new_role = st.selectbox("分配权限", ["第二种：查阅和修改", "第三种：仅录入和查阅", "管理员"])
    
    if st.button("创建/修改该账号"):
        if new_user and new_pwd:
            # 把新账号发给云端的 users 档案柜
            db.collection("users").document(new_user).set({
                "password": new_pwd,
                "role": new_role
            })
            st.success(f"✅ 成功！已将账号【{new_user}】设置为【{new_role}】！该员工现在可以登录了。")
        else:
            st.warning("⚠️ 账号和密码不能为空！")