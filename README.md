# RefiModel
Lambda function to update "Suboridnation New Mad" field in Salesforce

Subordination-MAD-Service Lambda Introduction
Description
Subordination-MAD-Service API will update the value of “Subordination_New_MAD__c” in Opportunity object. It’s a recommended value that Home Partner Team will use as MAD reference when dealing with cash-out refinance request.
Data Needed
Values below in the Autoby.opportunity table should be prepared:
Opportunity_fields=['Id', 'Deal_ID__c' ,'Maximum_Authorized_Debt__c', \
              'Original_Agreed_Value__c','Original_Investment_Price__c',\
              'Pricing_Ratio__c','Current_AVM__c',\
              'Qualifying_Credit_Score__c',\
              'Current_Applicant_Credit_Score__c','Current_Co_Applicant_Credit_Score__c',\
              'Back_End_DTI__c','Applicant__c', 'Co_Applicant__c']
Input
No input needed. The Lambda function is scheduled to run weekly update.
Output
The values of “Subordination_New_MAD__c” in Opportunity object will be updated.
