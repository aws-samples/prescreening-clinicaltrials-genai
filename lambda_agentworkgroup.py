import json
import boto3
import logging
import os
import requests

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client('s3')
bucket = os.environ['S3_BUCKET']  # Name of bucket with data file and OpenAPI file


def fetch_clinical_trial_data(search_expr, max_studies):
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
        response = requests.get(base_url, params=params, timeout=60)

        if response.status_code == 200:
            data = response.json()
            studies = data.get('studies', [])

            for study in studies:
                nct_id = study['protocolSection']['identificationModule'].get('nctId', 'Unknown')
                nct_ids.append(nct_id)

                eligibility_criteria_text = study['protocolSection']['eligibilityModule'].get('eligibilityCriteria', 'Unknown')
                eligibility_criteria.append(eligibility_criteria_text)

                studies_fetched += 1
                if studies_fetched >= max_studies:
                    break

            nextPageToken = data.get('nextPageToken')
            if nextPageToken and studies_fetched < max_studies:
                params['pageToken'] = nextPageToken
            else:
                break

        else:
            print(f"Failed to fetch data. Status code: {response.status_code}")
            break

    return eligibility_criteria, nct_ids

def return_patient_info(p_name, c_name):
    """
    Function returns all patient info for a particular patient name and condition
    Args:
        p_name (str): patient name
        c_name: condition for the patient
    Returns:
        patient details
    """
    s3_clientobj = s3.get_object(Bucket=bucket, Key='patientdata.json')
    s3_patientdata = s3_clientobj['Body'].read().decode('utf-8')
    s3patientlist=json.loads(s3_patientdata)
    loclientdict={}
    matchedPatients=[item for item in s3patientlist if item["patientName"].lower() == p_name.lower() and item["condition"].lower() == c_name.lower()]
    if not matchedPatients:
        return loclientdict
    else:
        loclientdict=matchedPatients[0]
    return loclientdict

def return_trial_info(age, medicalCondition, gender, country):
    """
    Function returns all trial info for a combination of information
    Args:
        age,medicalCondition,gender,country (str): patient details for fetching trials
        c: a cursor for the connection
    Returns:
        trial(s) details
    """
    max_studies = 3
    search_expr = medicalCondition
    critlist, nctidlist = fetch_clinical_trial_data(search_expr,max_studies)
    loclientdict =[critlist,nctidlist]
    return loclientdict
    
def get_named_parameter(event, name):
    """
    Function that gets the parameter 'name' from the lambda event object
    Args:
        event: lambda event
        name: name of the parameter to return
    Returns:
        parameter value
    """
    return next(item for item in event['parameters'] if item['name'] == name)['value']


def get_named_property(event, name):
    """
    get the named property 'name' from the lambda event object
    Args:        
        event: lambda event
        name: name of the named property to return
    Returns:
        named property value
    """
    return next(item for item in event['requestBody']['content']['application/json']['properties'] if item['name'] == name)['value']



def lambda_handler(event, context):
    responses = []
    api_path = event['apiPath']
    logger.info('API Path')
    logger.info(api_path)
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
        body = return_trial_info(age,medicalCondition,gender,country)
    else:
        body = {"{} is not a valid api, try another one.".format(api_path)}

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

    api_response = {
        'messageVersion': '1.0',
        'response': action_response}

    return api_response