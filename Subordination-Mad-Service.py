# -*- coding: utf-8 -*-
"""
Created on Mon Oct  7 10:46:15 2019

@author: szhou
"""

import pandas as pd
from base64 import b64decode
import numpy as np
from scipy.stats import norm
from scipy.stats import lognorm
from simple_salesforce import Salesforce
import os
import io
import sqlalchemy as sql
import pymysql
import boto3

def Opportunity():

	def dict_clean(a):
		for v in a.values():
			for j,k in v.items():
				if k is None:
					k=''
				v[j] = k
		return a
		
	fields = ['Id', 'Deal_ID__c' ,'Maximum_Authorized_Debt__c', \
              'Original_Agreed_Value__c','Original_Investment_Price__c',\
              'Pricing_Ratio__c','Current_AVM__c',\
              'Qualifying_Credit_Score__c',\
              'Current_Applicant_Credit_Score__c','Current_Co_Applicant_Credit_Score__c',\
              'Back_End_DTI__c','Applicant__c', 'Co_Applicant__c']
	soql = "SELECT {} FROM Opportunity where Termination_Flag__c=False".format(','.join(fields))
	df = pd.DataFrame(sf_engine.query_all(soql)['records'])
	df.drop('attributes', inplace=True, axis=1)

	# converting to dict & removing NoneType deal_ids
	dataDict = df.T.to_dict()
	dataDict = {k: v for k, v in dataDict.items() if v['Deal_ID__c'] not in [None, '', np.nan]}
	dataDict = {i: v for i, v in enumerate(dataDict.values())}
	return dict_clean(dataDict)

def match(a,target):
    for i in range(len(a)):
        if target>=a[i]:
            loc=i
            value=a[i]
    return([loc,value])
def find_beta(fico,dti,ltv,number_of_borrower):
    #calculate the default probability for cash-out refinance mortgages
    a=[0,15,25,35,40,45,50,55]
    b=[0,13,26,13*3,13*4,13*5,13*6,13*7]
    c=[0,600,650,675,690,715,730,745,760,770,780,790,800] 
    d=[0,30,40,50,60,65,70,75,80,85,90]
    beta_n=(number_of_borrower-1.57162278545291)/0.49484358824703*(-0.234140464003778)
    beta_p=(1-0.90118283747068)/0.29842*(-0.046732357)
    beta_I=(0-0.0558383800115628)/0.229609353855063*(-0.0124287990210395)
    beta_c=(1-0.290380996953753)/0.4539381827423558*(0.150737546378101)
    beta_pur=(0-0.373521104556809)/0.373521104556809*(-0.193022278208868)
    [dti_loc,dti_value]=match(a,dti)
    [fico_loc,fico_value]=match(c,fico)
    [ltv_loc,ltv_value]=match(d,ltv)
    beta_credit=passbook_data.iloc[b[dti_loc]+fico_loc][ltv_value]
    defaut_rate=1-(1-np.exp(beta_n+beta_p+beta_c+beta_credit+beta_pur+beta_I))**60
    return(defaut_rate)
def refi_model(orig_mad, OAV, OIP, pricing_ratio, current_avm,fico,dti,number_of_borrower):
        
    def credit_check(default_rate):
        if default_rate<0.045:
            return(True)
        else:
            return(False)
        
    #Statistic settings
    expected_return=0.035 #per year housing price return
    volatility=0.15 #per year housing price vol
    probability_control=0.95
    ltv_control_prct=0.7
    
    appreciation=(current_avm-OAV)/OAV
    share_in_prct=pricing_ratio*OIP/OAV
    
    #New Potential Maximum Allowed Debt 1
    condition1=(appreciation<0.5)
    new_mad1=OAV-OIP/share_in_prct  
    default_rate1=find_beta(fico,dti,100*(new_mad1/current_avm),number_of_borrower)
    credit_condition1=credit_check(default_rate1)
    
    #New Potential Maximum Allowed Debt 2
    condition2=True
    horizon=5 #years
    s =volatility*horizon**0.5
    new_mad2=ltv_control_prct*current_avm*lognorm.ppf((1-probability_control), s, loc=0, scale=np.exp(expected_return*horizon))
    default_rate2=find_beta(fico,dti,100*(new_mad2/current_avm),number_of_borrower)
    credit_condition2=credit_check(default_rate2)
    
    #New Potential Maximum Allowed Debt 3
    condition3=(orig_mad/OAV<0.5)
    new_mad3=orig_mad*(1+appreciation)
    default_rate3=find_beta(fico,dti,100*(new_mad3/current_avm),number_of_borrower)
    credit_condition3=credit_check(default_rate3)
    
    #New Potential Maximum Allowed Debt 4
    condition4=(share_in_prct<0.51)
    new_mad4=current_avm-((current_avm-OAV)*share_in_prct+OIP)*1.8
    default_rate4=find_beta(fico,dti,100*(new_mad4/current_avm),number_of_borrower)
    credit_condition4=credit_check(default_rate4)
    
    #New Potential Maximum Allowed Detb 5
    condition5=(share_in_prct>0.5)
    new_mad5=0.8*current_avm-((current_avm-OAV)*share_in_prct+OIP)
    default_rate5=find_beta(fico,dti,100*(new_mad5/current_avm),number_of_borrower)
    credit_condition5=credit_check(default_rate5)
    
    def condition_check(condition,condition2,mad):
        if (condition) & (condition2):
            return(mad)
        else:
            return(np.nan)
       
    
    new_mad_list=[condition_check(condition1,credit_condition1,new_mad1), condition_check(condition2,credit_condition2,new_mad2),
                  condition_check(condition3,credit_condition3,new_mad3),
                 condition_check(condition4,credit_condition4,new_mad4),condition_check(condition5,credit_condition5,new_mad5)]
    mad_candidate1=np.nanmax([orig_mad,np.nanmin(new_mad_list)])
    
    #statistical test
    prob_candidate1=lognorm.cdf(mad_candidate1/current_avm, s, loc=0, scale=np.exp(expected_return*horizon))
    check_candidate1=(prob_candidate1<=0.01)
    
    if check_candidate1:
        mad_candidate2=mad_candidate1
    else:
        mad_candidate2=np.nanmax([orig_mad,lognorm.ppf(0.01, s, loc=0, scale=np.exp(expected_return*horizon))*current_avm])
        
    #final back test
    max_dd=-27.42/100
    check_orig=(1+max_dd)*current_avm<orig_mad
    check_candidate2=(1+max_dd)*current_avm<mad_candidate2
    
    if check_candidate2:
        new_mad=mad_candidate2
    elif check_orig:
        new_mad=orig_mad
    else:
        new_mad=mad_candidate2
    
    return(new_mad)
    
def lambda_handler(event, context):


    # Confgure MySQL engine
    mysql_engine = sql.create_engine('mysql+pymysql://'+ os.environ['mysql_user'] + ':' + os.environ['mysql_password'] + '@' +
                                    os.environ['mysql_path'] + '?charset=utf8')

   
    # Configure salesforce object
    sf_engine = Salesforce(
        username=os.environ['username'],
        password=os.environ['password'],
        instance=os.environ['instance'],
        security_token=os.environ['security_token'])
    
    oppo_dict= Opportunity()
    passbook_data=pd.read_excel("s3://uim-raw-datasets/adhoc/Scott/Passbook_Data.xlsx" )
    
    for i in range(len(oppo_dict)):
        #prerparing input
        #orig_mad, OAV, OIP, pricing_ratio, current_avm,fico,dti,number_of_borrower
        orig_mad=oppo_dict[i]['Maximum_Authorized_Debt__c']
        OAV=oppo_dict[i]['Original_Agreed_Value__c']
        OIP=oppo_dict[i]['Original_Investment_Price__c']
        pricing_ratio=oppo_dict[i]['Pricing_Ratio__c']
        if ~np.isnan(oppo_dict[i]['Current_AVM__c']):
            current_avm=oppo_dict[i]['Current_AVM__c']
        else:
            current_avm=oppo_dict[i]['Original_Agreed_Value__c']
        if  (np.isnan(oppo_dict[i]['Current_Co_Applicant_Credit_Score__c']) and np.isnan(oppo_dict[i]['Current_Applicant_Credit_Score__c'])):
            if len(oppo_dict[i]['Qualifying_Credit_Score__c'])>0:
                fico=float(oppo_dict[i]['Qualifying_Credit_Score__c'])
            else:
                fico=0
        elif (np.isnan(oppo_dict[i]['Current_Co_Applicant_Credit_Score__c']) and ~np.isnan(oppo_dict[i]['Current_Applicant_Credit_Score__c'])): 
            fico=float(oppo_dict[i]['Current_Applicant_Credit_Score__c'])
        elif  (~np.isnan(oppo_dict[i]['Current_Co_Applicant_Credit_Score__c']) and ~np.isnan(oppo_dict[i]['Current_Applicant_Credit_Score__c'])):
            fico=(float(oppo_dict[i]['Current_Applicant_Credit_Score__c'])+float(oppo_dict[i]['Current_Co_Applicant_Credit_Score__c']))/2            

        if oppo_dict[i]['Back_End_DTI__c']>=0:
            dti=oppo_dict[i]['Back_End_DTI__c']
        else:
            dti=30

        if len(oppo_dict[i]['Co_Applicant__c'])==0:
            number_of_borrower=1
        else:
            number_of_borrower=2

        if OIP>0:
            #output calculation
            Subordination_new_mad= refi_model(orig_mad, OAV, OIP, pricing_ratio, current_avm,fico,dti,number_of_borrower)
        else:
            Subordination_new_mad=orig_mad
        new_oppo_field={'Id':oppo_dict[i]['Id'],'Subordination_new_mad':Subordination_new_mad}

        sf_engine.Opportunity.update(
            new_oppo_field['Id'], {
                'Subordination_New_MAD__c': new_oppo_field['Subordination_new_mad'],
            })
	return "success"