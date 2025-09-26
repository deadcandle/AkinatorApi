# Akinator FastAPI

This project is a FastAPI application that allows users to play the Akinator game through a web interface. It utilizes Selenium to automate the game without displaying the Windows interface, enabling multiple games to run simultaneously.

## Project Structure

```
akinator-fastapi
├── app.py                # FastAPI application with game endpoints
├── requirements.txt      # Project dependencies
├── .gitignore            # Files and directories to ignore in Git
└── README.md             # Project documentation
```

## Setup Instructions

1. **Clone the repository:**
   ```
   git clone <repository-url>
   cd akinator-fastapi
   ```

2. **Create a virtual environment:**
   ```
   python -m venv venv
   ```

3. **Activate the virtual environment:**
   - On Windows:
     ```
     venv\Scripts\activate
     ```
   - On macOS/Linux:
     ```
     source venv/bin/activate
     ```

4. **Install the required dependencies:**
   ```
   pip install -r requirements.txt
   ```

## Usage

1. **Run the FastAPI application:**
   ```
   uvicorn app:app --reload
   ```

2. **Access the API:**
   - Start a new game by sending a POST request to `/start`.
   - Process the next turn by sending a POST request to `/turn` with the necessary parameters.

## Dependencies

This project requires the following Python packages:

- FastAPI
- Selenium
- [Web driver package for your browser of choice]

## Contributing

Feel free to submit issues or pull requests for improvements or bug fixes.

## License

This project is licensed under the MIT License.