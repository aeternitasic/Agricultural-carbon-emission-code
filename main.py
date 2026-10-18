import os
from config import DATA_DIR, DEA_Inputs, DEA_Desirables
from panel import build_panel, construct_matrix
from compute import compute_ace
from sbm import solve_panel
from sbm_output import export_panel, export_summary
from output_stata import output_to_dta


def main():
    # 装载投入与期望产出的 (指标, 省份, 年份) 三维面板
    X_3d, provinces, years = build_panel(DEA_Inputs)        # (7, 31, 14)
    Y_g3d, _, _ = build_panel(DEA_Desirables)              # (2, 31, 14)

    # 非期望产出 = 农业碳排放总量 ACE（31, 14）
    Q, Phi, _, _ = construct_matrix()
    ACE = compute_ace(Q, Phi)

    # 逐年求解（先模型一，前沿省份补跑模型二；每算完一年写断点 CSV）
    panel = solve_panel(X_3d, Y_g3d, ACE, provinces = provinces, years = years, checkpoint = os.path.join(DATA_DIR, "efficiency_panel_results.csv"))

    # 导出面板与汇总表
    export_panel(panel, provinces, years, os.path.join(DATA_DIR, "农业碳排放效率面板（2011-2024）.xlsx"))
    export_summary(panel, provinces, years, os.path.join(DATA_DIR, "农业碳排放效率汇总（2011-2024）.xlsx"))

    # 导出 Stata 长面板：效率值 + DEA 指标 + 控制变量 + 政策冲击
    output_to_dta(panel=panel, provinces=provinces, years=years, X_3d=X_3d, Y_g3d=Y_g3d, ACE=ACE)


if __name__ == "__main__":
    main()