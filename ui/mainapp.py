import InvokeAgent as agenthelper
import streamlit as st
import json
import pandas as pd
from PIL import Image, ImageOps, ImageDraw

# Streamlit page configuration
st.set_page_config(page_title="Clinical Trials Sorter", page_icon=":robot_face:", layout="wide")

# Function to crop image into a circle
def crop_to_circle(image):
    mask = Image.new('L', image.size, 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.ellipse((0, 0) + image.size, fill=255)
    result = ImageOps.fit(image, mask.size, centering=(0.5, 0.5))
    result.putalpha(mask)
    return result

# Title
st.title("Clinical Trials Sorter")

# Form adding
with st.form('Add patient details'):
    patient_name = st.text_input('Patient Name', max_chars=50)
    patient_cond = st.text_input('Patient Condition - top level', max_chars=100)
    submit = st.form_submit_button('Submit Query')

if patient_name and patient_cond:
    prompt = " Can you please fetch clinical trials for " + patient_name.strip() + " with " + patient_cond.strip()
else:
    prompt=''
if submit:
    if not prompt:
        st.error("Either patient name or medical condition is not provided !!")

# Display a button to end the session
end_session_button = st.button("End Session")

# Sidebar for user input
st.sidebar.title("Trace Data")

# Session State Management
if 'history' not in st.session_state:
    st.session_state['history'] = []

# Function to parse and format response
def format_response(response_body):
    try:
        # Try to load the response as JSON
        data = json.loads(response_body)
        # If it's a list, convert it to a DataFrame for better visualization
        if isinstance(data, list):
            return pd.DataFrame(data)
        else:
            return response_body
    except json.JSONDecodeError:
        # If response is not JSON, return as is
        return response_body

# Handling user input and responses
if submit and prompt:
    print(prompt)
    event = {
        "sessionId": "CLINSESSION115",
        "question": prompt
    }
    response = agenthelper.lambda_handler(event, None)
    
    try:
        # Parse the JSON string
        if response and 'body' in response and response['body']:
            response_data = json.loads(response['body'])
            #print("TRACE & RESPONSE DATA ->  ", response_data)
        else:
            print("Invalid or empty response received")
    except json.JSONDecodeError as e:
        print("JSON decoding error:", e)
        response_data = None 
    txt= response_data['response']
    try:
        # Extract the response and trace data
        
        index1 = txt.find('\"trace\"')
        if index1 != -1:
            end_index = txt.find('Lst Response:', index1)
            if end_index != -1:
                txt =  txt[index1:end_index]
            else:
                txt = txt[index1:]
        all_data = format_response(response_data['response'])
        the_response = response_data['trace_data']
    except:
        all_data = "..." 
        the_response = "Apologies, but an error occurred. Please rerun the application" 

    # Use trace_data and formatted_response as needed
    
    st.session_state['history'].append({"question": prompt, "answer": the_response})
    st.session_state['trace_data'] = the_response
    prev_questions = [i["question"]for i in st.session_state['history']] 
    #st.sidebar.text_area("", value=prev_questions, height=300)
    st.sidebar.text_area("", value=txt, height=300)
    
  

if end_session_button:
    st.session_state['history'].append({"question": "Session Ended", "answer": "Thank you for using Clinical Trials Sorter!"})
    event = {
        "sessionId": "MYSESSION115",
        "question": "placeholder to end session",
        "endSession": True
    }
    agenthelper.lambda_handler(event, None)
    st.session_state['history'].clear()

# Display conversation history
st.write("## Conversation History")

# Load images outside the loop to optimize performance
human_image = Image.open('images/human_face.png')
robot_image = Image.open('images/robot_face.jpg')
circular_human_image = crop_to_circle(human_image)
circular_robot_image = crop_to_circle(robot_image)

for index, chat in enumerate(reversed(st.session_state['history'])):
    # Creating columns for Question
    col1_q, col2_q = st.columns([2, 10])
    with col1_q:
        st.image(circular_human_image, width=125)
    with col2_q:
        # Generate a unique key for each question text area
        st.text_area("Q:", value=chat["question"], height=50, key=f"question_{index}", disabled=True)

    # Creating columns for Answer
    col1_a, col2_a = st.columns([2, 10])
    if isinstance(chat["answer"], pd.DataFrame):
        with col1_a:
            st.image(circular_robot_image, width=100)
        with col2_a:
            # Generate a unique key for each answer dataframe
            st.dataframe(chat["answer"], key=f"answer_df_{index}")
    else:
        with col1_a:
            st.image(circular_robot_image, width=150)
        with col2_a:
            # Generate a unique key for each answer text area
            st.text_area("A:", value=chat["answer"], height=100, key=f"answer_{index}")
