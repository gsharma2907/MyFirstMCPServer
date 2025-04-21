import streamlit as st
import boto3
import os
import json
import requests

# Initialize Bedrock client
bedrock_client = boto3.client(
    'bedrock-runtime',
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY"),
    aws_secret_access_key=os.getenv("AWS_SECRET_KEY"),
    region_name="us-west-2"
)

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_results" not in st.session_state:
    st.session_state.last_results = []
if "selected_results" not in st.session_state:
    st.session_state.selected_results = []
if "debug_results" not in st.session_state:
    st.session_state.debug_results = []
if "query_counter" not in st.session_state:
    st.session_state.query_counter = 0

# Streamlit app
st.title("Document Search Chatbot")
st.subheader("Find documents in Google Drive by keyword (e.g., 'patient data')")

# Function to query FastAPI server for metadata
def query_source(query):
    try:
        response = requests.get("http://localhost:8000/google_drive", params={"query": query})
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": str(e), "source": "google_drive"}

# Function to fetch file content
def fetch_file_content(file_id):
    try:
        response = requests.get(f"http://localhost:8000/google_drive/content/{file_id}")
        response.raise_for_status()
        return response.json().get("content", "")
    except Exception as e:
        return f"Error fetching content: {str(e)}"

# Function to summarize documents with Claude
def summarize_documents(documents):
    summaries = []
    for doc in documents:
        file_id = doc.get('location', '').split('file ID: ')[-1].strip(')')  # Extract file ID
        content = fetch_file_content(file_id)
        if content.startswith("Error"):
            summaries.append(f"Cannot summarize {doc.get('name', 'Unknown')}: {content}")
            continue
        prompt = f"""
        You are an AI assistant. Summarize the following Google Drive document content:
        - Document: {doc.get('name', 'Unknown')}
        - Content: {content[:1000]}  # Limit to avoid token issues
        Tasks:
        - Provide a concise summary (100 words or less).
        - Highlight key details (e.g., file type, purpose) if available.
        """
        try:
            response = bedrock_client.invoke_model(
                modelId="anthropic.claude-3-sonnet-20240229-v1:0",
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 150,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ]
                }),
                contentType="application/json",
                accept="application/json"
            )
            response_body = json.loads(response['body'].read())
            summary = response_body.get('content', [{}])[0].get('text', '')
            summaries.append(f"Summary for {doc.get('name', 'Unknown')}: {summary}")
        except Exception as e:
            summaries.append(f"Cannot summarize {doc.get('name', 'Unknown')}: Bedrock API error: {str(e)}")
    return "\n\n".join(summaries) if summaries else "No summaries generated."

# Function to split query into keywords
def split_keywords(query):
    common_words = {'search', 'for', 'find', 'look'}
    keywords = [word.lower() for word in query.strip().split() if word.lower() not in common_words]
    st.write(f"**Debug**: Searching for keywords: {keywords}")
    return keywords if keywords else [query.strip().lower()]

# Chat interface
with st.container():
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Debug toggle
    if st.checkbox("Show debug output (raw API responses)"):
        if st.session_state.debug_results:
            st.write("**Raw API Responses**:")
            st.json(st.session_state.debug_results)
        else:
            st.write("No debug results yet.")

    if prompt := st.chat_input("What document are you looking for? (e.g., 'patient data')"):
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Split query into keywords
        keywords = split_keywords(prompt)
        if not keywords:
            response = "Please specify a keyword (e.g., 'patient data' or 'invoice')."
            st.session_state.messages.append({"role": "assistant", "content": response})
            with st.chat_message("assistant"):
                st.markdown(response)
            st.stop()

        # Search Google Drive for each keyword
        with st.spinner(f"Searching for '{prompt}' in Google Drive..."):
            all_results = []
            debug_results = []
            for keyword in keywords:
                results = query_source(keyword)
                debug_results.append({"google_drive_" + keyword: results})
                if isinstance(results, dict) and results.get("error"):
                    response = f"Error searching Google Drive: {results['error']}\n"
                    st.session_state.messages.append({"role": "assistant", "content": response})
                    with st.chat_message("assistant"):
                        st.markdown(response)
                elif results:
                    for item in results:
                        item['source'] = 'google_drive'
                        all_results.append(item)

            # Store debug results
            st.session_state.debug_results = debug_results

            # Deduplicate by name and location, limit to top 5
            seen = set()
            unique_results = []
            for item in all_results:
                key = (item.get('name'), item.get('location'))
                if key not in seen and len(unique_results) < 5:
                    seen.add(key)
                    unique_results.append(item)

            # Update session state
            st.session_state.last_results = unique_results
            st.session_state.selected_results = [False] * len(unique_results)
            st.session_state.query_counter += 1

            # Add response to chat history
            if unique_results:
                response = f"Found {len(unique_results)} documents (select to summarize)."
            else:
                response = f"No results found for '{prompt}' in Google Drive."
            st.session_state.messages.append({"role": "assistant", "content": response})
            with st.chat_message("assistant"):
                st.markdown(response)

# Display results with checkboxes
if st.session_state.last_results:
    st.markdown("**Found documents** (select to summarize):")
    for idx, item in enumerate(st.session_state.last_results):
        name = item.get('name', 'Unknown')
        location = item.get('location', 'Location not specified')
        source = item.get('source', 'Unknown').replace('_', ' ').title()
        st.session_state.selected_results[idx] = st.checkbox(
            f"File: {name} (Location: {location}, Source: {source})",
            value=st.session_state.selected_results[idx],
            key=f"result_{st.session_state.query_counter}_{idx}"
        )

# Summarization button
if st.session_state.last_results:
    if st.button("Summarize Selected Results"):
        selected_docs = [
            doc for idx, doc in enumerate(st.session_state.last_results)
            if st.session_state.selected_results[idx]
        ]
        if not selected_docs:
            st.warning("Please select at least one document to summarize.")
        else:
            with st.spinner("Summarizing..."):
                summary = summarize_documents(selected_docs)
                st.session_state.messages.append({"role": "assistant", "content": f"**Summary**:\n{summary}"})
                with st.chat_message("assistant"):
                    st.markdown(f"**Summary**:\n{summary}")
