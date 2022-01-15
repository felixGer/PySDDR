# -*- coding: utf-8 -*-
"""
Created on Tue Jan 11 16:27:03 2022

@author: felix
"""
import time
import pandas as pd
import nltk
with open('C:/Users/felix/Downloads/umls-2021AB-full/2021AB-full/Test_Folder/2021AB/META/MRCONSO.RRF', encoding = 'UTF-8') as f:
    lines = f.readlines()
    
    
lines_test = lines


time1 = time.time()

splitted_RRF =[line.split('|')for line in lines_test]

cui = [line[0] for line in splitted_RRF]
string = [line[14].lower() for line in splitted_RRF]

time2 = time.time()

cui_string_df = pd.DataFrame({'cui': cui, 'string':string})

cui_string_df.drop_duplicates(inplace = True)

cui2vec_df = pd.read_csv('C:/Users/felix/Documents/GitHub/MA/Docs/Literature/Representations/Clinical Notes/Word_Embeddings/cui2vec_pretrained.csv/cui2vec_pretrained.csv')


string_list = ['COPD','ACUTE RENAL FAILURE','CHRONIC OBST PULM DISEASE', 'CARDIAC CATH','ACUTE RESPIRATORY DISTRESS','LEFT LUNG CA/SDA','SHORTNESS OF BREATH','PANCREATIC CA', 'INTRACRANIAL HEMORRHAGE','ANEURYSM','BILIARY COLIC','PULMONARY HYPERTENSION','PNEUMONIA','Telemetry','HYPONATREMIA', 'CHOLANGIO CARCINOMA', 'PNEUMONIA', 'Sepsis', 'ANGINA', 'Lower GI bleed', 'LUNG CA', 'FAILURE TO WEAN', 'DRUG REFRACTORY ATRIAL FIBRILLATION','COPD FLARE', 'ASCENDING AORTA REPLACEMENT']
string_list_lower = [i.lower() for i in string_list ]
result_list = []


### DELETE strings with less than 2 letters in cui dict

cui_string_df = cui_string_df.where(cui_string_df.string.str.len()>2)


###EXACT MATCHING
for i in string_list_lower:
    result_list.append(cui_string_df.loc[cui_string_df.string == i])
    
result_list
    
## FUZZY MATCHING

from rapidfuzz import fuzz
from rapidfuzz import process

time3 = time.time()


results = list()
for i in string_list:
    results.append(process.extract(i, cui_string_df.string, scorer=fuzz.WRatio, limit = 4))
    
time4 = time.time()

time4 - time3

results

fuzz('dede', 'dede')