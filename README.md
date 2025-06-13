# Train Route Finder 🚂✨

**Train Route Finder is an AI-powered railway travel assistant designed to revolutionize how users plan and book train journeys, especially within complex systems like Indian Railways. It intelligently finds trains with confirmed seats, predicts delays, offers unique solutions for urgent travel, and provides a seamless, AI-driven user experience.**

## The Problem แก้ปัญหา

Navigating railway travel can be a frustrating experience due to:
*   Frequent unavailability of direct confirmed seats, leading to uncertain waitlists.
*   Unpredictable train delays disrupting travel plans and connections.
*   Complex and often non-intuitive user interfaces on existing booking platforms.
*   Lack of reliable options for finding seats for urgent, same-day travel.
*   Difficulty in manually planning efficient multi-leg journeys.

## Our Solution 💡

Train Route Finder tackles these challenges head-on by:
*   Finding routes with **guaranteed confirmed seats**, often by intelligently breaking journeys into multiple segments where each leg has confirmed availability, eliminating waitlist anxiety.
*   Providing an **Urgent Mode** for real-time seat availability on trains departing within the next 4-6 hours, including innovative same-train seat segmentation.
*   Leveraging **AI for predictive delay analysis**, offering insights into potential disruptions and connection risks.
*   Integrating an **AI-powered Chatbot (via Gemini API)** for natural conversation-based form filling.
*   Utilizing **Automatic Speech Recognition (ASR) and Named Entity Recognition (NER)** for hands-free, voice-activated search queries.
*   Offering **Personalized Travel Modes** ("Comfort" & "Economy") to cater to diverse passenger preferences.

## Key Features 🌟

*   **WL Rescue Algorithm:** Finds confirmed alternative routes (direct or multi-leg) when your initial choice is waitlisted. No more gambling on waitlist clearance!
*   **Same-Day Urgent Mode:**
    *   Shows real-time seat availability for trains departing in the next **4-6 hours**.
    *   Includes "same-train seat finding" – intelligently finds available segments (e.g., different classes/quotas) on the *same physical train* if a direct through-seat isn't available for the entire journey from A to C, but seats are free from A-B and B-C.
    *   **Urgent Mode Options:**
        *   **Comfort Mode:** Prioritizes minimizing train changes and overall journey ease, while still being cost-effective.
        *   **Economy Mode:** Focuses on the absolute cheapest seat options, even if it means more segments or changes.
*   **AI-Powered Chatbot (Gemini API):**
    *   Engage in natural conversation to find trains. The chatbot understands your needs and intelligently fills in the search form for you.
    *   Example: "I need to get from Delhi to Mumbai next Tuesday."
    *   _`[Link to Screenshot of Chatbot Interface]`_
*   **ASR & NER Integration (Google Cloud):**
    *   Use voice commands to initiate searches.
    *   "Find a train from Delhi to Patna for tomorrow"
    *   "Book a train from Ahmedabad to Jaipur on 30 June"
    *   The system accurately transcribes your speech and uses NER to extract origin, destination, and dates to populate the form automatically.
*   **AI Delay Prediction (Vertex AI):**
    *   Predicts potential train delays based on historical data (analyzing 5+ years, including factors like monsoons, strikes, maintenance).
    *   Calculates connection risks for multi-leg journeys.
*   **Smart Connection Prioritization:** When suggesting multi-leg journeys, the system prioritizes intermediate/changing stations that are major hubs, enhancing passenger safety, comfort, and access to amenities compared to remote or smaller stations.
*   **Mobile-Friendly Responsive Design.**

## Why We Stand Out (Differentiation) 🆚

*   **vs. IRCTC/RailYatri:** They show WL status but often **no viable confirmed alternatives**. We proactively find them. They display current running delays but **don't predict future delays** or connection risks with AI.
*   **vs. Google Maps:** Maps suggest routes but **ignore real-time seat availability**. We prioritize confirmed seats.
*   **Unique Capabilities:** Our **Same-Day Urgent Mode** with same-train segmentation and **AI Chatbot** for form-filling are not commonly found on other platforms.

## Technologies Used 🛠️

*   **Frontend:** HTML, CSS, JavaScript
*   **Backend:** Python, Flask
*   **Google Cloud Platform (GCP):**
    *   **Vertex AI:** For training and deploying train delay prediction models.
    *   **Gemini API:** Powers the AI conversational chatbot.
    *   **Cloud Speech-to-Text API:** For Automatic Speech Recognition.
    *   **Cloud Natural Language API:** For Named Entity Recognition (extracting journey details from text/speech).
    *   *(Specify if other GCP services like App Engine/Cloud Run are used for deployment)*
*   **Machine Learning:**
    *   **PyTorch:** Used for deep learning models that identify optimal intermediate stations with available seats, crucial for multi-leg journey planning.
*   **Automation/Scraping:**
    *   **Selenium:** For real-time data scraping of third-party train schedules and seat availability (use responsibly and respect terms of service).
*   **Caching:**
    *   In-memory caching for frequently accessed routes and station data to improve response times.
*   **Deployment:** *(Mention where it's hosted, e.g., Google Cloud App Engine, or if it's primarily a local prototype currently).*

## Getting Started 🚀

### Prerequisites

*   Python 3.7+
*   pip (Python package installer)
*   Google Cloud SDK installed and configured with a project.
*   Enabled APIs in your Google Cloud Project:
    *   Vertex AI API
    *   Gemini API (or appropriate Generative Language API)
    *   Cloud Speech-to-Text API
    *   Cloud Natural Language API
*   `GOOGLE_APPLICATION_CREDENTIALS` environment variable set up to point to your GCP service account key JSON file.
*   (If using Selenium for local scraping) Appropriate WebDriver (e.g., chromedriver) installed and in your PATH.
*   PyTorch installed.

### Installation

1.  **Clone the repository:**
    ```bash
    git clone [Your Repository URL]
    cd train-route-finder 
    ```
2.  **Create and activate a virtual environment (recommended):**
    ```bash
    python -m venv venv
    # On Windows
    # venv\Scripts\activate
    # On macOS/Linux
    # source venv/bin/activate
    ```
3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
4.  **Set up API Keys/Environment Variables:**
    *   Ensure your `GOOGLE_APPLICATION_CREDENTIALS` environment variable is correctly set.
    *   *(If you have any other API keys or settings in a `.env` file or similar, document that here, e.g., create a `.env` file from `.env.example` and fill in your keys).*
5.  **(If applicable) Database Setup:**
    *   *(Add any database migration/setup steps here if you have a local DB).*

### Running the Application

```bash
python app.py
# or if using Flask CLI
# flask run
