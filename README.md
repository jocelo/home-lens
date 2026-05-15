# Home Lens

A Python web application for a home dashboard with information realted with the family built with Flask.

## Project Structure

```
home-lens/
├── app.py              # Main Flask application
├── requirements.txt    # Python dependencies
├── templates/
│   └── index.html     # Home page template
├── README.md          # This file
└── .gitignore         # Git ignore configuration
```

## Getting Started

### Prerequisites

- Python 3.7 or higher
- pip (Python package manager)

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd home-lens
```

2. Create a virtual environment:
```bash
python -m venv venv
```

3. Activate the virtual environment:

**On macOS/Linux:**
```bash
source venv/bin/activate
```

**On Windows:**
```bash
venv\Scripts\activate
```

4. Install dependencies:
```bash
pip install -r requirements.txt
```

### Running the Application

Start the Flask development server:
```bash
python app.py
```

The application will be available at `http://localhost:5000`

## Features

- Simple and clean home page
- Responsive design
- Easy to extend with additional pages and features

## Development

To add more routes, edit `app.py` and create corresponding templates in the `templates/` directory.

Example:
```python
@app.route('/about')
def about():
    return render_template('about.html')
```

## License

This project is licensed under the MIT License.
