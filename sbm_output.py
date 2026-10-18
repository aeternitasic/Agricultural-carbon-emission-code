import numpy as np
import pandas as pd
from openpyxl.styles import Font
from config import Regions


def _apply_font(worksheet):
    font_cn = Font(name="仿宋_GB2312")
    font_en_num = Font(name="Times New Roman")

    for row in worksheet.iter_rows():
        for cell in row:
            if cell.value is None:
                continue
            if isinstance(cell.value, (int, float)):
                cell.font = font_en_num
            else:
                val_str = str(cell.value)
                if val_str.isdigit():
                    cell.font = font_en_num
                else:
                    cell.font = font_cn


def export_panel(panel: np.ndarray, provinces: list[str], years: list[int], output_excel_path):
    """导出 31 省 × 14 年效率面板（布局与 output.py 的导出完全一致）"""
    df = pd.DataFrame(panel, index=provinces, columns=[str(year) for year in years]).round(4)
    df.index.name = "地区"
    df.reset_index(inplace=True)
    df.insert(0, "序号", range(1, len(df) + 1))

    with pd.ExcelWriter(output_excel_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Sheet1", index=False)
        _apply_font(writer.sheets["Sheet1"])

    print("效率面板已保存至: {}".format(output_excel_path))


def export_summary(panel: np.ndarray, provinces: list[str], years: list[int], output_excel_path):
    """
    汇总表（三个工作表）：
    逐年汇总：效率均值、前沿省份数量、最低/最高效率
    分省均值：14 年均值与有效年份数，按均值降序
    分区域均值：六大区域逐年效率均值（区域划分取自 config.Regions）
    """
    panel_df = pd.DataFrame(panel, index=provinces, columns=years)
    is_frontier = panel_df >= 1 - 1e-4

    # 表一：逐年汇总
    yearly = pd.DataFrame({
        "年份": years,
        "效率均值": panel_df.mean(axis=0).round(4).values,
        "前沿省份数量": is_frontier.sum(axis=0).values,
        "最低效率": panel_df.min(axis=0).round(4).values,
        "最高效率": panel_df.max(axis=0).round(4).values,
    })

    # 表二：分省均值
    province_mean = pd.DataFrame({
        "省份": provinces,
        "效率均值（2011-2024）": panel_df.mean(axis=1).round(4).values,
        "有效年份数（14 年）": is_frontier.sum(axis=1).values,
    }).sort_values("效率均值（2011-2024）", ascending=False).reset_index(drop=True)
    province_mean.insert(0, "排名", range(1, len(province_mean) + 1))

    # 表三：分区域均值
    region_rows = []
    for region in Regions:
        provs = [p for p in region["provinces"] if p in panel_df.index]
        sub = panel_df.loc[provs]
        region_rows.append([region["name"]] + sub.mean(axis=0).round(4).tolist())
    region_df = pd.DataFrame(region_rows, columns=["区域"] + years)

    with pd.ExcelWriter(output_excel_path, engine="openpyxl") as writer:
        yearly.to_excel(writer, sheet_name="逐年汇总", index=False)
        province_mean.to_excel(writer, sheet_name="分省均值", index=False)
        region_df.to_excel(writer, sheet_name="分区域均值", index=False)
        for sheet_name in writer.sheets:
            _apply_font(writer.sheets[sheet_name])

    print("汇总表已保存至: {}".format(output_excel_path))
