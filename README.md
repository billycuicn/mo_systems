# 中证1000 30分钟缠论分析系统 MVP

本项目是一个本地网页系统，用于拉取中证1000指数 30 分钟 K 线，生成候选笔，并通过人工确认后的笔继续分析线段、中枢和买卖点。

## 启动

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

打开浏览器访问：

```text
http://127.0.0.1:8000
```

## 第一版功能

- 从新浪接口拉取中证1000指数 30 分钟 K 线。
- 自动生成候选笔。
- 在网页中确认、删除、调整、新增笔。
- 只有已确认笔参与线段、中枢、买卖点分析。
- 使用 SQLite 保存 K 线、笔和分析结果。

## 测试

```bash
python3 -m unittest
```

