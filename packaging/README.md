# Windows 打包说明

将考试系统打包为 Windows 可执行程序，教师机双击即可运行，无需安装 Python 或 Node.js。

## 教师机使用（已打包）

1. 解压 `微机教室考试系统.zip`（或运行安装程序）
2. 双击 **`ExamSystem.exe`**
3. 浏览器自动打开，学生机访问窗口中显示的 IP 地址
4. 关闭黑色命令行窗口即停止服务

**数据存储位置**：`%APPDATA%\微机教室考试系统\exam_system.db`

---

## 开发者打包步骤

### 环境要求

- Windows 10/11（64位）
- Python 3.10+
- Node.js 18+

### 一键打包

```bat
packaging\build_windows.bat
```

完成后输出：
- `dist\微机教室考试系统\ExamSystem.exe` — 可运行程序
- `release\微机教室考试系统.zip` — 分发压缩包

### 制作安装程序（可选）

1. 安装 [Inno Setup 6](https://jrsoftware.org/isinfo.php)
2. 运行：

```bat
packaging\build_installer.bat
```

生成：`release\微机教室考试系统_Setup.exe`

---

## 局域网部署

1. 教师机运行 `ExamSystem.exe`
2. 记下窗口中的 **学生机访问地址**（如 `http://192.168.1.100:8000`）
3. 确保 Windows 防火墙允许 8000 端口：
   - 控制面板 → Windows 防火墙 → 高级设置 → 入站规则 → 新建规则 → 端口 8000 TCP
4. 学生机浏览器输入上述地址即可

---

## 默认账号

| 角色 | 用户名 | 密码 |
|------|--------|------|
| 教师 | teacher | teacher123 |
| 学生 | student01 | 123456 |

---

## 常见问题

**Q: 双击 exe 闪退？**  
以管理员身份运行，或检查是否被杀毒软件拦截。

**Q: 学生机无法访问？**  
检查防火墙、确认学生机与教师机在同一局域网。

**Q: 如何备份数据？**  
复制 `%APPDATA%\微机教室考试系统\exam_system.db` 即可。

**Q: 如何更换端口？**  
设置环境变量 `EXAM_PORT=8080` 后启动（或在快捷方式属性中添加）。
