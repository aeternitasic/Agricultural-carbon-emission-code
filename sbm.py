"""超效率 SBM（含非期望产出）求解模块

两种后端（通过 solve_dmu / solve_year / solve_panel 的 backend 参数切换）：

backend="numpy"（默认）：模型一、模型二都经 Charnes-Cooper 变换为线性规划，
  由本模块内置的两阶段单纯形法（Bland 规则）求解，不依赖任何第三方优化求解器；
backend="pyomo"：原 pyomo + ipopt 实现（模型一为分式 NLP、模型二为 CC-LP），
  完整保留用于交叉验证。
"""
import numpy as np
import pandas as pd

try:
    import pyomo.environ as pyo
except ImportError:
    pyo = None   # numpy 后端不需要 pyomo；只有 backend="pyomo" 时才用到


MERGE_TOL = 1e-4   # 合并规则阈值：模型一得分 >= 1 - MERGE_TOL 视为"位于前沿"，补跑模型二
LB = 1e-10         # pyomo 后端变量下界：ipopt 内点法需要严格正的迭代点，故不用 0
SIMPLEX_TOL = 1e-9        # 单纯形法零判定容差（检验数、比值检验、右端项）
SIMPLEX_MAX_ITER = 20000  # 单个 LP 每个阶段的最大迭代次数，超过视为失败


def _valid_dim(values):
    """返回严格大于零的维度索引列表

    SBM 的目标函数与等式约束都要求被评价 DMU 的 x0/y0g/y0b 严格为正。
    若某个投入恰好为 0，该维度对分式无定义，则对该被评价 DMU 剔除该维度（文献中"投入不适用"的标准处理）。
    数据完整时本函数原样返回全部索引，模型与标准形式完全一致。
    """
    return [i for i, v in enumerate(values) if v > 0]

# 两阶段单纯形法

def _pivot(T, r, s):
    """在单纯形表 T 上以 (r, s) 为主元做行变换（含最后一行检验数行）"""
    T[r, :] /= T[r, s]
    scale = T[:, s].copy()
    scale[r] = 0.0
    T -= np.outer(scale, T[r, :])
    T[np.abs(T) < 1e-12] = 0.0   # 清理浮点残渣，保持退化判定稳定


def _entering(red, tol):
    """Bland 入基：检验数 < -tol 的列中取最小下标；无候选返回 None"""
    idx = np.where(red < -tol)[0]
    return int(idx[0]) if idx.size else None


def _leaving(col, rhs, basis, tol):
    """Bland 出基：col > tol 的行中取比值最小；平局取最小基变量下标；
    该列无正元则返回 None（目标函数在可行域上无界）"""
    pos = np.where(col > tol)[0]
    if pos.size == 0:
        return None
    ratios = rhs[pos] / col[pos]
    rmin = ratios.min()
    cand = pos[ratios <= rmin + tol]
    return int(min(cand, key=lambda i: basis[i]))


def _simplex_min(A, b, c, tol=SIMPLEX_TOL, max_iter=SIMPLEX_MAX_ITER):
    """两阶段单纯形法：min c·x  s.t. A·x = b, x >= 0

    返回 (x, 目标值)；无可行解或数值异常时返回 None。
    相位一用人工变量求可行基；Bland 规则（入基取最小下标、出基比值
    平局取最小基变量下标）保证退化情形下有限步终止。
    """
    A = np.array(A, dtype=float, copy=True)
    b = np.array(b, dtype=float, copy=True).ravel()
    c = np.array(c, dtype=float, copy=True).ravel()
    m, n = A.shape

    # 右端项非负化（必要时整行取负）；|b| 小于容差的量按 0 处理
    b[np.abs(b) < tol] = 0.0
    flip = b < 0.0
    A[flip] *= -1.0
    b[flip] *= -1.0

    n_full = n + m
    basis = list(range(n, n_full))          # 初始基 = 人工变量
    T = np.zeros((m + 1, n_full + 1))
    T[:m, :n] = A
    T[:m, n:n_full] = np.eye(m)
    T[:m, -1] = b
    T[-1, n:n_full] = 1.0                   # 相位一目标：最小化人工变量之和
    T[-1, :] -= T[:m, :].sum(axis=0)        # 化为检验数形式；末列为 -z1

    # 相位一
    for _ in range(max_iter):
        s = _entering(T[-1, :n_full], tol)
        if s is None:
            break
        r = _leaving(T[:m, s], T[:m, -1], basis, tol)
        if r is None:
            return None                     # 相位一目标有下界 0，不应无界
        _pivot(T, r, s)
        basis[r] = s
    else:
        return None

    if T[-1, -1] < -tol:                    # z1 = 人工变量之和 > tol → 无可行解
        return None

    # 把仍留在基中的零水平人工变量驱逐出去（或删除冗余行）
    # 换入列只从原变量中选，人工变量一旦出基不再入基，故本循环必然有限
    for _ in range(max_iter):
        art = [r for r, bi in enumerate(basis) if bi >= n]
        if not art:
            break
        r = art[0]
        T[r, -1] = 0.0                      # 该人工变量数值≈0，取整保证后续枢轴可行性
        cand = [j for j in range(n) if abs(T[r, j]) > tol]
        if not cand:
            T = np.delete(T, r, axis=0)     # 该行与原变量无关（冗余方程），整行删除
            del basis[r]
            continue
        s = cand[0]                         # 最小下标换入
        _pivot(T, r, s)
        basis[r] = s
    else:
        return None

    # 相位二：删除人工列，重建检验数行
    nb = len(basis)
    T2 = np.zeros((nb + 1, n + 1))
    T2[:-1, :n] = T[:nb, :n]
    T2[:-1, -1] = T[:nb, -1]
    T2[-1, :n] = c - sum(c[basis[i]] * T2[i, :n] for i in range(nb))
    T2[-1, -1] = -sum(c[basis[i]] * T2[i, -1] for i in range(nb))

    for _ in range(max_iter):
        s = _entering(T2[-1, :n], tol)
        if s is None:
            break
        r = _leaving(T2[:-1, s], T2[:-1, -1], basis, tol)
        if r is None:
            return None                     # 无界（对 SBM 的 LP 不应发生）
        _pivot(T2, r, s)
        basis[r] = s
    else:
        return None

    x = np.zeros(n)
    for i, bi in enumerate(basis):
        x[bi] = T2[i, -1]
    x[np.abs(x) < tol] = 0.0
    obj = -T2[-1, -1]
    return x, obj


# 两个模型的 Charnes-Cooper 线性化构造器
# 输出标准形 LP：min c·x  s.t. A·x = b, x >= 0（b 已非负）

def _lp_sbm(x0, y0g, y0b, X, Y_g, Y_b, vrs=False):
    """模型一：Undesirable-SBM（Tone 2004）的归一化 Charnes-Cooper 线性化

    变换：t = 1/分母，Λ̂_j = t·λ_j，Ŝ⁻ᵢ = t·s⁻ᵢ/x0ᵢ，Ŝᵍ_r = t·sᵍ_r/y0g_r，
          Ŝᵇ_z = t·sᵇ_z/y0b_z（归一化变量，系数量级 O(1)）
        min  t − (1/m)·ΣŜ⁻ᵢ
        s.t. t + (1/(s1+s2))·(ΣŜᵍ + ΣŜᵇ) = 1
             Σ_j Λ̂_j·(X_ji/x0_i) + Ŝ⁻ᵢ − t = 0        ∀i
             Σ_j Λ̂_j·(Yᵍ_jr/y0ᵍ_r) − Ŝᵍ_r − t = 0      ∀r
             Σ_j Λ̂_j·(Yᵇ_jz/y0ᵇ_z) + Ŝᵇ_z − t = 0      ∀z
             [VRS] Σ_j Λ̂_j − t = 0
             t, Λ̂, Ŝ ≥ 0

    最优目标值 = 原分式规划的 ρ*（t = 1/分母 下目标恰为 分子/分母）。
    """
    n = X.shape[0]
    I = _valid_dim(x0)
    R = _valid_dim(y0g)
    Z = _valid_dim(y0b)
    m, s1, s2 = len(I), len(R), len(Z)
    if m == 0 or s1 + s2 == 0:
        raise ValueError("被评价 DMU 的投入或产出全部为 0，无法构建模型")

    x0v, Xv = x0[I], X[:, I]
    y0gv, Ygv = y0g[R], Y_g[:, R]
    y0bv, Ybv = y0b[Z], Y_b[:, Z]

    # 变量布局：[t, Λ̂_0..Λ̂_{n-1}, Ŝ⁻(m), Ŝᵍ(s1), Ŝᵇ(s2)]
    t_i = 0
    L_i = slice(1, 1 + n)
    Sm_i = slice(1 + n, 1 + n + m)
    Sg_i = slice(1 + n + m, 1 + n + m + s1)
    Sb_i = slice(1 + n + m + s1, 1 + n + m + s1 + s2)
    n_vars = 1 + n + m + s1 + s2
    n_rows = 1 + m + s1 + s2 + (1 if vrs else 0)

    A = np.zeros((n_rows, n_vars))
    b = np.zeros(n_rows)
    c = np.zeros(n_vars)

    # 归一化约束（右端 = 1）
    A[0, t_i] = 1.0
    A[0, Sg_i] = 1.0 / (s1 + s2)
    A[0, Sb_i] = 1.0 / (s1 + s2)
    b[0] = 1.0

    row = 1
    for q, i in enumerate(I):               # 投入约束
        A[row, t_i] = -1.0
        A[row, L_i] = Xv[:, q] / x0v[q]
        A[row, Sm_i.start + q] = 1.0
        row += 1
    for q, r in enumerate(R):               # 期望产出约束
        A[row, t_i] = -1.0
        A[row, L_i] = Ygv[:, q] / y0gv[q]
        A[row, Sg_i.start + q] = -1.0
        row += 1
    for q, z in enumerate(Z):               # 非期望产出约束
        A[row, t_i] = -1.0
        A[row, L_i] = Ybv[:, q] / y0bv[q]
        A[row, Sb_i.start + q] = 1.0
        row += 1
    if vrs:                                 # 规模报酬：Σλ = 1 ⇔ ΣΛ̂ = t
        A[row, t_i] = -1.0
        A[row, L_i] = 1.0
        row += 1

    c[t_i] = 1.0
    c[Sm_i] = -1.0 / m

    names = (["t"] + ["L{}".format(j) for j in range(n)]
             + ["Sm{}".format(q) for q in range(m)]
             + ["Sg{}".format(q) for q in range(s1)]
             + ["Sb{}".format(q) for q in range(s2)])
    return A, b, c, names


def _lp_super(x0, y0g, y0b, X, Y_g, Y_b, k, vrs=False):
    """模型二：Super-Undesirable-SBM（Tone 2002 扩展）的归一化 CC 线性化

    参考集剔除被评价 DMU 本身。变量：t、Λ̂（peers）、X̂ᵢ = X̄ᵢ/x0ᵢ、
    Ŷᵍ_r = Ȳᵍ_r/y0ᵍ_r、Ŷᵇ_z = Ȳᵇ_z/y0ᵇ_z，以及把不等式化为等式的松弛变量：
        min  (1/m)·ΣX̂ᵢ
        s.t. (1/(s1+s2))·(ΣŶᵍ + ΣŶᵇ) = 1
             X̂ᵢ − t ≥ 0，            X̂ᵢ − Σ_{j≠k} Λ̂_j·(X_ji/x0_i) ≥ 0
             Ŷᵍ_r ≤ Σ_{j≠k} Λ̂_j·(Yᵍ_jr/y0ᵍ_r)，   Ŷᵍ_r ≤ t
             Ŷᵇ_z ≥ Σ_{j≠k} Λ̂_j·(Yᵇ_jz/y0ᵇ_z)，   Ŷᵇ_z ≤ t
             [VRS] Σ_{j≠k} Λ̂_j − t = 0
             t, Λ̂, X̂, Ŷ, slack ≥ 0

    最优目标值 = 超效率分 δ*。被评价 DMU 无效率时该 LP 无可行解
    （正常现象：合并规则只对前沿 DMU 调用模型二，无解时保留模型一得分 1）。
    """
    n = X.shape[0]
    I = _valid_dim(x0)
    R = _valid_dim(y0g)
    Z = _valid_dim(y0b)
    m, s1, s2 = len(I), len(R), len(Z)
    if m == 0 or s1 + s2 == 0:
        raise ValueError("被评价 DMU 的投入或产出全部为 0，无法构建模型")

    x0v, Xv = x0[I], X[:, I]
    y0gv, Ygv = y0g[R], Y_g[:, R]
    y0bv, Ybv = y0b[Z], Y_b[:, Z]
    peers = [j for j in range(n) if j != k]   # 剔除被评价 DMU 本身
    np_peers = len(peers)

    n_ineq = 2 * m + 2 * s1 + 2 * s2
    # 变量布局：[t, Λ̂(peers), X̂(m), Ŷᵍ(s1), Ŷᵇ(s2), slack(n_ineq)]
    t_i = 0
    L_i = slice(1, 1 + np_peers)
    Xh_i = slice(1 + np_peers, 1 + np_peers + m)
    Yg_i = slice(1 + np_peers + m, 1 + np_peers + m + s1)
    Yb_i = slice(1 + np_peers + m + s1, 1 + np_peers + m + s1 + s2)
    S_i = slice(1 + np_peers + m + s1 + s2, 1 + np_peers + m + s1 + s2 + n_ineq)
    n_vars = 1 + np_peers + m + s1 + s2 + n_ineq
    n_rows = 1 + n_ineq + (1 if vrs else 0)

    A = np.zeros((n_rows, n_vars))
    b = np.zeros(n_rows)
    c = np.zeros(n_vars)

    # 归一化约束（右端 = 1）
    A[0, Yg_i] = 1.0 / (s1 + s2)
    A[0, Yb_i] = 1.0 / (s1 + s2)
    b[0] = 1.0

    row = 1
    sl = S_i.start
    for q in range(m):                      # X̂ ≥ t
        A[row, Xh_i.start + q] = 1.0
        A[row, t_i] = -1.0
        A[row, sl] = -1.0
        sl += 1
        row += 1
    for q, i in enumerate(I):               # X̂ ≥ 参考集投入
        A[row, Xh_i.start + q] = 1.0
        A[row, L_i] = -Xv[peers, q] / x0v[q]
        A[row, sl] = -1.0
        sl += 1
        row += 1
    for q, r in enumerate(R):               # Ŷᵍ ≤ 参考集期望产出
        A[row, Yg_i.start + q] = -1.0
        A[row, L_i] = Ygv[peers, q] / y0gv[q]
        A[row, sl] = -1.0
        sl += 1
        row += 1
    for q in range(s1):                     # Ŷᵍ ≤ t
        A[row, Yg_i.start + q] = -1.0
        A[row, t_i] = 1.0
        A[row, sl] = -1.0
        sl += 1
        row += 1
    for q, z in enumerate(Z):               # Ŷᵇ ≥ 参考集非期望产出
        A[row, Yb_i.start + q] = 1.0
        A[row, L_i] = -Ybv[peers, q] / y0bv[q]
        A[row, sl] = -1.0
        sl += 1
        row += 1
    for q in range(s2):                     # Ŷᵇ ≤ t
        A[row, Yb_i.start + q] = -1.0
        A[row, t_i] = 1.0
        A[row, sl] = -1.0
        sl += 1
        row += 1
    if vrs:                                 # Σλ = 1 ⇔ ΣΛ̂ = t
        A[row, L_i] = 1.0
        A[row, t_i] = -1.0
        row += 1

    c[Xh_i] = 1.0 / m

    names = (["t"] + ["L{}".format(j) for j in peers]
             + ["Xh{}".format(q) for q in range(m)]
             + ["Yg{}".format(q) for q in range(s1)]
             + ["Yb{}".format(q) for q in range(s2)]
             + ["slack{}".format(q) for q in range(n_ineq)])
    return A, b, c, names


# 求解接口

def solve_dmu(X, Y_g, Y_b, k, super=False, vrs=False, tol=None, backend="numpy") -> float:
    """求解单个 DMU 的模型一（SBM）或模型二（超效率 SBM），返回效率得分；异常时返回 NaN

    backend="numpy"（默认）：内置两阶段单纯形法解 CC-LP，零第三方优化器依赖；
    backend="pyomo"：原 pyomo + ipopt 实现（模型一为分式 NLP、模型二为 CC-LP），保留作交叉验证。
    """
    x0 = X[k, :]
    y0g = Y_g[k, :]
    y0b = Y_b[k, :]

    if backend == "numpy":
        if not super:
            A, b, c, _ = _lp_sbm(x0, y0g, y0b, X, Y_g, Y_b, vrs=vrs)
        else:
            A, b, c, _ = _lp_super(x0, y0g, y0b, X, Y_g, Y_b, k, vrs=vrs)
        res = _simplex_min(A, b, c, tol=(tol if tol is not None else SIMPLEX_TOL))
        if res is None:
            print("Warning: DMU {}（{}）单纯形法求解失败（无可行解或数值异常）".format(
                k, "模型二" if super else "模型一"))
            return np.nan
        obj = res[1]
        # 轻量健全性检查：模型一得分理论界 [0,1]，模型二得分理论界 >= 1
        if not super and not (-1e-9 <= obj <= 1 + 1e-6):
            print("Warning: DMU {}（模型一）得分 {} 超出 [0,1]，判为异常".format(k, obj))
            return np.nan
        if super and obj < 1 - 1e-6:
            print("Warning: DMU {}（模型二）超效率得分 {} < 1，判为异常".format(k, obj))
            return np.nan
        return float(obj)

    if backend == "pyomo":
        if pyo is None:
            raise ImportError("backend=\"pyomo\" 需要安装 pyomo；backend=\"numpy\" 无需任何第三方求解库")
        if not super:
            model = build_model_sbm(x0, y0g, y0b, X, Y_g, Y_b, vrs=vrs)
        else:
            model = build_model_super_cc(x0, y0g, y0b, X, Y_g, Y_b, k, vrs=vrs)
        return _solve(model, k, "模型二" if super else "模型一", tol)

    raise ValueError("backend 只能是 \"numpy\" 或 \"pyomo\"，收到：{}".format(backend))


def solve_year(X_t, Y_gt, Y_bt, vrs=False, backend="numpy") -> np.ndarray:
    """某一年的截面：先全跑模型一；得分达到 1 - MERGE_TOL 的视为前沿，补跑模型二"""
    n_DMUs = X_t.shape[0]
    scores = np.full(n_DMUs, np.nan)

    # 模型一（含非期望产出的 SBM）
    for k in range(n_DMUs):
        scores[k] = solve_dmu(X_t, Y_gt, Y_bt, k, super=False, vrs=vrs, backend=backend)

    # 前沿 DMU 补跑模型二
    for k in range(n_DMUs):
        if not np.isnan(scores[k]) and scores[k] >= 1 - MERGE_TOL:
            super_score = solve_dmu(X_t, Y_gt, Y_bt, k, super=True, vrs=vrs, backend=backend)
            if not np.isnan(super_score):
                scores[k] = super_score
            # 若模型二求解失败，保留模型一得分 1

    return scores


def solve_panel(X_3d, Y_g3d, ACE, vrs=False, provinces=None, years=None,
                checkpoint=None, backend="numpy") -> np.ndarray:
    """逐年截面求解，返回 (n_DMUs, n_years) 的效率面板

    X_3d:   [投入, DMU, 年份]
    Y_g3d:  [期望产出, DMU, 年份]
    ACE:    [DMU, 年份]（非期望产出）
    checkpoint: 若给出 CSV 路径，每算完一年就把当前面板写入该文件
    backend: "numpy"（默认，内置单纯形法）或 "pyomo"（ipopt 交叉验证）
    """
    n_x, n_DMUs, n_years = X_3d.shape
    assert Y_g3d.shape[1:] == (n_DMUs, n_years), "期望产出矩阵维度与投入矩阵不一致"
    assert ACE.shape == (n_DMUs, n_years), "非期望产出矩阵维度与投入矩阵不一致"
    assert not np.isnan(X_3d).any() and not np.isnan(Y_g3d).any() and not np.isnan(ACE).any(), \
        "数据中存在 NaN，请先检查 Excel 文件"

    panel_scores = np.full((n_DMUs, n_years), np.nan)

    for t in range(n_years):
        Xt = X_3d[:, :, t].T             # (31, 7)
        Ygt = Y_g3d[:, :, t].T           # (31, 2)
        Ybt = ACE[:, t].reshape(-1, 1)   # (31, 1)

        panel_scores[:, t] = solve_year(Xt, Ygt, Ybt, vrs=vrs, backend=backend)

        year_label = years[t] if years is not None else t
        print("第 {} 年（{}）计算完成".format(t + 1, year_label))

        if checkpoint is not None:
            pd.DataFrame(panel_scores, index=provinces, columns=years).to_csv(
                checkpoint, encoding="utf-8-sig")

    print("全部 {} 年计算完成".format(n_years))
    return panel_scores

# pyomo + ipopt 后端（原实现完整保留，仅作交叉验证）

def _solve(model, dmuk, tag, tol):
    """用 ipopt 求解并做状态检查，异常时返回 NaN 并打印警告。"""
    solver = pyo.SolverFactory("ipopt")

    if tol is not None:
        solver.options["tol"] = tol

    try:
        result = solver.solve(model, tee=False)
        status = result.solver.termination_condition
        if status in (pyo.TerminationCondition.optimal, pyo.TerminationCondition.locallyOptimal):
            return float(pyo.value(model.obj))
        print("Warning: DMU {}（{}）求解异常，状态码为 {}".format(dmuk, tag, status))
        return np.nan
    except Exception as e:
        print("Warning: DMU {}（{}）求解抛出异常：{}".format(dmuk, tag, e))
        return np.nan


def build_model_sbm(x0, y0g, y0b, X, Y_g, Y_b, vrs=False):
    """模型一：含非期望产出的 SBM（Tone 2004），分式目标直接交给 ipopt，不做线性化"""
    n = X.shape[0]          # 截面 DMU 数量
    I = _valid_dim(x0)      # 投入维度（剔除被评价 DMU 中为 0 的投入）
    R = _valid_dim(y0g)     # 期望产出维度
    Z = _valid_dim(y0b)     # 非期望产出维度

    m, s1, s2 = len(I), len(R), len(Z)
    if m == 0 or s1 + s2 == 0:
        raise ValueError("被评价 DMU 的投入或产出全部为 0，无法构建模型")

    # 只保留有效维度的数据视图，pyomo 索引可直接与之一一对应
    x0v, Xv = x0[I], X[:, I]
    y0gv, Ygv = y0g[R], Y_g[:, R]
    y0bv, Ybv = y0b[Z], Y_b[:, Z]

    model = pyo.ConcreteModel()
    model.I = pyo.RangeSet(0, m - 1)      # 投入松弛的索引
    model.R = pyo.RangeSet(0, s1 - 1)     # 期望产出松弛的索引
    model.Z = pyo.RangeSet(0, s2 - 1)     # 非期望产出松弛的索引
    model.J = pyo.RangeSet(0, n - 1)      # DMU 索引（对应 X 的行）

    model.Lambda = pyo.Var(model.J, domain=pyo.NonNegativeReals, bounds=(LB, None))
    model.s_minus = pyo.Var(model.I, domain=pyo.NonNegativeReals, bounds=(LB, None))
    model.s_g = pyo.Var(model.R, domain=pyo.NonNegativeReals, bounds=(LB, None))
    model.s_b = pyo.Var(model.Z, domain=pyo.NonNegativeReals, bounds=(LB, None))

    def objective_function(model):
        numerator = 1 - (1 / m) * sum(model.s_minus[i] / x0v[i] for i in model.I)
        denominator = 1 + (1 / (s1 + s2)) * (
            sum(model.s_g[r] / y0gv[r] for r in model.R) +
            sum(model.s_b[z] / y0bv[z] for z in model.Z))
        return numerator / denominator

    model.obj = pyo.Objective(rule=objective_function, sense=pyo.minimize)

    # 投入约束：参考点投入 + 投入松弛 = 被评价 DMU 投入
    def constrain_x(model, i):
        return sum(model.Lambda[j] * Xv[j, i] for j in model.J) + model.s_minus[i] == x0v[i]

    # 期望产出约束：参考点产出 - 产出松弛 = 被评价 DMU 产出
    def constrain_yg(model, r):
        return sum(model.Lambda[j] * Ygv[j, r] for j in model.J) - model.s_g[r] == y0gv[r]

    # 非期望产出约束：参考点非期望产出 + 松弛 = 被评价 DMU 非期望产出
    def constrain_yb(model, z):
        return sum(model.Lambda[j] * Ybv[j, z] for j in model.J) + model.s_b[z] == y0bv[z]

    model.constrain_x = pyo.Constraint(model.I, rule=constrain_x)
    model.constrain_yg = pyo.Constraint(model.R, rule=constrain_yg)
    model.constrain_yb = pyo.Constraint(model.Z, rule=constrain_yb)

    # 规模报酬假设
    if vrs:
        def constrain_vrs(model):
            return sum(model.Lambda[j] for j in model.J) == 1.0
        model.constrain_vrs = pyo.Constraint(rule=constrain_vrs)

    return model


def build_model_super_cc(x0, y0g, y0b, X, Y_g, Y_b, k, vrs=False):
    """模型二：超效率（Tone 2002 扩展，剔除被评价 DMU 本身），用 Charnes-Cooper 线性化形式

    为什么不直接用分式 NLP？实测 ipopt 会因初值不同收敛到非最优的 KKT 点
    （上海 2024：分式解 19.40，CC-LP 真值 1.0219）
    CC 变换后是线性规划，全局最优有保证，且求解更快

    变换（t = 1/分母，Xbar = t*x̄，Ybar = t*ȳ，Λ = t*λ）：
        delta* = min (1/m) * sum(Xbar_i / x0_i)
        s.t. (1/(s1+s2)) * (sum(Ybar_g_r / y0g_r) + sum(Ybar_b_z / y0b_z)) = 1
             Xbar_i >= t*x0_i,                Xbar_i >= sum_{j!=k} Λ_j * X_ji
             Ybar_g_r <= sum_{j!=k} Λ_j * Y_g_jr,   Ybar_g_r <= t*y0g_r
             Ybar_b_z >= sum_{j!=k} Λ_j * Y_b_jz,   Ybar_b_z <= t*y0b_z
             t, Λ, Xbar, Ybar >= 0
    """
    n = X.shape[0]
    I = _valid_dim(x0)
    R = _valid_dim(y0g)
    Z = _valid_dim(y0b)
    m, s1, s2 = len(I), len(R), len(Z)
    if m == 0 or s1 + s2 == 0:
        raise ValueError("被评价 DMU 的投入或产出全部为 0，无法构建模型")

    x0v, Xv = x0[I], X[:, I]
    y0gv, Ygv = y0g[R], Y_g[:, R]
    y0bv, Ybv = y0b[Z], Y_b[:, Z]
    peers = [j for j in range(n) if j != k]   # 剔除被评价 DMU 本身

    model = pyo.ConcreteModel()
    model.t = pyo.Var(bounds=(0, None))
    model.L = pyo.Var(peers, bounds=(0, None))
    model.Xb = pyo.Var(range(m), bounds=(0, None))
    model.Ybg = pyo.Var(range(s1), bounds=(0, None))
    model.Ybb = pyo.Var(range(s2), bounds=(0, None))

    def objective_function(model):
        return (1 / m) * sum(model.Xb[i] / x0v[i] for i in range(m))

    model.obj = pyo.Objective(rule=objective_function, sense=pyo.minimize)

    def constrain_norm(model):
        return (1 / (s1 + s2)) * (
            sum(model.Ybg[r] / y0gv[r] for r in range(s1)) +
            sum(model.Ybb[z] / y0bv[z] for z in range(s2))) == 1

    def constrain_x0(model, i):
        return model.Xb[i] >= model.t * x0v[i]

    def constrain_xref(model, i):
        return model.Xb[i] >= sum(model.L[j] * Xv[j, i] for j in peers)

    def constrain_ygref(model, r):
        return model.Ybg[r] <= sum(model.L[j] * Ygv[j, r] for j in peers)

    def constrain_yg0(model, r):
        return model.Ybg[r] <= model.t * y0gv[r]

    def constrain_ybref(model, z):
        return model.Ybb[z] >= sum(model.L[j] * Ybv[j, z] for j in peers)

    def constrain_yb0(model, z):
        return model.Ybb[z] <= model.t * y0bv[z]

    model.constrain_norm = pyo.Constraint(rule=constrain_norm)
    model.constrain_x0 = pyo.Constraint(range(m), rule=constrain_x0)
    model.constrain_xref = pyo.Constraint(range(m), rule=constrain_xref)
    model.constrain_ygref = pyo.Constraint(range(s1), rule=constrain_ygref)
    model.constrain_yg0 = pyo.Constraint(range(s1), rule=constrain_yg0)
    model.constrain_ybref = pyo.Constraint(range(s2), rule=constrain_ybref)
    model.constrain_yb0 = pyo.Constraint(range(s2), rule=constrain_yb0)

    if vrs:
        def constrain_vrs(model):
            return sum(model.L[j] for j in peers) == model.t
        model.constrain_vrs = pyo.Constraint(rule=constrain_vrs)

    return model
