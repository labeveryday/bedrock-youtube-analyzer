"""
YouTube Analysis Assistant
"""
import base64
import io
import json
import re
import logging
import boto3
from random import randint

# Used to display the UI components
import streamlit as st
from streamlit_chat import message


from PIL import Image

# Used to conversation with LLM
from langchain.prompts import PromptTemplate
from langchain.document_loaders import YoutubeLoader
from langchain.chains import ConversationChain
from langchain.memory import ConversationBufferMemory
from langchain.chat_models import BedrockChat


logging.basicConfig(filename="app.log", filemode='w', format="%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S", level=logging.INFO) 
logger = logging.getLogger(__name__)


logger.info('Starting analysis')

# Create title and header
st.set_page_config(page_title="YouTube Analysis", page_icon="🤖", layout="wide")
st.header("YouTube Analysis Assistant 🤖", divider="blue")
st.subheader('I am here to help you improve your :red[YouTube] channel:')

# Define bedrock
bedrock = boto3.client(
    service_name="bedrock-runtime",
    region_name="us-east-1"
)


def get_video_transcript(url: str) ->YoutubeLoader:
    """
    Fetches and transcribes the video contents for a given YouTube video ID.

    Args:
        url (str):                          The unique identifier of the YouTube video.

    Returns:
        loaded_video_document (str):        The transcribed contents of the video.
    """
    # The loader downloads and transcribes the video and creates document loader
    loader = YoutubeLoader.from_youtube_url(url, add_video_info=True)
    # Loads the documents
    loaded_video_document = loader.load()
    # Returns the transcribed contents
    return loaded_video_document[0].page_content


def create_prompt(context):
    """
    Generates a prompt from the video transcript.

    Args:
        context (str):      The transcribed contents of the video.

    Returns:
        prompt (str):        The prompt template with the video transcript.
    """
    questions = """
    1. Engaging Title: Propose a catchy and appealing title that encapsulates the essence of the content. \
    2. SEO Tags: Identify a list of SEO-friendly tags that are relevant to the content and could improve its searchability. \
    3. Thumbnail Design: Describe the elements of an eye-catching thumbnail that would compel viewers to click. \
    4. Content Enhancement: Offer specific suggestions on how the content could be improved for viewer engagement and retention. \
    5. Viral Potential Segment: Identify the best section that might have the potential to be engaging or entertaining for a short-form viral video based on factors like humor, uniqueness, relatability, or other notable elements. \
    Provide the entire text section identified and explain why. \
    """
    prompt_template = PromptTemplate.from_template("""You are a engaging humorous expert content editor. \
    Your first task is to provide a concise 4-6 sentence  summary of the given text as if you were preparing an introduction for a personal blog post. \
    Begin your summary with a phrase such as 'In this post' or 'In this interview,' setting the stage for what the reader can expect.
    Your second task is to provide your responses to the following inquiries in the form of bullet points:  \
    
    {context}

    Provide Summary Here: 
    
    Answer Inquiries Here: {questions}
    """
    )
    prompt = prompt_template.format(context=context, questions=questions)
    return prompt

def convert_to_text_file(transcript):
    """
    Converts the transcript to a text file and returns the file path.

    Args:
        transcript (str):      The transcribed contents of the video.

    Returns:
        file_path (str):       The file path of the text file.
    """
    file_path = './downloaded_transcripts/transcript.txt'
    with open(file_path, 'w') as file:
        file.write(transcript)
    return file_path

# Bedrock api call to stable diffusion
def generate_image(prompt):
    """
    Purpose:
        Uses Bedrock API to generate an Image
    Args/Requests:
         text: Prompt
         style: style for image
    Return:
        image: base64 string of image
    """
    body = {
        "text_prompts": [{"text": prompt}],
        "height": 1024,
        "width": 1024,
        "cfg_scale": 25,
        "seed": 420731490,
        "steps": 102,
    }

    body = json.dumps(body)

    modelId = "stability.stable-diffusion-xl-v1"
    accept = "application/json"
    contentType = "application/json"

    response = bedrock.invoke_model(
        body=body, modelId=modelId, accept=accept, contentType=contentType
    )
    response_body = json.loads(response.get("body").read())

    results = response_body.get("artifacts")[0].get("base64")
    return results

# Turn base64 string to image with PIL
def base64_to_pil(base64_string):
    """
    Purpose:
        Turn base64 string to image with PIL
    Args/Requests:
         base64_string: base64 string of image
    Return:
        image: PIL image
    """


    imgdata = base64.b64decode(base64_string)
    image = Image.open(io.BytesIO(imgdata))
    return image


@st.cache_resource
def load_chain():
    """
    Loads the LLM and the memory.
    
    Returns:
        chain (ConversationChain):      The LLM and the memory.
    """
    llm = BedrockChat(
        model_id="anthropic.claude-v2:1", 
        model_kwargs={
            "temperature": 1,
            "max_tokens_to_sample": 4096,
            "top_k": 500
        },
        verbose=True
    )
    memory = ConversationBufferMemory()
    chain = ConversationChain(llm=llm, memory=memory)
    return chain


# Contains the LLM and the memory
chain = load_chain()

# Creates session state variables
if "generated" not in st.session_state:
    st.session_state["generated"] = []
if "previous" not in st.session_state:
    st.session_state["previous"] = []
if "unique_id" not in st.session_state:
    st.session_state["unique_id"] = str(randint(1000, 10000000))

# Sidebar to clear the chat
st.sidebar.title("Sidebar")
clear_button = st.sidebar.button("Clear Conversation", key="clear")

# This is a hack to clear the chat
if clear_button:
    st.session_state.update({"generated": [], "previous": [], "unique_id": str(randint(1000, 10000000))})
    chain.memory.clear()

# Gets video transcript from url
url = st.sidebar.text_input("Insert YouTube URL", key=st.session_state["unique_id"])
submitted_button = st.sidebar.button("Submit", key=st.session_state["unique_id"] + "submit")      

# Container to display previous conversations
response_container = st.container()
# Container input text box
container = st.container()

# Creates a form with a text area for user input and a submit button.
with container:
    with st.form(key="youtub_app", clear_on_submit=True):
        user_input = st.text_area("You:", key="input", height=100)
        submit_button = st.form_submit_button(label="Send")

    # When submit button clicked and user input is received a prompt is sent to the LLM
    if submit_button and user_input:
        output = chain(user_input)["response"]
        st.session_state["previous"].append(user_input)
        st.session_state["generated"].append(output)
    
    # When user input is received and submit button gets the video transcript from the URL, converts the contents to a text file, and stores the path to the transcript file.
    elif user_input is not None and submitted_button is True:
        contents = get_video_transcript(url)
        transcript_file_path = convert_to_text_file(contents)
        # Download button in Streamlit
        with st.sidebar:
            with open(transcript_file_path, "r") as file:
                st.download_button(
                    label="Download Transcript as Text",
                    data=file,
                    file_name="transcript.txt",
                    mime="text/plain",
                )
        # Creates a prompt from the video transcript and sends it to the LLM
        prompt = create_prompt(contents)
        output = chain(prompt)["response"]    
        st.session_state["previous"].append("Video received. Currently reviewing...")
        st.session_state["generated"].append(output)

    history = chain.memory.load_memory_variables({})["history"]

# Displays the conversation history in the Streamlit app by iterating over previous and generated messages.
if st.session_state["previous"]:
    with response_container:
        for i, (previous_message, generated_message) in enumerate(zip(st.session_state["previous"], st.session_state["generated"])):
            message(previous_message, is_user=True, key=f"{i}_user")
            message(generated_message, key=str(i))
        # Regular expression to capture content between 'Thumbnail Design' and 'Content Enhancement'
        pattern = r"Thumbnail Design:(.*?)Content Enhancement:"
        try: 
            # Search for the pattern in the text
            match = re.search(pattern, output, re.DOTALL)
        except NameError as e:
            logging.error(f"Error: {e}", exc_info=True)
            match = None

        if match:
            result = match.group(1).strip()
            generated_thumbnail = base64_to_pil(generate_image(f"Create a colorful engaging YouTube Thumbnail without text based on this design: {result}"))
            st.image(generated_thumbnail)
        else:
            print("No match found.")