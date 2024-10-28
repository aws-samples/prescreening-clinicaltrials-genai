"""
This Lambda function handles API requests for patient medical details and clinical trial information.
It interfaces with ClinicalTrials.gov API and an S3 bucket containing patient data.
"""

import json
import boto3
import logging
import os
import requests

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS S3 client
s3 = boto3.client('s3')
bucket = os.environ['S3_BUCKET']  # S3 bucket containing patient data and OpenAPI files

def fetch_clinical_trial_data(search_expr, max_studies):
    """
    Fetches clinical trial data from ClinicalTrials.gov API based on search criteria.
    
    Args:
        search_expr (str): Medical condition to search for
        max_studies (int): Maximum number of studies to retrieve
    
    Returns:
        tuple: (list of eligibility criteria, list of NCT IDs)
    """
    base_url = "https://clinicaltrials.gov/api/v2/studies"
    params = {
        "query.cond": search_expr,
        "query.term": "AREA[Phase](PHASE4 OR PHASE3)AND AREA[LocationCountry](United States)",
        "filter.overallStatus": "RECRUITING",
        "pageSize": max_studies
    }

    eligibility_criteria = []
    nct_ids = []
    studies_fetched = 0

    while True:
        # Make API request with timeout
        response = requests.get(base_url, params=params, timeout=60)

        if response.status_code == 200:
            data = response.json()
            studies = data.get('studies', [])

            # Process each study in the response
            for study in studies:
                nct_id = study['protocolSection']['identificationModule'].get('nctId', 'Unknown')
                nct_ids.append(nct_id)

                eligibility_criteria_text = study['protocolSection']['eligibilityModule'].get('eligibilityCriteria', 'Unknown')
                eligibility_criteria.append(eligibility_criteria_text)

                studies_fetched += 1
                if studies_fetched >= max_studies:
                    break

            # Handle pagination
            nextPageToken = data.get('nextPageToken')
            if nextPageToken and studies_fetched < max_studies:
                params['pageToken'] = nextPageToken
            else:
                break
        else:
            logger.error(f"Failed to fetch data. Status code: {response.status_code}")
            break

    return eligibility_criteria, nct_ids

def return_patient_info(p_name, c_name):
    """
    Retrieves patient information from S3 bucket based on patient name and condition.
    
    Args:
        p_name (str): Patient name
        c_name (str): Medical condition
    
    Returns:
        dict: Patient details or empty dictionary if no match found
    """
    # Fetch patient data from S3
    s3_clientobj = s3.get_object(Bucket=bucket, Key='patientdata.json')
    s3_patientdata = s3_clientobj['Body'].read().decode('utf-8')
    s3patientlist = json.loads(s3_patientdata)
    
    # Find matching patient
    loclientdict = {}
    matchedPatients = [item for item in s3patientlist 
                      if item["patientName"].lower() == p_name.lower() 
                      and item["condition"].lower() == c_name.lower()]
    
    return matchedPatients[0] if matchedPatients else loclientdict

def return_trial_info(age, medicalCondition, gender, country):
    """
    Fetches clinical trial information based on patient criteria.
    
    Args:
        age (str): Patient age
        medicalCondition (str): Medical condition
        gender (str): Patient gender
        country (str): Patient country
    
    Returns:
        list: Contains eligibility criteria and NCT IDs
    """
    max_studies = 3
    search_expr = medicalCondition
    critlist, nctidlist = fetch_clinical_trial_data(search_expr, max_studies)
    loclientdict = [critlist, nctidlist]
    return loclientdict

def get_named_parameter(event, name):
    """
    Extracts a named parameter from the Lambda event object.
    
    Args:
        event (dict): Lambda event object
        name (str): Name of the parameter to retrieve
    
    Returns:
        str: Value of the requested parameter
    """
    return next(item for item in event['parameters'] if item['name'] == name)['value']

def get_named_property(event, name):
    """
    Extracts a named property from the Lambda event object's request body.
    
    Args:
        event (dict): Lambda event object
        name (str): Name of the property to retrieve
    
    Returns:
        str: Value of the requested property
    """
    return next(item for item in event['requestBody']['content']['application/json']['properties'] 
               if item['name'] == name)['value']

def lambda_handler(event, context):
    """
    Main Lambda handler function that processes API requests.
    
    Args:
        event (dict): Lambda event object
        context (object): Lambda context object
    
    Returns:
        dict: API response with messageVersion and response details
    """
    responses = []
    api_path = event['apiPath']
    logger.info('API Path')
    logger.info(api_path)
    
    # Route API requests and process accordingly
    body = ""
    if api_path == '/patientMedDetails/{patientName}/{topMedCondition}':
        p_name = get_named_parameter(event, "patientName")
        c_name = get_named_parameter(event, "medicalCondition")
        body = return_patient_info(p_name, c_name)
    elif api_path == '/getTrials/{age}/{medicalCondition}/{gender}/{country}':
        age = get_named_parameter(event, "age")
        medicalCondition = get_named_parameter(event, "medicalCondition")
        gender = get_named_parameter(event, "gender")
        country = get_named_parameter(event, "country")
        body = return_trial_info(age, medicalCondition, gender, country)
    else:
        body = {"{} is not a valid api, try another one.".format(api_path)}

    # Construct response structure
    response_body = {
        'application/json': {
            'body': json.dumps(body)
        }
    }

    action_response = {
        'actionGroup': event['actionGroup'],
        'apiPath': event['apiPath'],
        'httpMethod': event['httpMethod'],
        'httpStatusCode': 200,
        'responseBody': response_body
    }

    responses.append(action_response)

    # Return the final API response
    api_response = {
        'messageVersion': '1.0',
        'response': action_response
    }

    return api_response
