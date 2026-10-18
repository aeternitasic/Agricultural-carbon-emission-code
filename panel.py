import numpy as np
from config import Indicators, Regions
from excel_io import load_sheet

def province_to_region() -> dict[str, str]:
    province_to_region_dict = {}
    for region in Regions:
        for province in region["provinces"]:
            province_to_region_dict[province] = region["name"]
    '''
    Regions 是以区域为键，省份列表为值的字典，在实际使用时需要反过来，即以省份为键，区域为值的字典，这样在处理数据时可以根据省份快速找到对应的区域
    因此，对于 Regions 中的每一个区域，如果这个省属于这个区域，那么就将这个省作为键，区域作为值，存入 province_to_region_dict 字典中
    类似于 {"北京": "华北"}
    '''
    return province_to_region_dict


def parameter_matrix(provinces) -> np.ndarray:
    """把 20 个 ACE 指标的碳排放系数按省份展开，得到 Phi[指标, 省]

    分两种情况：
    当 phi 是数值：全国统一系数，直接复制成一行
    当 phi 是字典：分区域系数，按省份所属区域取值（config 中已保证每个区域都有值）

    本函数只处理 Indicators（ACE 专用清单），与 DEA 清单无关
    """
    ptrd = province_to_region()
    phi_list = []

    for item in Indicators:
        phi = item["phi"]
        # isinstance(phi, dict) 表示检查 phi 是否是字典类型，返回值是 True 或 False
        # isinstance(object, classinfo) 的第二个参数如果是一个元组，表示的含义是或，例如 isinstance(phi, (int, float)) 表示检查 phi 是否是 int 或 float 类型
        '''
        先前的设置的字典中，部分条目的 phi 是一个字典，表示不同地区的 phi 值，而其他条目的 phi 是一个单一的数值
        因此这里需要判断 phi 的类型，如果是字典，就根据当前省份所在的地区来获取对应的 phi 值；如果不是字典，就直接使用这个数值作为全局的 phi 值
        '''
        if isinstance(phi,(int, float)):
            row = [float(phi)] * len(provinces)
        elif isinstance(phi, dict):
            row = [float(phi.get(ptrd.get(province), 0)) for province in provinces]
            '''
            读的时候要从内往外读，先从 province_to_region_dict 获取 province 对应的区域，也就是 region, 再从 phi 字典中获取这个区域对应的 phi 值
            如果没有区域对应的 phi 值，就返回 0 作为碳排放系数
            当然，在 config 中已经设定了所有区域的 phi 值，如果对应区域没有这种条目的发展水平，统一规定这种情况的 phi 值为 0，即碳排放系数为 0
            '''
        else:
            raise ValueError("指标 {} 的 phi 配置类型错误".format(item["name"]))

        phi_list.append(row)
    Phi = np.array(phi_list)

    assert Phi.shape == (len(Indicators), len(provinces)), "系数矩阵的维度异常，应当为（指标数量，省份数量），实际为 ({}, {})".format(Phi.shape[0], Phi.shape[1])

    return Phi

def build_panel(items) -> tuple[np.ndarray, list[str], list[int]]:
    """通用装载函数：把任意"指标清单"读成三维数组 Q[指标, 省, 年]
    输入为 config 中的列表
    """
    matrix_list = []
    base_provinces = None
    base_years = None

    for index, item in enumerate(items):
        provinces, data_matrix, years = load_sheet(item["file"])
        if index == 0:
            base_provinces, base_years = provinces, years
        else:
            assert provinces == base_provinces, "指标 {} 的省份列表与第一个读入的指标不一致，需要检查文件排版".format(item["name"])
            assert years == base_years, "指标 {} 的年份列表与第一个读入的指标不一致，需要检查文件排版".format(item["name"])

        matrix_list.append(data_matrix)

    return np.stack(matrix_list, axis=0), base_provinces, base_years

def construct_matrix() -> tuple[np.ndarray, np.ndarray, list[str], list[int]]:
    Q, provinces, years = build_panel(Indicators)
    Phi = parameter_matrix(provinces)

    return Q, Phi, provinces, years

if __name__  == "__main__":
    pass