

use "C:\Users\ZHANG\Downloads\农业碳排放效率与控制变量（长面板）.dta", clear

generate lnland = ln(land)
label variable lnland "ln土地经营规模（农作物播种面积/第一产业从业人员）"
rename econ lnecon
label variable lnecon "ln经济发展水平（农林牧渔总产值/乡村人口，2011年基期）"

global v1 "eff"  // 被解释变量
global v2 "did"	// 解释变量
global v3 " fin plant lnecon env disaster urban lnland "	// 控制变量
global v4 " sown_area labor fert mach_power irrig_area pesticide diesel "	// 投入指标
global v5 " grain agri_value "	// 期望产出
global v6 " ace "	// 非期望产出

* 碳排放效率描述性统计
tabstat $v4 $v5 $v6, stats(n mean sd min median max) format(%10.4f)column(stats)
logout,save("C:\Users\ZHANG\Downloads\描述性统计") excel dec(3) replace:  tabstat $v4 $v5 $v6, stats(n mean sd min median max) format(%10.4f)column(stats) 

* 回归分析描述性统计
tabstat $v1 $v2 $v3, stats(n mean sd min median max) format(%10.4f)column(stats)
logout,save("C:\Users\ZHANG\Downloads\描述性统计2") excel dec(3) replace:  tabstat $v1 $v2 $v3, stats(n mean sd min median max) format(%10.4f)column(stats) 

* 基准回归-----------------------------------------------------------------------------------------------
reghdfe eff did ,a(i.year i.prov) vce(robust) keepsingletons
est store a1

reghdfe eff did $v3 ,a(i.year i.prov) vce(robust) keepsingletons
keep if e(sample)
est store a2 
outreg2 [a1 a2] using "C:\Users\ZHANG\Downloads\基准回归结果.xls", replace tstat bdec(4) tdec(4) adjr2 



* 稳健性检验-----------------------------------------------------------------------------------------------
* 事件研究法
bysort prov: egen treat = max(did)

bysort prov: egen start_year = min(cond(did == 1, year, .))

gen rel_year = year - start_year

gen Before4 = (rel_year == -4 & treat == 1)
gen Before3 = (rel_year == -3 & treat == 1)
gen Before2 = (rel_year == -2 & treat == 1)
gen Current = (rel_year == 0  & treat == 1)
gen After1  = (rel_year == 1  & treat == 1)
gen After2  = (rel_year == 2  & treat == 1)
gen After3  = (rel_year == 3  & treat == 1)
gen After4  = (rel_year == 4  & treat == 1)
gen After5  = (rel_year == 5  & treat == 1)


reghdfe eff Before4 Before3 Before2 Current After1 After2 After3 After4 After5 $v3, absorb(prov year) vce(robust) keepsingletons
keep if e(sample)


coefplot reg1, keep(Before4 Before3 Before2 Current After1 After2 After3 After4 After5) ///
    levels(85) vertical ///
    yline(0, lcolor(edkblue*0.8)) ///
    xline(4, lwidth(vthin) lpattern(dash) lcolor(teal)) ///
    ylabel(, labsize(*0.75)) xlabel(, labsize(*0.75) angle(0)) ///
    ytitle("政策动态效应", size(small)) ///
    xtitle("政策时点", size(small)) ///
    addplot(line @b @at) ///
    ciopts(lpattern(dash) recast(rcap) msize(medium)) ///
    msymbol(circle_hollow) ///
    scheme(s1mono)

	
* 蒙特卡罗方法
use "C:\Users\ZHANG\Downloads\农业碳排放效率与控制变量（长面板）.dta", clear

generate lnland = ln(land)
label variable lnland "ln土地经营规模（农作物播种面积/第一产业从业人员）"
rename econ lnecon
label variable lnecon "ln经济发展水平（农林牧渔总产值/乡村人口，2011年基期）"

global v1 "eff"  // 被解释变量
global v2 "did"	// 解释变量
global v3 " fin plant lnecon env disaster urban lnland "	// 控制变量
global v4 " sown_area labor fert mach_power irrig_area pesticide diesel "	// 投入指标
global v5 " grain agri_value "	// 期望产出
global v6 " ace "	// 非期望产出

reghdfe eff did $v3, absorb(prov year) vce(robust) keepsingletons
keep if e(sample)
local b_true = _b[did]
save placebo_base.dta, replace


duplicates drop prov, force
keep prov
gen prov_fake = _n
save prov_list.dta, replace

use placebo_base.dta, clear
merge m:1 prov using prov_list.dta, nogen
keep prov_fake year did
rename did fake_did
save fake_did_map.dta, replace


set seed 100000

forvalue i = 1/1000 {
    use prov_list.dta, clear
    gen rand = runiform()
    sort rand
    gen prov_shuffled = _n
    keep prov prov_shuffled
    rename prov_shuffled prov_fake
    save prov_map.dta, replace

    use placebo_base.dta, clear
    merge m:1 prov using prov_map.dta, nogen
    
    merge m:1 prov_fake year using fake_did_map.dta, nogen keep(1 3)

    qui reghdfe eff fake_did $v3, absorb(prov year) vce(robust) keepsingletons
    
    gen b_did  = _b[fake_did]
    gen se_did = _se[fake_did]
    
    keep b_did se_did
    duplicates drop b_did, force
    save placebo_`i'.dta, replace
}


erase prov_list.dta
erase prov_map.dta
erase fake_did_map.dta
erase placebo_base.dta



use placebo_1.dta, clear
forvalue k = 2/1000 {
    append using placebo_`k'.dta
    erase placebo_`k'.dta
}
erase placebo_1.dta

gen tvalue = b_did / se_did
gen pvalue = 2 * ttail(e(df_r), abs(tvalue))

graph set window fontface     "Times New Roman"
graph set window fontfacesans "宋体"

	
twoway (kdensity b_did, lcolor(black) lwidth(medium) yaxis(1)) ///
       (scatter pvalue b_did, msymbol(smcircle_hollow) mcolor(gray) yaxis(2)), ///
    title("个体随机安慰剂检验", size(medlarge)) ///
    xlabel(-0.1(0.04)0.1, labsize(medium) format(%04.2f)) ///
    xline(0, lpattern(dash) lcolor(black)) ///
    xline(`b_true', lpattern(solid) lcolor(red)) ///
    xtitle("{stSans:估计系数}", size(medlarge)) ///
    ytitle("{stSans:核密度}", size(medium) axis(1)) ///
    ytitle("{stSans:P}""{stSans:值}", size(medium) orientation(h) axis(2)) ///
    yline(0.1, lpattern(shortdash) lcolor(blue) axis(2)) ///
    ylabel(0(0.2)1.0, axis(2) angle(0)) ///
    legend(label(1 "估计系数核密度") label(2 "P值")) ///
    plotregion(style(none)) ///
    graphregion(color(white))

use "C:\Users\ZHANG\Downloads\农业碳排放效率与控制变量（长面板）.dta", clear

generate lnland = ln(land)
label variable lnland "ln土地经营规模（农作物播种面积/第一产业从业人员）"
rename econ lnecon
label variable lnecon "ln经济发展水平（农林牧渔总产值/乡村人口，2011年基期）"

global v1 "eff"  // 被解释变量
global v2 "did"	// 解释变量
global v3 " fin plant lnecon env disaster urban lnland "	// 控制变量
global v4 " sown_area labor fert mach_power irrig_area pesticide diesel "	// 投入指标
global v5 " grain agri_value "	// 期望产出
global v6 " ace "	// 非期望产出


* 剔除极端值（北京、上海、重庆、天津、西藏）
reghdfe eff did if !inlist(prov, 1, 2, 9, 22, 26), absorb(prov year) vce(robust) keepsingletons
est store b1
reghdfe eff did $v3 if !inlist(prov, 1, 2, 9, 22, 26), absorb(prov year) vce(robust) keepsingletons
est store b2

outreg2 [b1 b2] using "C:\Users\ZHANG\Downloads\剔除极端值回归结果.xls", replace tstat bdec(4) tdec(4) adjr2 

* 缩尾处理
winsor2 eff, suffix(_w1) cuts(1 99)
reghdfe eff_w1 did, absorb(prov year) vce(robust) keepsingletons
est store b3
reghdfe eff_w1 did $v3, absorb(prov year) vce(robust) keepsingletons
est store b4

winsor2 eff, suffix(_w5) cuts(5 95)
reghdfe eff_w5 did, absorb(prov year) vce(robust) keepsingletons
est store b5
reghdfe eff_w5 did $v3, absorb(prov year) vce(robust) keepsingletons
est store b6

outreg2 [b3 b4 b5 b6] using "C:\Users\ZHANG\Downloads\缩尾处理回归结果.xls", replace tstat bdec(4) tdec(4) adjr2

* 异质性分析
reghdfe eff did if region == "华北", absorb(prov year) vce(robust) keepsingletons
est store c1
reghdfe eff did $v3 if region == "华北", absorb(prov year) vce(robust) keepsingletons
est store c2

reghdfe eff did if region == "东北", absorb(prov year) vce(robust) keepsingletons
est store c3
reghdfe eff did $v3 if region == "东北", absorb(prov year) vce(robust) keepsingletons
est store c4

reghdfe eff did if region == "华东", absorb(prov year) vce(robust) keepsingletons
est store c5
reghdfe eff did $v3 if region == "华东", absorb(prov year) vce(robust) keepsingletons
est store c6

reghdfe eff did if region == "华中与华南", absorb(prov year) vce(robust) keepsingletons
est store c7
reghdfe eff did $v3 if region == "华中与华南", absorb(prov year) vce(robust) keepsingletons
est store c8

reghdfe eff did if region == "西南", absorb(prov year) vce(robust) keepsingletons
est store c9
reghdfe eff did $v3 if region == "西南", absorb(prov year) vce(robust) keepsingletons
est store c10

reghdfe eff did if region == "西北", absorb(prov year) vce(robust) keepsingletons
est store c11
reghdfe eff did $v3 if region == "西北", absorb(prov year) vce(robust) keepsingletons
est store c12

outreg2 [c1 c2 c3 c4 c5 c6 c7 c8 c9 c10 c11 c12] using "C:\Users\ZHANG\Downloads\异质性分析回归结果.xls", replace tstat bdec(4) tdec(4) adjr2