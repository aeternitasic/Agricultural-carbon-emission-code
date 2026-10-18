import os

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

Regions = [
    {"name": "华北", "provinces": ["北京", "天津", "河北", "山西", "内蒙古"]},
    {"name": "华东", "provinces": ["上海", "江苏", "浙江", "安徽", "福建", "江西", "山东"]},
    {"name": "华中与华南", "provinces": ["河南", "湖北", "湖南", "广东", "广西", "海南"]},
    {"name": "西南", "provinces": ["重庆", "四川", "贵州", "云南", "西藏"]},
    {"name": "东北", "provinces": ["辽宁", "吉林", "黑龙江"]},
    {"name": "西北", "provinces": ["陕西", "甘肃", "青海", "宁夏", "新疆"]}

]
Indicators = [
    # 农用物资投入 kg CE / kg (等价于 万吨 CE / 万吨)
    {"name": "氮肥", "file": os.path.join(DATA_DIR, "各地区氮肥施用量(万吨).xlsx"), "phi": 0.4173, "group": "农用物资投入"},
    {"name": "磷肥", "file": os.path.join(DATA_DIR, "各地区磷肥施用量(万吨).xlsx"), "phi": 0.4445, "group": "农用物资投入"},
    {"name": "钾肥", "file": os.path.join(DATA_DIR, "各地区钾肥施用量(万吨).xlsx"), "phi": 0.1773, "group": "农用物资投入"},
    {"name": "复合肥", "file": os.path.join(DATA_DIR, "各地区复合肥施用量（万吨）.xlsx"), "phi": 0.4827, "group": "农用物资投入"},

    {"name": "农用机械柴油", "file": os.path.join(DATA_DIR, "各地区农用柴油使用量（万吨）.xlsx"), "phi": 0.5927, "group": "农用物资投入"},
    {"name": "农药", "file": os.path.join(DATA_DIR, "各地区农药使用量（万吨）.xlsx"), "phi": 3.6818, "group": "农用物资投入"},
    {"name": "农膜", "file": os.path.join(DATA_DIR, "各地区农用塑料薄膜使用量（万吨）.xlsx"), "phi": 5.18, "group": "农用物资投入"},
    {"name": "灌溉用电", "file": os.path.join(DATA_DIR, "各地区有效灌溉面积（千公顷）.xlsx"), "phi": 0.0020476, "group": "农用物资投入"},


    # 农业生产过程 kg CE / kha
    {"name": "耕作", "file": os.path.join(DATA_DIR, "各地区农作物播种面积（千公顷）.xlsx"), "phi": 0.0003126, "group": "农业生产过程"},
    
    {"name": "双季早稻", "file": os.path.join(DATA_DIR, "各地区早稻播种面积（千公顷）.xlsx"), 
     "phi": {"华北": 0, "华东": 0.14413636, "华中与华南": 0.16431818, "西南": 0.1065, "东北": 0, "西北": 0}, "group": "农业生产过程"},

    {"name": "中稻与单季稻", "file": os.path.join(DATA_DIR, "各地区中稻和一季晚稻播种面积（千公顷）.xlsx"), 
     "phi": {"华北": 0.15954545, "华东": 0.14693182, "华中与华南": 0.16138636, "西南": 0.1065, "东北": 0.11454545, "西北": 0.15763636}, "group": "农业生产过程"},

    {"name": "双季晚稻", "file": os.path.join(DATA_DIR, "双季晚稻播种面积（千公顷）.xlsx"), 
     "phi": {"华北": 0, "华东": 0.15272727, "华中与华南": 0.18627273, "西南": 0.11706818, "东北": 0, "西北": 0}, "group": "农业生产过程"},

    # 畜禽养殖 kg CE / head *1000 转换成 万吨的
    {"name": "奶牛", "file": os.path.join(DATA_DIR, "各地区奶牛年均存栏量（万头）.xlsx"), "phi": 0.7004416, "group": "畜禽养殖"},    
    {"name": "肉牛", "file": os.path.join(DATA_DIR, "各地区肉牛年均存栏量（万头）.xlsx"), "phi": 0.5597735, "group": "畜禽养殖"},
    {"name": "马", "file": os.path.join(DATA_DIR, "各地区马年均存栏量（万头）.xlsx"), "phi": 0.3114320, "group": "畜禽养殖"},
    {"name": "驴", "file": os.path.join(DATA_DIR, "各地区驴年均存栏量（万头）.xlsx"), "phi": 0.2518410, "group": "畜禽养殖"},
    {"name": "骡", "file": os.path.join(DATA_DIR, "各地区骡年均存栏量（万头）.xlsx"), "phi": 0.2518410 , "group": "畜禽养殖"},
    {"name": "羊", "file": os.path.join(DATA_DIR, "各地区羊年均存栏量（万只）.xlsx"), "phi": 0.0983704, "group": "畜禽养殖"},
    {"name": "猪", "file": os.path.join(DATA_DIR, "各地区猪年均存栏量（万头）.xlsx"), "phi": 0.1028704, "group": "畜禽养殖"},
    {"name": "家禽", "file": os.path.join(DATA_DIR, "各地区家禽年均存栏量（万只）.xlsx"), "phi": 0.0026906, "group": "畜禽养殖"},
]

DEA_Inputs = [
    {"name": "播种面积", "var": "sown_area", "label": "农作物播种面积（千公顷）", "file": os.path.join(DATA_DIR, "各地区农作物播种面积（千公顷）.xlsx")},
    {"name": "劳动力", "var": "labor", "label": "农业从业人员（万人）", "file": os.path.join(DATA_DIR, "各地区农业从业人员（万人）.xlsx")},
    {"name": "化肥", "var": "fert", "label": "农用化肥施用量（万吨）", "file": os.path.join(DATA_DIR, "各地区农用化肥施用量(万吨).xlsx")},
    {"name": "机械", "var": "mach_power", "label": "农业机械总动力（万千瓦）", "file": os.path.join(DATA_DIR, "各地区农业机械总动力（万千瓦）.xlsx")},
    {"name": "灌溉", "var": "irrig_area", "label": "有效灌溉面积（千公顷）", "file": os.path.join(DATA_DIR, "各地区有效灌溉面积（千公顷）.xlsx")},
    {"name": "农药", "var": "pesticide", "label": "农药使用量（万吨）", "file": os.path.join(DATA_DIR, "各地区农药使用量（万吨）.xlsx")},
    {"name": "柴油", "var": "diesel", "label": "农用柴油使用量（万吨）", "file": os.path.join(DATA_DIR, "各地区农用柴油使用量（万吨）.xlsx")},
]

DEA_Desirables = [
    {"name": "粮食", "var": "grain", "label": "粮食总产量（万吨）", "file": os.path.join(DATA_DIR, "各地区粮食总产量（万吨）.xlsx")},
    {"name": "农林牧渔总产值", "var": "agri_value", "label": "农林牧渔总产值（亿元，2011年为基期）", "file": os.path.join(DATA_DIR, "各地区农林牧渔总产值（亿元，以2011年为基期）.xlsx")},
]

# DID 回归的控制变量清单：
# 每项登记一个宽面板 Excel（行=省份、列=年份，与项目统一的文件排版一致），
# output_stata.output_to_dta 导出 .dta 时会按 var 命名并入长面板
Controls = [
    {"var": "fin", "name": "财政支农水平", "file": os.path.join(DATA_DIR, "各地区财政支农水平.xlsx"), "label": "财政支农水平（农林水支出/一般公共预算支出）"},
    {"var": "plant", "name": "种植结构", "file": os.path.join(DATA_DIR, "各地区种植结构.xlsx"), "label": "种植结构（粮食播种面积/农作物总播种面积）"},
    {"var": "econ", "name": "经济发展水平", "file": os.path.join(DATA_DIR, "各地区经济发展水平（frac{万元}{人}）.xlsx"), "label": "经济发展水平（ln(农林牧渔总产值/乡村人口)，2011年基期）"},
    {"var": "env", "name": "环境规制强度", "file": os.path.join(DATA_DIR, "各地区环境规制强度.xlsx"), "label": "环境规制强度（环境污染治理投资/GDP）"},
    {"var": "disaster", "name": "农业受灾率", "file": os.path.join(DATA_DIR, "各地区农业受灾率.xlsx"), "label": "农业受灾率（受灾面积/农作物总播种面积）"},
    {"var": "urban", "name": "城镇化率", "file": os.path.join(DATA_DIR, "各地区城镇化率.xlsx"), "label": "城镇化率（城镇人口/总人口）"},
    {"var": "land", "name": "土地经营规模", "file": os.path.join(DATA_DIR, "各地区土地经营规模.xlsx"), "label": "土地经营规模（农作物播种面积/第一产业从业人员）"},
]

# 政策冲击变量（大数据交易平台设立的 0-1 虚拟变量）
# 文件缺失时导出会自动跳过该变量并给出警告，不影响其余变量导出
Did_Variable = {"var": "did", "name": "数据要素市场化", "file": os.path.join(DATA_DIR, "大数据交易平台设立（政策冲击）.xlsx"), "label": "政策冲击（设立大数据交易平台的省份，自设立年份起取 1）"}