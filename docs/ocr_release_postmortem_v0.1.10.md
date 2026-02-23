# OCR 上线复盘（v0.1.7 ~ v0.1.10）

日期：2026-02-16  
范围：Windows Release OCR 初始化与模型加载稳定性

## 1. 背景

本次上线目标是让 Windows 安装包中的 OCR 在用户机器上稳定可用，避免反复出现首次 OCR 失败、升级后仍失败、需要手动清缓存等问题。

用户侧先后反馈两类核心报错：

1. `OCR failed: A dependency error occurred during pipeline creation...`
2. `OCR failed: Model name mismatch，please input the correct model dir.`

## 2. 版本时间线

| 版本 | Commit | 变更主题 |
|---|---|---|
| v0.1.7 | `ae3d99b` | 修复 packaged build 中 OCR 依赖检查误判与打包缺件 |
| v0.1.8 | `04bd577` | 强化模型目录选择，避免跨缓存根目录混配 |
| v0.1.9 | `da77387` | 处理本地 `model_dir` 加载时的模型名不一致回退 |
| v0.1.10 | `e2fd7c9` | 定位 mismatch 精确触发点并补齐 `model_name` 读取与预取一致性 |

## 3. 问题 1：Pipeline dependency error

### 3.1 现象

OCR 初始化阶段失败，外层只看到统一报错：

`A dependency error occurred during pipeline creation`

### 3.2 根因判断

1. `PaddleOCR -> PaddleX` 在 pipeline 创建时会进行依赖检查。
2. 该依赖检查部分依赖 `importlib.metadata`（`dist-info` 元数据）。
3. PyInstaller 打包环境中可能出现“模块已打进包，但 metadata 不完整”，导致误判为缺依赖。
4. 旧打包脚本对 OCR 额外依赖收集不足，放大了误判/缺件概率。

### 3.3 解决方案

1. 运行时容错（`backend/ocr/engine.py`）
   - 对 dependency error 做特定分支处理。
   - 当判断为 metadata 误判时，改用“模块可导入”探测并重试一次。
   - 如果是真缺依赖，抛出更明确的缺失依赖信息。
2. 打包修复（`scripts/build_windows.ps1`）
   - 增加 `--recursive-copy-metadata paddleocr/paddlex`。
   - 补齐 OCR 关键依赖的 `--collect-all`。

## 4. 问题 2：Model name mismatch

### 4.1 现象

OCR 初始化失败并报：

`Model name mismatch，please input the correct model dir.`

### 4.2 精确触发点

在 `paddlex/inference/models/__init__.py` 中存在断言：

`model_name == config["Global"]["model_name"]`

不一致就抛出上述错误。

### 4.3 根因拆解

1. **缓存混用**  
   发布包模型目录与用户历史缓存目录可能被同时参与选择，det/rec 存在跨 root 混配风险。
2. **本地目录加载与模型名校验冲突**  
   传入了 `*_model_dir` 但对应 `model_name` 与目录内模型元信息不一致时会触发断言。
3. **预取阶段模型来源不一致**  
   预取脚本最初未强约束模型根目录，可能从用户已有缓存“借用”模型，导致发布包与目标模型集合不一致。
4. **模型名读取口径不完整**  
   初版只尝试 `config.json`；部分模型（例如 mobile）实际以 `inference.yml` 提供 `Global.model_name`。

### 4.4 解决方案

1. 模型根目录隔离（`v0.1.8`）
   - 有 `DEEPREAD_OCR_MODEL_DIR` 时，仅使用该 root 做模型选择，隔离用户缓存。
2. 成对选择策略（`v0.1.8`）
   - det/rec 必须在同一 root 下成对成立才采用，避免跨目录拼接。
3. mismatch 自动恢复（`v0.1.8`）
   - 识别 `Model name mismatch` 后清理陈旧缓存并重试。
4. 本地加载回退（`v0.1.9`）
   - 本地 `model_dir` 分支失败且命中 mismatch 时，自动回退到按 `model_name` 加载。
5. 真实模型名读取（`v0.1.10`）
   - 从 `config.json` / `inference.yml` 读取 `Global.model_name`，以真实值传给 PaddleOCR。
6. 预取一致性修复（`v0.1.10`）
   - 在 `scripts/prefetch_ocr_models.py` 明确设置 `DEEPREAD_OCR_MODEL_DIR=output_dir`，确保预取来源与打包使用路径一致。

## 5. 验证过程

1. 自动化测试
   - 每轮修复后执行 `uv run pytest -q`，当前保持 `41 passed`。
2. 失效场景模拟
   - 模拟 metadata 丢失，验证 dependency probe fallback 生效。
   - 构造 det/rec 错配目录，复现并定位 mismatch 断言链路。
3. 运行时验证
   - 清理 Windows 用户缓存后复测，排除历史污染干扰。
   - 推送 tag 触发 release 构建，按安装包路径复测。

## 6. 本次上线思考

1. **打包问题不能只靠“本地开发环境可跑”判断**  
   对 OCR 这类依赖重、动态加载多的模块，必须将“冻结后运行时”视为独立环境。
2. **模型选择逻辑要“确定性优先”**  
   与其“尽量复用任意可见缓存”，更稳妥的是“强约束唯一来源 + 明确回退策略”。
3. **错误信息必须能指向行动**  
   仅返回统一错误会导致反复试错。后续统一保持“可诊断、可执行”的报错结构。
4. **预取脚本与运行时逻辑要同构**  
   预取阶段如果和运行时不是同一选择规则，发布后就会出现“构建通过但用户失败”的偏差。

## 7. 后续改进项（建议）

1. 在应用日志中打印一次 OCR 启动诊断快照：
   - 实际 `det/rec model_dir`
   - 实际 `det/rec model_name`
   - `PADDLE_PDX_CACHE_HOME` / `DEEPREAD_OCR_MODEL_DIR`
2. 在 CI 增加“冻结包端到端 OCR 冒烟测试”（独立 Windows runner，空缓存用户）。
3. 发布前增加 `MODEL_MANIFEST` 完整性校验，安装后首次启动做轻量校验。
4. 为常见 OCR 异常维护错误码映射，前端 toast 给出可执行建议。

## 8. 涉及关键文件

1. `backend/ocr/engine.py`
2. `scripts/build_windows.ps1`
3. `scripts/prefetch_ocr_models.py`

