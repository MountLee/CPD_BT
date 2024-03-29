import numpy as np
import scipy.stats as stats
import random

import itertools

import bisect

from sklearn import linear_model

######### bt basic functions ########

def get_beta_with_gap(N, delta = 0.1):
    beta = np.arange(N) * delta
    beta = beta - np.mean(beta)
    return beta

def get_er_edge(n, m):
    """
    generate m edges uniformly randomly from a graph with n nodes
    """
    all_edge = np.where(np.triu(np.ones((n,n)), 1))
    ix = np.random.choice(n * (n - 1) // 2, m, replace = True)
    edge = [(all_edge[0][i], all_edge[1][i]) for i in ix]
    return edge

def get_X_from_edge(edge, n):
    m = len(edge)
    X = np.zeros((m, n))
    for i, e in enumerate(edge):
        X[i,e[0]] = 1
        X[i,e[1]] = -1
    return X

def get_X(n, m):
    edge = get_er_edge(n, m)
    return get_X_from_edge(edge, n)


def logistic(X, beta):
    beta = beta.reshape((-1,1))
#     t = np.clip(X @ beta, a_max = 1000, a_min = -1000)
    t = X @ beta
    exp = np.exp(t)
    return exp / (1 + exp)

def loglike_logistic(X, Y, beta):
    Y = Y.reshape((-1,1))
    beta = beta.reshape((-1,1))
    t = X @ beta
    res = Y.T @ t - np.sum(np.log(1 + np.exp(t)))
    return res.item()
#     prob = logistic(X, beta)
#     return np.sum(y * np.log(prob + 1e-8) + (1 - y) * np.log(1 - prob + 1e-8))
#     return np.sum(y * np.log(prob) + (1 - y) * np.log(1 - prob))

def grad_logistic(X, beta, y):
    prob = logistic(X, beta)
    return X.T @ (y.reshape((-1,1)) - prob)

def hessian_logistic(X, beta, y):
    prob = logistic(X, beta).reshape((len(y),))
#     return -(prob * (1 - prob) * X.T) @ X - 1e-8 * np.eye(X.shape[1])
    return -(prob * (1 - prob) * X.T) @ X

def bt_loss(beta, X_train, y_train, lam):
    return -loglike_logistic(X_train, y_train, beta) + lam / 2 * np.sum(beta**2)





#######################################
#### functions for general purpose
#######################################



def change_type(beta, type = 1):
    b = beta.copy()
    if type == 1:
        return b[::-1]
    elif type == 2:
        b = b[::-1]
        n = len(b)
        for i in range(n // 2):
            b[i], b[i + n // 2] = b[i + n // 2], b[i]
        return b
    elif type == 3:
        n = len(b)
        for i in range(n // 2):
            b[i], b[i + n // 2] = b[i + n // 2], b[i]
        return b
        

def generate_data_bt(m, T, beta):
    n = len(beta[0])
    X_train = [get_X(n, m[t]) for t in range(T)]
    y_train = np.concatenate([np.random.binomial(1, logistic(X_train[i], beta[i])) for i in range(T)], axis = 0)

    X_train = np.concatenate(X_train)
    X_train_joint = X_train.reshape((-1, n))
    y_train_joint = y_train.reshape((-1, ))
    nt = len(y_train_joint)
    
    return nt, y_train_joint, X_train_joint


def likelihood_interval(Y, X, s, e, lam = 0.1):
    Y = Y.reshape((-1,))
    nt, p = X.shape
    solver = linear_model.LogisticRegression(fit_intercept = False, penalty = 'l2', solver = 'lbfgs',
                                                C = 1/lam, random_state = 0, warm_start = True)
    solver.fit(X, Y)
    beta_hat = solver.coef_.squeeze()
    loglike = loglike_logistic(X, Y, beta_hat)

    return beta_hat, loglike


def likelihood_path(Y, X, sm, em, smooth_s = 100, smooth_e = 0, step = 1, lam = 0.1):
    """
    smooth parameter > 0
    """
    Y = Y.reshape((-1,))
    Y = Y[int(sm):int(em) + 1]
    X = X[int(sm):int(em) + 1]
    nt, p = X.shape

    if nt < (smooth_s + smooth_e):
        return None, None, None
    
    n = int((nt - smooth_s - smooth_e) // step) + 1
    beta_hat = np.zeros((n, p))
    loglike = np.zeros(n)
    sample_size = np.array([smooth_s + i * step for i in range(n)])

    solver = linear_model.LogisticRegression(fit_intercept = False, penalty = 'l2', solver = 'lbfgs',
                                                C = 1/lam, random_state = 0, warm_start = True)
    for i in range(n):
        loc = sample_size[i]
        X_cur, Y_cur = X[:loc], Y[:loc]
        solver.fit(X_cur, Y_cur)
        beta_i = solver.coef_
        beta_hat[i] = beta_i.squeeze().copy()
        loglike[i] = loglike_logistic(X_cur, Y_cur, beta_i)
    
    return beta_hat, loglike, sample_size


def glr_path(Y, X, sm, em, smooth = 100, step = 1, lam = 0.1):
    """
    Y: T x -1 array
    X: T x p array
    
    """
    Y = Y.reshape((-1,))
    Y = Y[int(sm):int(em) + 1]
    X = X[int(sm):int(em) + 1]
    nt = len(Y)
    
    beta_left, loglike_left, sample_size_left = likelihood_path(Y, X, 0, nt - 1, smooth, smooth, step, lam)
    resid = nt - sample_size_left[-1]
    beta_right, loglike_right, sample_size_right = likelihood_path(Y[::-1], X[::-1], 0, nt-1, resid, smooth, step, lam)
    
    return (beta_left, loglike_left, sample_size_left), (beta_right[::-1], loglike_right[::-1], sample_size_right[::-1])
    

def glr_path_test(Y, X, sm, em, smooth = 100, step = 1, lam = 0.1):
    """
    Y: T x -1 array
    X: T x p array
    
    """
    
    def likelihood_path_test(Y, X, sm, em, smooth_s = 100, smooth_e = 0, step = 1, lam = 0.1):
        def loglike_logistic(X, Y, beta):
            Y = Y.reshape((-1,1))
            beta = beta.reshape((-1,1))
            t = X @ beta
            res = Y.T @ t - np.sum(np.log(1 + np.exp(t)))
            return -res.item()

        Y = Y.reshape((-1,))
        Y = Y[int(sm):int(em) + 1]
        X = X[int(sm):int(em) + 1]
        nt, p = X.shape
        if nt < (smooth_s + smooth_e):
            return np.zeros(nt - 1)

        n = int((nt - smooth_s - smooth_e) // step) + 1
        beta_hat = np.zeros((n, p))
        loglike = np.zeros(n)
        sample_size = np.array([smooth_s + i * step for i in range(n)])

        return beta_hat, loglike, sample_size
    
    
    Y = Y.reshape((-1,))
    Y = Y[int(sm):int(em) + 1]
    X = X[int(sm):int(em) + 1]
    nt = len(Y)
    
    beta_left, loglike_left, sample_size_left = likelihood_path_test(Y, X, 0, nt - 1, smooth, smooth, step, lam)
    resid = nt - sample_size_left[-1]
    beta_right, loglike_right, sample_size_right = likelihood_path_test(Y[::-1], X[::-1], 0, nt-1, resid, smooth, step, lam)
    
    return sample_size_left, sample_size_right



########## online cpd ##########

def cp_distance(cp1, cp2):
    """
    Hausdoff distance between two sets of change points
    """
    cp1.sort()
    cp2.sort()
    cp2_ = np.concatenate([[-np.infty], cp2, [np.infty]])
    mx = -np.infty
    for x in cp1:
        y = bisect.bisect_left(cp2_, x)
        mx = max(mx, min(abs(cp2_[y - 1] - x), abs(cp2_[y] - x)))
    cp1_ = np.concatenate([[-np.infty], cp1, [np.infty]])
    for x in cp2:
        y = bisect.bisect_left(cp1_, x)
        mx = max(mx, min(abs(cp1_[y - 1] - x), abs(cp1_[y] - x)))
    return mx


########## WBS related functions ##########

##### wbs for bt with likelihood


class wbs_cv_covariate():
    def __init__(self, m_intervals, grid_n, lam_list, gamma_list, smooth = 10, buffer = 10):
        """
        smooth: length of smoothing window for cusum_func
        buffer: buffer for binary segmentation, when segmenting at bm, search (start, bm - buffer], (bm + buffer, end] 
        """
        self.m_intervals = m_intervals
        self.lam_list = lam_list
        self.gamma_list = gamma_list
        self.smooth = smooth
        self.buffer = buffer
        
        self.grid_n = grid_n

    def cusum_func(self, Y, X, grid, sm, em, lam, smooth):
        pass
    
    def goodness_of_fit(self, data_train, data_test, cp_loc, lam):
        pass

    def random_intervals(self, n, m):
        intervals = np.zeros((m, 2))
        intervals[:,0] = np.random.uniform(1, n - 1, m).astype(int)
        intervals[:,1] = np.random.uniform(1, n - 1, m).astype(int)
        for i in range(m):
            while intervals[i, 0] == intervals[i, 1]:
                intervals[i, :] = np.random.uniform(1, n - 1, 2).astype(int)
            intervals[i, :] = sorted(intervals[i, :])
        return intervals    
    

    def fit(self, data_train, data_test):
        X_train, Y_train = data_train
        X_test, Y_test = data_test

        fit_best = np.infty
        cp_best = None
        cp_val_best = None
        cusum_val_best = None
        t_best = None

        n = len(Y_train)
        step = max(n // self.grid_n, 1)
        grid = np.arange(0, n, step)
        
        lam_gamma_list = list(itertools.product(self.lam_list, self.gamma_list))
        for i, x in enumerate(lam_gamma_list):
            lam, gamma = x
            cp_loc, cp_val, cusum_val = self.wbs_func(Y_train, X_train, grid, lam, gamma)
            fit_cp = self.goodness_of_fit(data_train, data_test, cp_loc, lam)
            if fit_cp < fit_best:
                fit_best = fit_cp
                cp_best = cp_loc
                cp_val_best = cp_val
                cusum_val_best = cusum_val
                t_best = gamma
        return cp_best, cp_val_best, cusum_val_best, t_best, fit_best

    def wbs_func(self, Y, X, grid, lam, threshold):
        """
        wbs over the grid
        """
        n = len(grid)
        intervals = self.random_intervals(n, self.m_intervals)
        n_interval = len(intervals)
        cp_loc, cp_val = [], []
        cusum_val = np.zeros(n)

        def wbs_recurs(Y, X, start, end, intervals, threshold):
            nonlocal cp_loc, cp_val, cusum_val, n_interval, grid
            cand_loc, cand_val = np.zeros(n_interval), np.ones(n_interval) * -1
            for m in range(n_interval):
                sm, em = int(max(intervals[m][0], start)), int(min(intervals[m][1], end))
    #             print(sm)
    #             print(em)
                if em - sm > self.buffer:
                    cusum = self.cusum_func(Y, X, grid, sm, em, lam, smooth = self.smooth)
    #                 print("len" + str(len(cusum)))
                    for t in range(sm, em):
                        cusum_val[t] = cusum[t - sm]
    #                 print(np.argmax(cusum))
                    cand_loc[m] = sm + np.argmax(cusum)
                    cand_val[m] = cusum_val[int(cand_loc[m])]
            m_star = np.argmax(cand_val)
            if cand_val[m_star] > threshold:
                bm = int(cand_loc[m_star])
                cp_loc.append(int(bm))
                sm, em = int(max(intervals[m_star][0], start)), int(min(intervals[m_star][1], end))
    #             print("new cp: " + str(bm) + " with cusum " + str(cusum_val[bm]) + " in interval: " + str([sm, em]))
                wbs_recurs(Y, X, start, bm - self.buffer, intervals, threshold)
                wbs_recurs(Y, X, bm + self.buffer, end, intervals, threshold)

        wbs_recurs(Y, X, 0, n - 1, intervals, threshold)
        for loc in cp_loc:
            cp_val.append(cusum_val[loc])
        cp_loc = [grid[c] for c in cp_loc]
        return cp_loc, cp_val, cusum_val


    
class wbs_cv_bt(wbs_cv_covariate):
    def __init__(self, m_intervals, grid_n, lam_list, gamma_list, smooth = 10, buffer = 10):
        """
        smooth: length of smoothing window for cusum_func
        buffer: buffer for binary segmentation, when segmenting at bm, search (start, bm - buffer], (bm + buffer, end] 
        """
        self.m_intervals = m_intervals
        self.lam_list = lam_list
        self.gamma_list = gamma_list
        self.smooth = smooth
        self.buffer = buffer
        
        self.grid_n = grid_n
    
    def cusum_func(self, Y, X, grid, sm, em, lam = 0.1, smooth = 1):
        """
        Y: T x * array

        cusum_left[i]: summation of Y[grid[sm]],...,Y[grid[i]]
        cusum_right[i]: summation of Y[grid[i] + 1],...,Y[grid[em]]
        """
        Y_train = Y[grid[int(sm)]:grid[int(em)] + 1]
        X_train = X[grid[int(sm)]:grid[int(em)] + 1]

        grid_train = grid[int(sm):int(em) + 1]
        grid_train = [g - grid_train[0] for g in grid_train]

        nt = len(grid_train)

        if nt < 2 * smooth:
            return np.zeros(nt)

        beta_left = np.zeros_like(X_train)
        beta_right = np.zeros_like(X_train)
        loglike_left = np.zeros(nt)
        loglike_right = np.zeros(nt)
        loglike_sum = np.zeros(nt)

        solver = linear_model.LogisticRegression(fit_intercept = False, penalty = 'l2', solver = 'lbfgs',
                                                C = 1/lam, random_state = 0, warm_start = True)
        for i in range(smooth, nt - smooth):
            loc = grid_train[i] + 1
            X_cur, Y_cur = X_train[:loc], Y_train[:loc]
            solver.fit(X_cur, Y_cur)
            beta_i = solver.coef_
            beta_left[i] = beta_i.squeeze().copy()
            loglike_left[i] = loglike_logistic(X_cur, Y_cur, beta_i)

        solver.fit(X_train, Y_train)
        beta_joint = solver.coef_.squeeze()
        loglike_joint = loglike_logistic(X_train, Y_train, beta_joint)

        solver = linear_model.LogisticRegression(fit_intercept = False, penalty = 'l2', solver = 'lbfgs',
                                                C = 1/lam, random_state = 0, warm_start = True)
        for i in range(smooth, nt - smooth):
            loc = grid_train[nt - 1 - i] + 1
            X_cur, Y_cur = X_train[loc:], Y_train[loc:]
            solver.fit(X_cur, Y_cur)
            beta_i = solver.coef_
            beta_right[nt - 1 - i] = beta_i.squeeze().copy()
            loglike_right[nt - 1 - i] = loglike_logistic(X_cur, Y_cur, beta_i)

        loglike_sum = loglike_left + loglike_right - loglike_joint
        for i in range(smooth):
    #         loglike_sum[i] = loglike_sum[smooth]
    #         loglike_sum[-i-1] = loglike_sum[-smooth-1]
            loglike_sum[i] = 0
            loglike_sum[-i-1] = 0

        return loglike_sum

    def estimate_func(self, Y, X, lam, initial = None):
        Y = Y.reshape((-1,))
        if 0 not in Y or 1 not in Y:
            return np.zeros((X.shape[1], 1))
        
        logit = linear_model.LogisticRegression(fit_intercept = False, penalty = 'l2', solver = 'lbfgs',
                                                C = 1/lam, random_state = 0, max_iter = 50)
        logit.fit(X, Y)
        beta_hat = logit.coef_
        return beta_hat.reshape((-1,1))
    
    def goodness_of_fit(self, data_train, data_test, cp_loc, lam):
        X_train, Y_train = data_train
        X_test, Y_test = data_test

        nt = len(Y_train)
        cp_loc = np.concatenate([[0], cp_loc, [nt]])
        cp_loc = cp_loc.astype(int)
        res = []
        for i in range(len(cp_loc) - 1):
            if cp_loc[i + 1] > cp_loc[i] + 1:
                X_sub = X_train[cp_loc[i]:cp_loc[i + 1]]
                Y_sub = Y_train[cp_loc[i]:cp_loc[i + 1]]
                beta = self.estimate_func(Y_sub, X_sub, lam)

                X_sub = X_test[cp_loc[i]:cp_loc[i + 1]]
                Y_sub = Y_test[cp_loc[i]:cp_loc[i + 1]]
                loss = -loglike_logistic(X_sub, Y_sub, beta)
                res.append(loss)
        return np.mean(res)


########## dp related functions ##########


########## dp general


def cp_distance(cp1, cp2):
    """
    Hausdoff distance between two sets of change points
    """
    cp1.sort()
    cp2.sort()
    cp2_ = np.concatenate([[-np.infty], cp2, [np.infty]])
    mx = -np.infty
    for x in cp1:
        y = bisect.bisect_left(cp2_, x)
        mx = max(mx, min(abs(cp2_[y - 1] - x), abs(cp2_[y] - x)))
    cp1_ = np.concatenate([[-np.infty], cp1, [np.infty]])
    for x in cp2:
        y = bisect.bisect_left(cp1_, x)
        mx = max(mx, min(abs(cp1_[y - 1] - x), abs(cp1_[y] - x)))
    return mx


class dp_cv():
    def __init__(self, grid_n, lam_list, gamma_list, smooth = 100, buffer = 200):
        self.grid_n = grid_n
        self.lam_list = lam_list
        self.gamma_list = gamma_list
        self.smooth = smooth
        self.buffer = buffer
        
    def estimate_func(self, y, X, lam):
        pass

    def loss_func(self, Y, X, beta):
        pass
 
    def goodness_of_fit(self, data_train, data_test, cp_loc, lam, gamma):
        '''
        currently the penalty is not included in the value of goodness-of-fit
        '''
        Y_train, X_train = data_train
        Y_test, X_test = data_test
        
        n = len(Y_train)
        p = X_train.shape[1]
        cp_loc = np.concatenate([[0], cp_loc, [n]])
        cp_loc = cp_loc.astype(int)
        res = 0
        for i in range(len(cp_loc) - 1):
            if cp_loc[i + 1] > cp_loc[i] + np.log(p) + 1:
                Y_sub = Y_train[cp_loc[i]:cp_loc[i + 1]]
                X_sub = X_train[cp_loc[i]:cp_loc[i + 1]]
                estimate = self.estimate_func(Y_sub, X_sub, lam)
                
                Y_sub = Y_test[cp_loc[i]:cp_loc[i + 1]]
                X_sub = X_test[cp_loc[i]:cp_loc[i + 1]]
                res += self.loss_func(Y_sub, X_sub, estimate)
            else:
                res += 0
        return res
        
    def fit(self, data_train, data_test):
#         Y_train, X_train = data_train
#         Y_test, X_test = data_test

        lam_gamma_list = list(itertools.product(self.lam_list, self.gamma_list))
        # n_grid = len(lam_gamma_list)
        fit_res_best = np.infty
        cp_best = None
        param_best = None
        n = len(data_train[0])
        step = max(n // self.grid_n, 1)
        grid = np.arange(0, n, step)

        for i, x in enumerate(lam_gamma_list):
            lam, gamma = x
            cp_loc, obj = self.dp_grid(data_train, grid, lam, gamma)
            fit_res = self.goodness_of_fit(data_train, data_test, cp_loc, lam, gamma)
            if fit_res < fit_res_best:
                cp_best = cp_loc
                param_best = x
                fit_res_best = fit_res
        return cp_best, param_best


    def dp_grid(self, data, grid, lam, gamma):
        """
        data: (Y, X)
        Y: n x -1 array
        cp_loc: for each ix in cp_loc, it means theta[ix - 1] != theta[ix]
        """
        Y, X = data
        
        n = len(Y)
        point_map = np.ones(n + 1) * -1
        B = np.ones(n + 1) * np.infty
        B[0] = gamma

        r_cand = np.concatenate([[0], grid, [n]])
        grid_ix = {x:i for i, x in enumerate(r_cand)}
        l_cand = np.concatenate([[0], grid])
        m = len(grid)
        dp = [[np.infty] * (m + 2) for r in range(m + 1)]

        for r in r_cand:
            for l in l_cand:
                if l >= r:
                    break
                Y_sub = Y[l:r]
                X_sub = X[l:r]
                estimate = self.estimate_func(Y_sub, X_sub, lam)
                dp[grid_ix[l]][grid_ix[r]] = self.loss_func(Y_sub, X_sub, estimate)

        for r in r_cand:
            for l in l_cand:
                if l >= r:
                    break
                b = B[l] + gamma + dp[grid_ix[l]][grid_ix[r]]
                if b < B[r]:
                    B[r] = b
                    point_map[r] = l

        k = n
        cp_loc, cp_val = set([]), []
        while k > 0:
            h = int(point_map[k])
            if h > 0:
                cp_loc.add(h)
            k = h
        cp_loc = np.array(sorted(cp_loc))
        return cp_loc, B[-1]

    def dp_grid_test(self, data, grid, lam, gamma):
        """
        data: (Y, X)
        Y: n x -1 array
        cp_loc: for each ix in cp_loc, it means theta[ix - 1] != theta[ix]
        """
        Y, X = data
        
        n = len(Y)
        point_map = np.ones(n + 1) * -1
        B = np.ones(n + 1) * np.infty
        B[0] = gamma

        r_cand = np.concatenate([[0], grid, [n]])
        grid_ix = {x:i for i, x in enumerate(r_cand)}
        l_cand = np.concatenate([[0], grid])
        m = len(grid)
        dp = [[np.infty] * (m + 2) for r in range(m + 1)]

        for r in r_cand:
            for l in l_cand:
                if l >= r:
                    break
                Y_sub = Y[l:r]
                X_sub = X[l:r]
                estimate = self.estimate_func(Y_sub, X_sub, lam)
                dp[grid_ix[l]][grid_ix[r]] = self.loss_func(Y_sub, X_sub, estimate)

        for r in r_cand:
            for l in l_cand:
                if l >= r:
                    break
                b = B[l] + gamma + dp[grid_ix[l]][grid_ix[r]]
                if b < B[r]:
                    B[r] = b
                    point_map[r] = l

        k = n
        cp_loc, cp_val = set([]), []
        while k > 0:
            h = int(point_map[k])
            if h > 0:
                cp_loc.add(h)
            k = h
        cp_loc = np.array(sorted(cp_loc))
        return cp_loc, B, dp   
    
    
    
    
class dplr_cv(dp_cv):
    def __init__(self, grid_n, lam_list, gamma_list, smooth = 100, 
                 buffer = 200, step_refine = 1, buffer_refine = 30, lam_refine = 0.1):
        self.grid_n = grid_n
        self.lam_list = lam_list
        self.gamma_list = gamma_list
        
        self.smooth = smooth
        self.buffer = buffer
        
        self.step_refine = step_refine
        self.buffer_refine = buffer_refine
        self.lam_refine = lam_refine

    def joint_estimate_func(self, Y1, X1, Y2, X2, lam):
        pass
        
    def estimate_func(self, y, X, lam):
        pass
    
    def loss_func(self, Y, X, beta):
        pass
 
    def goodness_of_fit(self, data_train, data_test, cp_loc, lam, gamma):
        Y_train, X_train = data_train
        Y_test, X_test = data_test
        
        n = len(Y_train)
        p = X_train.shape[1]
        cp_loc = np.concatenate([[0], cp_loc, [n]])
        cp_loc = cp_loc.astype(int)
        res = 0
        for i in range(len(cp_loc) - 1):
            if cp_loc[i + 1] > cp_loc[i] + np.log(p) + 1:
                Y_sub = Y_train[cp_loc[i]:cp_loc[i + 1]]
                X_sub = X_train[cp_loc[i]:cp_loc[i + 1]]
                estimate = self.estimate_func(Y_sub, X_sub, lam)
                
                Y_sub = Y_test[cp_loc[i]:cp_loc[i + 1]]
                X_sub = X_test[cp_loc[i]:cp_loc[i + 1]]
                res += self.loss_func(Y_sub, X_sub, estimate)
            else:
                Y_sub = Y_test[cp_loc[i]:cp_loc[i + 1]]
                res += np.sum(Y_sub**2)
        return res

    def fit(self, data_train, data_test):
        lam_gamma_list = list(itertools.product(self.lam_list, self.gamma_list))
        # n_grid = len(lam_gamma_list)
        fit_res_best = np.infty
        cp_best = None
        param_best = None
        n = len(data_train[0])
        step = max(n // self.grid_n, 1)
        grid = np.arange(0, n, step)

        for i, x in enumerate(lam_gamma_list):
            lam, gamma = x
            cp_loc, obj = self.dp_grid(data_train, grid, lam, gamma)
            cp_loc_refined = self.local_refine(data_train, cp_loc)
            fit_res = self.goodness_of_fit(data_train, data_test, cp_loc_refined, lam, gamma)
            if fit_res < fit_res_best:
                cp_best = cp_loc_refined
                cp_best_cand = cp_loc
                param_best = x
                fit_res_best = fit_res
        return cp_best, param_best, cp_best_cand

    def local_refine(self, data, cp_cand):
        n = len(data[0])
        K = len(cp_cand)
        cp_cand = np.concatenate([[0], cp_cand[:], [n]])
        cp_loc = []
        for i in range(1, K + 1):
            if cp_cand[i - 1] + 2 * self.buffer_refine > cp_cand[i]:
                continue
            st, ed = int(2/3 * cp_cand[i - 1] + 1/3 * cp_cand[i]), int(2/3 * cp_cand[i + 1] + 1/3 * cp_cand[i])
            cp = self.screen_cp(data, st, ed)
            if cp is not None:
                cp_loc.append(cp)
        return cp_loc

    def screen_cp(self, data, st, ed):
        '''
        currently not using group lasso in refinement
        '''
        Y, X = data
        buffer_refine = self.buffer_refine
        step_refine = self.step_refine
        
        if st + 2 * buffer_refine + step_refine >= ed:
            return None
        n_step = (ed - st - 2 * buffer_refine - 1) // step_refine + 1

        loss_min = np.infty
        loc_min = None
        for i in range(1, n_step):
            loc = st + buffer_refine + int(i * step_refine)
            theta_1, theta_2 = self.joint_estimate_func(Y[st:loc],
                                                        X[st:loc],
                                                        Y[loc:ed],
                                                        X[loc:ed],self.lam_refine)
            loss_split = self.loss_func(Y[st:loc], 
                                        X[st:loc], theta_1)
            loss_split += self.loss_func(Y[loc:ed],
                                         X[loc:ed], theta_2)
            if loss_split < loss_min:
                loss_min = loss_split
                loc_min = st + buffer_refine + int(i * step_refine)
        return loc_min
    
    def local_refine_test(self, data, cp_cand):
        n = len(data[0])
        K = len(cp_cand)
        cp_cand = np.concatenate([[0], cp_cand[:], [n]])
        cp_loc = []
        for i in range(1, K + 1):
            if cp_cand[i - 1] + 2 * self.buffer_refine > cp_cand[i]:
                continue
            st, ed = int(2/3 * cp_cand[i - 1] + 1/3 * cp_cand[i]), int(2/3 * cp_cand[i + 1] + 1/3 * cp_cand[i])
            cp = self.screen_cp(data, st, ed)
            if cp is not None:
                cp_loc.append(cp)
        return cp_loc

    def screen_cp_test(self, data, st, ed):
        Y, X = data
        buffer_refine = self.buffer_refine
        step_refine = self.step_refine
        
        if st + 2 * buffer_refine + step_refine >= ed:
            return None
        n_step = (ed - st - 2 * buffer_refine - 1) // step_refine + 1

        loss_min = np.infty
        loc_min = None
        loss_list = []
        loc_list = []
        
        for i in range(1, n_step):
            loc = st + buffer_refine + int(i * step_refine)
            theta_1, theta_2 = self.joint_estimate_func(Y[st:loc],
                                                        X[st:loc],
                                                        Y[loc:ed],
                                                        X[loc:ed],self.lam_refine)
            loss_split = self.loss_func(Y[st:loc], 
                                        X[st:loc], theta_1)
            loss_split += self.loss_func(Y[loc:ed],
                                         X[loc:ed], theta_2)
            
            loss_list.append(loss_split)
            loc_list.append(loc)
            
            if loss_split < loss_min:
                loss_min = loss_split
                loc_min = st + buffer_refine + int(i * step_refine)
        return loc_min, loss_list, loc_list





##### specialized for BT






class dp_cv_bt(dp_cv):
    def __init__(self, grid_n, lam_list, gamma_list, smooth = 100, buffer = 200):
        self.grid_n = grid_n
        self.lam_list = lam_list
        self.gamma_list = gamma_list
        self.smooth = smooth
        self.buffer = buffer
        
    def estimate_func(self, Y, X, lam, initial = None):
#         fit = lr_newton_solver_linear(X, y)

#         sm_model = sm.OLS(y, (X)).fit(disp=0)
#         beta_hat = sm_model.params


        Y = Y.reshape((-1,))
        if 0 not in Y or 1 not in Y:
            return np.zeros((X.shape[1], 1))

#         beta_hat = bt_newton_solver(X, Y, initial, lam)
        
        logit = linear_model.LogisticRegression(fit_intercept = False, penalty = 'l2', solver = 'lbfgs',
                                                C = 1/lam, random_state = 0, max_iter = 50)
#         logit = linear_model.LogisticRegression(fit_intercept = False, penalty = 'none', solver = 'lbfgs',
#                                                 random_state = 0)
# #         logit = linear_model.LogisticRegression(fit_intercept = False, penalty = 'none', solver = 'lbfgs',
# #                                                 C = 1/lam, random_state = 0)
        logit.fit(X, Y)
        beta_hat = logit.coef_
        return beta_hat.reshape((-1,1))

    def loss_func(self, Y, X, beta):
        '''
        the negative loglikelihood
        currently the penalty is not included in the value of loss
        '''
        Y = Y.reshape((-1,1)) 
        t = X @ beta
        l = -Y.T @ t + np.sum(np.log(1 + np.exp(t)))
        return l.squeeze()


class dplr_cv_bt(dplr_cv):
    def __init__(self, grid_n, lam_list, gamma_list, smooth = 100, 
                 buffer = 200, step_refine = 1, buffer_refine = 30, lam_refine = 0.1):
        self.grid_n = grid_n
        self.lam_list = lam_list
        self.gamma_list = gamma_list
        
        self.smooth = smooth
        self.buffer = buffer
        
        self.step_refine = step_refine
        self.buffer_refine = buffer_refine
        self.lam_refine = lam_refine

    def joint_estimate_func(self, Y1, X1, Y2, X2, lam):
        Y1 = Y1.reshape((-1,))
        Y2 = Y2.reshape((-1,))

#         if set(np.unique(Y1)) != set([0,1]):
        if 0 not in Y1 or 1 not in Y1:
            beta_hat1 = np.zeros((X1.shape[1], 1))
        else:
            logit = linear_model.LogisticRegression(fit_intercept = False, penalty = 'l2', solver = 'lbfgs',
                                                    C = 1/lam, random_state = 0, max_iter = 50)
            logit.fit(X1, Y1)
            beta_hat1 = logit.coef_
        
#         if set(np.unique(Y1)) != set([0,1]):
        if 0 not in Y2 or 1 not in Y2:
            beta_hat2 = np.zeros((X2.shape[1], 1))
        else:
            logit = linear_model.LogisticRegression(fit_intercept = False, penalty = 'l2', solver = 'lbfgs',
                                                    C = 1/lam, random_state = 0, max_iter = 50)
            logit.fit(X2, Y2)
            beta_hat2 = logit.coef_
        
        return beta_hat1.reshape((-1,1)), beta_hat2.reshape((-1,1))
    
    def estimate_func(self, y, X, lam):
#         fit = lr_newton_solver_linear(X, y)

#         sm_model = sm.OLS(y, (X)).fit(disp=0)
#         beta_hat = sm_model.params
#         if set(np.unique(y)) != set([0,1]):
        y = y.reshape((-1,))
        if 0 not in y or 1 not in y:
            return np.zeros((X.shape[1], 1))

        logit = linear_model.LogisticRegression(fit_intercept = False, penalty = 'l2', solver = 'lbfgs',
                                                C = 1/lam, random_state = 0, max_iter = 50)
        logit.fit(X, y)
        beta_hat = logit.coef_
        return beta_hat.reshape((-1,1))

    def loss_func(self, Y, X, beta):
        '''
        the negative loglikelihood
        currently the penalty is not included in the value of loss
        '''
        Y = Y.reshape((-1,1)) 
        t = X @ beta
        l = -Y.T @ t + np.sum(np.log(1 + np.exp(t)))
        return l.squeeze()