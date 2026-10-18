import os

import numpy as np
import pandas as pd

from config import DATA_DIR, Controls, Did_Variable, DEA_Inputs, DEA_Desirables
from excel_io import load_sheet
from panel import province_to_region

EFF_CSV = os.path.join(DATA_DIR, "efficiency_panel_results.csv")
DEFAULT_DTA = os.path.join(DATA_DIR, "农业碳排放效率与控制变量（长面板）.dta")

# 非期望产出（ACE）是 compute_ace 的计算结果，没有对应 Excel 文件，故在模块内登记变量名与标签
ACE_VAR = "ace"
ACE_LABEL = "农业碳排放总量（万吨CE）"


def load_long_panel(file_path, value_name):
    """通用宽转长：把宽面板 Excel 读成 [province, year, value_name] 长表
    依赖 excel_io.load_sheet 读取（复用项目统一的文件排版约定）
    返回的三列长表可以直接与其它长表按（province, year）合并
    """
    provinces, matrix, years = load_sheet(file_path)

    wide = pd.DataFrame(matrix, index=provinces, columns=years)
    wide.index.name = "province"

    long = wide.reset_index().melt(id_vars="province", var_name="year", value_name=value_name)
    long["year"] = long["year"].astype(int)
    return long


def _load_efficiency(panel, provinces, years):
    """效率值来源：优先使用传入的 panel；未传入时读断点 CSV（免重跑 SBM）"""
    if panel is not None:
        if provinces is None or years is None:
            raise ValueError("传入 panel 时必须同时传入 provinces 与 years")
        wide = pd.DataFrame(np.asarray(panel, dtype = float), index = provinces, columns = years)
    else:
        wide = pd.read_csv(EFF_CSV, index_col=0, encoding="utf-8-sig")
        wide.columns = [int(col) for col in wide.columns]

    wide.index.name = "province"
    long = wide.reset_index().melt(id_vars="province", var_name="year", value_name="eff")
    long["year"] = long["year"].astype(int)
    long["eff"] = long["eff"].round(4)
    return long


def _merge_variable(df, file_path, value_name):
    """把一个宽面板文件转成长表并合并进 df（按省份名 + 年份对齐）"""
    long = load_long_panel(file_path, value_name)
    long[value_name] = long[value_name].round(4)
    return df.merge(long, on=["province", "year"], how="left", validate="one_to_one")


def _add_ids(df):
    """省份代码（与面板行序一致，1-31）与所属六大区域"""
    provinces = df["province"].unique()
    df["prov"] = df["province"].map({p: i + 1 for i, p in enumerate(provinces)})
    df["region"] = df["province"].map(province_to_region())
    return df


def _validate(df):
    """长面板完整性校验：31 省 × 14 年无缺行、数值变量无缺失"""
    assert df.shape[0] == 31 * 14, "长面板行数应为 434，实际 {}".format(df.shape[0])
    assert df["province"].nunique() == 31, "省份数量应为 31"
    assert list(sorted(df["year"].unique())) == list(range(2011, 2025)), "年份应为 2011-2024"
    assert df["region"].notna().all(), "存在无法匹配六大区域的省份，请检查 config.Regions"
    for col in df.columns:
        if col not in ("province", "region"):
            assert df[col].notna().all(), "变量 {} 存在缺失值，请检查对应文件".format(col)


def _load_indicators(X_3d, Y_g3d, ACE, provinces, years):
    """把 DEA 指标数组（投入/期望产出/非期望产出）转成 [province, year, ...指标列] 长表

    数组直接来自 main.py 中的 build_panel / compute_ace 结果，不重复读 Excel；
    展开顺序与 _load_efficiency 的 melt 一致（省外循环、年内循环），
    变量名与中文标签取自 config 的 DEA_Inputs / DEA_Desirables 登记。
    """
    assert X_3d.shape == (len(DEA_Inputs), len(provinces), len(years)), \
        "X_3d 维度应为 ({}, {}, {})，且指标顺序与 config.DEA_Inputs 一致".format(
            len(DEA_Inputs), len(provinces), len(years))
    assert Y_g3d.shape == (len(DEA_Desirables), len(provinces), len(years)), \
        "Y_g3d 维度应为 ({}, {}, {})，且指标顺序与 config.DEA_Desirables 一致".format(
            len(DEA_Desirables), len(provinces), len(years))
    assert ACE.shape == (len(provinces), len(years)), \
        "ACE 维度应为 ({}, {})".format(len(provinces), len(years))

    long = pd.DataFrame({
        "province": np.repeat(provinces, len(years)),
        "year": np.tile(years, len(provinces)),
    })
    # X_3d[i] 形状为 (省, 年)，C 序展平即"省外循环、年内循环"，与上面两列的构造顺序一致
    for i, item in enumerate(DEA_Inputs):
        long[item["var"]] = X_3d[i].reshape(-1).round(4)
    for i, item in enumerate(DEA_Desirables):
        long[item["var"]] = Y_g3d[i].reshape(-1).round(4)
    long[ACE_VAR] = ACE.reshape(-1).round(4)
    return long


def output_to_dta(panel=None, provinces=None, years=None, output_dta_path=None,
                  X_3d=None, Y_g3d=None, ACE=None):
    """将效率值 + DEA 指标（7 投入 + 2 期望产出 + 非期望产出）+ 控制变量 + 政策冲击
    合并导出为 Stata 长面板 .dta

    DEA 指标取自在 main.py 中已装载的数组（X_3d / Y_g3d / ACE），
    三个数组需同时传入或同时不传；不传时 .dta 只含效率值、控制变量与政策冲击。
    """
    df = _load_efficiency(panel, provinces, years)

    # DEA 指标（不重复读 Excel，直接展开内存数组；ACE 为计算值，本就没有对应文件）
    if X_3d is not None or Y_g3d is not None or ACE is not None:
        if X_3d is None or Y_g3d is None or ACE is None or provinces is None or years is None:
            raise ValueError("整合 DEA 指标需要同时传入 X_3d、Y_g3d、ACE、provinces、years")
        indicators = _load_indicators(X_3d, Y_g3d, ACE, provinces, years)
        df = df.merge(indicators, on=["province", "year"], how="left", validate="one_to_one")

    for item in Controls:
        df = _merge_variable(df, item["file"], item["var"])

    if os.path.exists(Did_Variable["file"]):
        df = _merge_variable(df, Did_Variable["file"], Did_Variable["var"])
        df[Did_Variable["var"]] = df[Did_Variable["var"]].astype(int)
    else:
        print("警告：未找到政策冲击文件 {}，本次导出跳过变量 {}；"
              "如需加入，请将文件放入 data/ 后重新运行".format(Did_Variable["file"], Did_Variable["var"]))

    df = _add_ids(df)
    df = df.sort_values(["prov", "year"]).reset_index(drop=True)
    _validate(df)

    # 固定列顺序：识别变量 → 效率值 → 政策冲击 → DEA 指标 → 控制变量（按 config 登记顺序）
    var_order = ["prov", "province", "region", "year", "eff"]
    if Did_Variable["var"] in df.columns:
        var_order.append(Did_Variable["var"])
    var_order += [item["var"] for item in DEA_Inputs + DEA_Desirables if item["var"] in df.columns]
    if ACE_VAR in df.columns:
        var_order.append(ACE_VAR)
    var_order += [item["var"] for item in Controls]
    df = df[var_order]

    labels = {
        "prov": "省份代码（1-31，与面板行序一致）",
        "province": "省份名称",
        "region": "所属六大区域",
        "year": "年份",
        "eff": "农业碳排放效率（超效率SBM得分）",
    }
    for item in DEA_Inputs + DEA_Desirables:
        if item["var"] in df.columns:
            labels[item["var"]] = item["label"]
    if ACE_VAR in df.columns:
        labels[ACE_VAR] = ACE_LABEL
    labels.update({item["var"]: item["label"] for item in Controls})
    if Did_Variable["var"] in df.columns:
        labels[Did_Variable["var"]] = Did_Variable["label"]

    if output_dta_path is None:
        output_dta_path = DEFAULT_DTA

    df.to_stata(output_dta_path,
                version=118,          
                write_index=False,
                data_label="农业碳排放效率与控制变量（2011-2024，长面板）",
                variable_labels=labels)

    print("长面板（.dta）已保存至: {}".format(output_dta_path))
    print("共 {} 个观测（{} 省 × {} 年），变量：{}".format(
        df.shape[0], df["province"].nunique(), df["year"].nunique(),
        " ".join(df.columns)))


if __name__ == "__main__":
    # 不传 panel 时自动从 data/efficiency_panel_results.csv 读入效率断点结果
    output_to_dta()
