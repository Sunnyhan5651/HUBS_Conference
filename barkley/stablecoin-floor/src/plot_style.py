"""모든 노트북에서 같이 쓰는 그래프 설정 (한글 폰트, 색, 모양)."""
import platform

import matplotlib.pyplot as plt
from matplotlib import font_manager

# 여러 선을 그릴 때 이 순서대로 쓴다 (색약인 사람도 구분하기 쉬운 조합)
COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]   # 파랑, 주황, 청록, 노랑
MUTED = "#8a8984"       # 보조선 (0선, 평균선 등)
TEXT_SUB = "#52514e"    # 보조 글씨
SHADE = "#e4e3df"       # 배경 음영

# 운영체제별 기본 한글 폰트
_KOREAN_FONTS = {
    "Windows": "Malgun Gothic",   # 맑은 고딕
    "Darwin": "AppleGothic",      # macOS
    "Linux": "NanumGothic",       # 리눅스 (나눔고딕 설치 필요)
}


def setup_plot_style():
    """한글 폰트와 그래프 기본 모양을 설정한다. 노트북 맨 앞에서 한 번 부른다."""
    font = _KOREAN_FONTS.get(platform.system(), "Malgun Gothic")
    installed = {f.name for f in font_manager.fontManager.ttflist}
    if font not in installed:
        print(f"[주의] '{font}' 폰트가 없어 한글이 깨질 수 있습니다.")

    plt.rcParams["font.family"] = font
    plt.rcParams["axes.unicode_minus"] = False   # 한글 폰트에서 마이너스(-) 기호가 깨지는 문제 방지
    plt.rcParams.update({
        "figure.figsize": (10, 4.5),
        "figure.dpi": 110,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.color": SHADE,
        "grid.linewidth": 0.8,
        "axes.edgecolor": MUTED,
        "axes.labelcolor": TEXT_SUB,
        "xtick.color": TEXT_SUB,
        "ytick.color": TEXT_SUB,
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
        "lines.linewidth": 1.5,
        "legend.frameon": False,
    })
    return font
