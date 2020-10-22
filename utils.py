import numpy as np
from patsy import dmatrix
import statsmodels.api as sm
import pandas as pd
import scipy as sp
import warnings
import os
from torch import nn
import torch
import parser
from patsy.util import have_pandas, no_pickling, assert_no_pickling
from patsy.state import stateful_transform

from statsmodels.gam.api import CyclicCubicSplines, BSplines


def _checkups(params, formulas):
    """
    Checks if the user has given an available distribution, too many formulas or wrong parameters for the given distribution
    Parameters
    ----------
        params : list of strings
            A list of strings of the parameters of the current distribution

        formulas : dictionary
            A dictionary with keys corresponding to the parameters of the distribution defined by the user and values to strings defining the
            formula for each distribution, e.g. formulas['loc'] = '~ 1 + spline(x1, bs="bs", df=9) + dm1(x2)'
            
            
    Returns
    -------
        new_formulas : dictionary
            If the current distribution is available in the list of families, new_formulas holds a formula for each parameter of the distribution.
            If a formula hasn't been given for a parameter and ~0 formula is set. If the current distribution is not available an empty dictionary
            is returned.  
    """
    new_formulas=dict()
    for param in params:
        if param in formulas:
            new_formulas[param] = formulas[param]
        # define an empty formula for parameters for which the user has not specified a formula
        else:
            print('Parameter formula', param,'for distribution not defined. Creating a zero formula for it.')
            new_formulas[param] = '~0'
    return new_formulas

def _split_formula(formula, net_names_list):
    """
    Splits the formula into two parts - the structured and unstructured part
    Parameters
    ----------
        formula : string
            The formula to be split, e.g. '~ 1 + bs(x1, df=9) + dm1(x2, df=9)'
            
        net_names_list : list of strings
            A list of all newtwork names defined by the user
            
    Returns
    -------
        structured_part : string
            A string holding only the structured part of the original formula
        unstructured_terms: list of strings
            A list holding all the unstructured parts of the original formula   
    """
    structured_terms = []
    unstructured_terms = []
    # remove spaces the tilde and split into formula terms
    formula = formula.replace(' ','')
    formula = formula.replace('~','')
    formula_parts = formula.split('+')
    # for each formula term
    for part in formula_parts:
        term = part.split('(')[0]
        # if it an unstructured part
        if term in net_names_list:
            # append it to a list
            unstructured_terms.append(part)
        else:
            structured_terms.append(part)
    # join the structured terms together again
    structured_part = '+'.join(structured_terms)    
    return structured_part, unstructured_terms


class Spline(object):
    """
     Class for computation of spline basis functions and and smooting penalty matrix for differents types of splines (BSplines, Cyclic cubic splines).
     Compatible with patsy statefull transform.
    
     Parameters
     ----------
         x: Pandas.DataFrame
             A data frame holding all the data 
         bs: string, default is 'bs'
             The type of splines to use - default is b splines, but can also use cyclic cubic splines if bs='cc'
         df: int, default is 4
             Number of degrees of freedom (equals the number of columns in s.basis)
         degree: int, default is 3
             degree of polynomial e.g. 3 -> cubic, 2-> quadratic
         return_penalty: bool, default is False
             has no function - necessary for backwards compatibility with the tests. Should be cleaned up at some point.
     Returns
     -------
         The function returns one of:
         s.basis: The basis functions of the spline
         s.penalty_matrices: The penalty matrices of the splines 
     """
    def __init__(self):
        pass

    def memorize_chunk(self, x, bs, df=4, degree=3, return_penalty = False):
        assert bs == "bs" or bs == "cc", "Spline basis not defined!"
        if bs == "bs":
            self.s = BSplines(x, df=[df], degree=[degree], include_intercept=True)
        elif bs == "cc":
            self.s = CyclicCubicSplines(x, df=[df])
        
        self.penalty_matrices = self.s.penalty_matrices

    def memorize_finish(self):
        pass


    def transform(self, x, bs, df=4, degree=3, return_penalty = False):
        
        return self.s.transform(np.expand_dims(x.to_numpy(),axis=1)) 
            

    __getstate__ = no_pickling

spline = stateful_transform(Spline) #conversion of Spline class to patsy statefull transform


def make_matrix_positive_semi_definite(A,machine_epsilon):

    #get smallest eigenvalue for a symmetric matrix
    #and use some additional tolerance to ensure semipositive definite matrices
    min_eigen = min(np.linalg.eigh(A)[0]) - np.sqrt(machine_epsilon)

    # smallest eigenvalue negative = not semipositive definit
    if min_eigen < -1e-10:
        rho = 1 / (1 - min_eigen)
        A = rho * A + (1 - rho) * np.identity(A.shape[0])

        ## now check if it is really positive definite by recursively calling
        A = make_matrix_positive_semi_definite(A)

    return (A)

def dfFun(lam, d, hat1):
    if hat1:
        res = sum(1 / (1 + lam * d))
    else:
        res = 2 * sum(1 / (1 + lam * d)) - sum(1 / (1 + lam * d) ^ 2)
    return res

def df2lambda(dm, P, df, lam = None, hat1 = True, lam_max = 1e+15):

    #dm = dm.to_numpy()
    machine_epsilon = np.finfo(float).eps * 2

    # throw exception if neither df nor lambda is given
    if df == None and lam == None:
        raise Exception('Either degrees of freedom or lambda has to be provided.')

    # check if rank of design matrix is large enough for given df
    if df != None:
        rank_dm = np.linalg.matrix_rank(dm)
        if df >= rank_dm:
            warnings.simplefilter('error')
            warnings.warn("""df too large: Degrees of freedom (df = {0}) cannot be larger than the rank of the design matrix (rank = {1}). Unpenalized base-learner with df = {1} used. Re-consider model specification.""".format(df,rank_dm))
            lam = 0
            return df, lam

    # if lambda is given, but equal 0, return rank of design matrix as df
    if lam != None:
        if lam == 0:
            df = np.linalg.matrix_rank(dm)
            return df, lam


    # otherwise compute df or lambda
    XtX = dm.T @ dm

    ## avoid that XtX matrix is not (numerically) singular and make sure that A is also numerically positiv semi-definit
    A = XtX + P * 1e-15
    A = make_matrix_positive_semi_definite(A,machine_epsilon)

    #make sure that A is also numerically symmetric
    #A = np.triu(A) + np.triu(A).T - np.diag(np.diag(A))
    Rm = sp.linalg.solve_triangular(sp.linalg.cholesky(A, lower=False), np.identity(XtX.shape[1]))

    # singular value decomposition --> might be possible to speed up if set 'hermitian = True'
    try:
        # try compuattion without computing u and vh
        d = np.linalg.svd((Rm.T @ P) @ Rm, compute_uv = False)
    except:
        ## if unsucessfull try the same computation but compute u and vh as well
        d = np.linalg.svd((Rm.T @ P) @ Rm, compute_uv=True)[1] # vector with singular values

    if lam != None:
        df = dfFun(lam,d,hat1)
        return df, lam

    if df >= len(d):
        lam = 0
        return df, lam

    df_for_lam_max = dfFun(lam_max, d, hat1)
    if (df_for_lam_max - df) > 0 and (df_for_lam_max - df) > np.sqrt(machine_epsilon):
        warnings.simplefilter('error')
        warnings.warn("""lambda needs to be larger than lambda_max = {0} for given df. Settign lambda to {0} leeds to an deviation from your df of {1}. You can increase lambda_max in parameters. """.format(lam_max,df_for_lam_max - df))
        lam = lam_max
        return df, lam

    lam = sp.optimize.brentq(lambda l: dfFun(l, d, hat1) - df, 0, lam_max)
    if abs(dfFun(lam, d, hat1) - df) > np.sqrt(machine_epsilon):
        warnings.simplefilter('error')
        warnings.warn("""estimated df differ from given df by {0} """.format(dfFun(lam, d, hat1) - df))

    return df, lam


def _get_penalty_matrix_from_factor_info(factor_info):
    '''
    Extracts the penalty matrix from a factor_info object if the factor infor object is a spline.
    Explanation: "spline" is a statefull pasty transform. After computation of the design matrix these statefull transforms are stored in the factor infos of the design matrix. In this function we extract this object and obtain the penalty matrix that corresponds to this spline.
    
     Parameters
     ----------
         factor_info: patsy factor info object
             
     Returns
     -------
         P: numpy-array or False
             Penalty matrix of the spline term or False
        
    '''


    factor = factor_info.factor
    
    if 'spline' not in factor.name():
        P = False #factor is not a spline, so there is not penalty matrix
        return P
    
    outer_objects_in_factor = factor_info.state['pass_bins'][-1] #a factor can be nested e.g. Spline(center(x)). The outer objects (e.g. Spline) are the last in the list 'pass_bins'
    obj_name = next(iter(outer_objects_in_factor)) #use last=outermost object in factor. should only have a single element in the set. Explanation: the 'pass_bins' list contains tuples. e.g. if an object is Spline(center(x1)+center(x2)) then 'pass_bins' is a list with two tuples, where the first tuple containts the name of the two center objects. There should only be one element in the outer tuple and this is extracted here(we will check later, that this tuple contains indeed only one element)
    obj = factor_info.state['transforms'][obj_name] #obtain the actal statefull transform object that corresponds to the extracted object name

    if (len(outer_objects_in_factor)==1) and isinstance(obj, Spline): #check if the tuple indeed contained only one element and that the obtained object is a spline. If both is true obatain and return the penalty matrix of this spline.
        P = obj.penalty_matrices
        return P

    else:
        P = False #factor is not a spline, so there is not penalty matrix
        return P 

def _get_P_from_design_matrix(dm, data, dfs):
    """
    Computes and returns the penalty matrix that corresponds to a patsy design matrix. The penalties are multiplied by the regularization parameters lambda computed from given degrees of freedom. The result us a single block diagonal penalty matrix that combines the penalty matrices of each term in the formula that was used to create the design matrix. Only smooting splines terms have a non-zero penalty matrix.
    The degrees of freedom can either be given as a single value, then all individual penalty matrices are mutliplied with a single lambda. Or they can be given as a list, then all (non-zero) penalty matrices are mutliplied by different lambdas. The mutliplication is in the order of the terms in the formula.
    
    Parameters
    ----------
        dm: patsy.dmatrix
            The design matrix for the structured part of the formula - computed by patsy
        data: Pandas.DataFrame
            A data frame holding all features from which the design matrix was created
        dfs: float or list of floats
            Either a single smooting parameter for all penalities of all splines for this parameter, or a list of smoothing parameters, each for one of the splines that appear in the formula for this parameter
    Returns
    -------
        big_P: numpy array
            The penalty matrix of the design matrix
    """
    factor_infos = dm.design_info.factor_infos
    terms = dm.design_info.terms
    
    big_P = np.zeros((dm.shape[1],dm.shape[1]))
    
    column_counter = 0
    spline_counter = 0
    
    for term in terms:
        dm_term_name = term.name()
        # get the slice object for this term (corresponding to start and end index in the designmatrix)
        slice_of_term = dm.design_info.term_name_slices[dm_term_name] 
        

        if len(term.factors) == 1: #currently we only use smoothing for 1D, in the future we also want to add smoothing for tensorproducts
            factor_info = factor_infos[term.factors[0]]
            num_columns = factor_info.num_columns
            
            P = _get_penalty_matrix_from_factor_info(factor_info)
                
            if P is not False:
                df = dfs[spline_counter] if type(dfs) == list else dfs
                dm_spline = dm.iloc[:,slice_of_term]
                # regularization parameters are given in degrees of freedom. Here they are converted to lambda.
                df_lam = df2lambda(dm_spline, P[0], df)
                big_P[slice_of_term,slice_of_term] = P[0]*df_lam[1]
                
                spline_counter += 1
            column_counter += num_columns

    return big_P

def _get_input_features_for_functional_expression(functional_expression : str, feature_names : list):
    '''
    Parses variables from a functional expression using the python parser
    Parameters
    ----------
        functional_expression: string
            functional expression from which to extract the input features like "spline(x1,x2, bs="bs", df=4, degree=3)"
            
        feature_names: set
            set of all possible feature names in the data set like [x1,x2,x3,x4,x5]
            
    Returns
    -------
        input_features: list
            list of feature names that appear as input in functional_expression. here in the example ["x1","x2"]
    '''
    co_names = parser.expr(functional_expression).compile().co_names #co names are local variables of functions in a python expression
    co_names_set = set(co_names)
    input_features = list(co_names_set.intersection(set(feature_names)))
    return input_features


def _get_all_input_features_for_term(term, feature_names):
    '''
    Extracts all feature names that appear in a patsy term. For this it loops through all factors and uses then a python code paser to extract input variables.
    Parameters
    ----------
        term: patsy term object
            patsy term object for which the feature names should be extracted
            
        feature_names: list
            list of all possible feature names in the data set like [x1,x2,x3,x4,x5]
            
    Returns
    -------
        input_features_term: list
            list of feature names that appear in the patsy term. e.g. for a term x1:spline(x2, bs="bs", df=4, degree=3) -> ["x1","x2"]
    '''
    
    factors = term.factors
    input_features_term = set()
    for factor in factors:
        factor_name = factor.name()
        input_features_factor = _get_input_features_for_functional_expression(factor_name, list(feature_names))
        input_features_term = input_features_term.union(set(input_features_factor))
        
    input_features_term = list(input_features_term)
    return input_features_term

def _get_info_from_design_matrix(structured_matrix, feature_names):
    """
    Parses the formulas defined by the user and returns a dict of dicts which can be fed into SDDR network
    Parameters
    ----------
        structured_matrix: patsy.dmatrix
            The design matrix for the structured part of the formula - computed by patsy
    Returns
    -------
        list_of_spline_slices: list of slice objects
            A list containing slices in the design matrix that correspond to a spline-term e.g. "spline(x2, bs="bs", df=4, degree=3)" or "x1:spline(x2, bs="bs", df=4, degree=3)"
        list_of_spline_input_features: list of strings
            A list of lists. Each item in the parent list corresponds to a term that contains a spline and 
            is a list of the names of the features (used to compute the design matrix) sent as input into that spline.
    """
    spline_info = {'list_of_spline_slices': [],
                   'list_of_spline_input_features': [],
                   'list_of_term_names' : []}
    
    non_spline_info = {'list_of_non_spline_slices': [],
                       'list_of_non_spline_input_features': [],
                       'list_of_term_names' : []}
    
    for term in structured_matrix.design_info.terms:
        dm_term_name = term.name()

        # get the feature names sent as input to each spline
        feature_names_spline = _get_all_input_features_for_term(term, feature_names)

        # get the slice object for this term (corresponding to start and end index in the designmatrix)
        slice_of_term = structured_matrix.design_info.term_name_slices[dm_term_name] 

        # append to lists
        if 'spline' in dm_term_name:
            spline_info['list_of_spline_input_features'].append(feature_names_spline)
            spline_info['list_of_spline_slices'].append(slice_of_term)
            spline_info['list_of_term_names'].append(dm_term_name)
        else:
            non_spline_info['list_of_non_spline_input_features'].append(feature_names_spline)
            non_spline_info['list_of_non_spline_slices'].append(slice_of_term)
            non_spline_info['list_of_term_names'].append(dm_term_name)
            
    return spline_info, non_spline_info


def _orthogonalize(constraints, X):
    
    Q, _ = np.linalg.qr(constraints) # compute Q
    Projection_Matrix = np.matmul(Q,Q.T)
    constrained_X = X - np.matmul(Projection_Matrix,X)
    
    return constrained_X

def _orthogonalize_spline_wrt_non_splines(structured_matrix, 
                                         spline_info, 
                                         non_spline_info):
    
    for spline_slice, spline_input_features in zip(spline_info['list_of_spline_slices'], 
                                                   spline_info['list_of_spline_input_features']):
        
        X = structured_matrix.iloc[:,spline_slice]
        # construct constraint matrix
        constraints = []
        for non_spline_slice, non_spline_input_features in zip(non_spline_info['list_of_non_spline_slices'], non_spline_info['list_of_non_spline_input_features']):
            if set(non_spline_input_features).issubset(set(spline_input_features)):
                constraints.append(structured_matrix.iloc[:,non_spline_slice].values)

        if len(constraints)>0:
            constraints = np.concatenate(constraints,axis=1)
            constrained_X = _orthogonalize(constraints, X)
            structured_matrix.iloc[:,spline_slice] = constrained_X

def parse_formulas(family, formulas, data, deep_models_dict, degrees_of_freedom, verbose=False):
    """
    Parses the formulas defined by the user and returns a dict of dicts which can be fed into SDDR network
    Parameters
    ----------
        family: dictionary
            A dictionary holding all the available distributions as keys and values are again dictionaries with the 
            parameters as keys and values the formula which applies for each parameter 
        formulas: dictionary
            A dictionary with keys corresponding to the parameters of the distribution defined by the user and values
            to strings defining the formula for each distribution, e.g. formulas['loc'] = '~ 1 + spline(x1, bs="bs", df=9) + dm1(x2)'
        data: Pandas.DataFrame
            A data frame holding all the data 
        cur_distribution : string
            The current distribution defined by the user
        deep_models_dict: dictionary 
            A dictionary where keys are model names and values are dicts with model architecture and output shapes
        degrees_of_freedom: dict
            A dictionary where keys are the name of the distribution parameter (e.g. eta,scale) and values 
            are either a single smooting parameter for all penalities of all splines for this parameter, or a list of smooting parameters, each for one of the splines that appear in the formula for this parameter
            
    Returns
    -------
        parsed_formula_contents: dictionary
            A dictionary where keys are the distribution's parameter names and values are dicts. The keys of these dicts 
            will be: 'struct_shapes', 'P', 'deep_models_dict' and 'deep_shapes' with corresponding values
        meta_datadict: dictionary
            A dictionary where keys are the distribution's parameter names and values are dicts. The keys of these dicts 
            will be: 'structured' and neural network names if defined in the formula of the parameter (e.g. 'dm1'). Their values 
            are the data for the structured part (after smoothing for the non-linear terms) and unstructured part(s) of the SDDR 
            model 
         dm_info_dict: dictionary
            A dictionary where keys are the distribution's parameter names and values are dicts containing: a bool of whether the
            formula has an intercept or not and a list of the degrees of freedom of the splines in the formula and a list of the inputs features for each spline
    """
    # perform checks on given distribution name, parameter names and number of formulas given
    formulas = _checkups(family.get_params(), formulas)
    meta_datadict = dict()
    parsed_formula_contents = dict()
    struct_list = []
    dm_info_dict = dict()
    
    # for each parameter of the distribution
    for param in formulas.keys():
        meta_datadict[param] = dict()
        parsed_formula_contents[param] = dict()
        
        dfs = degrees_of_freedom[param]
        
        # split the formula into sructured and unstructured parts
        structured_part, unstructured_terms = _split_formula(formulas[param], list(deep_models_dict.keys()))
        
        # print the results of the splitting if verbose is set
        if verbose:
            print('results from split formula')
            print(structured_part)
            print(unstructured_terms)
            
        # if there is not structured part create a null model
        if not structured_part:
            structured_part='~0'
            
        # create the structured matrix from the structured part of the formula - based on patsy
        structured_matrix = dmatrix(structured_part, data, return_type='dataframe')
        
        # get bool depending on if formula has intercept or not and degrees of freedom and input feature names for each spline
        spline_info, non_spline_info = _get_info_from_design_matrix(structured_matrix, feature_names = data.columns)
        dm_info_dict[param] = spline_info
        
        # compute the penalty matrix
        P = _get_P_from_design_matrix(structured_matrix, data, dfs)
        
        #orthogonalize splines with respect to non-splines (including an intercept if it is there)
        _orthogonalize_spline_wrt_non_splines(structured_matrix, 
                                         spline_info, 
                                         non_spline_info)
        
        # add content to the dicts to be returned
        meta_datadict[param]['structured'] = structured_matrix.values
        parsed_formula_contents[param]['struct_shapes'] = structured_matrix.shape[1]
        parsed_formula_contents[param]['P'] = P
        parsed_formula_contents[param]['deep_models_dict'] = dict()
        parsed_formula_contents[param]['deep_shapes'] = dict()
        
        # if there are unstructured terms in the formula (returned from split_formula)
        if unstructured_terms:
            
            # for each unstructured term of the unstructured part of the formula
            for term in unstructured_terms:
                
                # get the feature name as input to each term
                term_split = term.split('(')
                net_name = term_split[0]
                feature_names = term_split[1].split(')')[0]
                
                # create a list of feature names if there are multiple inputs in term
                feature_names_list = feature_names.split(',')
                
                # and create the unstructured data
                unstructured_data = data[feature_names_list]
                unstructured_data = unstructured_data.to_numpy()
                meta_datadict[param][net_name] = unstructured_data
                
                #store deep models given by the user in a deep model dict that corresponds to the parameter in which this deep model is used
                # if the deeps models are given as string, evaluate the expression first
                if isinstance(deep_models_dict[net_name]['model'],str):
                    parsed_formula_contents[param]['deep_models_dict'][net_name]= eval(deep_models_dict[net_name]['model'])
                else:
                    parsed_formula_contents[param]['deep_models_dict'][net_name]= deep_models_dict[net_name]['model']
                    
                parsed_formula_contents[param]['deep_shapes'][net_name] = deep_models_dict[net_name]['output_shape']
                
    return parsed_formula_contents, meta_datadict,  dm_info_dict

