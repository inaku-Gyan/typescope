# 旧仓库的发布目标与 testcov 能力

本记录回答 wayfinder 票据“研究旧仓库的发布目标与 testcov 能力”。资料来源优先采用仓库配置、提交历史、GitHub Actions 定义和 PyPI 官方 JSON API；没有把旧业务实现当作重建约束。

## 发布目标

- 包名是 `typescope`，当前仓库元数据版本为 `0.0.2`，要求 Python `>=3.11`，并声明 Python 3.11、3.12、3.13 分类器。构建后端是 Hatchling（`hatchling.build`）。这些字段位于当前 `pyproject.toml`。[当前 `pyproject.toml`](https://github.com/inaku-Gyan/typescope/blob/3ad7715cffc8a43330e3f1514360b378522501b5/pyproject.toml)
- PyPI 官方 JSON API 显示该项目确实以 `typescope` 发布过 `0.0.1` 和 `0.0.2`；每个版本同时提供通用 wheel（`py3-none-any.whl`）和 source distribution（`tar.gz`）。上传时间分别为 2025-08-25 07:33 UTC 和 15:59 UTC。[PyPI JSON API](https://pypi.org/pypi/typescope/json)
- 初始提交的说明直接写明“发布到 PyPI”，并以 Hatchling 作为构建后端；该提交创建了 `0.0.1` 元数据。[初始发布提交 `3187851`](https://github.com/inaku-Gyan/typescope/commit/318785112c96693d7437e8ab46cc525d129fba01)
- 仓库的 README 保留 PyPI 版本和支持 Python 版本徽章，项目 URL 也把 GitHub 仓库、Issue tracker 作为元数据链接。[README](https://github.com/inaku-Gyan/typescope/blob/3ad7715cffc8a43330e3f1514360b378522501b5/README.md)
- GitHub Actions 当前只有 `Tests` 和 `Pre-Commit Format Check` 两个工作流，未发现构建、发布到 PyPI 或 GitHub Release 的工作流；GitHub API 当前返回 0 个 Release 对象和 0 个 tag。因而“保留发布目标”应理解为继续产出可上传到 PyPI 的 wheel + sdist，并重新设计发布自动化，而不是复用一个现存的 release workflow。[工作流目录](https://github.com/inaku-Gyan/typescope/tree/3ad7715cffc8a43330e3f1514360b378522501b/.github/workflows) · [Releases API](https://api.github.com/repos/inaku-Gyan/typescope/releases) · [Tags API](https://api.github.com/repos/inaku-Gyan/typescope/tags)

## testcov 能力

- 开发依赖包含 `pytest` 和 `pytest-cov`，pytest 测试路径配置为 `tests`。[当前 `pyproject.toml`](https://github.com/inaku-Gyan/typescope/blob/3ad7715cffc8a43330e3f1514360b378522501b5/pyproject.toml)
- `Makefile` 的 `testcov` 目标运行 `uv run pytest --cov=typescope --cov-fail-under=70`。因此本地入口会统计 `typescope` 包覆盖率，并以 70% 作为失败阈值；该目标不显式要求 XML 或 HTML 报告。[`Makefile`](https://github.com/inaku-Gyan/typescope/blob/3ad7715cffc8a43330e3f1514360b378522501b/Makefile)
- CI 的 `Tests` 工作流在 Ubuntu、macOS、Windows × Python 3.11、3.12、3.13 矩阵中执行测试；命令同样要求覆盖率至少 70%，并额外使用 `--cov-report=xml` 生成 `coverage.xml`，随后用 `codecov/codecov-action@v5` 上传该文件。`CODECOV_TOKEN` secret 缺失或上传动作失败会因 `fail_ci_if_error: true` 使步骤失败。[`test.yml`](https://github.com/inaku-Gyan/typescope/blob/3ad7715cffc8a43330e3f1514360b378522501b5/.github/workflows/test.yml)
- 覆盖率门槛和 Codecov 上传是历史上分两步加入的：提交 `2c30913` 把 70% 阈值加入 Makefile 和 CI，提交 `743c516` 增加 XML 报告并上传 Codecov。[`2c30913`](https://github.com/inaku-Gyan/typescope/commit/2c309138ac80d866d07a3784dcb19d411a3c1f87) · [`743c516`](https://github.com/inaku-Gyan/typescope/commit/743c5168ac8d93980dd293499032d4518fbf206f)
- README 的 Codecov badge 表明覆盖率结果是项目对外可见的质量信号。[README](https://github.com/inaku-Gyan/typescope/blob/3ad7715cffc8a43330e3f1514360b378522501b5/README.md)

## 对重建项目的可执行约束

1. 发布兼容性基线：包仍应以 `typescope` 名称发布到 PyPI，至少保留 wheel 与 sdist 两类产物；Python 支持版本、版本号策略和实际发布自动化可以在后续决策票中重新定义。
2. 覆盖率能力基线：保留一个等价于 `testcov` 的开发入口和 CI 门槛；70% 是旧仓库事实基线，不应在没有新决策的情况下默认为新项目最终门槛。
3. 报告基线：CI 继续生成 Cobertura XML（文件名曾为 `coverage.xml`）并上传 Codecov；是否继续使用 Codecov、是否增加 HTML/终端报告以及 token 认证方式属于新工具链决策。
4. 旧仓库没有可直接复用的发布 workflow、tag 或 GitHub Release；重建时应把构建、检查、凭据、Trusted Publishing/Token 和触发条件作为独立发布设计问题处理。
