# 干净发行包

## 生成前

先完成代码测试和真实在线验收，然后执行：

```bash
python -m ruff check src tests scripts
python -m pytest -q
python scripts/offline_self_check.py --require-runtime
git status
```

## 生成

```bash
python scripts/build_release.py
```

默认生成：

```text
dist/EnterpriseConceptRadar-0.1.0.zip
```

## 密钥保护

发行脚本不依赖人工删除密钥，而是强制执行：

1. `.env` 和 `.env.*` 不进入文件列表；
2. 读取当前电脑 `.env` 中名称包含 `API_KEY`、`TOKEN`、`PASSWORD` 或 `SECRET` 的非空值；
3. 扫描全部待打包文本；
4. 发现任何本机秘密值副本时拒绝构建；
5. ZIP 生成后再次扫描；
6. 安全复检失败时删除不合格 ZIP。

错误示例：

```text
安全检查失败：发现本机秘密值被复制到待打包文件。
README.md：LLM_API_KEY
```

错误信息不会显示 API Key 内容。

## 自动排除

```text
.env
.env.local
.env.* 本地文件
.venv/
venv/
env/
data/runtime/
outputs 中的运行结果
build/
dist/
.git/
编辑器缓存
Python 缓存
其他 ZIP 和本地数据库
```

`.env.example` 会保留，但 API Key 必须为空。

## 清单

ZIP 内 `RELEASE_MANIFEST.json` 包含：

- 产品版本；
- 来源 Git 提交；
- 构建时间；
- 文件列表；
- 每个文件的 SHA-256；
- 已执行的安全检查。

它不包含 `.env` 内容、API Key 或其他秘密值。

## 接收方首次使用

接收方解压后运行安装脚本，使用自己的 Key：

macOS：

```bash
./setup_macos.command
```

Windows：

```bat
setup_windows.cmd
```

开发者的 `.env` 不会出现在发行包中。
