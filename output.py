import numpy as np
import pandas as pd
import os 
from panel import construct_matrix
from compute import compute_ace
from openpyxl.styles import Font

def export_to_excel(total_ace: np.ndarray, provinces: list[str], years: list[int], output_excel_path = None):
    
    if output_excel_path is None:
        data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
        os.makedirs(data_dir, exist_ok = True)

        output_excel_path = os.path.join(data_dir, "各地区农业碳排放量（万吨）.xlsx")


    df = pd.DataFrame(total_ace, index = provinces, columns = [str(year) for year in years])
    df.index.name = "地区"

    df.reset_index(inplace = True)  # 将原本作为行索引的地区放回表体，变为普通的第一列，重置为默认索引 0 1 2,...
    df.insert(0, "序号", range(1, len(df) + 1)) #在第一零列插入叫做“序号”的列

    with pd.ExcelWriter(output_excel_path, engine = "openpyxl") as writer:
        df.to_excel(writer, sheet_name = "Sheet1", index = False)   # 先前已经手动插入了“序号”和“地区”列，因此去掉 pandas 自带的默认索引

        workbook = writer.book
        worksheet = writer.sheets["Sheet1"]

        font_cn = Font(name = "仿宋_GB2312")
        font_en_num = Font(name = "Times New Roman")

        for row in worksheet.iter_rows():   # worksheet.iter_rows() 遍历工作表中存在的行
            for cell in row:
                if cell.value is None:
                    continue

                # 如果是数字类型
                if isinstance(cell.value, (int, float)):
                    cell.font = font_en_num
                
                # 如果是字符串类型
                else:
                    val_str = str(cell.value)
                    # 如果字符串纯粹由数字构成（如表头的年份 "2011"）
                    if val_str.isdigit():
                        cell.font = font_en_num
                    # 其他情况（表头的 "序号"、"地区" 以及各个省份名称），使用仿宋
                    else:
                        cell.font = font_cn

    print("Excel 结果已成功保存至: {}".format(output_excel_path))

    return

if __name__ == "__main__":
    Q, Phi, provinces, years = construct_matrix()
    result = compute_ace(Q, Phi)

    export_to_excel(total_ace = result, provinces = provinces, years = years)