"""项目基础配置和跨平台路径定义。"""

from pathlib import Path

# 当前文件：
# src/enterprise_concept_radar/config.py
PACKAGE_DIR = Path(__file__).resolve().parent

# 项目根目录：
# TonyAnYa-EnterpriseConceptRadar/
PROJECT_ROOT = PACKAGE_DIR.parents[1]

CONFIG_DIR = PROJECT_ROOT / "config"

DATA_DIR = PROJECT_ROOT / "data"
SAMPLE_DATA_DIR = DATA_DIR / "sample"
SAMPLE_POLICY_DIR = SAMPLE_DATA_DIR / "policies"
BASELINE_DATA_DIR = SAMPLE_DATA_DIR / "baselines"
RUNTIME_DATA_DIR = DATA_DIR / "runtime"

OUTPUT_DIR = PROJECT_ROOT / "outputs"
REPORT_DIR = OUTPUT_DIR / "reports"
CONCEPT_CARD_DIR = OUTPUT_DIR / "concept_cards"


def ensure_runtime_directories() -> None:
    """创建程序运行过程中需要的目录。"""
    directories = [
        RUNTIME_DATA_DIR,
        REPORT_DIR,
        CONCEPT_CARD_DIR,
    ]

    for directory in directories:
        directory.mkdir(
            parents=True,
            exist_ok=True,
        )