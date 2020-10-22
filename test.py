import unittest

import numpy as np
from torch import nn
import pandas as pd

import unittest

from dataset import SddrDataset

from patsy import dmatrix
import statsmodels.api as sm
from utils import parse_formulas, Spline, spline, _orthogonalize_spline_wrt_non_splines, _get_info_from_design_matrix, df2lambda
from family import Family


class TestSddrDataset(unittest.TestCase):
    '''
    Test SddrDataset for model with a linear part, splines and deep networks using the iris data set. 
    
    It is tested 
        - if get_list_of_feature_names() returns the correct list of feature names of the features from the input dataset.
        - if get_feature(feature_name) returns the correct features (shape and value)
        - if the structured part and the input to the deep network are in meta_datadict are correct (shape and value)
        - if the correct target (shape and value) are returned)
        
    We do not check parsed_formula_content and dm_info_dict herem as they are tested by Testparse_formulas.
    '''


    def __init__(self,*args,**kwargs):

        super(TestSddrDataset, self).__init__(*args,**kwargs)


        #define distribution
        self.current_distribution  = 'Poisson'
        self.family = Family(self.current_distribution)


        #define formulas and network shape
        self.formulas = {'rate': '~1 + x1 + x2 + spline(x1, bs="bs",df=9) + spline(x2, bs="bs",df=9)+d1(x1)+d2(x2)'}

        self.deep_models_dict = {
            'd1': {
                'model': nn.Sequential(nn.Linear(1,15)),
                'output_shape': 15},
            'd2': {
                'model': nn.Sequential(nn.Linear(1,3),nn.ReLU(), nn.Linear(3,8)),
                'output_shape': 8}
        }

        self.train_parameters = {
            'batch_size': 1000,
            'epochs': 2500,
            'degrees_of_freedom': {'rate': 4}
        }


        # load data
        self.data_path = './test_data/x.csv'
        self.ground_truth_path = './test_data/y.csv'

        self.data = pd.read_csv(self.data_path ,sep=None,engine='python')
        self.target = pd.read_csv(self.ground_truth_path)

        self.true_feature_names = ["x1", "x2", "x3", "x4"]
        self.true_x2_11 = np.float32(self.data.x2[11])
        self.true_target_11 = self.target.values[11]


    def test_pandasinput(self):
        """
        Test if SddrDataset correctly works with a pandas dataframe as input.
        """


        # load data
        data = pd.concat([self.data, self.target], axis=1, sort=False)

        dataset = SddrDataset(data = data, 
                              target = "y",
                              family = self.family,
                              formulas=self.formulas,
                              deep_models_dict=self.deep_models_dict,
                              degrees_of_freedom = self.train_parameters['degrees_of_freedom'])

        feature_names = dataset.get_list_of_feature_names()
        feature_test_value = dataset.get_feature('x2')[11]
        linear_input_test_value = dataset[11]["meta_datadict"]["rate"]["structured"].numpy()[2]
        deep_input_test_value = dataset[11]["meta_datadict"]["rate"]["d2"].numpy()[0]
        target_test_value = dataset[11]["target"].numpy()


        #test if outputs are equal to the true values in the iris dataset
        self.assertEqual(feature_names, self.true_feature_names)
        self.assertAlmostEqual(feature_test_value, self.true_x2_11,places=4)
        self.assertAlmostEqual(linear_input_test_value, self.true_x2_11,places=4)
        self.assertAlmostEqual(deep_input_test_value, self.true_x2_11,places=4)
        self.assertAlmostEqual(target_test_value, self.true_target_11,places=4)


        # test shapes of outputs
        self.assertEqual(self.true_target_11.shape,target_test_value.shape)
        self.assertEqual(self.true_x2_11.shape,linear_input_test_value.shape)
        self.assertEqual(self.true_x2_11.shape,deep_input_test_value.shape)
        self.assertEqual(self.true_x2_11.shape,feature_test_value.shape)


    def test_pandasinputpandastarget(self):
        """
        Test if SddrDataset correctly works with a pandas dataframe as input and target also given as dataframe.
        """


        # load data
        dataset = SddrDataset(data = self.data, 
                              target = self.target,
                              family = self.family,
                              formulas=self.formulas,
                              deep_models_dict=self.deep_models_dict,
                              degrees_of_freedom = self.train_parameters['degrees_of_freedom'])

        feature_names = dataset.get_list_of_feature_names()
        feature_test_value = dataset.get_feature('x2')[11]
        linear_input_test_value = dataset[11]["meta_datadict"]["rate"]["structured"].numpy()[2]
        deep_input_test_value = dataset[11]["meta_datadict"]["rate"]["d2"].numpy()[0]
        target_test_value = dataset[11]["target"].numpy()


        #test if outputs are equal to the true values in the iris dataset
        self.assertEqual(feature_names, self.true_feature_names)
        self.assertAlmostEqual(feature_test_value, self.true_x2_11,places=4)
        self.assertAlmostEqual(linear_input_test_value, self.true_x2_11,places=4)
        self.assertAlmostEqual(deep_input_test_value, self.true_x2_11,places=4)
        self.assertAlmostEqual(target_test_value, self.true_target_11,places=4)


        # test shapes of outputs
        self.assertEqual(self.true_target_11.shape,target_test_value.shape)
        self.assertEqual(self.true_x2_11.shape,linear_input_test_value.shape)
        self.assertEqual(self.true_x2_11.shape,deep_input_test_value.shape)
        self.assertEqual(self.true_x2_11.shape,feature_test_value.shape)
    
    
    def test_filepathinput(self):
        """
        Test if SddrDataset correctly works with file paths as inputs.
        """


        #load data
        dataset = SddrDataset(self.data_path, 
                              self.ground_truth_path,
                              self.family,
                              self.formulas,
                              self.deep_models_dict,
                              self.train_parameters['degrees_of_freedom'])
        
        feature_names = dataset.get_list_of_feature_names()
        feature_test_value = dataset.get_feature('x2')[11]
        linear_input_test_value = dataset[11]["meta_datadict"]["rate"]["structured"].numpy()[2]
        deep_input_test_value = dataset[11]["meta_datadict"]["rate"]["d2"].numpy()[0]
        target_test_value = dataset[11]["target"].numpy()


        #test if outputs are equal to the true values in the iris dataset
        self.assertEqual(feature_names, self.true_feature_names)
        self.assertAlmostEqual(feature_test_value, self.true_x2_11,places=4)
        self.assertAlmostEqual(linear_input_test_value, self.true_x2_11,places=4)
        self.assertAlmostEqual(deep_input_test_value, self.true_x2_11,places=4)
        self.assertAlmostEqual(target_test_value, self.true_target_11,places=4)
        

        # test shapes of outputs
        self.assertEqual(self.true_target_11.shape,target_test_value.shape)
        self.assertEqual(self.true_x2_11.shape,linear_input_test_value.shape)
        self.assertEqual(self.true_x2_11.shape,deep_input_test_value.shape)
        self.assertEqual(self.true_x2_11.shape,feature_test_value.shape)


class Testparse_formulas(unittest.TestCase):
    '''
    Test parse_formulas function for different formulas with the iris dataset.
    
    It is tested (for all parameters of the distribution)
        - if in meta_datadict
            + the structured part is correct and has correct shape
            + the inputs for the neural networks is correct (values and shape)
        - if in parsed_formula_content
            + the penatly matrix is correct
            + struct_shape is correct
            + the deep shape is correct
        - if in dm_info_dict
            + the correct spline slices are given
            + the correct spline input features are given
        - if for smoothing splines:
            + the correct penaly matrix is computed
            + the correct regularization parameter lambda is computed
    '''


    def __init__(self,*args,**kwargs):

        super(Testparse_formulas, self).__init__(*args,**kwargs)


        # load data
        data_path = './test_data/x.csv'
        ground_truth_path = './test_data/y.csv'

        self.x = pd.read_csv(data_path, sep=None, engine='python')
        self.y = pd.read_csv(ground_truth_path)

        # iris = sm.datasets.get_rdataset('iris').data
        # self.x = iris.rename(columns={'Sepal.Length':'x1','Sepal.Width':'x2','Petal.Length':'x3','Petal.Width':'x4','Species':'y'})
        
        
    def test_patsyfreedummytest_parse_formulas(self):
        """
        Test dummy formulas with only intercept. Pasty is not used here to compute the ground truth.
        """

        # define distribution
        cur_distribution = 'Normal'
        family = Family(cur_distribution)


        # define formulas and network shape
        formulas = dict()
        formulas['loc'] = '~1'
        formulas['scale'] = '~1'

        degrees_of_freedom = {'loc': 4, 'scale': 4}

        deep_models_dict = dict()


        #call parse_formulas
        parsed_formula_content, meta_datadict, dm_info_dict = parse_formulas(family, formulas, self.x, deep_models_dict, degrees_of_freedom)
        ground_truth = np.ones([len(self.x),1])


        #test if shapes of design matrices and P are as correct
        self.assertTrue((meta_datadict['loc']['structured'] == ground_truth).all())
        self.assertTrue((meta_datadict['loc']['structured'].shape == ground_truth.shape),'shape missmatch')
        self.assertEqual(parsed_formula_content["loc"]['struct_shapes'], 1)
        self.assertEqual(parsed_formula_content["loc"]['P'].shape, (1, 1))
        self.assertEqual(parsed_formula_content["loc"]['P'], 0)

        self.assertTrue((meta_datadict['scale']['structured'].shape == ground_truth.shape), 'shape missmatch')
        self.assertTrue((meta_datadict['scale']['structured'] == ground_truth).all())
        self.assertEqual(parsed_formula_content["scale"]['struct_shapes'], 1)
        self.assertEqual(parsed_formula_content["scale"]['P'].shape, (1, 1))
        self.assertEqual(parsed_formula_content["scale"]['P'], 0)


        # test if dm_info_dict is correct
        self.assertTrue(dm_info_dict['loc']['list_of_spline_slices'] == [])
        self.assertTrue(dm_info_dict['scale']['list_of_spline_slices'] == [])
        self.assertTrue(dm_info_dict['loc']['list_of_spline_input_features'] == [])
        self.assertTrue(dm_info_dict['scale']['list_of_spline_input_features'] == [])


    def test_structured_parse_formulas(self):
        """
        Test if linear model is correctly processed in parse_formulas.
        """


        # define distribution
        cur_distribution = 'Normal'
        family = Family(cur_distribution)


        # define formulas and network shape
        formulas = dict()
        formulas['loc'] = '~1'
        formulas['scale'] = '~1 + x1'

        degrees_of_freedom = {'loc': 4, 'scale': 4}

        deep_models_dict = dict()


        #call parse_formulas
        parsed_formula_content, meta_datadict, dm_info_dict = parse_formulas(family, formulas, self.x, deep_models_dict, degrees_of_freedom)
        ground_truth_loc = dmatrix(formulas['loc'], self.x, return_type='dataframe').to_numpy()
        ground_truth_scale = dmatrix(formulas['scale'], self.x, return_type='dataframe').to_numpy()


        #test if shapes of design matrices and P are as correct
        self.assertTrue((meta_datadict['loc']['structured'] == ground_truth_loc).all())
        self.assertTrue((meta_datadict['loc']['structured'].shape == ground_truth_loc.shape),'shape missmatch')
        self.assertEqual(parsed_formula_content["loc"]['struct_shapes'], 1)
        self.assertEqual(parsed_formula_content["loc"]['P'].shape, (1, 1))
        self.assertTrue((parsed_formula_content["loc"]['P']==0).all())

        self.assertTrue((meta_datadict['scale']['structured'].shape == ground_truth_scale.shape), 'shape missmatch')
        self.assertTrue((meta_datadict['scale']['structured'] == ground_truth_scale).all())
        self.assertEqual(parsed_formula_content["scale"]['struct_shapes'], 2)
        self.assertEqual(parsed_formula_content["scale"]['P'].shape, (2, 2))
        self.assertTrue((parsed_formula_content["scale"]['P']==0).all())


        # test if dm_info_dict is correct
        self.assertTrue(dm_info_dict['loc']['list_of_spline_slices'] == [])
        self.assertTrue(dm_info_dict['scale']['list_of_spline_slices'] == [])
        self.assertTrue(dm_info_dict['loc']['list_of_spline_input_features'] == [])
        self.assertTrue(dm_info_dict['scale']['list_of_spline_input_features'] == [])


    def test_unstructured_parse_formulas(self):
        """
        Test if parse_formulas is correctly dealing with NNs.
        """


        # define distributions
        cur_distribution = 'Normal'
        family = Family(cur_distribution)


        # define formulas and network shape
        formulas = dict()
        formulas['loc'] = '~1 + d1(x2,x1,x3)'
        formulas['scale'] = '~1 + x1 + d2(x1)'
        
        degrees_of_freedom = {'loc': 4, 'scale': 4}

        deep_models_dict = dict()
        deep_models_dict['d1'] = {'model': nn.Sequential(nn.Linear(1, 15)), 'output_shape': 42}
        deep_models_dict['d2'] = {'model': nn.Sequential(nn.Linear(1, 15)), 'output_shape': 42}


        #call parse_formulas
        parsed_formula_content, meta_datadict, dm_info_dict = parse_formulas(family, formulas, self.x, deep_models_dict, degrees_of_freedom)
        ground_truth_loc = dmatrix('~1', self.x, return_type='dataframe').to_numpy()
        ground_truth_scale = dmatrix('~1 + x1', self.x, return_type='dataframe').to_numpy()


        #test if shapes of design matrices and P are as correct
        self.assertTrue((meta_datadict['loc']['structured'] == ground_truth_loc).all())
        self.assertTrue((meta_datadict['loc']['structured'].shape == ground_truth_loc.shape),'shape missmatch')
        self.assertTrue((meta_datadict['loc']['d1'] == self.x[['x2','x1','x3']].to_numpy()).all())
        self.assertTrue((meta_datadict['loc']['d1'].shape == self.x[['x2','x1','x3']].shape),'shape missmatch for neural network input')
        self.assertEqual(parsed_formula_content["loc"]['struct_shapes'], 1)
        self.assertEqual(parsed_formula_content["loc"]['P'].shape, (1, 1))
        self.assertTrue((parsed_formula_content["loc"]['P']==0).all())
        self.assertEqual(list(parsed_formula_content['loc']['deep_models_dict'].keys()), ['d1'])
        self.assertEqual(parsed_formula_content['loc']['deep_models_dict']['d1'], deep_models_dict['d1']['model'])
        self.assertEqual(parsed_formula_content['loc']['deep_shapes']['d1'], deep_models_dict['d1']['output_shape'])

        self.assertTrue((meta_datadict['scale']['structured'] == ground_truth_scale).all())
        self.assertTrue((meta_datadict['scale']['structured'].shape == ground_truth_scale.shape), 'shape missmatch')
        self.assertTrue((meta_datadict['scale']['d2'] == self.x[['x1']].to_numpy()).all())
        self.assertTrue((meta_datadict['scale']['d2'].shape == self.x[['x1']].shape),'shape missmatch for neural network input')
        self.assertEqual(parsed_formula_content["scale"]['struct_shapes'], 2)
        self.assertEqual(parsed_formula_content["scale"]['P'].shape, (2, 2))
        self.assertTrue((parsed_formula_content["scale"]['P']==0).all())
        self.assertEqual(list(parsed_formula_content['scale']['deep_models_dict'].keys()), ['d2'])
        self.assertEqual(parsed_formula_content['scale']['deep_models_dict']['d2'],deep_models_dict['d2']['model'])
        self.assertEqual(parsed_formula_content['scale']['deep_shapes']['d2'], deep_models_dict['d2']['output_shape'])


        # test if dm_info_dict is correct
        self.assertTrue(dm_info_dict['loc']['list_of_spline_slices'] == [])
        self.assertTrue(dm_info_dict['scale']['list_of_spline_slices'] == [])
        self.assertTrue(dm_info_dict['loc']['list_of_spline_input_features'] == [])
        self.assertTrue(dm_info_dict['scale']['list_of_spline_input_features'] == [])
        
        
    def test_smoothingspline_parse_formulas(self):
        """
        Test if parse_formulas is correctly dealing with smoothingsplines.
        We test here explicitly if parse_formulas deals correctly with
            - a missing intercept
            - reordering of the arguments in the spline functions
            - explicitly adding the return_penalty= False statement
            - having explicit interactions between splines and linear terms
        """

        # define distributions
        cur_distribution = 'Normal'
        family = Family(cur_distribution)


        # define formulas and network shape
        formulas = dict()
        formulas['loc'] = '~-1 + spline(x1,bs="bs",df=4, degree=3):x2 + x1:spline(x2,bs="bs",df=5, degree=3)'
        formulas['scale'] = '~1 + x1 + spline(x1,df=10,return_penalty=False, degree=3,bs="bs")'
        
        degrees_of_freedom = {'loc': 4, 'scale': [4]}

        deep_models_dict = dict()


        #call parse_formulas
        parsed_formula_content, meta_datadict, dm_info_dict = parse_formulas(family, formulas, self.x, deep_models_dict, degrees_of_freedom)
        ground_truth_loc = dmatrix('~-1 + spline(x1,bs="bs",df=4, degree=3):x2 + spline(x2,bs="bs",df=5, degree=3):x1', self.x, return_type='dataframe').to_numpy()
        ground_truth_scale = dmatrix('~1 + x1 + spline(x1,bs="bs",df=10, degree=3)', self.x, return_type='dataframe').to_numpy()


        #test if shapes of design matrices and P are as correct
        self.assertTrue((meta_datadict['loc']['structured'] == ground_truth_loc).all())
        self.assertTrue((meta_datadict['loc']['structured'].shape == ground_truth_loc.shape),'shape missmatch')
        self.assertEqual(parsed_formula_content["loc"]['struct_shapes'], 9)
        self.assertEqual(parsed_formula_content["loc"]['P'].shape, (9, 9))
        self.assertTrue((parsed_formula_content["loc"]['P']==0).all())

        self.assertFalse((meta_datadict['scale']['structured'] == ground_truth_scale).all())  # assertFalse is due to orthogonalization
        self.assertTrue((meta_datadict['scale']['structured'].shape == ground_truth_scale.shape), 'shape missmatch')
        self.assertEqual(parsed_formula_content["scale"]['struct_shapes'], 12)
        self.assertEqual(parsed_formula_content["scale"]['P'].shape, (12, 12))


        # test if dm_info_dict is correct
        self.assertTrue(dm_info_dict['loc']['list_of_spline_slices'] == [slice(0,4), slice(4,9)])
        self.assertTrue(dm_info_dict['scale']['list_of_spline_slices'] == [slice(2,12)])
        self.assertTrue(dm_info_dict['loc']['list_of_spline_input_features'] == [list({'x1','x2'}), list({'x1','x2'})])
        self.assertTrue(dm_info_dict['scale']['list_of_spline_input_features'] == [list({'x1'})])


    def test_spline_penaltymatrix_lambda(self):
        """
        Test if P-matrix is correctly computed and test if regularization parameter lambda is correctly computed from degrees of freedom.
        We test here explicitly if for a smoothing spline
            - the penalty matrix is computed correctly
            - the penalty matrix is regularized correctly
            - the regularization parameter lambda is computed correctly from degrees of freedom
        """


        # define distributions
        cur_distribution = 'Poisson'
        family = Family(cur_distribution)


        # define formulas and network shape
        formulas=dict()
        formulas['rate'] = "~ -1 + spline(x1, bs='bs', df=9, degree=3)"

        degrees_of_freedom = {'rate': 4}

        deep_models_dict = dict()


        # call parse_formulas
        parsed_formula_content, meta_datadict, dm_info_dict = parse_formulas(family, formulas, self.x, deep_models_dict, degrees_of_freedom)


        # get original P and get penalized P (by lambda)
        sp = Spline()
        sp.memorize_chunk(self.x.x1, bs="bs", df=9, degree=3, return_penalty=True)
        P_original = sp.penalty_matrices[0]
        P_penalized = parsed_formula_content["rate"]['P']


        # calculate regularization parameter lambda
        dm_spline = dmatrix(formulas['rate'], self.x, return_type='dataframe')
        df_lam = df2lambda(dm_spline, P_original, degrees_of_freedom['rate'])


        # calculate lambda from original and penalized P matrix
        lambdas = np.divide(P_penalized, P_original, out=np.zeros_like(P_penalized), where=P_original != 0).flatten()
        lam = np.unique(lambdas[lambdas != 0])


        # test if lambda value, degrees of freedom and penalty matrix are correct
        self.assertAlmostEqual(df_lam[1], 1.00276544, places=4)
        self.assertTrue(lam == df_lam[1])
        self.assertTrue(df_lam[0] == degrees_of_freedom['rate'])
        self.assertTrue((P_original == (P_penalized / df_lam[1])).all())



class Testorthogonalize_spline_wrt_non_splines(unittest.TestCase):
    '''
    Tests the orthogonalize_spline_wrt_non_splines function.
    We test for two cases if the design matrix gets correctly orthogonalized.
    '''


    def __init__(self,*args,**kwargs):
        super(Testorthogonalize_spline_wrt_non_splines, self).__init__(*args,**kwargs)


    def test_case_one(self):
        '''
        Test with variables x1, x2 and a spline that is only dependent on x1.
        Orthogonalization should be w.r.t. intercept and x1
        '''


        # load data
        iris = sm.datasets.get_rdataset('iris').data
        data = iris.rename(columns={'Sepal.Length':'x1','Sepal.Width':'x2','Petal.Length':'x3','Petal.Width':'x4','Species':'y'})

        structured_matrix = dmatrix('~ 1 + x1 + x2 + spline(x1, bs="bs", df=4, return_penalty = False, degree=3)', data, return_type='dataframe')

        spline_info, non_spline_info = _get_info_from_design_matrix(structured_matrix, data.columns)
        
        
        _orthogonalize_spline_wrt_non_splines(structured_matrix, spline_info, non_spline_info)

        test_features_not_zero = abs(structured_matrix).values.max().min() > 0
        self.assertTrue(test_features_not_zero) #test if features are not just equal to a zero vector

        p=structured_matrix.shape[1]

        correct_orthogonality_pattern = np.array([[1., 1., 1., 0., 0., 0., 0.],
                                                  [1., 1., 1., 0., 0., 0., 0.],
                                                  [1., 1., 1., 1., 1., 1., 1.],
                                                  [0., 0., 1., 1., 1., 1., 1.],
                                                  [0., 0., 1., 1., 1., 1., 1.],
                                                  [0., 0., 1., 1., 1., 1., 1.],
                                                  [0., 0., 1., 1., 1., 1., 1.]])

        for i in range(p):
            for j in range(p):
                is_not_orthogonal = abs(np.matmul(structured_matrix.values[:,i], structured_matrix.values[:,j]))>0.01
                test_orthog = correct_orthogonality_pattern[i,j] == is_not_orthogonal
                self.assertTrue(test_orthog) #test if orthogonality is correct 
        
        
    def test_case_two(self):
        '''
        Test with variables x1, x2 and a spline that dependent on x1 and multiplied with x2.
        Orthogonalization should be w.r.t. intercept, x1 and x2
        '''


        # load data
        iris = sm.datasets.get_rdataset('iris').data
        data = iris.rename(columns={'Sepal.Length':'x1','Sepal.Width':'x2','Petal.Length':'x3','Petal.Width':'x4','Species':'y'})

        structured_matrix = dmatrix('~ 1 + x1 + x2 + spline(x1, bs="bs", df=4, return_penalty = False, degree=3):x2', data, return_type='dataframe')

        spline_info, non_spline_info = _get_info_from_design_matrix(structured_matrix, data.columns)

        _orthogonalize_spline_wrt_non_splines(structured_matrix, spline_info, non_spline_info)

        test_features_not_zero = abs(structured_matrix).values.max().min() > 0
        self.assertTrue(test_features_not_zero) #test if features are not just equal to a zero vector

        p=structured_matrix.shape[1]

        correct_orthogonality_pattern = np.array([[1., 1., 1., 0., 0., 0., 0.],
                                                  [1., 1., 1., 0., 0., 0., 0.],
                                                  [1., 1., 1., 0., 0., 0., 0.],
                                                  [0., 0., 0., 1., 1., 1., 1.],
                                                  [0., 0., 0., 1., 1., 1., 1.],
                                                  [0., 0., 0., 1., 1., 1., 1.],
                                                  [0., 0., 0., 1., 1., 1., 1.]])

        for i in range(p):
            for j in range(p):
                is_not_orthogonal = abs(np.matmul(structured_matrix.values[:,i], structured_matrix.values[:,j]))>0.01
                test_orthog = correct_orthogonality_pattern[i,j] == is_not_orthogonal
                self.assertTrue(test_orthog) #test if orthogonality is correct 
        
        
if __name__ == '__main__':
    unittest.main()