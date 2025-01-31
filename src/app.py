import os
import glob
import streamlit as st

# Local imports
from video_processing import process_videos_in_directory
from app_utils import (
    should_skip_analysis,
    save_analysis
)
from analysis_utils import (
    analyze_with_gemini_api,
    load_existing_analysis,
    get_all_existing_analyses
)


##############################################################################
# Constants and Defaults
##############################################################################
DEFAULT_PROMPT = """Analyze this audio for specific examples of [target topic] - these are instances where [explain what you're looking for]. 

Please start with a brief overview of what the audio is about.

For each relevant example found, include:
- When it was mentioned (timestamp)
- What specific aspect of [target topic] was discussed
- The context and details provided
- Direct quotes from the speaker if they described it specifically

Don't include:
- General discussion about [target topic] without specific examples
- Tangential mentions or references
- Theory or hypothetical scenarios

End with your assessment: How confident are you these were genuine examples of [target topic]? Were any examples unclear or ambiguous? How reliable were the speakers in their descriptions?

If no clear examples are found, simply state that."""

DEFAULT_MODEL = "gemini-1.5-flash-002"
DEFAULT_GCP_PROJECT = "my-gcp-project"
DEFAULT_GCP_LOCATION = "us-east1"


##############################################################################
# Helper Functions
##############################################################################
def analyze_audio(
    audio_path,
    prompt,
    credentials,
    model_name=DEFAULT_MODEL,

):
    """
    Analyzes audio using the selected API and returns text.
    """
    response_text = analyze_with_gemini_api(
        audio_path,
        prompt,
        api_key=credentials,
        model_name=model_name
    )
    return response_text


def get_gemini_api_key_from_secrets():
    """
    Safely retrieve the GEMINI_API_KEY from Streamlit secrets if it exists.
    If secrets.toml doesn't exist or doesn't contain GEMINI_API_KEY, return None.
    """
    if "GEMINI_API_KEY" in st.secrets and st.secrets["GEMINI_API_KEY"]:
        return st.secrets["GEMINI_API_KEY"]
    return None





##############################################################################
# UI Sections
##############################################################################
def render_prompt_input():
    with st.expander("📝 Prompt Configuration & Tips", expanded=True):
    # Initialize session state if not present
        if "analysis_prompt" not in st.session_state:
            st.session_state.analysis_prompt = DEFAULT_PROMPT

        # Use columns for better button placement
        col1, col2 = st.columns([4, 1])
        with col1:
            st.markdown("**Customize your analysis prompt:**")
        with col2:
            if st.button("🔄 Reset to Default", help="Click to restore original template"):
                st.session_state.analysis_prompt = DEFAULT_PROMPT
                st.success("Prompt reset to default!")  # Add feedback

        # Add visual separator
        st.markdown("---")

        # Enhanced text area with usage tips
        st.session_state.analysis_prompt = st.text_area(
            "**Edit your analysis prompt:**",
            value=st.session_state.analysis_prompt,
            height=300,
            help="""You can use the following placeholders in your prompt:
            - {text}: Will be replaced with the input text
            - {format}: Will be replaced with the output format""",
            key="prompt_editor"
        )

        # Add helper text below the text area
        st.caption("💡 Tip: Drag the bottom-right corner to resize the editing area")

        # Add section with prompt crafting tips
        with st.container():
            st.markdown("**📌 Prompt Crafting Tips:**")
            st.markdown("""
            - Clearly specify the desired output format
            - Include examples for better results
            - Define the tone and style requirements
            - Set clear boundaries for the analysis scope
            - Use markdown formatting for better readability
            """)

        # Optional: Add a preview section
        if st.checkbox("Show live preview", help="Preview how your prompt will be used"):
            st.markdown("**Prompt Preview:**")
            st.markdown(st.session_state.analysis_prompt[:500] + "...", unsafe_allow_html=True)
   


def render_api_configuration():
    with st.expander("🔧 API Configuration", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            api_choice = st.radio(
                "Select API Provider:",
                ["Gemini API"],
                index=0,
                help="Choose the API service for your AI model",
                key="api_selector"
            )
        
        with col2:
            model_name = st.text_input(
                "Model Name:",
                value=DEFAULT_MODEL,
                help="Specify the model version (e.g., 'gemini-1.5-pro')",
                placeholder="Enter model name",
                key="model_name_input"
            )

        st.divider()
        
        st.subheader("🔑 Credentials Setup")
        
        if api_choice == "Gemini API":
            credentials_container = st.container()
            with credentials_container:
                gemini_secrets_key = get_gemini_api_key_from_secrets()
                
                if gemini_secrets_key:
                    st.success("✅ Using secure API key from secrets.toml")
                    credentials = gemini_secrets_key
                else:
                    credentials = st.text_input(
                        "Enter Gemini API Key:",
                        type="password",
                        help="[Get your API key](https://ai.google.dev/)",
                        placeholder="Paste your API key here...",
                        key="gemini_key_input"
                    )
                    
                    if not credentials:
                        st.warning("⚠️ API key is required for Gemini access")
                    
                    st.caption("Your API key is never stored and only used for the current session")

            # Additional configuration for different providers can be added here
            project_id, location = None, None

        # Session state management
        st.session_state.update({
            "api_choice": api_choice,
            "credentials": credentials if credentials else None,
            "project_id": project_id,
            "location": location,
            "model_name": model_name
        })



def render_video_to_audio():
    if "processed_audio_files" not in st.session_state:
        st.session_state.processed_audio_files = []

    with st.expander("Video to Audio Conversion", expanded=True):
    # Input section
        video_folder = st.text_input(
            "Video Folder Path:",
            "./videos",
            help="Path to directory containing video files for conversion"
        )
        
        # Conversion trigger
        if st.button("Convert Videos to Audio", key="video_convert_btn"):
            if not os.path.isdir(video_folder):
                st.error("Invalid folder path. Please provide a valid directory.")
                st.stop()

            with st.spinner("Converting videos to audio..."):
                try:
                    audio_files = process_videos_in_directory(video_folder)
                    st.session_state.processed_audio_files = audio_files
                    
                    if audio_files:
                        st.success(f"Successfully converted {len(audio_files)} videos")
                        st.toast(f"Processed {len(audio_files)} files!", icon="✅")
                    else:
                        st.warning("No audio files were created. Check input files and logs.")
                        
                except Exception as e:
                    st.error(f"Conversion failed: {str(e)}")
                   

def render_analysis_viewer():
    """
    Renders a viewer for existing analysis files.
    """
    with st.expander("View Existing Analyses", expanded=True):
        # Get all existing analyses
        existing_analyses = get_all_existing_analyses()
        
        if not existing_analyses:
            st.info("No existing analysis files found in output/analysis directory.")
            return
            
        st.write(f"Found {len(existing_analyses)} existing analysis files.")
        
        # Create a selectbox for choosing which analysis to view
        analysis_options = ["Select an analysis..."] + [audio_file for audio_file, _ in existing_analyses]
        selected_analysis = st.selectbox(
            "Choose an analysis to view:",
            analysis_options
        )
        
        if selected_analysis and selected_analysis != "Select an analysis...":
            # Find the corresponding analysis file
            selected_file = next(
                (analysis_path for audio_file, analysis_path in existing_analyses 
                 if audio_file == selected_analysis),
                None
            )
            
            if selected_file:
                with open(selected_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                # Create tabs for different view options
                raw_tab, rendered_tab = st.tabs(["Raw Text", "Rendered Markdown"])
                
                with raw_tab:
                    st.text_area(
                        label=f"Raw analysis for {selected_analysis}",
                        value=content,
                        height=300
                    )
                
                with rendered_tab:
                    st.markdown(content)

def render_audio_analysis():
    with st.expander("Analyze Audio Files", expanded=True):
        skip_reanalysis = st.checkbox("Skip re-analysis if file already exists?", value=True)
        
        # Check for existing files on load if not already in session state
        if "processed_audio_files" not in st.session_state:
            existing_audio_files = glob.glob("output/audio/*.mp3")
            if existing_audio_files:
                st.session_state.processed_audio_files = existing_audio_files
                st.success(f"Found {len(existing_audio_files)} existing audio files in output/audio directory.")
            else:
                st.session_state.processed_audio_files = []
                st.info("No audio files found in output/audio directory.")
        
        if st.button("Run Analysis"):
            audio_files = st.session_state.processed_audio_files
            if not audio_files:
                st.warning("No audio files found to analyze. Please convert videos or ensure .mp3 files exist.")
                return

            # Check credentials
            if not st.session_state.credentials:
                
                st.error("Please provide your Gemini API key.")
                return

            st.markdown("### Starting Analysis")
            st.write(f"Processing {len(audio_files)} audio files...")
            
            for audio_file in audio_files:
                if skip_reanalysis and should_skip_analysis(audio_file, skip_reanalysis=True):
                    st.info(f"Skipping re-analysis for `{os.path.basename(audio_file)}` (analysis file exists).")
                    
                    # Display existing analysis
                    exists, content = load_existing_analysis(audio_file)
                    if exists:
                        st.markdown(f"#### Existing Analysis: `{os.path.basename(audio_file)}`")
                        raw_tab, rendered_tab = st.tabs(["Raw Text", "Rendered Markdown"])
                        with raw_tab:
                            st.text_area(
                                label=f"Raw analysis",
                                value=content,
                                height=200
                            )
                        with rendered_tab:
                            st.markdown(content)
                    continue

                st.markdown(f"#### Analyzing: `{os.path.basename(audio_file)}`")
                try:
                    response_text = analyze_audio(
                        audio_file,
                        st.session_state.analysis_prompt,
                        st.session_state.credentials,
                        model_name=st.session_state.model_name,
                    )
                    save_analysis(audio_file, response_text)
                    
                    # Create tabs for different view options
                    raw_tab, rendered_tab = st.tabs(["Raw Text", "Rendered Markdown"])
                    
                    with raw_tab:
                        st.text_area(
                            label=f"Raw analysis",
                            value=response_text,
                            height=200
                        )
                    
                    with rendered_tab:
                        st.markdown(response_text)
                    
                    st.success(f"Saved analysis to output/analysis/{os.path.basename(audio_file).replace('.mp3', '_analysis.txt')}")
                except Exception as e:
                    st.error(f"Failed to analyze {audio_file}. Error: {str(e)}")

            st.success("Analysis complete!")


##############################################################################
# Main Streamlit App
##############################################################################
def main():
    st.title("SearchInVideos")
    # Render UI sections
    render_prompt_input()
    render_api_configuration()
    render_video_to_audio()
    render_audio_analysis()
    render_analysis_viewer()



if __name__ == "__main__":
    # UV run snippet
    if "__streamlitmagic__" not in locals():
        import streamlit.web.bootstrap
        streamlit.web.bootstrap.run(__file__, False, [], {})
    main()