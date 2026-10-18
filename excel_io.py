import numpy as np
import pandas as pd
import re

def load_sheet(file_path) -> tuple[list[str], list[int], np.ndarray]:

    df = pd.read_excel(file_path, sheet_name = "Sheet1")

    df.columns = [col.strip() if isinstance(col, str) else col for col in df.columns]
    df = df[df["地区"].notna()] # 删除地区列为空的行，先把 excel 中的内容和解释行去掉

    provinces = df["地区"].tolist() # 对地区列进行处理，提取出所有的地区名称，存入 provinces 列表中

    year_columns = [col for col in df.columns if re.fullmatch(r"20\d{2}", str(col))]  # 使用正则表达式，选取所有年份列
    r'''
    re.fullmatch 是正则完全匹配函数，也就是说只有当给定的字符串完全符合正则表达式时，才会返回匹配结果，否则返回 None
    此处设定的匹配规则是 "20\d{2}"，即以 "20" 开头，后面各跟着任意两个数字。\d 是表示 0-9 的数字，{2} 表示前面的模式重复两次
    因此，这个正则表达式可以匹配所有以 "20" 开头的四位数年份，如 2000、2010、2023 等，更进一步，哪怕以后年份更新了，也可以适配
    ''' 
    years = [int(col) for col in year_columns]

    try:
        data_matrix = df[year_columns].astype("float64").to_numpy()
    except ValueError as e:
        raise ValueError("文件 {} 中的数据格式不正确".format(file_path)) from e

    # 断言校验
    assert len(provinces) == 31, "文件 {} 省份数量与数据矩阵行数不匹配".format(file_path)
    assert len(years) == data_matrix.shape[1], "文件 {} 年份数量与数据矩阵列数不匹配".format(file_path)

    return provinces, data_matrix, years